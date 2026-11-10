# Host recording receipts on Windows

Base: integration `4036c59afbb3953bc57c52cb7b982de739cfd139` (PR #60/#61 merged; runtime pin `fcae1678`). Branch `feat/host-recording-receipts`. This is a module-1 backend batch; it does not close other modules or release gates.

## Existing behavior and selected path

| Path | Before | This batch |
| --- | --- | --- |
| `host.finish_turn` → `_take_turn` → spool → `flush` | Returned records "stored **or** queued"; callers could not tell server-saved from queued, excluded, failed or unmatched | Optional `receipt=` sink filled with one entry per message; returned list unchanged |
| `host_turns.take` | Fails closed without saying why | Optional `outcome=` reports unmatched/ambiguous/finished/mismatch or the stored exclusion |
| Pause, erasure, policy discard | Marked turns paused/completed | Also store the cause (reason, scope, control owner, server evidence) |
| `flush` | Counted any successful answer as delivered | Unchanged acknowledgement; optional per-record outcomes, `recorded` only with one confirmed event ID |
| `ChatMemory.record` / AstrBot | Returned `None`; AstrBot logged only exceptions | Returns the receipt; AstrBot warns on `failed`/`unknown` messages |
| Plugin hooks, Hermes, OpenAI proxy, runtime `DeliveryReceipt` | Separate contracts | Unchanged |

States: `recorded` (service observation receipt names exactly one accepted or duplicate event), `queued` (journal admission confirmed, server storage unconfirmed: `service_unavailable`, `replay_not_observed`, `server_outcome_unknown`; a lost answer may already be committed and another replay worker may drain the journal first, so this is not a queue-membership query), `excluded` (policy reason with scope and, for local controls, `applies_to`; server causes carry evidence), `failed` (a definite recording or admission failure: `queue_full` means journal admission was refused and is retryable; `rejected` means an admitted record was permanently refused and set aside, and a failed checkpoint write can leave its journal copy; `message_unavailable`) and `unknown` (unmatched or repeated callbacks, `confirmation_missing`). Receipts hold source references, never text, and never describe chat-platform delivery.

## Independent review findings incorporated

Codex reproduced two defects in the first candidate before any commit and later confirmed both fixed in a source-stable recheck; probe results are retained under `D:/memBrain-setup/receipt-review-*`. Codex also corrected the `queued` documentation (admission confirmed, storage unconfirmed, not a membership query) and the architecture note's open items.

1. A conversation pause of the default home brain was labelled `installation`. Pause causes and the staging-time scope reader ignored the `conversations` marker for the installation control. Both now report `scope: "conversation"` with `applies_to: "installation"` (or `"user"`), for pause before and after staging, per-user pauses and role-play. Enforcement is unchanged.
2. A completed 200 answer whose observation result was `{}` produced `recorded`. Confirmation now requires `outcome: "completed"` and exactly one string ID across `accepted_event_ids`/`duplicate_event_ids`. Otherwise the message is `unknown`/`confirmation_missing`. Replay still acknowledges such answers, preserving existing doubles and legacy clients.

## Verification

Runtime commit `294db3d83fcf649c5e1535019ef7366d79adc8d4`; pin commit `4f0ce5957d2ae75a0aae9e2e0ef2a9de70c414d7` points all nine launchers at it. Windows native checks used Python 3.12.16 with a task-owned embedded PostgreSQL 16.15/pgvector 0.8.6 per run, stopped afterwards. Run-by-run counts, failures and source hashes are in [evidence](evidence/backend-host-recording-receipts-2026-11-09/results.json).

The new receipt file passes **60 tests, zero skips**, on the final source. It covers each state, malformed confirmations, a lost answer after commit, a bounded replay backlog, another replay worker draining the journal first, a held replay lock and a failed checkpoint write. It also covers duplicate and unidentified callbacks, damaged stored causes, local pause scopes and owners, ChatMemory and AstrBot, and real-service confirmation, lost-answer replay and pause rejection. The host-core batch passes **379 tests with 5 failures**. Four failed because this batch ran concurrently with the adapter group: nested test installations collided on PostgreSQL's default port 55433. Those four pass when rerun alone (4/4).

The fifth, `test_a_rejected_spooled_record_is_set_aside_instead_of_blocking_the_rest`, asserts POSIX mode `0o600`; Windows reports `0o666`. It fails identically on a clean worktree of the base, so it is a pre-existing native-Windows assertion, not a receipt regression. A first no-database receipt run also failed once (49 passed, 1 failed, 3 skipped) because online staging drained the backlog the test meant to keep. The test now stages offline.

The adapter, extraction, fence, plugin, MCP, proxy, OpenClaw, C5 and companion group did not complete natively. One concurrent attempt was stopped after 21 passes to end the port collisions. The sequential attempt was stopped after 61 passes with no failures, after more than 40 minutes, by the reviewer's bounded-scope decision. An earlier run of an intermediate source was stopped after 74 passes. None of these is reported as a pass. Ruff (`src tests examples`) passes. `uv build` produces the wheel and sdist; all **213 runtime inputs** match the checkout. **148 tests pass** with imports verified from the extracted wheel (wheel sha256 `e17af11c5ec3c030ef9d017f673ecdcc8beb6c066ec68fc97d8723089496798f`). The pin checks pass (2/2).

**Complete Linux Verify on the pull request head is pending** and is not claimed here. These scoped native checks are not a complete Windows suite, WSL validation or five-platform qualification.

## Limitations

A receipt records what this call observed; another or later replay can confirm a `queued` message without a new receipt. An exact idempotent replay after a lost answer returns the service's original answer (`duplicate: false`) naming the committed event. Wrappers of `finish_turn` must forward `receipt`, or `ChatMemory.record` returns `None`; a wrapper with a fixed signature rejects the new keyword. Plugin hooks, Hermes and the proxy do not surface receipts. Integration with the independent AgentRuntime turn/delivery receipts and synchronization of the independent device and conversation controls remain open. No paid or subscription evaluation ran. R4 remains failed, C5 invalid/unscored and publication blocked.
