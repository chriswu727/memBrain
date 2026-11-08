# Host capture revision fence

Runtime commit: `6094a0945076a5cfc4897c72f23cacca0f435abd`.
Build ID: `cf92060603b904d155372df91088501e1b2321d522820f84897bfebb160d514f`.

## Result

Previously, an input staged before a server pause could arrive after resume and be accepted under the current unpaused policy. Hosts now read the authenticated policy before staging and preserve its revision through reply delivery and offline replay. The observation transaction compares that revision under its existing brain lock, with no additional database query. A mismatch returns non-retryable `recording_stale`. Both SDKs expose the optional capture revision.

Known server pauses exclude new local staging even offline and cannot be overridden by local resume. Policy caches are isolated by owner/role-play and reject response-order regression. Captures bind a known brain, endpoint, credential and recovery epoch. Legacy records default to revision zero, so a later policy change cannot silently make them eligible. Whole-turn hosts read policy at the time the completed turn is supplied.

Policy-rejected records are removed without a rejected-content archive; their matching local prompt cue is cleared. A later turn's cue is preserved. Prompt cues also retain the capture policy, so a prior-policy cue is not sent into a new recall. Server exclusions cannot be downgraded to resumable local pauses by duplicate callbacks.

## Verification

- 297 related source tests pass, zero skips, in 113.86 seconds, including real PostgreSQL/API behavior, offline replay, owner/role-play isolation, callback races, host adapters and contracts.
- 94 extracted-wheel tests pass, zero skips, in 4.97 seconds. All 202 runtime inputs match source byte-for-byte.
- 56 TypeScript tests pass, zero failures/skips; strict types, Ruff and wheel/sdist builds pass. Both launcher-pin checks pass.
- Complete GitHub Verify and five-platform native qualification are pending on this candidate. The preceding server-control runtime's results remain historical evidence, not qualification of this change.

## Local control-path cost

On the installed wheel, an arm64 loopback HTTP/embedded PostgreSQL probe measured 100 policy reads with cache persistence: median **2.047 ms**, p95 **2.326 ms**. Interleaved observation samples had medians **3.154 ms** without a capture revision and **3.167 ms** with one (100 each); the small difference is not a statistically established speed change. A 500-record stale queue was discarded in **1.938 seconds** with no rejected-content archive and no queued content stored. Both service ports closed after the probe. This is a local ingestion/control-path measurement, not recall latency, production concurrency or memory capacity. No model calls were made.

## Retained failures

The first source run had 145 passes and four failures: rejected prompt cues remained locally, one new test counted assistant messages through the user-only timeline default, and an existing assertion expected the earlier conversation-pause wording. Cue cleanup was implemented, the test explicitly requests both roles, and the wording now preserves the tested meaning without claiming server resume. The first TypeScript run had 55 passes and one failure because the new mock omitted response identity; the fixture now echoes request ID and action.

The second source run had 184 passes and two failures: a minimal legacy record without conversation metadata made cleanup raise, and fixed synthetic user IDs collided with another test principal in the reused database. Cleanup now requires locatable session identity, and the multi-user test uses unique fixture identities. A subsequent 295-test run passed. Review then added two regression tests that both failed: an old policy's cue still reached recall, and duplicate staging could downgrade a server exclusion. Both production paths were repaired before the final 297-test run. The failed logs remain in the evidence directory; rejection assertions were not removed.

## Limits and release status

Disconnected hosts cannot learn remote changes immediately: content can be buffered under a last-known unpaused policy and rejected only at replay. This does not remotely erase disconnected files or external transcripts. Local conversation/timed controls are not synchronized back to the whole-brain server switch. The observation fence does not cover separately submitted derived notes; direct SDK callers may intentionally omit it. It does not make a user/reply pair or host ledger/delivery crash-atomic, and does not add ephemeral durable-runtime chat.

This is ingestion correctness and privacy work, not new evidence of recall quality, human-like personality/emotion, memory capacity or recall speed. No paid evaluation, subscription test, main merge or publication was performed. R4 remains failed and C5 invalid/unscored; release remains frozen.

[Evidence](evidence/backend-capture-revision-2026-11-08) · [API semantics](../docs/reference.md#server-recording-control)
