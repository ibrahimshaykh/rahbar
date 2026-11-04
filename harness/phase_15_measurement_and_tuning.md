# Phase 15 — Measurement and Tuning

**Goal.** Flip the cluster to the real pipeline, then measure: three chunking
configurations against recall@5, three cache thresholds against false hits, and
the relevance floor. Commit `baseline.json` and `results.json`.

**Requirements closed.** IX-07, IX-08, CA-03, EV-04, EV-05 (the numbers),
EV-08, GN-07 (the justification), SB-05.

**Core specs needed.** `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §5 and §6.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
ls corpus/raw/ | head              # P12 fetched the corpus
cd eval && ../.venv/bin/pytest -q  # P13 complete
git log --oneline --diff-filter=A -- eval/golden.yaml   # the golden set exists and predates this phase
```

**This phase is almost entirely `[HUMAN]`** — every number must come from a real
run against a real cluster with a real model. The agent writes the scripts,
registers them, and writes up the results when they arrive.

---

## The rule this phase exists to satisfy

*"Tune chunking with measurements, not guesses. Run at least three (size,
overlap) configurations, measure recall@5 on your golden set for each, put the
three results in a table in docs/PIPELINE.md, and justify the one you shipped.
**A sensible number with no measurement behind it scores zero on that rubric
line.**"*

And for the cache: *"Choose the threshold with data. The lowest threshold with
zero false hits on your test questions. Report the two or three thresholds you
tried and the false hit that ruled one out."*

**Anti-hallucination law L1 applies with full force here.** Every cell of every
table in this phase must come from a command whose output is pasted in the Run
Log. A plausible-looking recall figure is both a wrong answer and academic
dishonesty.

---

## Task list

### P15-T01 `[AGENT]` · Flip the configuration to the real pipeline

Thursday's switch, from `STARTER.md`: *"Implement the five pipeline stages,
`ChromaRetriever.retrieve` and a provider, switch the ConfigMap to
`RETRIEVER=chroma` and a real `LLM_PROVIDER`."*

Edit `k8s/overlays/dev/patch-config-dev.yaml`:

```yaml
data:
  LOG_LEVEL: "DEBUG"
  RETRIEVER: "chroma"               # was stub
  LLM_PROVIDER: "ollama-host"       # was stub
  EMBED_MODEL: "nomic-embed-text"   # was dummy-768
```

And delete `k8s/overlays/dev/patch-indexer-dummy.yaml` plus its entry in the
dev overlay's `patches:` list (Decision D-010 said to remove it here).

```bash
kustomize build k8s/overlays/dev | grep -E 'RETRIEVER|LLM_PROVIDER|EMBED_MODEL'
kustomize build k8s/overlays/dev | grep -c -- '--dummy'     # 0
kustomize build k8s/overlays/dev | kubeconform -strict -ignore-missing-schemas
```

> **Do not apply this and the first real index in the same step.** Apply the
> ConfigMap change, observe the api go to `0/1 READY` because the collection
> still says `dummy-768`, **capture that** — it is the K8-20 demonstration and
> P16-T10 can reuse it — and only then run the real indexer Job.

### P15-T02 `[HUMAN]` · Index the real corpus

Write `scripts/evidence/P15-T02_first_real_index.sh`:

```bash
#!/usr/bin/env bash
# P15-T02 · the first real index over the real corpus · IX-01..IX-05
set -euo pipefail
NS=rahbar; OUT=docs/evidence/first_real_index.txt
JOB="real-index-$(date +%s)"
mkdir -p "$(dirname "$OUT")"
{
  echo "# P15-T02 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "# Ollama must be reachable from the cluster:"
  echo "\$ curl -s http://localhost:11434/api/tags | head -c 300"
  curl -s http://localhost:11434/api/tags 2>&1 | head -c 300; echo
  echo; echo "\$ make images && kubectl apply -k k8s/overlays/dev"
  make images 2>&1 | tail -8
  kubectl apply -k k8s/overlays/dev 2>&1
  echo; echo "# BEFORE the real index: the api must be 0/1 READY (pin mismatch)"
  kubectl get pods -n "$NS" -l app=api 2>&1
  kubectl logs -n "$NS" -l app=api --tail=10 2>&1 | grep -i 'pin\|not ready' || true
  echo; echo "\$ kubectl create job --from=cronjob/reindex $JOB -n $NS"
  kubectl create job --from=cronjob/reindex "$JOB" -n "$NS" 2>&1
  START=$(date +%s)
  kubectl wait --for=condition=complete "job/$JOB" -n "$NS" --timeout=2400s 2>&1 \
    || { kubectl logs "job/$JOB" -n "$NS" --tail=80 2>&1; exit 1; }
  echo "duration_seconds=$(( $(date +%s) - START ))"
  echo; echo "\$ kubectl logs job/$JOB -n $NS"
  kubectl logs "job/$JOB" -n "$NS" 2>&1
  echo "# ^ the JSON lines carry per-document chunk counts and the total"
  echo; echo "\$ kubectl rollout status deployment/api -n $NS"
  kubectl rollout status deployment/api -n "$NS" --timeout=300s 2>&1
  echo; echo "\$ /readyz now"
  kubectl exec -n "$NS" deploy/api -- python -c \
    "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/readyz').read().decode())" 2>&1
} | tee "$OUT"
```

One-liner for the human:

```bash
OLLAMA_HOST=0.0.0.0 ollama serve &      # if not already running
ollama pull nomic-embed-text && ollama pull llama3.2:3b
bash scripts/evidence/P15-T02_first_real_index.sh
```

**Expect this to take a while.** Ten documents, ~190 pages, chunked at 400
words with 50 overlap is roughly 1500–2500 chunks, each needing an embedding.
Batched at 32, that is 50–80 requests to Ollama. Budget 10–30 minutes on a
laptop CPU. The Job's `activeDeadlineSeconds` is unset and `backoffLimit: 4`
gives four attempts, so a slow run completes rather than failing.

**If the indexer is OOMKilled (exit 137)**, raise the Job's memory limit. That
is P16-T06's measurement arriving early — capture `kubectl top pods` while it
runs and use the real peak.

### P15-T03 `[AGENT]` · Reconcile the golden set's section labels

Now that a real index exists, bind `relevant` to the labels the indexer actually
produces, per `phase_13` P13-T01's final step. Write
`scripts/reconcile_golden.py`:

```python
#!/usr/bin/env python3
"""Print, for each golden question, the (source, section) pairs the retriever
returns - so `relevant` can be bound to the indexer's real vocabulary.

READ THE OUTPUT AND EDIT BY HAND. This script never writes golden.yaml:
relevance is a judgement made from the documents, not from what came back.
"""
from __future__ import annotations

import argparse
import json

import httpx
import yaml


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", required=True)
    ap.add_argument("--host")
    ap.add_argument("--golden", default="eval/golden.yaml")
    args = ap.parse_args()

    questions = yaml.safe_load(open(args.golden, encoding="utf-8"))["questions"]
    headers = {"Host": args.host} if args.host else {}
    with httpx.Client(timeout=180.0, headers=headers) as client:
        for q in questions:
            r = client.post(f"{args.api.rstrip('/')}/api/ask",
                            json={"question": q["question"]})
            body = r.json()
            print(f"\n=== {q['id']} [{q['type']}] {q['question'][:70]}")
            print(f"    golden says : {json.dumps(q.get('relevant') or [])}")
            print(f"    abstained   : {not body['answered_from_context']}")
            for p in body["retrieved"]:
                print(f"    retrieved   : {p['source']:<42} | {p['section'][:45]} | {p['score']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Register `[HUMAN]` **P15-T04**:
`python scripts/reconcile_golden.py --api "http://$(minikube ip)" --host rahbar.local | tee docs/evidence/golden_reconcile.txt`

Then edit `eval/golden.yaml` by hand. **Rules for the edit**, which go in the
commit message:

- A `relevant` entry may be **relabelled** (`"5.4"` → `"5.4 Academic Warning"`)
  to match the indexer's vocabulary.
- A `relevant` entry may **not** be changed to point at a different passage
  because the right one did not come back. That is the finding.
- A `must_abstain` question's `relevant` stays `[]`, always.
- If a question's answer turns out not to be in the corpus at all, the question
  is **wrong**, not the system — replace it with one that is answerable and say
  so in the Decision Log.

### P15-T05 `[HUMAN]` · The three chunking configurations

Write `scripts/evidence/P15-T05_chunking.sh` per
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §5's protocol, parameterised:

```bash
#!/usr/bin/env bash
# P15-T05 · measure recall@5 for three (size, overlap) configurations · IX-07
# usage: P15-T05_chunking.sh <TAG> <SIZE> <OVERLAP>
set -euo pipefail
TAG="$1"; SIZE="$2"; OVERLAP="$3"
NS=rahbar; OUT=docs/evidence/chunking_runs.txt
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")" eval/experiments
{
  echo; echo "########## config $TAG  size=$SIZE overlap=$OVERLAP  $(date -u +%H:%M:%SZ)"
  kubectl patch configmap rahbar-config -n "$NS" --type merge \
    -p "{\"data\":{\"CHUNK_SIZE\":\"$SIZE\",\"CHUNK_OVERLAP\":\"$OVERLAP\"}}" 2>&1
  JOB="chunkexp-$TAG-$(date +%s)"
  kubectl create job --from=cronjob/reindex "$JOB" -n "$NS" 2>&1
  kubectl wait --for=condition=complete "job/$JOB" -n "$NS" --timeout=2400s 2>&1 \
    || { kubectl logs "job/$JOB" -n "$NS" --tail=40 2>&1; exit 1; }
  echo "--- indexer log (chunk counts)"
  kubectl logs "job/$JOB" -n "$NS" 2>&1 | tail -4
  kubectl rollout status deployment/api -n "$NS" --timeout=300s 2>&1
  echo "--- local amplification for this config"
  python3 scripts/amplification.py --corpus corpus/raw --size "$SIZE" --overlap "$OVERLAP" 2>&1 | tail -5
  echo "--- eval"
  python eval/run_eval.py --api "http://$IP" --host "$HOST" \
    --out "eval/experiments/results-$TAG.json" 2>&1 | tail -20
  echo "exit=$?"
  python3 - "$TAG" "$SIZE" "$OVERLAP" <<'PY' 2>&1
import json, sys
tag, size, overlap = sys.argv[1], sys.argv[2], sys.argv[3]
r = json.load(open(f"eval/experiments/results-{tag}.json"))
bt = r["by_type"]
print(f"ROW {tag} | {size} | {overlap} | r@3={r['recall_at_3']:.3f} | "
      f"r@5={r['recall_at_5']:.3f} | exact={bt['exact']['recall_at_5']} | "
      f"ordinary={bt['ordinary']['recall_at_5']} | version={bt['version']['recall_at_5']} | "
      f"cit={r['citation_validity']:.3f} | abst={r['abstention_correctness']:.3f}")
PY
} | tee -a "$OUT"
```

Human runs it three times:

```bash
bash scripts/evidence/P15-T05_chunking.sh A 400 50
bash scripts/evidence/P15-T05_chunking.sh B 250 40
bash scripts/evidence/P15-T05_chunking.sh C 700 80
```

**Each run re-indexes**, so budget 30–90 minutes for all three. The hypotheses
to test, from §5 of the spec:

| Config | Hypothesis | What to look for |
|---|---|---|
| A 400/50 | a balanced middle | the reference |
| B 250/40 | sharper vectors, better on exact terms, **worse on long definitions** that now span chunks | `exact` up, `ordinary` down, q05 (the Generative AI policy) likely lost |
| C 700/80 | whole definitions survive, but the vector averages several topics and **dilutes exact terms** | `ordinary` up, `exact` down |

**If the results do not match the hypotheses, report what happened.** An
unexpected result that you notice and explain is worth more than a tidy one you
assumed. *"Your exact-term recall will be visibly worse than your definitional
recall; noticing that yourself, and explaining it, is a finding."*

Finish by restoring the winner and leaving the ConfigMap holding it.

### P15-T06 `[AGENT]` · Write the chunking table and the amplification figure

Fill `docs/PIPELINE.md` → **Chunking** with the measured table. This is the
table the checker counts pipe characters in (≥12 required).

```markdown
| Config | Size (words) | Overlap (words) | Chunks stored | Amplification | recall@3 | recall@5 | r@5 exact | r@5 ordinary | r@5 version |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **A (shipped)** | 400 | 50 | … | … | … | … | … | … | … |
| B | 250 | 40 | … | … | … | … | … | … | … |
| C | 700 | 80 | … | … | … | … | … | … | … |
```

Then a justification paragraph **written from the numbers**, not from the
hypothesis. The shape to aim for:

> We shipped **A (400/50)**. It scored recall@5 of X overall against B's Y and
> C's Z. B's advantage on exact-term questions (A vs B on `r@5 exact`) did not
> compensate for losing q05 entirely: at 250 words the Generative AI policy's
> definition spans three chunks and no single passage answers the question. C
> recovered the definitional questions but lost N points of exact-term recall,
> which is the embedding-dilution effect the RAG lecture describes — a 700-word
> chunk's vector is the average of several topics, so a clause number
> contributes proportionally less to it.

**Storage amplification** (IX-08): the measured figure from
`scripts/amplification.py`, beside the theoretical `1 + overlap/size = 1.125`,
with the divergence explained — short sections produce chunks with no
predecessor to overlap with, pulling the real figure below the theoretical one.

### P15-T07 `[HUMAN]` · The three cache thresholds

Write `scripts/evidence/P15-T07_cache_threshold.sh` implementing the nine-pair
probe set from `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §6:

```bash
#!/usr/bin/env bash
# P15-T07 · the lowest cache threshold with zero false hits · CA-03
# usage: P15-T07_cache_threshold.sh <THRESHOLD>
set -euo pipefail
T="$1"; NS=rahbar; OUT=docs/evidence/cache_threshold_runs.txt
IP="${INGRESS_IP:-$(minikube ip)}"; HOST="${HOST:-rahbar.local}"
mkdir -p "$(dirname "$OUT")"

ask() {   # prints "HIT" or "MISS" plus the answer's first 60 chars
  local body; body=$(curl -s -D /tmp/h.txt -X POST "http://$IP/api/ask" -H "Host: $HOST" \
    -H 'Content-Type: application/json' -d "$(python3 -c "import json,sys;print(json.dumps({'question':sys.argv[1]}))" "$1")")
  if grep -qi 'x-cache: *hit' /tmp/h.txt; then echo -n "HIT  "; else echo -n "MISS "; fi
  python3 -c "import json,sys;print(json.load(sys.stdin)['answer'][:60])" <<<"$body"
}

{
  echo; echo "########## threshold $T  $(date -u +%H:%M:%SZ)"
  kubectl patch configmap rahbar-config -n "$NS" --type merge \
    -p "{\"data\":{\"CACHE_THRESHOLD\":\"$T\"}}" 2>&1
  kubectl rollout restart deployment/api -n "$NS" 2>&1
  kubectl rollout status  deployment/api -n "$NS" --timeout=300s 2>&1
  # a fresh generation so earlier runs cannot pollute this one
  kubectl exec -n "$NS" deploy/redis -- redis-cli INCR rahbar:cache:gen 2>&1

  run_pair() {  # id, A, B, expected (HIT|MISS)
    echo "--- $1  expected=$4"
    echo -n "    A: "; ask "$2"
    echo -n "    B: "; ask "$3"
  }
  run_pair P1 "What CGPA avoids academic warning?" \
              "What is the minimum CGPA to stay off academic warning?" HIT
  run_pair P2 "What attendance is needed for the final exam?" \
              "How much attendance do I need to sit the final?" HIT
  run_pair P3 "What is the BS fee per credit hour?" \
              "How much does one credit hour cost for BS?" HIT
  run_pair P4 "What is the current attendance requirement?" \
              "What was the previous attendance requirement?" MISS
  run_pair P5 "What CGPA avoids academic warning?" \
              "What CGPA avoids probation?" MISS
  run_pair P6 "What does clause 1.21 require?" \
              "What does clause 1.12 require?" MISS
  run_pair P7 "What is the BS fee per credit hour?" \
              "What is the MS fee per credit hour?" MISS
  run_pair P8 "How do I apply for a hostel room?" \
              "How do I apply for a transcript?" MISS
  run_pair P9 "What is the refund policy for withdrawal?" \
              "What is the refund policy for deferment?" MISS
  echo "# A 'HIT' on any pair marked MISS is a FALSE HIT and rules this threshold out."
} | tee -a "$OUT"
```

Human runs it three times:

```bash
for T in 0.80 0.90 0.95; do bash scripts/evidence/P15-T07_cache_threshold.sh "$T"; done
```

**The response needs an `X-Cache` header for this to work.** `STARTER.md` says
the UI *"shows a cache chip if you add `"cached": true` to the response or send
an `X-Cache` header."* Add the header in `routes/ask.py` on a hit — one line,
and it is what makes the measurement observable:

```python
@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, request: Request, response: Response) -> AskResponse:
    state = request.app.state
    result, cached = answer_question(body.question, state.retriever, state.provider,
                                     state.settings, getattr(state, "cache", None))
    response.headers["X-Cache"] = "hit" if cached else "miss"
    return result
```

`answer_question` returns `(AskResponse, cached: bool)`. Update `T-ASK-07`…
`T-ASK-12` and the starter tests accordingly — **the starter's six tests must
still pass**, so keep the response body unchanged.

**The write-up requires naming the false hit**, with both questions and the
measured similarity, as `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §6 shows. Pair P4
is the one to watch: a false hit there means failure mode E arriving through the
cache instead of the retriever, which is worse than a latency miss. Pair P6
(clause 1.21 vs 1.12) is the other likely one, and it is the same embedding
weakness the exact-term recall measurement exposes — say that, because the two
findings reinforce each other.

### P15-T08 `[HUMAN]` · Sanity-check the relevance floor

The floor is `0.35` by default and the abstention gate depends on it being
right. Two checks:

```bash
# 1. the must-abstain questions actually abstain
for q in "How do I apply for a room in the university hostel?" \
         "What is the monthly charge for university hostel accommodation and transport?"; do
  make ask Q="$q" | python3 -c "
import json,sys; r=json.load(sys.stdin)
print(f\"afc={r['answered_from_context']} max_score={max((p['score'] for p in r['retrieved']), default=0):.3f}\")"
done

# 2. the answerable questions do NOT abstain
make ask Q="What CGPA puts a student on academic warning?" | python3 -c "
import json,sys; r=json.load(sys.stdin)
print(f\"afc={r['answered_from_context']} max_score={max(p['score'] for p in r['retrieved']):.3f}\")"
```

**Read the gap.** If must-abstain questions score 0.20–0.30 and answerable ones
score 0.60–0.85, then 0.35 sits comfortably in the gap and needs no change —
say so, with the numbers. If a must-abstain question scores 0.45, raise the
floor until it abstains **without** causing any answerable question to abstain,
and record the two bounding numbers. Put the chosen value and the gap in
`docs/PIPELINE.md`; this is the measurement behind `RELEVANCE_FLOOR`.

### P15-T09 `[HUMAN]` · Commit the baseline and the results

```bash
# the shipped configuration, one final clean run
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local
echo "exit=$?"     # must be 0

# then write it as the baseline
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local --update-baseline

git add eval/baseline.json eval/results.json
```

**`--update-baseline` only after a deliberate improvement.** `STARTER.md` is
explicit, and the first baseline is by definition deliberate. Never update it to
make a failing gate pass — that is the one move that makes the whole §5.4
mechanism worthless.

Both files are a submission deliverable (SB-05).

### P15-T10 `[HUMAN]` · The UI screenshot — evidence file 9

```bash
echo "$(minikube ip) rahbar.local" | sudo tee -a /etc/hosts   # if not already
# open http://rahbar.local/ and ask a question with a visible citation
```

Screenshot a grounded, cited answer → `docs/evidence/ui_answer.png`. Also ask a
hostel question and screenshot the declined state — the UI shows both, per
`STARTER.md`. The README needs an image or a mermaid block, and this is the
honest one to use.

---

## Files created or modified

| Path | Action |
|---|---|
| `k8s/overlays/dev/patch-config-dev.yaml` | flipped to the real pipeline |
| `k8s/overlays/dev/patch-indexer-dummy.yaml` | **deleted** |
| `k8s/base/configmap.yaml` | the winning `CHUNK_SIZE`/`CHUNK_OVERLAP`/`CACHE_THRESHOLD`/`RELEVANCE_FLOOR` |
| `eval/golden.yaml` | `relevant` relabelled to the indexer's vocabulary |
| `eval/baseline.json`, `eval/results.json` | created, committed |
| `eval/experiments/results-{A,B,C}.json` | created, committed |
| `api/app/routes/ask.py`, `services/answer.py` | the `X-Cache` header |
| `scripts/reconcile_golden.py` | created |
| `scripts/evidence/P15-T02,T05,T07*.sh` | created |
| `docs/PIPELINE.md` | Chunking table, amplification, cache thresholds, the floor |

---

## Exit criteria

```bash
# 1. the real pipeline is what is configured
kustomize build k8s/overlays/dev | grep -E 'RETRIEVER|LLM_PROVIDER|EMBED_MODEL'
kustomize build k8s/overlays/dev | grep -c -- '--dummy'          # 0

# 2. the gate passes on the shipped configuration
python eval/run_eval.py --api "http://$(minikube ip)" --host rahbar.local; echo "exit=$?"   # 0

# 3. the hard numbers
python3 -c "
import json; r=json.load(open('eval/results.json'))
print('recall@3', r['recall_at_3']); print('recall@5', r['recall_at_5'])
print('citation_validity', r['citation_validity'])
print('abstention_correctness', r['abstention_correctness'])
print('by_type', json.dumps(r['by_type'], indent=2))
assert r['abstention_correctness'] == 1.0, 'MUST be exactly 1.0'
assert r['citation_validity'] >= 0.95
assert not r['must_abstain_failures']"

# 4. both baselines committed and distinct
git ls-files eval/ | grep -E 'baseline|results'
python3 -c "
import json
a=json.load(open('eval/baseline.json')); b=json.load(open('eval/baseline.fixture.json'))
assert a.get('golden') != b.get('golden'), 'the two baselines must come from different golden sets'
print('ok: real baseline', a['recall_at_5'], '| fixture baseline', b['recall_at_5'])"

# 5. PIPELINE.md has substance and a table
wc -c docs/PIPELINE.md                           # >= 1200
grep -o '|' docs/PIPELINE.md | wc -l             # >= 12
grep -ciE 'amplification|ratio' docs/PIPELINE.md # >= 1

# 6. no unmeasured number is left in the tuning sections
grep -n 'PENDING-HUMAN' docs/PIPELINE.md         # only P06-T08 (the table example) may remain

# 7. the checker's H section is green
python3 scripts/check_submission.py 2>&1 | sed -n '/H · evaluation/,/^$/p' | grep -c ' FAIL '   # 0

# 8. everything green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

---

## Rollback

```bash
# restore the last-known-good configuration and re-index
git checkout -- k8s/base/configmap.yaml k8s/overlays/dev/
kubectl apply -k k8s/overlays/dev
kubectl create job --from=cronjob/reindex restore-$(date +%s) -n rahbar
```

**Never** roll back `eval/baseline.json` to make a gate pass.

---

## Commits

```
build(k8s): switch the dev overlay to the real retriever, provider and model
test(eval): relabel golden sections to the indexer's vocabulary
feat(api): report cache hits with an X-Cache header
docs(pipeline): record three measured chunking configurations and ship 400/50
docs(pipeline): record the measured storage amplification
docs(pipeline): record three cache thresholds and the false hit that ruled one out
docs(pipeline): justify the relevance floor from the observed score gap
test(eval): commit the measured baseline and results
```

Eight commits.

---

## Before leaving

Tick P15-T01…T10 (register the human ones). **Paste every single measured
number's source command and output in the Run Log** — this is the phase where
L1 matters most. Mark IX-07, IX-08, CA-03, EV-04, EV-08, GN-07, SB-05 `CLOSED`.
Record the shipped configuration and the reasoning as **D-017**. Tick evidence
row 9. Carry the per-type recall figures forward: `ENGINEERING-NOTES.md`
question 5 needs them in P16. Advance the pointer to `P16` /
`harness/phase_16_failure_injection_and_engineering_notes.md`.
