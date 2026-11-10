# Conversation-scoped pause and module-1 closing fixes

Base: integration `9dd835d2` (the [status audit](status-audit-2026-11-10.md)). Runtime commit `ede5769548fed910473aa86e8251390b5650ac01`; pin commit `77adbe69f416b9bfdd9b8c2d2d724b23294fb36c` points all nine launchers at it. No migration is added. This is a module-1 backend batch that fixes four defects the audit found. It closes no release gate: **R4 remains failed and C5 invalid/unscored; main merge, tags and publication remain blocked.**

Everything below ran on WSL2 Linux against task-owned embedded PostgreSQL 16.15 with pgvector 0.8.6. No model was called. Verify, native Windows, macOS, five-platform qualification and the R5 overhead protocol were not run for this runtime, and the change has not had an independent review.

## What changed

| Audit finding | Before | Now |
| --- | --- | --- |
| H1. A pause of "this conversation" was ended by any other conversation that started | Opening a second window resumed recording in the window that had asked not to be recorded; its later messages were stored | The pause belongs to the conversations it lists. A later conversation is not covered, is told that another conversation is off the record, and does not end the pause |
| H2. Refused records outlived erasure | `spool-rejected.jsonl` kept the text of records the service had permanently refused; per-person erasure never touched it | `erase_user` removes that person's lines, and lines that cannot be attributed, under the replay lock |
| H4. A replay error at session start escaped | `session_context` raised; a host that calls it before every message then lost the exchange that followed (neither stored nor queued) | The error is logged by type and the session continues, as `prompt_context` already did |
| H7. Hermes imported `USER.md` during a pause | Entries were copied into notes at the next owner session start even while recording was paused | Nothing is imported while paused; the file is read again once recording is on |

### The pause rule

A conversation pause lists the host conversations in progress when it was set. With the change:

- **Covered conversations stay paused** until recording is resumed, or until a conversation outside the list starts after every listed one is over (no unfinished turn and no activity for six hours). An unreadable session ledger counts as still in progress.
- **A conversation outside the list is recorded as usual.** Staging, completion, abandoned-turn recovery, offline queueing and the notices in its context all check the pause for that conversation. Its opening context says that another conversation is off the record. This is said only about the person's own pause; another person's pause is neither inherited nor mentioned.
- **Memory writes follow their capture.** `memory_note` and `memory_observe` on a plugin connection, the hook note tool, `ChatMemory.note` and note extraction are checked against the conversation that their `recording_capture` or turn belongs to. A capture forged with a paused conversation's ledger id is refused as paused.
- **A write that names no conversation is refused** while any conversation pause is in effect, as before.
- **A pause that identified no conversation** (an empty list) keeps the earlier rule: it covers every conversation until the next one starts. The asking conversation is unknown there, so none may be recorded.
- Timed and until-resumed pauses, unreadable metadata and the server recording policy are unchanged.

`host.paused` and `_local_pause_cause` take the conversation as an optional `session` (or ledger `marker`). Callers that pass neither get the previous, wider answer.

## Limits and what stays open

- **Conversations already open when the pause is set stay paused longer.** The list holds every conversation in progress at that moment, because a tool call cannot always name its own conversation. Before, the next new conversation un-paused all of them; now each stays paused until it is over or recording is resumed, and each is told so on every prompt. This errs toward not recording.
- **The asking conversation can be missing from a non-empty list** when its own turn was never staged (for example its prompt hook failed) while another conversation was in progress. It is then not covered. Not reproduced; the previous rule covered it only until the next conversation started.
- **A resume lifts the whole pause**, including from a conversation that was not covered. It is an explicit request and is unchanged.
- **Status reports are not per conversation.** `control_status`, `GET /v1/local/recording` and the memory page report that a conversation pause exists; they do not say which conversation asks.
- **`USER.md` is read as a file.** An entry Hermes wrote to it during a pause is imported after recording resumes, because the import cannot tell when an entry was added.
- **A write-only host that never starts a session** leaves a stale conversation pause in place for writes that name no conversation until some conversation starts.
- Audit findings H3 (previous-prompt cue lost on hosts that call `session_context` before every message), H5 (role-play brains not covered by per-person erasure and export), H6 (Stop callbacks without a turn id) and the documented open items (local-to-server control synchronisation, `BrainRuntime` receipts, outcomes after service-side deletion, separate local and server transactions) are not addressed here.

## Verification

Counts are not additive; each run used its own task-owned database, stopped and removed afterwards. Results and log hashes are in [results.json](evidence/backend-conversation-pause-scope-2026-11-10/results.json).

| Run | Source | Result |
| --- | --- | --- |
| New regressions | Runtime commit | `tests/test_conversation_pause_scope.py`: 15 passed. The same file against the previous runtime: 15 failed |
| Audit reproductions | Previous runtime, then this one | [reproductions.py](evidence/status-audit-2026-11-10/reproductions.py): 2 failed before, 2 passed now. The second reproduction was rewritten to observe erasure instead of reading source text |
| Affected files without a database | Working tree before the commit | 23 host, adapter, recording and extraction files: 560 passed, 3 failed, 64 skipped. Two failures pinned the previous rule and were rewritten with it; the third is described below |
| Full source suite | Pin commit `77adbe69` | **8,469 passed, 4 failed, 15 skipped**, 3 fork warnings, 45 min 36 s. Runtime and migration files unchanged during the run |
| Launcher pins and build identity | Pin commit | `tests/test_installation_pin.py` and `tests/test_build_identity.py`: 12 passed |
| Ruff | `src tests examples` | Passed |

The 15 skips are the same as in the audit run: Docker journeys and tests that need the pinned local embedding model.

### Failures and corrections

- **Four failures in the full run are in background-learning tests of the cognition runtime**, which this change does not touch: one test each in `test_continuous_learning_acceptance.py`, `test_cross_conversation_funding.py`, `test_learning_windows.py` and `test_longitudinal_learning.py`. The last is the same case that failed in the audit's run of the previous runtime. Rerun on their own, the four files fail intermittently with a different test each time, **on the previous runtime as well**: three of four runs of these files on `9dd835d2` had one or two failures, and four of six runs on this runtime did. The cause is not established. It is a defect in those tests or in background learning, recorded here and not fixed.
- **`test_a_hermes_turn_that_cannot_be_matched_is_logged_and_listed_as_unknown`** failed once in the run without a database (the two exchanges were listed in the opposite order) and passed twelve times alone, six on each runtime, and in the full run. Not reproduced.
- **An aborted full run.** The first full run was stopped after 95 seconds and is not counted: the operator briefly checked out an older `src` tree for another check while it was in progress. Its log is kept; the run was repeated from the start with the runtime untouched.
- **A first version of the rule un-paused a conversation the pause could not identify.** `host.pause(conversation=True)` with no conversation in progress stores an empty list; treating that as "covers nothing" let the asking conversation be recorded. An existing test caught it. An empty list now covers every conversation until the next one starts.
- **A first version of the new notice told one person about another's pause.** The notice is now limited to the person's own pause, with a regression.

## Not run

Verify on GitHub, native Windows and macOS, five-platform qualification, the extracted-wheel regression and real host processes, the R5 overhead protocol, any model evaluation, and an independent review. The new test file uses `os.utime` on session ledgers and has not run on Windows.
