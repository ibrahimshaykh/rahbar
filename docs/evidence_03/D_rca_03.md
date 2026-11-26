# D5 root-cause analysis from one trace (`9b8ee73af996470386fd018dbc5058c7`)

Source: `docs/evidence_03/D_full_trace_G03-027_03.json` (candidate with `RERANK_POOL=8`).

1. **Symptom:** "late-payment surcharge per day for an overdue tuition instalment" was answered "Rs 10 per day", high confidence, citing `library_policy_03.md` 2.2.
2. **Retrieval:** the cited library chunk had the lowest similarity but one (0.633, below the fee-structure chunk's 0.667), yet the reranker (`rerank_enabled: true`) placed it first.
3. **Context:** the library chunk says an overdue *book* is charged "Rs 10 per day"; none of the five passages states a tuition late surcharge. The top score (0.667) is above the 0.55 floor, so the system did not abstain at retrieval.
4. **Generation:** the model transferred the book fine to tuition, against prompt rule 1; citation enforcement passed because it checks that the cited passage was retrieved, not that it supports the claim.
5. **Fix:** keep reranking inside the top 5 (do not widen the pool), and add a support check that the cited passage names the asked subject; the question is in the golden set as G03-027 so the gate catches a repeat.
