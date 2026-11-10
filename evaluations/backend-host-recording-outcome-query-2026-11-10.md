# Queryable host recording outcomes

Base: integration `74d9425309b152c650016854ace44a869dc19dd5`. Branch `feat/host-recording-outcome-query`. Runtime commit `d6aa3d58dd098ed6fc4beeacc788f32806f5b253`; pin commit `9a546fa8272b78046d4da8caa5cb96f5a6d9a6fe` points all nine launchers at it. Build `2f324016ad29a03fe11015b557e6915c4f337f3e21eee5ed902754699092afa7`; schema `65f39c3540715ba2fd40d3e0bad24c36143af1cceb27e2e560a813736fb28092`, unchanged because no migration is added. This is a module-1 backend batch. It does not close other modules or any release gate.

This report covers focused checks on WSL2 Linux and an independent reviewer's scoped runs, each with its own source and scope. Complete Verify runs on the pull request and is recorded there. Nothing here is native Windows, macOS or five-platform qualification of this feature, and no model was called.

## Problem and result

The [receipt batch](backend-host-recording-receipts-2026-11-09.md) made `finish_turn` able to say what happened to each message, but only as a return value. Plugin hooks discarded it, and the proxy and Hermes logged at most a generic failure. After the callback returned, nothing could answer "did that exchange reach memory?".

| Path | Before | Now |
| --- | --- | --- |
| Plugin hooks | Receipt discarded; exceptions in `hooks.log` | Outcome kept per session and turn ID; `membrain plugin outcome`; one bodyless log line when a message is `failed` or `unknown`. Hook output unchanged |
| OpenAI-compatible proxy | Receipt discarded; a warning naming only the exception type | `X-Membrain-Exchange` response header; `GET /v1/membrain/recording-outcomes[/{exchange}]` answered locally for the same token and person. Bodies unchanged |
| Hermes | Receipt not requested | `membrain_recording_status` tool and `recording_outcomes()`; same log line |
| `ChatMemory` / AstrBot | Receipt returned once | Also `ChatMemory.outcome()` and `recent_outcomes()` |

A lookup returns the last observation of each message with when it was seen: `recorded` (the service confirmed it), `queued` (journal admission confirmed, server storage not), `excluded` (policy, reason and scope), `failed` or `unknown`. A later journal replay, in any process, replaces a `queued` message with what the service answered. The states, statuses, storage, bounds and limits are in the [reference](../docs/reference.md#looking-up-a-recording-outcome); the design is in the [backend note](../architecture/backend-control-flow-2026-11-07.md#queryable-host-recording-outcomes-follow-up).

Design choices that shape the guarantees:

- **No second store.** Outcomes live in the entry of the turn they describe, in the existing session ledger. They are written in the same write that completes the turn, share its lock, owner-only files, 256-turn and 14-day bounds, and are removed by the same erasure.
- **Replay is the only later observer.** `flush` records what the service answered before the journal checkpoint. A lookup never contacts the service, replays or retries.
- **Evidence only improves.** A confirmation is never replaced. Unmatched, repeated and ambiguous callbacks are listed beside the exchange they named and never change it.
- **Bookkeeping never decides.** A failed outcome write is logged by error type and leaves the turn, the journal acknowledgement and the caller's result unchanged; the lookup then says `unavailable` or shows the earlier observation with its age.
- **Scope before disclosure.** Each entry is bound to its owner, producer and recording target (service, account key, brain, recovery epoch). Another owner's or target's exchange is `not_found`, indistinguishable from one that never existed, whether it is observed, awaiting, unretained or erased.

Two receipt labels changed. A whole-turn callback whose own message asks not to be kept is `excluded`/`pause_requested` instead of `unknown`/`turn_not_staged`. A journal write error, which still raises, now leaves `failed`/`queue_write_failed` when the append was rolled back and `unknown`/`admission_unconfirmed` when it could not be.

## Independent review

Codex reviewed immutable snapshots of the uncommitted candidate and reproduced three defects through public entry points before any commit. All three are fixed with regressions in `tests/test_host_recording_outcomes.py`.

| Finding | Resolution |
| --- | --- |
| Every journal write exception was stored as a definite retryable failure. When the append survived a failed sync and a failed rollback, both records stayed replayable, a later replay stored them, and the lookup still said `failed` | `_spool_records` raises `JournalAdmissionUncertain` (an `OSError` with the original arguments) when rollback fails. The outcome is `unknown`/`admission_unconfirmed`; a replay may refine it while the turn stays unfinished; a retried callback keeps what replay confirmed. A rolled-back failure remains a definite `failed` and is never refined |
| An erased exchange's tombstone was returned before the recording-target check, so another account or brain could learn that the exchange had existed and was erased | The target check now precedes every disclosure. Erasure keeps only the target digest that scopes the tombstone. Staged turns whose capture has no target are bound to the profile at staging. The lookup's target digest is the same one stamped on captures |
| Erasing one owner dropped other owners' unsettled callbacks in a shared session | The already-filtered list is kept through the session reset |

The reviewer then ran its own checks on the corrected candidate, whose build ID is the one committed here: on native Windows (Python 3.12.16) **58 passed, 5 deselected, 0 skipped**, covering this suite without its four database or service cases and the Linux-specific fault injection, plus three portable probes; on WSL **4 independent probes passed**. All 214 runtime inputs matched between the Windows worktree, the frozen review snapshot and the candidate. This is a native file, locking and API regression, not a Windows service qualification. An earlier reviewer probe against the first snapshot failed because that snapshot predated the proxy integration. The reviewer's compact record is [independent-review.json](evidence/backend-host-recording-outcome-query-2026-11-10/independent-review.json).

## Verification

Counts below are not additive: runs overlap and ran on different sources. Each run used its own task-owned embedded PostgreSQL 16.15 with pgvector 0.8.6, stopped afterwards; runtime files were hashed before and after every run and did not change. Run-by-run results, sources and log hashes are in the [manifest](evidence/backend-host-recording-outcome-query-2026-11-10/manifest.json).

### On the frozen runtime commit

| Run | Scope | Result |
| --- | --- | --- |
| Package | `uv build` at the pin commit with an empty working-tree diff; packaged runtime inputs compared with the checkout | 214 of 214 match; build identities equal ([identity](evidence/backend-host-recording-outcome-query-2026-11-10/package-identity.json)) |
| `wheel-targeted-1` | 14 suites against the extracted wheel: outcomes, receipts, delivery journal, turn isolation, queue batches, host recording and control status, Hermes (2), proxy, plugin (2), chat adapter, erasure fence | 378 passed, 0 skipped. 133 `membrain` modules loaded, none from outside the wheel |
| `frozen-live-1` | Real processes on the extracted wheel: installed service, hook commands, the proxy as a server process, the Hermes provider in its own interpreter, the outcome CLI | 39 of 39 checks. Every process reported the wheel as its import origin and the same build ID |
| Launcher pins | `tests/test_installation_pin.py` | 2 passed |
| Ruff | `src tests examples` | Passed |

`frozen-live-1` exercised, with a loopback stand-in provider and a fixed reply: server-confirmed outcomes whose event IDs equal the service's stored events; a repeated and an unmatched Stop hook; a local pause (installation scope) and a server pause (brain scope, current-policy evidence); the proxy's header, lookup, listing, streaming, 404 for another person and survival of a proxy restart; Hermes turns read back by a second interpreter; all three paths reporting `queued` while the service was stopped, with lookups leaving the journal, its cursor and every ledger byte-identical; an account-key switch hiding every earlier exchange and its reversal restoring them; the restarted service's own replay turning the three queued exchanges into `recorded`; and `forget-user` for one proxy person leaving `erased` for theirs and the other person's untouched.

### On candidate sources

| Run | Source | Scope | Result |
| --- | --- | --- | --- |
| `candidate-1` | Final candidate, committed unchanged as the runtime | Every test file that imports the host layer, an adapter, the plugin or the proxy (51 files), build identity, three longitudinal suites and the reviewer's four probes | **1,405 passed, 1 failed, 1 skipped.** The failure is described below. The skip needs a local embedding model directory |
| `mutations-1` | Same | Fifteen single removals of outcome invariants, each against the outcome suite without a database | 15 of 15 detected; source restored byte-for-byte |
| `focused-2` | After the first two review fixes | 21 host, adapter, recording and longitudinal suites | 560 passed |
| `focused-1` | First candidate | Outcomes, receipts, delivery journal, host recording, Hermes | 182 passed |

The mutations removed, one at a time: the no-downgrade rule, the separation of unmatched callbacks, the target check, the owner check, erasure of outcomes, the replay target check, keeping replay observations, the uncertain-admission classification, other owners' callbacks during erasure, the unfinished-turn restriction on replay, containment of a failed outcome write and of a failed outcome update, the proxy's namespace on lookups, keeping a confirmation across a retried callback, and the unreadable-store status.

### Failures and corrections

These happened and are kept; none is counted as passing.

| Run | What happened | Kind |
| --- | --- | --- |
| `candidate-1` | 1 failed: `tests/test_passage_index.py::test_invalid_batch_shapes_do_not_publish_a_partial_index[dimension]`, where `work_once` returned 0 | Not reproduced: the file passed alone (17) and twice with its neighbouring suites (61 passed, 1 skipped each). It tests the embedding index job and exercises no changed code. Cause not established |
| `nodb-1` | 1 failed, 78 passed, 3 skipped: `tests/test_host.py::test_users_of_a_shared_bot_keep_separate_memories` expected its own flush to replay two records | Existing test race: it simulates an outage while its real service keeps running, and that service's background replay can drain the journal first. Passed 3 of 3 alone and in both later batches. Not changed |
| Reviewer probes, snapshot 1 | Two reproduced defects (uncertain admission; erased tombstone) | Product defects found by review; fixed |
| Reviewer probe, snapshot 2 | One reproduced defect (other owners' callbacks) | Product defect found by review; fixed |
| `nodb-4` | 1 failed: a whole-turn Hermes callback asking not to be kept was `unknown` | Product mislabel inherited from the receipt batch; now `excluded` |
| `nodb-5` | 2 failed, 370 passed, 31 skipped | Two existing tests updated: the Hermes tool list gains the new tool, and an abandoned-turn test's crash injection is scoped to the interrupted process because replay now writes the ledger |
| `nodb-7` | 3 failed after the review fixes | An existing test matched the original error text, which the new exception now preserves; two new tests mixed a test double's target with a real profile |
| `nodb-3`, `nodb-6` | 1 failed each | Mistakes in new tests (the ledger has always kept a short cue of the last prompt; two lookups differ in age) |

## Local overhead

One local observation, not a benchmark and not repeated on the final source: with a full 256-exchange ledger, offline `finish_turn` took a median of about 7.4 ms with outcome bookkeeping and 4.9 ms without, and the ledger file grew from about 105 KB to 191 KB. No speed claim is made.

## Limitations

- An outcome is the last observation of one installation directory. It does not learn of deletions, corrections or resets made directly in the service or on the memory page, and it is not cross-device status.
- `queued` stays `queued` until some replay reaches the record. If the ledger write fails at that moment, or the session ledger has expired, the earlier observation or `not_found` is what remains.
- Adapter-level exclusions that never reach `finish_turn` (group recording off, unidentified speaker) are returned in the receipt only; the proxy sends no exchange header for them. Records queued outside a host turn have no exchange to attach to.
- Turn identity is the host's. Hermes turns have no host ID, so they are found by listing the session; a finish-only repeat of an identical message in one session is still `unknown`, as in the receipt batch.
- A turn staged before a profile switch and completed after it stays bound to the target it was captured under.
- The AgentRuntime turn and delivery receipts remain a separate vocabulary. Local and server controls are still not synchronized.
- Hosts were exercised through interface stubs, real hook and CLI processes and a real local service on WSL2 Linux, not inside native Claude Code, Codex, Hermes or a bot framework. No paid or subscription evaluation ran. R4 remains failed, C5 invalid/unscored and publication blocked.
