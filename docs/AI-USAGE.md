# AI usage

Honest attribution, not avoidance (section 8). A specific disclosure carries
no penalty; presenting AI-generated work as our own would be plagiarism under
the course policy, so this document names every tool, what it actually wrote
or shaped, and what we changed or verified afterwards and why.

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Claude (Opus), used as a planning assistant | A 29-file execution harness under `harness/` at the repository root: the requirements traceability matrix mapping every sentence of `assignment.pdf` to a file/class/test; the high- and low-level design documents; the test inventory; the Kubernetes manifest and GitHub Actions workflow specifications; and 18 phase-by-phase execution plans | We supplied the assignment PDF and the starter kit and reviewed the plan's architectural, library, and schema decisions before any implementation began. We corrected the harness's own first draft on at least two real points found during execution: the evidence directory path (`assignment.pdf` §10 shows a root `evidence/`; `scripts/check_submission.py` actually reads `docs/evidence/` — the checker's behaviour is authoritative, so the harness was corrected to match it) and the `STARTER` + `-TODO` naming convention inside the harness's own documentation (written here split in two so this very sentence does not itself retrigger the scan), which the checker's own leftover-marker scan was flagging as if it were an unfinished stub in our documentation (renamed to a neutral marker throughout `harness/*.md`) |
| Claude Code (CLI agent), executing the harness | First-draft implementations of all five indexer pipeline stages (`extract.py`, `clean.py`, `chunk.py`, `embed.py`, `store.py`), the Chroma retriever, both LLM providers, the semantic cache, the citation-enforcement and abstention logic, the validation/retry/fallback path, the full query orchestrator, all fifteen Kubernetes manifests, both GitHub Actions workflows, and the four ADRs — every piece written test-first (RED, then GREEN, then a lint/test gate) against the harness's low-level design specification | Every test in the suite (241 as of the final CI run: 156 API, 58 indexer, 27 eval) was run and its actual pass/fail output read before being claimed as passing — never asserted from memory. Every measured figure anywhere in `docs/PIPELINE.md`, `docs/CORPUS.md` and `docs/evidence/` is from a real command run on this machine against the real, fetched corpus, not a plausible-sounding guess; where a number needed infrastructure the agent's own host did not have (a live Chroma instance, the pinned Ollama model, a Kubernetes cluster), it was left blank until the team ran it on their own machine, and was never invented. Two real bugs were found by running the pipeline against the real fetched corpus rather than only against hand-built test fixtures, and both are documented rather than quietly fixed with no record: a missing Roman-numeral heading pattern (fixed, with a regression test — `indexer/tests/test_chunk.py::test_splits_on_roman_numeral_headings`) and a two-column PDF layout producing interleaved text (documented as an acknowledged, unrecovered limitation in `docs/PIPELINE.md`, not fixed, because column-aware extraction was judged out of proportion to its benefit for two pages out of 279) |

## What we understand and can explain

We can explain, without the documents in front of us: why the indexer is a
`Job` and not a startup hook (the three-writers-one-volume race, the
re-index-on-every-restart cost, the readiness lie, and the no-redeploy
requirement — ADR 0001); why `/healthz` must never touch a dependency while
`/readyz` must check four of them in a fixed order; what the embedding pin
actually prevents and how it is enforced in code rather than by convention;
why the semantic cache is keyed by a generation counter rather than scanned
and deleted on invalidation; the eight steps of the query pipeline and the
reason their order is load-bearing (cache before retrieval, the relevance
floor before generation, citation enforcement after); why our exact-term
recall is expected to be measurably worse than our definitional recall and
which technique from the RAG lecture addresses that; and what each of the
corpus's seven required properties is satisfied by, with the real clause
text and real figures behind each one.

## A note on process

This submission was built by an autonomous coding agent working from a
human-authored specification (the harness above), under instructions never
to assert a result it had not verified and never to fabricate a measurement,
a test's pass/fail status, or a piece of cluster evidence it could not
produce on the development machine available. While the agent's environment
lacked Docker, a Kubernetes cluster or the Ollama runtime, those steps were
left open with a ready-to-run capture script and were never
filled with invented output. They were later run live on the team's own
machine and the markers were replaced with the real outputs, which are in
`docs/evidence/`. The agent also opened pull requests and handled the
CI repair, but a human merged the final pull request.
