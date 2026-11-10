# Direct-chat local recording controls

Base: integration `788da00fe4758935a5d7a49f401a4ba462139b27`. Branch `feat/direct-chat-local-privacy`. Runtime commit `2ef05f3367f8cf9ef80654c520273500072eb60c`; pin commit `c78a4c9b620acb0666aba614669f4e09858b0954` points all nine launchers at it. Build `a4767c661011638f1a7dfff323242e2cb150cb85e8e69f388ca8762389d33533`; schema `65f39c3540715ba2fd40d3e0bad24c36143af1cceb27e2e560a813736fb28092`, unchanged because no migration is added. This is a module-1 backend batch. It does not close other modules or any release gate.

This report covers focused checks on WSL2 Linux only. Complete Verify starts with the pull request and is recorded there, as are the independent reviewer's final probe and scoped native Windows checks. Nothing here is native Windows, macOS or five-platform qualification.

## Problem and result

The memory page says its device capture control covers locally connected chats, but `open_agent`, `AgentSession` and `desktop chat` entered temporary mode only when the brain's server recording switch was paused. A device pause, or a wish to keep one conversation off the record, had no effect on direct chat: its messages were recorded.

Direct chat now follows three independent controls. Any one makes a new message a temporary turn with the existing temporary-chat guarantees.

| Control | Scope | Where it is bound |
| --- | --- | --- |
| Server recording | The whole brain | Unchanged |
| Device capture | Every direct conversation of the installation, timed or until resumed | `AgentSession`, read-only from the host's pause file |
| Conversation choice | One conversation branch of this installation, brain and user | `AgentSession`, a bodyless file beside the pending sidecar |

- The service's temporary reservation accepts an explicit `off_record` request while recording is enabled. It changes no recording control and keeps authentication, the expected recording revision, the dependency generation, branch reservation, lease fencing and turn idempotency. A service without the field rejects the request before any model call. There is no recorded fallback.
- `BrainRuntime` reads no device-local files. `respond(record=False)` keeps one turn out of memory and cannot be combined with `allow_temporary=False`.
- `desktop chat` gains `/off-record`, `/on-record` and `/recording`, with `--off-record`, `--on-record` and `--recording-status`. They are never sent as messages; a mistyped form is refused. `/resume` keeps its pending-turn meaning. A message that opens with a recognized English or Chinese control takes the branch off the record before capture; quoted or reported words do not.
- `TurnResult.temporary_causes` names every cause and its scope. It is a recording outcome, separate from `DeliveryReceipt`.
- `recording_state()` keeps each control's known state. An unreadable local control is `unknown` and leads to temporary handling only after the service confirms a reservation. A silent service is `unavailable`: no turn of either kind can start.
- A pending recorded turn is neither converted nor resumed while a local control excludes recording. Only bookkeeping for a reply already delivered may finish.
- A changed device pause, including one lifted and set again with the same duration, ends the session's temporary context. Nothing is backfilled.
- A pause that a host conversation asked for lists the host conversations active when it was set. It does not apply to a direct conversation, which neither inherits nor ends it. `GET /v1/local/recording` adds `local.scope`, and the page reports that case as a host conversation pause without promising that direct messages are recorded.

Details are in the [reference](../docs/reference.md#local-recording-controls-for-direct-chat).

## Independent review

Codex reviewed the uncommitted candidate twice before any commit.

| Finding | Resolution |
| --- | --- |
| A host-conversation pause was applied to unrelated direct conversations, and a test locked that in | Only installation-wide pauses apply to direct chat. The status API and page report the narrower scope. The test was replaced by one where the host conversation stays excluded while an unrelated direct conversation records |
| Status promised temporary handling while the service was unreachable | `new_message` separates `record`, `temporary` and `unavailable`; the terminal report no longer forecasts temporary handling without a reachable service |
| Temporary context survived a device pause that was lifted and set again between two messages | The session compares the pause's identity, taken from the same single file read, and clears its buffer on change. Codex reproduced the defect first; its failing log is kept, and its probe passes after the fix |
| The in-flight boundary was implicit | Documented and pinned by a test: local controls decide how a new message is captured and do not cancel a recorded turn already running; only the server switch fences that |
| Page text promised that direct chats are still captured, and attributed the pause to one host | Text now states what that pause covers and that direct chat follows its own three controls. A combined server-pause case is tested in the browser and terminal, in English and Chinese |

## Verification

Every run used a task-owned embedded PostgreSQL 16.15 with pgvector 0.8.6, stopped afterwards, on Python 3.12.16. Generation and delivery were deterministic callbacks; the live run used a loopback fake reply provider. No model was called. The runs below overlap in the tests they contain; their counts are not additive.

### On the frozen runtime commit

| Run | Scope | Result |
| --- | --- | --- |
| `wheel-targeted-1` | Six suites against the extracted wheel: direct-chat privacy, temporary chat and its context index, agent session, desktop chat, recording controls with Chromium | 244 passed, 0 failed, 0 skipped. All 125 loaded `membrain` modules came from the extracted wheel |
| `frozen-live-1` | Real CLI subprocesses, installed service, pseudo-terminal session and the page's `/v1/local/recording` endpoint | 30 of 30 checks. Private text absent from every table, database file, WAL segment and log |
| Package | `uv build`; packaged runtime inputs compared with the checkout | 213 of 213 match; build identities equal |
| Launcher pins | `tests/test_installation_pin.py` | 2 passed |
| Ruff | `src tests examples` | Passed |

`wording-affected-1` ran the privacy, recording-controls and desktop-chat suites on the working tree whose tracked diff is byte-identical to the runtime commit: 123 passed, 0 skipped.

### On earlier candidate sources

These results keep their own source identity. They are not results for the frozen runtime.

| Run | Source | Scope | Result |
| --- | --- | --- | --- |
| `review-final-regression-1` | Review-round source, before the final wording correction | 33 suites: the 31 below plus `test_host.py` and `test_memory_page_browser.py` | 923 passed, 0 skipped |
| `review-live-1` | Same | Live CLI and service | 30 of 30 |
| `codex-case-after-fix-2` | Review-round source before documentation edits | Codex's policy-cycle probe | 1 passed |
| `mutations-review-1` | Same | Four removals of the review fixes | 4 of 4 detected; source restored byte-for-byte |
| `final-regression-2` | First candidate | 31 suites: privacy, temporary chat, session, desktop chat, runtime, recording, host recording and receipts, chat adapter, plugin | 842 passed, 0 skipped |
| `live-4` | First candidate | Live CLI and service | 30 of 30 |
| `mutations-1` | First candidate | Nine removed privacy invariants | 9 of 9 detected; source restored byte-for-byte |

### Failures and runner errors

None of these is relabelled as a pass.

| Run | What happened | Kind |
| --- | --- | --- |
| `codex-policy-cycle-1` | 1 failed: the earlier secret remained in the second temporary prompt | Product defect found by review; fixed |
| First desktop-chat run (log not retained) | 1 failed, 37 passed: `/on-record: text` was sent as a message | Product defect; mistyped recording commands are now refused |
| `privacy-1` | 12 failed, 32 passed | Test fixture mistakes; no product change followed |
| `final-regression-1` | 778 passed, 64 errors: `Recall computation startup failed` | The runner script lacked a `__main__` guard, so recall worker processes re-imported it |
| `runtime-alone-1` | 1 error | Reproduction of the same runner defect |
| `live-1`, `live-2` | Live script failed its own database reads and event count | Script defects |
| `codex-case-after-fix-1` | Collection error | The out-of-repository probe ran without the tests directory on the import path |
| Pin check before pinning | 1 failed, 1 passed | Expected until the runtime commit existed and the launchers were pinned |

### Scoped native Windows review run

After the pull request opened, Codex ran three suites natively on Windows against head `ef3d4626dab9f4685443b4d070e38ca30953432c`: direct-chat privacy, desktop chat and recording controls. pytest reported **121 passed, 1 failed and 2 errors** over 123 logical tests; both errors are the setup and teardown of one test. Runtime hashes were unchanged during the run and its task database was stopped. This run stays a failed run. It is a scoped review check, not native Windows qualification.

Neither problem is a runtime defect; both are test-portability defects.

| Test | Native result | Cause | Correction |
| --- | --- | --- | --- |
| `test_direct_chat_privacy.py::test_each_control_resumes_independently_of_the_others` | 1 failed: `PermissionError` | The test scanned every installation file while its session was open. Windows does not let another handle read the session's exclusively locked lock file | The same file and table scan now runs after the session closes, and a second session continues the test. No assertion or scan was dropped; runtime locking is unchanged and lock files are still scanned |
| `test_desktop_chat.py::test_invalid_instruction_file_fails_before_opening_session` (64,001-byte case) | 2 errors: `ValueError: the environment variable is longer than 32767 characters` | pytest used the payload as the parameter ID, so `PYTEST_CURRENT_TEST` exceeded the Windows limit. The test predates this batch | Compact explicit IDs; payloads and assertions unchanged |

`portability-affected-1` ran the affected cases on WSL2 Linux after the correction: 3 passed. That confirms the corrected tests still pass on Linux only. The native rerun of the affected cases belongs to the reviewer and is recorded in the pull request. The native log is not copied here because it contains the oversized parameter IDs; its hash is in the manifest. The corrections change tests only, so the runtime commit, launcher pins and package identity above remain valid.

Run identities, counts, package hashes and the sanitized review log are in the [evidence manifest](evidence/backend-direct-chat-local-privacy-2026-11-10/manifest.json). Raw logs remain in the task root named there.

## Not run

- Complete Verify for this head. It starts with the pull request.
- A complete native Windows suite, macOS and five-platform qualification. WSL is neither Windows nor macOS, and the scoped native review run above is not qualification.
- The TypeScript suite locally: the SDK is unchanged.
- Paid or subscription-backed evaluations.
- Any performance benchmark. No speed change is claimed. A new direct turn adds two small local file reads; this was not measured.

## Limits

- Local controls and the service are not one transaction. A control changed after the session's read, including during a running turn, applies from the next message.
- While recording stays enabled, a correction, erasure or newly published belief relation advances the dependency generation. An in-flight temporary turn then stops with `context_stale` and its temporary context restarts.
- `off_record_reservation_rejected` also covers any other invalid-request refusal of that reservation.
- The page's device resume also clears a host-conversation pause, as before. Host enforcement of that pause is unchanged.
- A temporary turn's cause is not stored with its control row, so a replayed completion marker carries none.
- Plugin hooks, the proxy and Hermes are unchanged; their failure visibility is a separate batch.
- R4 remains failed, C5 invalid/unscored and the final release review incomplete. Main merge, tags and publication remain blocked.

## Cleanup

All task-owned databases, services and test installations were stopped and removed after their results were kept. The cleanup also removed the stopped database of the reviewer's run directory inside the same task root; its result and the reviewer's own log are retained. Real profiles, models, backups and other work were not touched. No goal, schedule or background task was created.
