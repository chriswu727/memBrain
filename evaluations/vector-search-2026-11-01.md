# Vector search, 2026-11-01: is an approximate index needed yet?

The architecture review asked whether meaning-based recall needs an approximate nearest-neighbour (HNSW) index, since every vector query is an exact scan within one brain. Measured on synthetic 384-dimension vectors (the local model's size) in the Docker test database (PostgreSQL 17, pgvector 0.8.7), one brain growing next to twenty small brains of 500 records. The harness is [`vector-search-2026-11-01.py`](vector-search-2026-11-01.py).

| Records in the brain | Exact nearest 50 (median of 5) | With an HNSW index |
| --- | --- | --- |
| 10,000 | 9 ms | — |
| 50,000 | 36 ms | — |
| 200,000 | 111 ms | 29 ms |
| a 500-record brain | — | 1 ms (the planner uses the brain index, not HNSW) |

Building the HNSW index over 210,000 vectors took 465 seconds.

## Decision: not yet

- At about 150 remembered statements a day, a heavy single user reaches 200,000 after three to four years, where an exact scan still takes about a tenth of a second. Bot users each have small brains, where the planner already prefers the brain index.
- The embedded engine ships pgvector 0.6.2, which has no iterative index scans: with a brain filter an HNSW scan returns only the nearest few dozen across all brains and then filters them, so a small brain could get few or no results. A per-model expression index would also tie the schema to one embedding model, and building it in a migration would block an upgrade for minutes on a large installation.
- Recall's vector query joins memory statements and applies eligibility filters, so using an index would also mean prefetching candidates and falling back to the exact scan when too few survive.

Revisit when one brain passes about 300,000 embedded statements or recall's vector step exceeds 150 ms at p95, and when the embedded engine has pgvector 0.8 or later.
