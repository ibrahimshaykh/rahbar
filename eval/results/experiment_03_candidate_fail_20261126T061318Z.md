# Experiment candidate_fail

Change: {"TOP_K": {"baseline": 5, "candidate": 1}}

| level | metric | baseline | candidate | delta | direction |
| --- | --- | ---: | ---: | ---: | :---: |
| module | paraphrase_mean_cos | 0.7261 | 0.7261 | 0.0000 | - |
| module | unrelated_mean_cos | 0.3814 | 0.3814 | 0.0000 | - |
| module | separation_gap | 0.3448 | 0.3448 | 0.0000 | - |
| module | n_paraphrase | 17.0000 | 17.0000 | 0.0000 | - |
| module | n_unrelated | 17.0000 | 17.0000 | 0.0000 | - |
| module | embed_ms_per_chunk_mean | 1148.2775 | 1094.2114 | -54.0661 | down |
| module | n_timed_chunks | 50.0000 | 50.0000 | 0.0000 | - |
| module | determinism_max_abs_diff | 0.0000 | 0.0000 | 0.0000 | - |
| module | determinism_n_texts | 10.0000 | 10.0000 | 0.0000 | - |
| component | recall_at_3 | 0.7812 | 0.7188 | -0.0625 | down |
| component | recall_at_5 | 0.7812 | 0.7188 | -0.0625 | down |
| component | mrr | 0.7500 | 0.7188 | -0.0312 | down |
| component | ndcg_at_5 | 0.7582 | 0.7188 | -0.0394 | down |
| component | n_items | 32.0000 | 32.0000 | 0.0000 | - |
| e2e | faithfulness | 0.9600 | 0.9259 | -0.0341 | down |
| e2e | n_human_labelled | 0.0000 | 0.0000 | 0.0000 | - |
| e2e | abstention_correctness | 1.0000 | 1.0000 | 0.0000 | - |
| e2e | n_unanswerable | 6.0000 | 6.0000 | 0.0000 | - |
| e2e | false_abstention_rate | 0.2000 | 0.1538 | -0.0462 | down |
| e2e | citation_validity | 1.0000 | 1.0000 | 0.0000 | - |
| e2e | n_citations | 27.0000 | 27.0000 | 0.0000 | - |
| e2e | answer_hit_rate | 0.5484 | 0.5938 | 0.0454 | up |
| e2e | latency_p50_ms | 70879.6584 | 31819.1875 | -39060.4710 | down |
| e2e | latency_p95_ms | 143321.0148 | 57141.6120 | -86179.4029 | down |
| e2e | n_latency | 37.0000 | 38.0000 | 1.0000 | up |
| e2e | cache_hits_in_run | 0.0000 | 0.0000 | 0.0000 | - |
