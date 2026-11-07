# Phase 13 — Golden Set and Evaluation Engine

**Goal.** Write the 16-question golden set **before any tuning**, then implement
the four functions in `eval/run_eval.py` under TDD so the CI gate becomes real.

**Requirements closed.** EV-01, EV-02, EV-03, EV-04, EV-06, EV-07, EV-09, EV-10.

**Core specs needed.** `03_LOW_LEVEL_DESIGN.md` §7.
`09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §3 and §4.
`05_TDD_AND_TESTING_HARNESS.md` §4.21.

**Preconditions.**

```bash
git rev-parse --abbrev-ref HEAD    # dev
ls corpus/MANIFEST.md              # P12 complete
cd api && ../.venv/bin/pytest -q   # green
grep -c 'NotImplementedError' eval/run_eval.py     # 4
```

---

## The ordering rule that is itself graded

**EV-02: write the golden set before you tune anything.** *"A golden set written
from the chunks you already retrieve will give you a flattering number that
means nothing."*

This is checked by **commit order**. `eval/golden.yaml` must be committed before
any commit that changes `CHUNK_SIZE`, `CHUNK_OVERLAP`, `RELEVANCE_FLOOR` or
`CACHE_THRESHOLD`. P15 is the tuning phase and comes after this one by design.

Write the questions by **reading the documents**, not by asking the running
system. Open the Academic Rules Handbook, find clause 5.4, and write down that
the CGPA threshold is 2.00 and that clause 5.4 is where it lives. That judgement
is made once, from the source, and never revised to flatter a number.

**§5 is where most of the difference between a 60 and a 90 lies.** This phase
and P15 are that difference.

---

## Task list

### P13-T01 `[AGENT]` · Write `eval/golden.yaml` — 16 questions

Copy `09_CORPUS_EVAL_AND_EVIDENCE_SPEC.md` §3 verbatim. The mix exceeds every
minimum:

| Type | Required | Ours | IDs |
|---|---|---|---|
| ordinary | 8 | **9** | q01–q09 |
| version-sensitive | 2 | **2** | q10, q11 |
| exact-term | 2 | **2** | q12, q13 |
| must abstain | 2 | **2** | q14, q15 |
| prompt injection | 1 | **1** | q16 |

Verify:

```bash
python3 -c "
import collections, yaml
qs = yaml.safe_load(open('eval/golden.yaml'))['questions']
print(len(qs), 'questions')
print(collections.Counter(q['type'] for q in qs))
assert len(qs) >= 15
c = collections.Counter(q['type'] for q in qs)
assert c['ordinary'] >= 8 and c['version'] >= 2 and c['exact'] >= 2
assert c['abstain'] >= 2 and c['injection'] >= 1
assert sum(1 for q in qs if q.get('must_abstain')) == 2
assert all(q['relevant'] == [] for q in qs if q.get('must_abstain')), \
    'a must-abstain question has no relevant passages'
ids = [q['id'] for q in qs]
assert len(set(ids)) == len(ids), 'duplicate ids'
print('ok: the mix satisfies EV-03')"
```

**Then commit it immediately**, before writing any of the four functions, so
`git log` records the order:

```bash
git add eval/golden.yaml
git commit -m "test(eval): write the golden set before any tuning

Phase: P13 · Task: P13-T01
Requirements: EV-01, EV-02, EV-03
Tests: n/a - this file IS the test corpus
Verification: 16 questions, mix 9/2/2/2/1, two must_abstain with no relevant passages

Co-Authored-By: ...
Co-Authored-By: ..."
```

**Binding `relevant` to real section labels — the one legitimate adjustment.**
Until the real index exists, `relevant` holds the section as printed in the
source document (`"5.4"`, `"1.21"`). After P15's first real index, run each
question and read what the retriever actually calls that section:

```bash
for q in q01 q02 q12; do
  echo "=== $q"
  make ask Q="$(python3 -c "
import yaml,sys
print(next(x['question'] for x in yaml.safe_load(open('eval/golden.yaml'))['questions'] if x['id']=='$q'))")" \
    | python3 -c "import json,sys; r=json.load(sys.stdin); [print(' ', p['source'], '|', p['section']) for p in r['retrieved']]"
done
```

Replace each `relevant` entry with values your indexer genuinely produces.

**Why this is not circular.** You are binding the golden set's *vocabulary* to
your indexer's, not its *judgement*. The judgement — "the answer to q01 lives in
clause 5.4" — came from reading the handbook and does not change. If clause 5.4
is absent from the top 5, recall is low and **that is the finding**, not a
problem to be relabelled away. Write that distinction into `docs/PIPELINE.md`
under "Evaluation method", and never adjust `relevant` to point at a chunk that
does not actually answer the question.

### P13-T02 `[AGENT]` · RED/GREEN — `recall_at_k`

Create `eval/pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = [".", ".."]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
```

and extend the Makefile's `test` target with `cd eval && $(BIN)/pytest -q`.

Then `eval/tests/test_run_eval.py` with `T-EVL-01` … `T-EVL-07`, then the
function per `03_LOW_LEVEL_DESIGN.md` §7.1.

```python
def test_returns_none_when_there_are_no_relevant_passages() -> None:   # T-EVL-01
    assert recall_at_k([], [{"source": "a.pdf", "section": "1"}], 5) is None


def test_respects_k() -> None:                                         # T-EVL-04
    relevant = [{"source": "a.pdf", "section": "5.4"}]
    retrieved = [{"source": "z.pdf", "section": f"{i}"} for i in range(3)] + \
                [{"source": "a.pdf", "section": "5.4 Academic Warning"}]
    assert recall_at_k(relevant, retrieved, 3) == 0.0
    assert recall_at_k(relevant, retrieved, 5) == 1.0


def test_section_prefix_matching_both_directions() -> None:            # T-EVL-05
    assert recall_at_k([{"source": "a.pdf", "section": "5.4"}],
                       [{"source": "a.pdf", "section": "5.4 Academic Warning"}], 5) == 1.0
    assert recall_at_k([{"source": "a.pdf", "section": "5.4 Academic Warning"}],
                       [{"source": "a.pdf", "section": "5.4"}], 5) == 1.0


def test_wrong_source_is_not_a_match() -> None:                        # T-EVL-06
    assert recall_at_k([{"source": "a.pdf", "section": "5.4"}],
                       [{"source": "b.pdf", "section": "5.4"}], 5) == 0.0
```

**`T-EVL-01` is the one that keeps the metric honest.** A must-abstain question
has no relevant passages. If `recall_at_k` returned `0.0` for it, the two
abstention questions would drag overall recall down by about 12% for behaving
**correctly**, the baseline would encode that penalty, and the CI gate would
compare nonsense against nonsense. `None` means "not scoreable", and `summarise`
excludes those rows from the means.

**The matching rule — EV-10 requires you to state it.** Source must match
exactly after case-folding and stripping; section matches when either normalised
string is a prefix of the other. Normalisation collapses whitespace, lowercases,
and strips a trailing period. Write it verbatim into `docs/PIPELINE.md`:

> `recall@k` matches a golden `(source, section)` pair against the response's
> `retrieved` list. **Source** must be identical after case-folding. **Section**
> matches when either normalised string is a prefix of the other, so a golden
> entry of `"5.4"` matches a chunk recorded as `"5.4 Academic Warning"` and vice
> versa, but never matches `"1.21"`. An empty golden section matches any section
> of that source. We match on `(source, section)` rather than `chunk_id` because
> chunk ids change when the chunking configuration changes, and P15 compares
> three configurations against one fixed golden set.

That last sentence is the design argument, and it is the sort of thing a marker
looks for.

### P13-T03 `[AGENT]` · RED/GREEN — `citation_validity`

Four tests (`T-EVL-08` … `T-EVL-11`), then §7.2.

`None` when there are no citations — distinct from `0.0`, which would mean
"every citation was invalid". An abstention legitimately has no citations and
must not be scored as a citation failure.

Reuse the same `_norm_source` / `_norm_section` helpers and the same prefix rule
as `recall_at_k`. Using a stricter rule here than the API's
`enforce_citations` uses would make the metric disagree with the thing it
measures: the API would keep a citation that the evaluator then counted invalid,
and `citation_validity` would never reach 1.0 no matter what the code did.
**The two rules must be the same rule**, and a comment in both places says so.

### P13-T04 `[AGENT]` · RED/GREEN — `summarise`

Seven tests (`T-EVL-12` … `T-EVL-18`), then §7.3 with the **exact** output
schema. `gate` reads these keys by name and `baseline.json` is this shape, so a
renamed key silently disables a gate.

```python
def test_must_abstain_rows_are_excluded_from_recall_means() -> None:   # T-EVL-16
    rows = [_row("q01", "ordinary", recall=1.0),
            _row("q14", "abstain", must_abstain=True, relevant=[])]
    out = summarise(rows)
    assert out["recall_at_5"] == 1.0, "a correct abstention must not look like a recall failure"
    assert out["by_type"]["abstain"]["recall_at_5"] is None


def test_abstention_correctness_falls_and_names_the_failure() -> None: # T-EVL-15
    rows = [_row("q14", "abstain", must_abstain=True, answered_from_context=False),
            _row("q15", "abstain", must_abstain=True, answered_from_context=True)]
    out = summarise(rows)
    assert out["abstention_correctness"] == 0.5
    assert out["must_abstain_failures"] == ["q15"]
```

`must_abstain_failures` holding the **ids** rather than a count is what makes a
CI failure actionable: the gate message names `q15` and you know which question
to investigate.

Three edge conventions, each with a test:

| Situation | Value | Why |
|---|---|---|
| no must-abstain rows at all | `abstention_correctness = 1.0` | nothing failed; `0.0` would fail the gate on a subset run |
| no citations anywhere | `citation_validity = 1.0` | nothing invalid was emitted |
| a type with no scoreable rows | `recall_at_k = None` | `null` in JSON, excluded from reporting |

### P13-T05 `[AGENT]` · RED/GREEN — `gate`

Eight tests (`T-EVL-19` … `T-EVL-26`), then §7.4.

**Do not edit the three constants.** `MAX_RECALL5_DROP = 0.05`,
`MIN_CITATION_VALIDITY = 0.95`, `REQUIRED_ABSTENTION = 1.0` are §5.4 verbatim.
`run_eval.py`'s own docstring says *"Change these only with a reason written in
docs/PIPELINE.md."*

The three boundary tests are the ones that matter:

```python
def test_fails_below_95_percent_citation_validity() -> None:           # T-EVL-21
    assert len(gate(_results(citation_validity=0.94), None)) == 1
    assert gate(_results(citation_validity=0.95), None) == []     # inclusive


def test_fails_when_recall5_drops_more_than_five_points() -> None:     # T-EVL-22
    base = {"recall_at_5": 0.80}
    assert len(gate(_results(recall_at_5=0.74), base)) == 1
    assert gate(_results(recall_at_5=0.75), base) == []           # exactly 0.05 passes


def test_missing_baseline_skips_only_the_recall_gate() -> None:        # T-EVL-24
    msgs = gate(_results(abstention_correctness=0.5), None)
    assert len(msgs) == 1 and "100%" in msgs[0]
```

A missing baseline is **not** a failure — the first run has none, and so does
a fresh clone. But a missing baseline must not suppress the other two gates,
which do not need one.

Each message must name the numbers and, where possible, the failing ids. A gate
message reading `"recall dropped"` wastes the CI run; one reading
`"recall@5 fell 0.080 below the baseline (0.800 -> 0.720), more than the allowed
0.050"` tells you the size of the regression at a glance.

### P13-T06 `[HUMAN]` · The fixture end-to-end run

Write `scripts/evidence/P13-T06_eval_fixtures.sh`:

```bash
#!/usr/bin/env bash
# P13-T06 · the eval engine scores a live stack against the fixture golden set
set -euo pipefail
OUT=docs/evidence/eval_fixtures.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P13-T06 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: EV-08, EV-09, EV-10. Needs 'make dev' in another terminal."
  echo; echo "\$ curl -s localhost:8000/readyz"; curl -s localhost:8000/readyz 2>&1; echo
  echo; echo "\$ python eval/run_eval.py --api http://localhost:8000 \\"
  echo "    --golden eval/fixtures/golden.fixture.yaml \\"
  echo "    --baseline eval/baseline.fixture.json --out eval/results.fixture.json"
  python eval/run_eval.py --api http://localhost:8000 \
    --golden eval/fixtures/golden.fixture.yaml \
    --baseline eval/baseline.fixture.json \
    --out eval/results.fixture.json 2>&1
  echo "exit=$?"
  echo; echo "\$ cat eval/results.fixture.json"
  python3 -m json.tool eval/results.fixture.json 2>&1
} | tee "$OUT"
```

One-liner for the human — two terminals:

```bash
# terminal 1
make dev
# terminal 2
bash scripts/evidence/P13-T06_eval_fixtures.sh
```

**With the stubs, expect low recall and that is correct.** `make dev` runs
`RETRIEVER=stub`, which returns the same three stub passages for every question,
so `recall_at_5` will be `0.0` and the gate will fail on citation validity or
abstention. What this run proves is that the *plumbing* works: the runner talks
to the API, `summarise` produces the schema, `gate` returns messages and the
exit code is non-zero. **Expect exit code 1, not 0, and record that.**

For a meaningful fixture score the stack must run `RETRIEVER=chroma` against an
index of `eval/fixtures/`, which is what CI's `e2e-eval` job does in P14. Run it
locally too if a cluster is up:

```bash
CORPUS_DIR=eval/fixtures RETRIEVER=chroma EMBED_MODEL=ci-hash-256 make dev
```

That requires the `ci-hash-` affordance from `08_CICD_WORKFLOW_SPEC.md` §4 —
implement it now, in both `indexer/pipeline/embed.py` and
`api/app/retrieval/chroma.py`:

```python
def _hash_vectors(texts: list[str], dim: int) -> list[list[float]]:
    """Deterministic hash vectors for CI, where no Ollama is reachable.
    Same algorithm as pipeline/dummy.fake_vector. Declared in docs/PIPELINE.md:
    it exercises real Chroma writes, real ANN search and real metadata filtering
    with no model. The recall numbers reported in baseline.json come from the
    real corpus and the real embedding model."""
```

Triggered when `settings.embed_model.startswith("ci-hash-")`, with the dimension
read from the suffix. Both sides must honour it or the pin check fails.

### P13-T07 `[AGENT]` · Commit `eval/baseline.fixture.json`

Once P13-T06 produces a passing fixture run against a real index, write it as
the fixture baseline:

```bash
python eval/run_eval.py --api http://localhost:8000 \
  --golden eval/fixtures/golden.fixture.yaml \
  --baseline eval/baseline.fixture.json \
  --out eval/results.fixture.json --update-baseline
git add eval/baseline.fixture.json
```

This is a **separate** baseline from `eval/baseline.json`. CI compares against
the fixture one; P15 writes the real one. Mixing them would compare recall
across two different corpora, which is meaningless.

---

## Files created or modified

| Path | Action |
|---|---|
| `eval/golden.yaml` | created — 16 questions, committed first |
| `eval/run_eval.py` | four functions implemented; `SPEC-REF`s removed |
| `eval/pyproject.toml` | created |
| `eval/tests/test_run_eval.py` | created — 26 tests |
| `eval/baseline.fixture.json` | created |
| `indexer/pipeline/embed.py` | `ci-hash-` affordance |
| `api/app/retrieval/chroma.py` | `ci-hash-` affordance |
| `Makefile` | `test` target runs the eval tests |
| `docs/PIPELINE.md` | "Evaluation method" section written |

---

## Exit criteria

```bash
# 1. the golden set satisfies the mix
python3 -c "
import collections, yaml
qs=yaml.safe_load(open('eval/golden.yaml'))['questions']
c=collections.Counter(q['type'] for q in qs)
assert len(qs)>=15 and c['ordinary']>=8 and c['version']>=2 and c['exact']>=2 and c['abstain']>=2 and c['injection']>=1
print(len(qs), dict(c))"

# 2. all 26 eval tests pass
cd eval && ../.venv/bin/pytest -q

# 3. NO NotImplementedError left anywhere in the repository
grep -rn 'raise NotImplementedError' --include='*.py' --exclude-dir=.venv --exclude-dir=tests .   # empty
grep -rn 'SPEC-REF' --exclude-dir=.venv --exclude-dir=.git --exclude=STARTER.md . | grep -v '\.example\.'   # empty

# 4. section 0 of the checker is finally clean
python3 scripts/check_submission.py 2>&1 | sed -n '/0 · starter kit/,/^$/p'
# EXPECT: "no SPEC-REF markers left" and "no NotImplementedError stubs left"

# 5. the H section is green apart from the P15 artefacts
python3 scripts/check_submission.py 2>&1 | sed -n '/H · evaluation/,/^$/p'

# 6. the golden set was committed before any tuning
git log --oneline --diff-filter=A -- eval/golden.yaml
git log --oneline -- k8s/base/configmap.yaml | tail -1
# EXPECT: no configmap commit touching CHUNK_SIZE after the golden.yaml commit

# 7. everything green
make test 2>&1 | tail -3
make lint 2>&1 | tail -3
make check 2>&1 | tail -3
```

Exit criterion 4 is a milestone: **section 0 of the checker is clean**, meaning
every stub the starter shipped has been replaced.

---

## Rollback

```bash
git checkout -- eval/run_eval.py
rm -f eval/tests/test_run_eval.py eval/pyproject.toml
```

Never roll back `eval/golden.yaml` — its commit timestamp is the EV-02 evidence.

---

## Commits

```
test(eval): write the golden set before any tuning          <- FIRST, alone
test(eval): assert recall@k returns None for must-abstain questions
feat(eval): compute recall@k with prefix section matching
test(eval): assert citation validity uses the API's matching rule
feat(eval): measure citation validity against the retrieved list
test(eval): assert abstention failures are named, not just counted
feat(eval): summarise overall and per-type metrics into results.json
test(eval): assert all three gate boundaries and a missing baseline
feat(eval): gate CI on abstention, citation validity and recall regression
feat(indexer,api): add the ci-hash embedding affordance for offline CI
docs(pipeline): state the recall matching rule and the CI affordance
```

Eleven commits, with the golden set first.

---

## Before leaving

Tick P13-T01…T07. Paste every test run and the fixture eval output (including
its exit code) in the Run Log. Mark EV-01…EV-04, EV-06, EV-07, EV-09, EV-10
`CLOSED`. Record the `ci-hash-` affordance as **D-016**. Advance the pointer to
`P14` / `harness/phase_14_cicd_pipelines.md`.
