# Embedding a statement as its whole message, and jobs that stay due when the clock steps back

Base: pin `6c0f8d12`. Runtime commits `5b944211` (jobs) and `02a1aecf` (embeddings); pin commit `b04af871` points all nine launchers at the latter. No migration. Third memory-quality batch measured against the [LoCoMo evidence-recall baseline](locomo-evidence-recall-2026-11-10.md). It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Everything ran on WSL2 Linux with task-owned embedded PostgreSQL 16.15 and pgvector 0.8.6. No model was called. GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## Message-context embeddings

### What was wrong

A stored message becomes one statement per sentence, and each statement was embedded on its own, with a role prefix and without its message. A question was therefore compared with sentences that had lost their speaker, their date and what the neighbouring sentences were about. On the development conversations ([message_level_routes.py](locomo/results-2026-11-10/message_level_routes.py), runtime `b301c55`, 519 evidence turns), counting where the evidence *message* ranks:

| Route | Evidence message in the first 10 | In the first 40 |
| --- | --- | --- |
| Meaning route over single statements (as it was) | 31.8% | 47.2% |
| Same model over whole messages | 53.4% | 71.7% |
| Service keyword route | 54.9% | 70.5% |
| Keyword route fused with the whole-message route (simulated) | 62.2% | 76.9% |
| Plain BM25 plus whole-message embeddings | 54.1% | 74.2% |

### What changed

- **A directly captured statement is embedded as its source message** when the message is at most 1,500 characters and the model takes it as one input. Otherwise it is embedded as its own text, with passages, as before; so is anything derived from several sources.
- **Identical inputs are sent to the model once**, so the statements of one message cost one embedding.
- **The meaning route lists a message once.** Statements that share a vector arrive at the same distance; the one that also matched by keyword is kept, so both routes credit the same candidate, otherwise the first.
- **The stored index version carries the rule** (`…+message-context-v1`), so vectors made under the earlier rule are queued again by the existing backfill and replaced in the background.

Erasure, suppression and correction are unchanged: vectors are still stored per statement and removed with it, and the staleness check still compares the statement.

### Result

A fresh ingestion of all ten conversations, then the same questions. Share of questions whose evidence turns are all in the recall block:

| | Questions | Morning baseline `ede5769` | `b301c55` | This runtime | Plain retrieval, 9,000 characters |
| --- | --- | --- | --- | --- | --- |
| All | 1,535 | 52.7% | 68.0% | **74.1%** | 73.6% |
| Development conversations | 383 | 54.3% | 71.5% | 79.9% | 76.2% |
| Held-out conversations | 1,152 | 52.2% | 66.8% | **72.2%** | 72.7% |
| Held out, single-hop | 641 | 67.6% | 84.6% | 88.6% | 88.1% |
| Held out, temporal | 230 | 55.7% | 68.7% | 74.3% | 76.5% |
| Held out, multi-hop | 208 | 10.1% | 21.2% | 30.3% | 30.8% |
| Held out, open-domain | 73 | 26.0% | 35.6% | 41.1% | 43.8% |
| Held out, several evidence turns | 321 | 13.7% | 25.2% | 34.9% | — |

- **The recall block is now level with plain retrieval over the same messages at the same size.** It was 21 points behind in the morning.
- Against `b301c55` on the held-out conversations, 101 questions gained all their evidence and 39 lost it (exact McNemar test, p < 0.001). The design was chosen on the development conversations.
- The recall block is 8,601 characters on average. Per-prompt recall takes 329 ms at the median and 358 ms at the 95th percentile (322 and 348 before); session start 242 ms. Ingesting and embedding the ten conversations took 945 seconds in total, against 928 for the baseline run.
- Questions that need several memories remain the weak point for both: about a third have all their evidence.

Rows and the comparison are in [results-2026-11-10](locomo/results-2026-11-10/) (`recall-02a1aec.jsonl.gz`, `compare-b301c55-02a1aec.txt`).

### Limits

- **Existing installations are re-embedded in the background** after the upgrade, one batch at a time while the worker is idle; until a statement is re-embedded its old vector is used. The time this takes on a large brain was not measured.
- A statement that has been retracted leaves its sentence in the message that its sibling statements are embedded with. The text shown to a host is filtered as before; only the ranking of the siblings can reflect it.
- Messages over 1,500 characters, and any message the model must split, keep statement-level vectors. LoCoMo's longest stored turn is 449 characters, so that path is covered by tests and not by the measurement.
- Being level with plain retrieval on one English benchmark is not a claim about answers, other languages, or long real histories. The measurement shares the [baseline's limits](locomo-evidence-recall-2026-11-10.md#limits).

## Jobs that stay due when the clock steps back

Four background-learning test files had failed intermittently in every recent full run, a different test each time. A delegated investigation found the cause in product code:

- **The wall clock on this machine steps backwards.** The system journal shows it stepping back against the monotonic clock in bursts of about half a second every 32 seconds, with single steps of 5 and 43.6 seconds, and three "Time jumped backwards" notices. Every full run that had such failures overlapped a burst; the one run in a quiet period had none.
- **A new job was compared with the clock.** `available_at` and `created_at` both default to the transaction time, and claiming required `available_at <= clock_timestamp()`. After a backward step, a job created just before it was not due for as long as the step, and learning stopped early (`current_encoding_not_ready`, `literal_work_previously_attempted`).
- **Fault injection reproduces it.** A database trigger that makes about 3% of new jobs two seconds newer, on fresh databases, four files, 88 tests per run:

| Injection | Failures per run |
| --- | --- |
| None, quiet clock (3 runs) | 0, 0, 0 |
| Both times shifted (2 runs) | 2, 9 |
| Due time only (2 runs) | 7, 8 |
| Creation time only (2 runs) | 0, 1 |
| Both shifted, with this fix (3 runs) | 1, 0, 0 |

The fix: a job is due when its time has come **or when it was never delayed** (`available_at <= created_at`). A retry delay still waits. The same condition is used by the learning progress report and the two example harnesses.

**Still open:** jobs are ordered by `created_at`, which a step can also disturb; that is the failure left under injection. Removing it needs an insertion sequence on the job table, a migration that this batch does not make. On a host whose clock steps back, work can therefore still be picked in a slightly wrong order; it could no longer be left waiting.

Scripts are in [clock-step-jobs-2026-11-10](evidence/clock-step-jobs-2026-11-10/). The journal analysis and the injection runs were carried out by the delegated agent; the migration default, the claim condition, the journal notices and the per-run failure counts were checked against the files.

## Verification

Results and log hashes are in [results.json](evidence/message-context-embeddings-2026-11-10/results.json). The suite run and its triage were carried out by a delegated agent.

| Run | Source | Result |
| --- | --- | --- |
| Embedding and ranking test files, fresh database | Working tree before the commit | 12 files: 187 passed; with the new file and `test_vector_jobs.py`: 14 passed |
| Job and learning test files, fresh database | Working tree before the commit | 7 files: 243 passed |
| Full source suite, with the local embedding model | Pin commit `b04af871` | **8,502 passed, 2 failed, 4 skipped** of 8,508, 3 fork warnings, 49 min 43 s. No backward clock step during the run (20 ms monitor). Runtime and migration files unchanged |
| The two failing tests after their correction | `1c0edeca` (tests only) | `tests/test_jobs.py` six times in one run: 90 passed. The host test eight times, each on a fresh database: 8 passed |
| Ruff | `src tests examples` | Passed |

### The two failures in the full run

Both were timing assumptions in tests, corrected in `1c0edeca` without a runtime change. The full suite was not repeated after that correction.

- `tests/test_jobs.py::test_a_job_created_before_the_clock_stepped_back_is_still_due`, new in this batch, set the job's two times from two clock readings. They can differ by microseconds, which makes the job a delayed one. Failed in the full run and in 2 of 3 reruns. It now sets one value, as the columns' shared default does.
- `tests/test_host.py::test_users_of_a_shared_bot_keep_separate_memories` required its own `flush` to replay two queued records. The service's replay thread, which exists since 2026-11-08, can store them first, and the call then returns 0. Failed in the full run and in 1 of 3 reruns; it had passed in the five earlier full runs. It now accepts either and waits for the queue to empty before checking what was stored. That the replay thread was the other party is inferred from the code and the empty queue, not observed directly.

None of the five files affected by clock steps failed in this run; no step occurred during it, so the run does not by itself show the fix at work. The injection runs above do.
