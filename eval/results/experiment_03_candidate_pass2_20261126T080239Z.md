# Experiment candidate_pass2

Change: {"RERANK_ENABLED": {"baseline": false, "candidate": true}}

| level | metric | baseline | candidate | delta | direction |
| --- | --- | ---: | ---: | ---: | :---: |
| module | paraphrase_mean_cos | 0.7261 | 0.7261 | 0.0000 | - |
| module | unrelated_mean_cos | 0.3814 | 0.3814 | 0.0000 | - |
| module | separation_gap | 0.3448 | 0.3448 | 0.0000 | - |
| module | n_paraphrase | 17.0000 | 17.0000 | 0.0000 | - |
| module | n_unrelated | 17.0000 | 17.0000 | 0.0000 | - |
| module | embed_ms_per_chunk_mean | 1148.2775 | 1110.3763 | -37.9013 | down |
| module | n_timed_chunks | 50.0000 | 50.0000 | 0.0000 | - |
| module | determinism_max_abs_diff | 0.0000 | 0.0000 | 0.0000 | - |
| module | determinism_n_texts | 10.0000 | 10.0000 | 0.0000 | - |
| component | recall_at_3 | 0.7812 | 0.7812 | 0.0000 | - |
| component | recall_at_5 | 0.7812 | 0.7812 | 0.0000 | - |
| component | mrr | 0.7500 | 0.7135 | -0.0365 | down |
| component | ndcg_at_5 | 0.7582 | 0.7310 | -0.0272 | down |
| component | n_items | 32.0000 | 32.0000 | 0.0000 | - |
| e2e | faithfulness | 0.9600 | 0.8889 | -0.0711 | down |
| e2e | n_human_labelled | 0.0000 | 0.0000 | 0.0000 | - |
| e2e | abstention_correctness | 1.0000 | 0.8333 | -0.1667 | down |
| e2e | n_unanswerable | 6.0000 | 6.0000 | 0.0000 | - |
| e2e | false_abstention_rate | 0.2000 | 0.1923 | -0.0077 | down |
| e2e | citation_validity | 1.0000 | 1.0000 | 0.0000 | - |
| e2e | n_citations | 27.0000 | 28.0000 | 1.0000 | up |
| e2e | answer_hit_rate | 0.5484 | 0.5625 | 0.0141 | up |
| e2e | latency_p50_ms | 70879.6584 | 65113.3483 | -5766.3102 | down |
| e2e | latency_p95_ms | 143321.0148 | 101390.5192 | -41930.4956 | down |
| e2e | n_latency | 37.0000 | 38.0000 | 1.0000 | up |
| e2e | cache_hits_in_run | 0.0000 | 0.0000 | 0.0000 | - |
