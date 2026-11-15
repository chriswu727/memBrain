# Reproducible memory enrichment diagnostic

Run from the repository's locked Python environment:

    python evaluations/memory-evolution/compare.py --out /path/to/new-disposable-run

The output directory must not exist. The runner creates its own embedded PostgreSQL profile, starts a loopback HTTP service, stops it in `finally`, records source/fixture hashes, and refuses a run with less than 2 GiB free. Preserve the JSON results and failure logs, then remove only this run's stopped synthetic installation. No model, subscription, remote API, or dataset download is used.

Three arms share the exact source, 40-message corpus, keyword-only configuration, concurrency of one, and a 2,400-character final context cap:

- `raw`: the current memBrain recall endpoint over original records, without notes or cue enrichment.
- `notes`: the same records plus eight scripted source-linked notes.
- `notes_and_cues`: those notes plus scripted cues submitted through the host's two-call consolidation path.

This is an enrichment ablation, **not** a comparison against an independently implemented retrieval system. The enriched arms include an uncached notes read in each query's timing; session-start caching and the rest of a host turn are outside the measurement. All arms request the same service recall budget. The final character cap includes note wrappers, instructions, and recall text. Records near the cap may be truncated. Input/output characters are reported; there is no measured model-token count or model-generation cost.

The eight questions check whether every expected evidence phrase is in the supplied context. They do not generate or grade answers, test real host willingness to consolidate, or establish that an inferred statement is true. The fixtures, cues, and questions are hand-authored and small; results are diagnostics, not held-out quality acceptance. Warm repetitions are repeated measurements of these same eight questions, not additional independent examples. First requests are separate from warm repetitions, but no OS or PostgreSQL cache is cleared. The arm order rotates deterministically.

Per-brain storage counts the logical tuples in the listed tables using PostgreSQL's `pg_column_size`, not filesystem allocation, index size, WAL, long-term growth, or production capacity. Timing comparisons are within this run and machine only. The script saves the first contexts for inspection, all query measurements, enrichment read/write latency and character counts, and the exact source identity. A failed run is retained as a failed run.

The companion state path is separately exercised by `tests/test_memory_evolution_scenario.py`: inferred versus reported feelings, correction, shared moments, time decay, user-confirmed persona changes, deletion, restore and user reset. These are engineering invariants, not R4/C5 behavioural acceptance.
