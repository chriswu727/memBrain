# Host control reporting on Windows

Runtime commit: `fcae1678262682c867aa196b55b165891e4a3ac5`. All nine host launchers pin this runtime. Initial qualification below used `cb8b2b3d7eecc1239b4165afdb7b6e333ffdac5c`; the CI follow-up records the correction and its separate evidence. This is a module-1 delivery; it does not close the remaining backend receipt work or release gates.

## Handoff and selected delivery

The fetched integration head is `27a0ad3d396886602ce084ae7c8ab67ff55092a7`, matching the Mac handoff. PR #59 and its qualification are retained. This batch addresses host-visible control results, not a new audit of the other five modules.

| Entry | Existing authority and behavior | Selected change |
| --- | --- | --- |
| HTTP / Python / TypeScript recording API | Authoritative per-brain switch, revisioned writes | Unchanged |
| BrainRuntime / open_agent / desktop chat | Server switch; bounded temporary mode during pause | Unchanged |
| Memory page | Separate server and device controls, versioned mutations | Unchanged |
| Shared host staging / replay | Local installation/user/conversation gates and captured server revision | Preserve enforcement; distinguish current policy from cached protection in notices |
| Plugin tools / local MCP / Hermes / ChatMemory / AstrBot / OpenClaw bridge | Local mutations previously reported `recording: on` after resume even when another control still blocked recording | Return effective state and the scopes that explain it |
| Plugin status / setup | Previously inspected only the installation pause file | Read the same scoped control snapshot |
| Host finish callbacks / durable external delivery receipts | Accepted-or-queued observations and external sends have separate contracts | Unchanged; receipt normalization remains open |

The reproduced user-visible problem is local resume reporting recording on while the server is paused. A second case is resuming a user's pause while installation capture remains paused. Offline cached policy cannot establish either current on or current off. Reporting now preserves those distinctions without promoting local controls into brain-wide mutations. Low-level local helper callers remain compatible.

## Environment and verification

Windows native development uses Python 3.12.16, Node 22.23.4 and the unchanged `uv.lock`. Initial native smoke checks pass: PostgreSQL 16.15, pgvector 0.8.6, server recording enforcement and real Chromium page execution (3 tests). The owned database is stopped afterward. No model provider is used.

WSL and VirtualMachinePlatform were disabled. The requested administrator launch was cancelled by Windows before the setup script ran. WSL/Ubuntu setup therefore remains pending administrator execution and any required user-managed restart. The intended WSL storage location is on D:, with source, dependencies and test data inside the distribution's Linux filesystem. Native Windows validation is not WSL validation.

The first broader Windows batch reports 115 passed and 3 failed. The new timeline assertion omitted assistant roles, an older MCP fixture had no policy reader but expected confirmed recording, and the Hermes service encountered a PostgreSQL socket bind permission error on a reused default port. The assertions are corrected; Hermes and OpenClaw integration fixtures now request task-exclusive ephemeral ports. Those original failures are not relabelled as passes.

The TypeScript suite initially reports 50 passed/6 failed because its Python parity tests hard-coded `.venv/bin/python`. Selecting the native Windows executable exposes a default-encoding failure (55/1), followed by a CRLF record-separator mismatch (55/1). The tests now run Python in UTF-8 mode and parse either platform's line separator, preserving byte-for-byte JSON payload comparisons. All 56 tests and strict typechecking then pass. No SDK runtime behavior or dependency pin changes.

The wider host batch then reports 226 passed/2 failed, with one output-decoding warning. OpenClaw's Python test reader used the console encoding for UTF-8 Node output, hiding a real plugin JSON encoding mismatch. AstrBot's export assertion used POSIX mode bits on Windows; the export writer also bypassed the existing private-file helper. Export now applies that helper before writing content, including the protected current-user Windows ACL. The first ACL check's PowerShell module loader failed, so the test uses the installed native Windows security bindings instead; a diagnostic corrected explicit native-handle cleanup before final test collection.

Four subprocess regressions reproduce plugin hook/tool failures under ASCII and GBK. The fixed JSON writer uses UTF-8 bytes for host pipes, preserving non-ASCII text independently of console encoding. The four checks pass with 17 control-result checks (21 total). The final wheel/sdist builds pass; all 212 runtime inputs match the checkout, and the same 21 checks pass after imports are verified to resolve to the extracted wheel. The OpenClaw real-runtime follow-up passes all nine Node checks with the corrected pipe.

The final frozen Windows native batch passes **32 tests, zero failures/skips**, including all nine Node checks inside the OpenClaw integration, AstrBot's real-service journey and native export ACL, combined start/status output, recording enforcement and the new status/encoding regressions. Seven additional compatibility/export checks and two launcher-pin checks pass; the export unit's POSIX mode assertion is platform-scoped because the real Windows journey verifies its protected ACL. Ruff passes. These are scoped checks, not a full Windows suite or five-platform qualification. The PR's Verify check records the complete Linux suite separately; no full CI result is claimed here in advance.

Checksummed, path-sanitized logs and package identity are under [evidence](evidence/backend-host-control-status-2026-11-09/manifest.json). All task-owned service/database processes are stopped. Tool approval review rejected recursive removal of the stopped synthetic smoke directory with only `blocked by policy`; no alternate deletion mechanism was used. Task artifacts remain under `D:/memBrain-setup` for explicit cleanup. Real profiles, models, backups and other projects are untouched.

## CI follow-up

The first complete [Verify run](https://github.com/chriswu727/memBrain/actions/runs/42711334362), on source `19a9a364dd8404a49fd78125bce4de92483e01b2`, failed with **8,274 passed, 5 failed and 3 warnings**. Diagnostics exposed an actual regression: a control read created an empty installation. Cache reads and local control inspection now avoid creating absent directories, and reporting leaves expired control files untouched. The other four failures were two ready-client fixtures missing the recording-policy reader and two offline hooks still expecting silence instead of the new unknown-state notice. Their memory and queue assertions remain intact. This failed run is not relabelled as successful.

On the corrected runtime, 24 focused checks pass. A frozen Windows PostgreSQL batch passes **186 tests with 9 skipped**, and its owned database stops successfully. The skips are Bash-only launcher checks because Bash is absent from the native test PATH; they do not qualify WSL or those launcher paths. Checking the remaining shared-fixture consumer exposed one obsolete unknown-state assertion (10 passed/1 failed); after it checks the now-current policy, all 11 context checks pass. No service was running when runtime edits were made.

The corrected wheel/sdist build passes, all 212 runtime inputs match, and 22 checks pass with imports verified against the extracted wheel. Both launcher-pin checks and Ruff pass. Corrected-runtime results, original CI failure excerpt and package identity are in [follow-up evidence](evidence/backend-host-control-status-2026-11-09/ci-correction.json). Initial Windows/TypeScript/package evidence retains its original runtime identity. The PR requires a new complete Verify result before merge; no rerun of an unchanged failing candidate was requested.

## Cost and boundaries

User-facing pause/resume and installation status add a read of the selected brain's policy through the existing local connection and brain-selection path. Prompt/session paths reuse their existing policy read; no new database migration, model request, delivery retry or queue replay is introduced. This is not a measured recall or throughput improvement, and no comparison with Mac timings is claimed.

Control stores are sampled separately. Offline observations may remain queued under the existing capture fence; a status result cannot prove their persistence. Per-message receipt normalization, independent runtime/local control integration and full-device synchronization remain open. R4 remains failed, C5 invalid/unscored, and final publication review remains blocked. No paid/subscription acceptance, main merge, release tag, Goal or scheduled work is authorized by this batch.
