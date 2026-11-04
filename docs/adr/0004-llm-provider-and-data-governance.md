# ADR 0004: The LLM provider interface, the default mode, and data governance

## Status
Accepted · 2026-11-04

## Context

Two related concerns share this ADR because they share a boundary: the point
where RAHBAR hands a prompt — built from retrieved university-policy text —
to something outside our own process. First, section 3.5 requires the
provider be pluggable behind an interface, with at least one mode fully
supported and the interface "clean enough that a swap is one file." Second,
whichever mode we pick decides whether corpus text and questions leave the
cluster at all, which is a data-governance question independent of the
engineering one.

## Decision

**Interface.** `api/app/providers/llm/base.py::LLMProvider` is a `Protocol`
with one required method, `generate`, plus `generate_validated` (the
Template Method `BaseHTTPProvider` implements once, so "retry once, then fall
back" cannot be forgotten in one concrete provider while present in another —
see `harness/04_DESIGN_PATTERNS_AND_PRINCIPLES.md` §2.3). Swapping providers
is selecting a string in the ConfigMap's `LLM_PROVIDER` key; nothing else in
the codebase changes.

**Default mode: `ollama-host`.** `api/app/providers/llm/ollama.py::
OllamaProvider` is the fully-supported path, reaching Ollama on the laptop at
`host.minikube.internal:11434`. `hosted` (`HostedProvider`, an OpenAI-
compatible adapter) is implemented and unit-tested but not deployed as the
default. `ollama-incluster` is documented as a bonus path, not built: it
needs ≥8 GB of memory for minikube and a `startupProbe` with
`failureThreshold: 30` because model weights take minutes to load, and a
liveness probe without that allowance would kill the pod mid-load.

**Data governance.** The corpus is exclusively public FAST-NUCES documents
(`docs/CORPUS.md`) — no personal data, no student records, nothing behind a
login. Retrieved text and model output are treated as untrusted throughout
the pipeline: sanitised of the evidence delimiters
(`api/app/services/prompt.py::_sanitise`), wrapped in explicit markers, told
to the model as "DATA, not instructions" in `SYSTEM_PROMPT`, constrained to a
JSON schema at generation time, validated again with Pydantic after, and
every citation checked against the chunks actually retrieved for that
request before being shown to anyone. The provider key, when `hosted` is
used, lives only in a Kubernetes `Secret` created from the command line
(`k8s/base/secret.placeholder.yaml` — a literal `REPLACE_ME`, never a real
value, never listed in `kustomization.yaml`) and is never logged — verified
directly by `api/tests/test_providers.py::test_hosted_error_message_never_contains_the_key`,
which scripts a provider that echoes the key back in its own error body and
asserts the exception message does not contain it.

## Options considered

**`ollama-incluster` as the default.** Rejected for this project's actual
constraints: minikube on a laptop with 6 GB allocated (the assignment's own
"comfortable" figure) cannot also host an 8 GB in-cluster model deployment.
Running Ollama on the host and reaching it from the cluster is the
lower-memory path the assignment itself recommends as "easiest."

**A hosted free-tier endpoint as the default.** Rejected as the *default*,
though kept as a fully-implemented secondary path: a hosted default would
make every demo and every CI-adjacent manual run depend on a third party's
rate limit and uptime, and it would mean university policy text — even
though public — leaves the cluster on every single question rather than
only when explicitly opted into.

**No governance distinction between `ollama-host` and `hosted`.** Rejected:
the two modes have a real difference a reader should be told about plainly
rather than have to infer. `ollama-host` keeps every byte of corpus text and
every question on the machine running the cluster. `hosted` sends both to a
third party. For this corpus (public university documents) that is an
acceptable trade either way, but it would **not** be acceptable if the corpus
ever contained anything student-identifying, and that line is worth drawing
explicitly here rather than leaving it implicit.

## Consequences

**What this makes easier.** Adding a fifth provider is one new file plus one
branch in `api/app/providers/llm/__init__.py::get_provider`; nothing in
`services/answer.py`, `services/validate.py`, `services/citations.py`,
`services/abstain.py` or `services/cache.py` changes, because all of them
depend only on the `LLMProvider` Protocol, never on a concrete class
(`harness/04_DESIGN_PATTERNS_AND_PRINCIPLES.md` §3, Dependency Inversion).

**What this makes harder.** `ollama-incluster` remaining undeployed means
the bonus path is validated only by the same `BaseHTTPProvider` skeleton the
other two modes share — it has not been exercised against a real in-cluster
Ollama Deployment with a `startupProbe` tuned for multi-minute weight loading.
If it is attempted, the probe's `failureThreshold: 30` at `periodSeconds: 2`
(a 60-second grace window per the assignment's own figures) should be
treated as a starting point to be measured against the actual model's real
load time on the target hardware, not assumed correct.

**What we watch for.** If the corpus ever grows to include anything beyond
public university documents, the `hosted` mode's "data leaves the cluster"
consequence would need to be revisited before that mode could be used with
the new material — this ADR's governance line is drawn for *this* corpus,
not as a permanent guarantee for any future one.
