# Returned-round evidence and Intel native qualification

The independent read-only Claude CLI review completed in 12 turns. It reported no blocking monetary-cap defect in the inspected billing guard and harness, but identified a real evidence gap: when the shared ledger stops between tool rounds, a previously returned and accounted host response could be lost before the completed-turn row is written. Codex reproduced both stop positions with the real billing guard and a mock provider; both regressions failed because the round journal was absent.

The harness now appends and syncs each returned host round's position, message and usage before executing tools, excluding reasoning text. It checks the ledger before executing a tool. Partial rounds remain in `host-rounds.jsonl`; they do not create a completed answer or change validity/scoring. The journal remains sealed with the scenario and replies. This records returned host rounds, not an unavailable response after an uncertain network failure; the ledger retains unknown reservations separately.

An existing round journal also prevents resuming a run whose first turn never completed. The first test attempt reached the live-ledger prerequisite instead of the resume path; that failure is retained. After explicitly using the offline stub, the old code incorrectly initialized a host. The final guard refuses before host initialization and preserves the journal unchanged.

Verification:

- Before journal repair: two failed regressions, 50 deselected.
- Billing, harness and review-pipeline group after repair: **355 passed in 120.17 seconds**, with two existing Python warnings about `fork()` in a multithreaded process. This is not a warning-free result.
- After adding the resume guard: **three focused checks passed in 19.26 seconds**, covering both stop positions and refusal to resume. The broader 355-test group preceded this final guard; it is not represented as a single 356-test invocation.
- Ruff, whitespace checks and workflow YAML parsing pass.

The review also noted that missing messages or message roles can reach the provider. This does not bypass the conservative reservation, and a provider error stops the ledger. The bounded review does not constitute approval of provider rates, live response compatibility, the separate manifest/scoring implementation or the final revised candidate. No held-out scenario was authored or read, and no paid/subscription behavioral evaluation ran. The [earlier malformed-model repair](maturity-billing-review-2026-11-05.md) remains independently reproduced and tested; it was committed while the read-only review was in progress, so the review's line references reflect its observed snapshot.

## Previous-source native job timeout

Native run [42124966174](https://github.com/chriswu727/memBrain/actions/runs/42124966174), source `f26d195`, finished **cancelled**. Linux x86/ARM, macOS ARM and Windows succeeded. Intel Mac job `127586675966` has an explicit annotation that it exceeded the 30-minute execution limit. All applicable steps are marked successful, including artifact upload; the job conclusion nevertheless remains cancelled and cannot be counted as a five-platform pass.

The Intel job spent 6 minutes 20 seconds installing Python dependencies and 12 minutes 56 seconds building the native bundle. Its checks and recovery journeys continued successfully, and the last cleanup step finished about 29 minutes 32 seconds after job start. Only the Intel native job allowance is now 45 minutes; all other native jobs remain at 30. No step, assertion, memory-quality requirement or R5 latency bar changed. The changed workflow still needs a completed CI run.

Runtime `174bc50` and all launcher pins are unchanged by this batch. Its completed R5 and Mac launcher acceptance retain their scope. Previous-source Verify `42124966090` was still running at capture; the integration push remains held to avoid canceling that run. Publication stays frozen pending current-source full/native CI, R4/C5 and final review.

The [ten-payload manifest](evidence/maturity-round-evidence-2026-11-05/manifest.json) preserves the review text and metadata, its prompt, failed and passing synthetic checks, and exact GitHub job/annotation metadata. Hashes and gzip round trips are verified. No profile, credential, private scenario or user conversation is exported. The full previous-source native job log is retained locally for diagnosis; its public metadata records the failure without relabeling it as success.
