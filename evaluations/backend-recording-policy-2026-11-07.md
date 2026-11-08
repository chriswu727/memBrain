# Shared host recording-control repair

Runtime: `3c33fdd3c07a82a08d9f592ec2d505179c47be3f`. Build identity: `139a91e17f5de44b0a7593dc5ba8ba20c97a98f66f980456be9468e62aafb342`. All nine launchers are pinned to that runtime. The [architecture review](../architecture/backend-control-flow-2026-11-07.md) describes repaired defects, exact policy scope and remaining backend work.

The fifth acceptance's public English/Chinese off-record reproductions now pass without a model or pause-tool call. Shared host staging and finish callbacks enforce a bounded command grammar. Excluded exchanges do not reach raw staging, offline spooling or automatic extraction. Local MCP observation writes respect pause; finish receipts no longer include records rejected at delivery. The pause-state read/removal is serialized, and a new pause binds the originating session even before its first staged input.

## Verification

- Final sequential source group: **269 passed, zero skips**, 151.95 seconds. It covers recording controls, host/plugin lifecycle, chatbot/proxy/extraction, MCP, Hermes and OpenClaw, including real local PostgreSQL. No model API or subscription calls were made. The preceding runtime `08bc162` passed 266 tests before the three orphan-reply cases were added; that evidence is retained separately.
- The preceding focused suite passed **63 tests**, 17.80 seconds, and the final source group includes those plus three orphan-reply cases. Streaming and non-streaming proxy tests inspect every public database table for the synthetic excluded content, verify empty raw history, and verify a later public conversation can record normally.
- Launcher equality: **2 passed**. All nine launcher pins match the runtime source.
- Ruff over `src tests examples` and `git diff --check` pass.
- `uv build` produces wheel and source archive. All **198 runtime inputs** in the final wheel exactly match source. The final wheel passes **77 tests**, zero skips, in 17.12 seconds; module loading uses the extracted wheel rather than the editable source. The preceding `08bc162` wheel's 74-test result is retained separately.
- [PR #46](https://github.com/chriswu727/memBrain/pull/46) targets the integration candidate. [Verify 42436984585](https://github.com/chriswu727/memBrain/actions/runs/42436984585) started on the earlier checkout `a88dcdbee764207fa25e0308e17ccc546735116f`; the orphan-reply repair requires new-source CI. No full-CI pass is claimed until the final source completes. Native bundle inputs are unchanged; no separate five-platform native workflow was started for this host-only repair.

## Retained failures and limits

The first run had **1 failed / 225 passed**: the finish fallback repeated an already-handled pause after an explicit resume. The implementation was repaired; the existing extraction regression was not weakened or modified. The final sequential group includes it.

Further failure-path review reproduced **3 failed** privacy guards on runtime `08bc162`: failed input staging could still save an orphan assistant reply, and a late duplicate finish after pause/resume could revive an excluded reply. The final runtime requires a staged or explicitly supplied input before accepting a reply. All three cases pass and remain in the final source group; their failing output is retained.

An expanded run had **1 failed / 263 passed**: OpenClaw's local service exited at API startup, before the JavaScript checks. Another local test process was starting a service concurrently; the exact startup cause was not established from the sanitized log and is not asserted to be a port collision. The unchanged isolated OpenClaw rerun passed in 20.49 seconds, and the complete final sequential group passed. The leftover database for that failed test was stopped by exact owned profile; completed temporary test data was cleaned while logs were retained.

A separate MCP recheck had **98 passed / 1 skipped**; the skipped HTTP integration requires `MEMORY_DATABASE_URL` for a dedicated test database. It is not counted as a pass. The full GitHub workflow supplies that database. An initial no-isolation build could not import `hatchling`; the standard isolated `uv build` subsequently succeeded.

Recognition is deliberately limited to documented direct opening English/Chinese commands. It is not general multilingual intent understanding, retroactive deletion, an upstream-provider privacy guarantee, or a transactional server policy. Direct HTTP/SDK observation writes and the separate durable AgentRuntime remain outside this local host policy. Same-session overlapping callbacks and stronger in-flight-write guarantees need the next architectural work.

The historical fifth acceptance remains **R4 failed / C5 invalid and unscored**. No new paid acceptance was started, and this repair does not clear release gates. Main merge, tag and publication remain blocked.

Raw local logs, including failures, are retained under [evidence/backend-recording-policy-2026-11-07](evidence/backend-recording-policy-2026-11-07).
