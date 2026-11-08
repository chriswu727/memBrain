# Shared host recording-control repair

Runtime: `08bc162a78fa2a7945dddc3d60d281d10329b9d7`. Build identity: `03041ca9895f929369129b429df2e7bc5afff60241c2fad7f143e574af0dccb0`. All nine launchers are pinned to that runtime. The [architecture review](../architecture/backend-control-flow-2026-11-07.md) describes repaired defects, exact policy scope and remaining backend work.

The fifth acceptance's public English/Chinese off-record reproductions now pass without a model or pause-tool call. Shared host staging and finish callbacks enforce a bounded command grammar. Excluded exchanges do not reach raw staging, offline spooling or automatic extraction. Local MCP observation writes respect pause; finish receipts no longer include records rejected at delivery. The pause-state read/removal is serialized, and a new pause binds the originating session even before its first staged input.

## Verification

- Final sequential source group: **266 passed, zero skips**, 151.26 seconds. It covers recording controls, host/plugin lifecycle, chatbot/proxy/extraction, MCP, Hermes and OpenClaw, including real local PostgreSQL. No model API or subscription calls were made.
- Focused suite: **63 passed**, 17.80 seconds. Streaming and non-streaming proxy tests inspect every public database table for the synthetic excluded content, verify empty raw history, and verify a later public conversation can record normally.
- Launcher equality: **2 passed**. All nine launcher pins match the runtime source.
- Ruff over `src tests examples` and `git diff --check` pass.
- `uv build` produces wheel and source archive. All **198 runtime inputs** in the wheel exactly match source. Installed-wheel behavior and GitHub qualification are tracked separately until completed.

## Retained failures and limits

The first run had **1 failed / 225 passed**: the finish fallback repeated an already-handled pause after an explicit resume. The implementation was repaired; the existing extraction regression was not weakened or modified. The final sequential group includes it.

An expanded run had **1 failed / 263 passed**: OpenClaw's local service exited at API startup, before the JavaScript checks. Another local test process was starting a service concurrently; the exact startup cause was not established from the sanitized log and is not asserted to be a port collision. The unchanged isolated OpenClaw rerun passed in 20.49 seconds, and the complete final sequential group passed. The leftover database for that failed test was stopped by exact owned profile; completed temporary test data was cleaned while logs were retained.

A separate MCP recheck had **98 passed / 1 skipped**; the skipped HTTP integration requires `MEMORY_DATABASE_URL` for a dedicated test database. It is not counted as a pass. The full GitHub workflow supplies that database. An initial no-isolation build could not import `hatchling`; the standard isolated `uv build` subsequently succeeded.

Recognition is deliberately limited to documented direct opening English/Chinese commands. It is not general multilingual intent understanding, retroactive deletion, an upstream-provider privacy guarantee, or a transactional server policy. Direct HTTP/SDK observation writes and the separate durable AgentRuntime remain outside this local host policy. Same-session overlapping callbacks and stronger in-flight-write guarantees need the next architectural work.

The historical fifth acceptance remains **R4 failed / C5 invalid and unscored**. No new paid acceptance was started, and this repair does not clear release gates. Main merge, tag and publication remain blocked.

Raw local logs, including failures, are retained under [evidence/backend-recording-policy-2026-11-07](evidence/backend-recording-policy-2026-11-07).
