# Phase 00 — Bootstrap and Repository Reconstruction

**Goal.** Turn the flattened starter dump in the working directory into the
exact repository tree, get `make test` green on the 11 starter tests, and make
the first commits on `dev`.

**Requirements closed.** None directly — this phase creates the ground every
other phase stands on. It does satisfy the checker's `A · structure` directory
assertions and establishes DED-01, DED-12 defences.

**Core specs this phase needs.** `02_HIGH_LEVEL_DESIGN.md` §8 (the tree).
Nothing else. Do not read ahead.

**Estimated agent time.** One session.

---

## Preconditions

```bash
pwd                                 # the directory holding the flat dump
ls "Assignment 02, RAHBAR Grounded RAG on Kubernetes.pdf"
ls check_submission.py STARTER.md Makefile
ls schemas.py main.py run.py extract.py          # the flat starter files
```

All five must succeed. If the files are not flat but already in a tree (because
you unzipped `rahbar-starter.zip` properly), skip to **P00-T06** and verify the
tree against §8 instead.

---

## Task list

### P00-T01 `[AGENT]` · Environment gate

```bash
python3 --version
docker --version
minikube version
kubectl version --client
kustomize version || kubectl kustomize --help | head -1
git --version
make --version
echo "$SHELL"
uname -a
```

Record every line in the Run Log. Missing tools are **not** a blocker for this
phase — Python, git and make are enough. Register anything missing as
`BLOCKED: G-ENV-01` with the install command from `99_HUMAN_RUNBOOK.md` §1, and
continue.

**Hard requirement:** Python must be **3.12.x**. If it is not, stop and block:
`pyproject.toml` pins `target-version = "py312"` and `mypy python_version =
3.12`, and `X | None` union syntax in the starter needs ≥3.10 at minimum.

### P00-T02 `[AGENT]` · Verify the immutable files

```bash
md5sum check_submission.py STARTER.md Makefile "Assignment 02, RAHBAR Grounded RAG on Kubernetes.pdf" | tee /tmp/immutable.md5
wc -l check_submission.py       # expect 974
wc -c STARTER.md                # expect ~12814
```

Record the checksums in the Run Log. These four files are never edited
(`CLAUDE.md` L3). Re-verify the checksums at the end of the phase.

### P00-T03 `[AGENT]` · Create the directory tree

```bash
mkdir -p api/app/{routes,services,retrieval,providers/llm} api/tests
mkdir -p indexer/pipeline indexer/tests
mkdir -p ui
mkdir -p corpus/raw
mkdir -p eval/fixtures eval/experiments eval/tests
mkdir -p k8s/base k8s/overlays/dev k8s/overlays/prod
mkdir -p scripts/evidence
mkdir -p docs/adr docs/evidence
mkdir -p .github/workflows
```

Verify:

```bash
find . -type d -not -path './.git*' -not -path './.venv*' | sort
```

Expect 24 directories matching `02_HIGH_LEVEL_DESIGN.md` §8.

### P00-T04 `[AGENT]` · Move every flat file to its true path

This is the critical task. The starter zip's structure was lost when the files
were extracted flat, and the `(1)`, `(2)` suffixes are the collision markers.
The table below is derived from file **content**, not from guessing — each row
was verified by reading the file.

#### Disambiguation rules used

| Collision | Which is which | How it was identified |
|---|---|---|
| `config.py` vs `config (1).py` | `config.py` → **indexer** (`IndexerSettings`, `corpus_dir`, `chunk_size`); `config (1).py` → **api** (`Settings`, `retriever`, `llm_provider`, `top_k`) | class name and fields |
| `base.py` vs `base (1).py` | `base.py` → **providers/llm** (`class LLMProvider(Protocol)`, `generate`); `base (1).py` → **retrieval** (`class Retriever(Protocol)`, `retrieve`) | protocol name |
| `stub.py` vs `stub (1).py` | `stub.py` → **providers/llm** (`class StubProvider`); `stub (1).py` → **retrieval** (`class StubRetriever`, `_PASSAGES`) | class name |
| `requirements.txt` vs `requirements (1).txt` | `requirements.txt` → **indexer** (`pdfplumber`, `pytesseract`); `requirements (1).txt` → **api** (`fastapi`, `uvicorn`, `redis`) | package list |
| `README.md` vs `README (1).md` | `README.md` → **root** (the `STARTER-TODO(10)` placeholder); `README (1).md` → **eval/fixtures** (`# CI fixtures`) | first heading |
| `__init__ (1).py` (648 B) vs `__init__ (6).py` (473 B) | 648 B → **providers/llm** (`get_provider`); 473 B → **retrieval** (`get_retriever`) | function name |
| the five 0-byte `__init__` files | interchangeable — any empty file works in any of the five package roots | size |
| `pyproject.toml` / `pyproject (1).toml`, `requirements-dev.txt` / `requirements-dev (1).txt` | byte-identical — either copy goes to either destination | `diff` |
| the five `gitkeep` files | all 0 bytes, interchangeable | size |

#### The move script

Run it exactly as written. It uses `git mv`-safe plain `mv` because git is not
initialised yet.

```bash
set -e

# ---------- api/app ----------
mv "schemas.py"                 api/app/schemas.py
mv "config (1).py"              api/app/config.py
mv "main.py"                    api/app/main.py
mv "logjson.py"                 api/app/logjson.py

# ---------- api/app/routes ----------
mv "ask.py"                     api/app/routes/ask.py
mv "health.py"                  api/app/routes/health.py
mv "metrics.py"                 api/app/routes/metrics.py

# ---------- api/app/services ----------
mv "answer.py"                  api/app/services/answer.py

# ---------- api/app/retrieval ----------
mv "base (1).py"                api/app/retrieval/base.py
mv "stub (1).py"                api/app/retrieval/stub.py
mv "chroma.py"                  api/app/retrieval/chroma.py
mv "__init__ (6).py"            api/app/retrieval/__init__.py

# ---------- api/app/providers/llm ----------
mv "base.py"                    api/app/providers/llm/base.py
mv "stub.py"                    api/app/providers/llm/stub.py
mv "ollama.py"                  api/app/providers/llm/ollama.py
mv "hosted.py"                  api/app/providers/llm/hosted.py
mv "__init__ (1).py"            api/app/providers/llm/__init__.py

# ---------- api packaging and tests ----------
mv "requirements (1).txt"       api/requirements.txt
mv "requirements-dev.txt"       api/requirements-dev.txt
mv "pyproject.toml"             api/pyproject.toml
mv "test_starter.py"            api/tests/test_starter.py

# ---------- indexer ----------
mv "config.py"                  indexer/pipeline/config.py
mv "models.py"                  indexer/pipeline/models.py
mv "run.py"                     indexer/pipeline/run.py
mv "extract.py"                 indexer/pipeline/extract.py
mv "clean.py"                   indexer/pipeline/clean.py
mv "chunk.py"                   indexer/pipeline/chunk.py
mv "embed.py"                   indexer/pipeline/embed.py
mv "store.py"                   indexer/pipeline/store.py
mv "dummy.py"                   indexer/pipeline/dummy.py
mv "requirements.txt"           indexer/requirements.txt
mv "requirements-dev (1).txt"   indexer/requirements-dev.txt
mv "pyproject (1).toml"         indexer/pyproject.toml
mv "test_starter_dummy.py"      indexer/tests/test_starter_dummy.py

# ---------- ui ----------
mv "index (1).html"             ui/index.html
mv "nginx.conf"                 ui/nginx.conf

# ---------- corpus ----------
mv "fetch.py"                   corpus/fetch.py
mv "sources.example.yaml"       corpus/sources.example.yaml

# ---------- eval ----------
mv "run_eval.py"                eval/run_eval.py
mv "golden.example.yaml"        eval/golden.example.yaml
mv "golden.fixture.yaml"        eval/fixtures/golden.fixture.yaml
mv "academic-rules-2023.md"     eval/fixtures/academic-rules-2023.md
mv "academic-rules-2026.md"     eval/fixtures/academic-rules-2026.md
mv "fees-2026.md"               eval/fixtures/fees-2026.md
mv "README (1).md"              eval/fixtures/README.md

# ---------- docs ----------
mv "CORPUS.md"                  docs/CORPUS.md
mv "PIPELINE.md"                docs/PIPELINE.md
mv "FAILURE-ANALYSIS.md"        docs/FAILURE-ANALYSIS.md
mv "ENGINEERING-NOTES.md"       docs/ENGINEERING-NOTES.md
mv "AI-USAGE.md"                docs/AI-USAGE.md
mv "0000-template.md"           docs/adr/0000-template.md

# ---------- scripts and dotfiles ----------
mv "check_submission.py"        scripts/check_submission.py
mv "gitignore"                  .gitignore

# ---------- the assignment keeps its place at the root ----------
mv "Assignment 02, RAHBAR Grounded RAG on Kubernetes.pdf" assignment.pdf

echo "move complete"
```

`README.md`, `Makefile`, `STARTER.md` and `CLAUDE.md` stay at the root — no move
needed.

#### Verify nothing is stranded

```bash
ls -1 *.py *.txt *.toml *.yaml *.html *.conf 2>/dev/null
# EXPECT: "No such file or directory" for every pattern

ls -1 | sort
# EXPECT exactly:
#   CLAUDE.md
#   Makefile
#   README.md
#   STARTER.md
#   api
#   assignment.pdf
#   corpus
#   docs
#   eval
#   gitkeep          <- handled in P00-T05
#   gitkeep (1)      <- "
#   gitkeep (2)      <- "
#   gitkeep (3)      <- "
#   gitkeep (4)      <- "
#   indexer
#   k8s
#   scripts
#   ui
#   __init__.py      <- handled in P00-T05
#   __init__ (2).py  <- "
#   __init__ (3).py  <- "
#   __init__ (4).py  <- "
#   __init__ (5).py  <- "
```

If any other file is left, read it and place it. Do not delete anything.

### P00-T05 `[AGENT]` · The empty package and keep files

The five 0-byte `__init__.py` files are interchangeable:

```bash
mv "__init__.py"       api/app/__init__.py
mv "__init__ (2).py"   api/app/routes/__init__.py
mv "__init__ (3).py"   api/app/services/__init__.py
mv "__init__ (4).py"   api/app/providers/__init__.py
mv "__init__ (5).py"   indexer/pipeline/__init__.py

# verify every one is empty and every package root has one
for f in api/app/__init__.py api/app/routes/__init__.py api/app/services/__init__.py \
         api/app/providers/__init__.py indexer/pipeline/__init__.py; do
  test -f "$f" && echo "$(wc -c < "$f") $f"
done
# EXPECT five lines, all starting with 0
```

`api/app/retrieval/__init__.py` and `api/app/providers/llm/__init__.py` already
have content from P00-T04. **Do not overwrite them.**

The five `gitkeep` files mark the empty directories:

```bash
mv "gitkeep"       k8s/base/.gitkeep
mv "gitkeep (1)"   k8s/overlays/dev/.gitkeep
mv "gitkeep (2)"   k8s/overlays/prod/.gitkeep
mv "gitkeep (3)"   .github/workflows/.gitkeep
mv "gitkeep (4)"   corpus/raw/.gitkeep
```

No `__init__.py` is needed in any `tests/` directory: both `pyproject.toml`
files set `pythonpath = ["."]` and `testpaths = ["tests"]`, which is how
`from app.main import app` resolves from inside `api/`.

### P00-T06 `[AGENT]` · Add `pytest-cov`

CI requires a coverage number. Append to **both** dev requirement files:

```bash
printf 'pytest-cov==6.1.1\n' >> api/requirements-dev.txt
printf 'pytest-cov==6.1.1\n' >> indexer/requirements-dev.txt
cat api/requirements-dev.txt indexer/requirements-dev.txt
```

Each file must now read exactly:

```
-r requirements.txt
pytest==8.3.5
ruff==0.11.8
mypy==1.15.0
pytest-cov==6.1.1
```

This is the **only** dependency added to the project (`CLAUDE.md` §6).

### P00-T07 `[AGENT]` · Install

```bash
make install 2>&1 | tail -20
ls .venv/bin/{pytest,ruff,mypy,uvicorn} 2>/dev/null || ls .venv/Scripts/ 2>/dev/null
```

If `make install` fails because `python3 -m venv` is unavailable, install
`python3-venv` and re-run. Paste the output in the Run Log.

### P00-T08 `[AGENT]` · `make test` — the 11 starter tests

```bash
make test 2>&1 | tail -30
```

**Expect `11 passed`**: 7 in `api/tests/test_starter.py` (the length test is
parametrised over two values, so six test functions produce seven results) and
4 in `indexer/tests/test_starter_dummy.py`.

If the count differs, the tree is wrong. Diagnose in this order:

| Failure | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | running from the wrong directory | the Makefile already does `cd api`; check `api/pyproject.toml` exists with `pythonpath = ["."]` |
| `ImportError: cannot import name 'StubRetriever'` | `stub.py` / `stub (1).py` swapped | re-read both files and swap them |
| `ImportError: cannot import name 'Retriever'` | `base.py` / `base (1).py` swapped | swap them |
| `AttributeError: 'Settings' object has no attribute 'retriever'` | `config.py` / `config (1).py` swapped | swap them |
| `test_discover_reads_fixture_front_matter` fails | the three fixture `.md` files are not in `eval/fixtures/` | the test walks `parents[2] / "eval" / "fixtures"` from `indexer/tests/` |
| `ModuleNotFoundError: No module named 'fastapi'` | install failed | re-run `make install` |

**Paste the passing output in the Run Log. This is the gate for the whole phase.**

### P00-T09 `[AGENT]` · `make lint` and the HUMAN gate

```bash
make lint 2>&1 | tail -30
grep -c '<<FILL' CLAUDE.md
```

`make lint` must be clean on the starter code (it was written to pass ruff and
mypy). If `mypy` complains about the unimplemented stages, that is expected —
record it; the complaints disappear as the stages are written.

**Gate G-HUMAN-01:** `grep -c '<<FILL' CLAUDE.md` must print `0`. If it does
not, register `BLOCKED: G-HUMAN-01` in the Blocked register and tell the human
exactly which block to fill. **Proceed with P00-T10 and P00-T11 regardless** —
the identity is only needed for the commit trailers, and the human can fill it
while you work.

### P00-T10 `[AGENT]` · The `make check` baseline

```bash
make check 2>&1 | tee /tmp/check-baseline.txt
tail -3 /tmp/check-baseline.txt
```

Record the `N passed · M warnings · K failures` line in §5 of
`00_MASTER_PLAN_AND_STATUS.md`. **Expect a high failure count** — roughly
60–80 failures, because no manifest, no workflow, no Dockerfile and no pipeline
stage exists yet. That is correct for P00.

The one line that matters now: `0 · starter kit` will report ~15
`STARTER-TODO` markers and ~9 `NotImplementedError` stubs. That count must fall
to zero by Phase 13.

### P00-T11 `[AGENT]` · `git init` and the first commit

```bash
git init
git config user.name  "<partner_a.name from CLAUDE.md>"
git config user.email "<partner_a.email from CLAUDE.md>"
git add -A
git status --short | head -40
git ls-files | wc -l
```

Verify the gitignore is doing its job **before** committing:

```bash
git check-ignore -v corpus/raw/.gitkeep   # should NOT be ignored (it is a keep file)
git status --porcelain | grep -c '\.venv' # expect 0
git status --porcelain | grep -c '__pycache__'  # expect 0
```

`corpus/raw/` is gitignored but `corpus/raw/.gitkeep` must be force-added so the
directory exists in a clone:

```bash
git add -f corpus/raw/.gitkeep
```

Then commit:

```bash
git commit -m "chore(repo): reconstruct the starter kit tree

Phase: P00 · Task: P00-T04, P00-T05
Requirements: repository layout (assignment section 10)
Tests: 11 starter tests green
Verification: make test -> 11 passed; make lint -> clean

Co-Authored-By: <partner_a.name> <<partner_a.email>>
Co-Authored-By: <partner_b.name> <<partner_b.email>>"
```

### P00-T12 `[AGENT]` · Branches

```bash
git branch -M main
git checkout -b dev
git branch -a
git rev-parse --abbrev-ref HEAD    # must print: dev
```

From here on, every commit is on `dev` (`CLAUDE.md` L4).

### P00-T13 `[HUMAN]` · GitHub remote

Write `scripts/evidence/P00-T13_remote.sh`:

```bash
#!/usr/bin/env bash
# P00-T13 · the repository exists on GitHub with both branches · CI-01
set -euo pipefail
OUT=docs/evidence/git_remote.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P00-T13 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo; echo "\$ git remote -v";      git remote -v 2>&1
  echo; echo "\$ git branch -a";      git branch -a 2>&1
  echo; echo "\$ git log --oneline -5"; git log --oneline -5 2>&1
} | tee "$OUT"
```

Register in the Pending-Human table with this one-liner for the human:

```bash
gh repo create <owner>/rahbar --private --source=. --remote=origin
git push -u origin main
git push -u origin dev
bash scripts/evidence/P00-T13_remote.sh
```

> Create it **private** for now. Make it public, or add both instructors, in
> P17. A private repo cannot be scanned by anyone who finds a leaked key.

### P00-T14 `[AGENT]` · Commit the harness

```bash
git add CLAUDE.md harness/
git commit -m "docs(harness): add the AI execution harness

Phase: P00 · Task: P00-T14
Requirements: SB-06 (disclosed in docs/AI-USAGE.md during P17)
Tests: n/a
Verification: ls harness/*.md | wc -l -> 29; test -f CLAUDE.md

Co-Authored-By: ...
Co-Authored-By: ..."
```

---

## Files created or modified

| Path | Action |
|---|---|
| 24 directories | created |
| ~50 starter files | moved to their true paths |
| `api/requirements-dev.txt`, `indexer/requirements-dev.txt` | one line appended each |
| `.gitignore` | renamed from `gitignore` |
| `assignment.pdf` | renamed from the long title |
| `.git/` | initialised; `main` and `dev` created |
| `scripts/evidence/P00-T13_remote.sh` | created |

**Nothing inside any starter file is edited in this phase.** Moves only.

---

## Exit criteria

Each line is a command whose output goes in the Run Log.

```bash
# 1. the tree matches the specification
find . -type d -not -path './.git*' -not -path './.venv*' | sort | wc -l   # >= 24

# 2. nothing stranded at the root
ls -1 | sort
# exactly: CLAUDE.md Makefile README.md STARTER.md api assignment.pdf corpus
#          docs eval indexer k8s scripts ui

# 3. the 11 starter tests pass
make test 2>&1 | tail -5                                    # 11 passed

# 4. lint is clean
make lint 2>&1 | tail -5

# 5. the checker baseline is recorded
make check 2>&1 | tail -3

# 6. the immutable files are unchanged
md5sum -c /tmp/immutable.md5 2>/dev/null || md5sum scripts/check_submission.py STARTER.md Makefile

# 7. on dev, with commits
git rev-parse --abbrev-ref HEAD                             # dev
git log --oneline | wc -l                                   # >= 2

# 8. the checker's directory assertions pass
python3 scripts/check_submission.py 2>&1 | grep -E 'api/ present|indexer/ present|k8s/ present|eval/ present'
```

Plus: G-HUMAN-01 clear, or registered as blocked; P00-T13 done or registered as
pending.

---

## Rollback

Nothing is destructive. If the moves go wrong before `git init`:

```bash
# the files are all still present, just in the wrong place
find . -name 'schemas.py' -o -name 'main.py' -o -name 'run.py'
# move them again per the table
```

After `git init` and the first commit:

```bash
git reset --hard HEAD     # back to the committed tree
```

Never `rm -rf` a directory to "start clean" — the starter files have no other
copy in this repository.

---

## Commit messages for this phase

```
chore(repo): reconstruct the starter kit tree
chore(repo): add pytest-cov for the CI coverage gate
docs(harness): add the AI execution harness
```

Three commits minimum. Target ≥25 non-merge commits across the project.

---

## Update before leaving the phase

1. Tick P00-T01 … P00-T14 in `00_MASTER_PLAN_AND_STATUS.md` §2.
2. Record the `make check` baseline in §5.
3. Record the environment versions and all test output in §7 Run Log.
4. Register P00-T13 in §8 Pending-Human if the human has not run it.
5. Set the pointer: `CURRENT PHASE: P01`,
   `CURRENT FILE: harness/phase_01_contracts_and_configuration.md`.
6. Write the Handover block in §10.
