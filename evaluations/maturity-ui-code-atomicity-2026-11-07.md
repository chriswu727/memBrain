# Memory-page sign-in concurrency

Runtime `4115e90c24eb1eb09857624a01db8bd3b22bfe50` serializes issuing and consuming memory-page sign-in codes with the same existing cross-process profile lock. Both operations publish the complete code store atomically. A concurrent new link can no longer restore an already-consumed code or discard another newly issued link. Failed publication raises an error while preserving the preceding complete store; it does not report successful consumption.

The defect was reproduced with synthetic local codes on predecessor runtime `f5e265c`: a paused issuer read the store, another thread consumed a code, then the issuer restored that code when publishing its stale snapshot. The consumed code was accepted again. A first diagnostic used a macOS temporary-directory symlink and failed the profile path guard; using a direct path allowed the actual concurrency reproduction. No live credentials or user installation was involved.

Four new regressions fail before the repair and pass afterward: overlapping issue/consume, overlapping issuers, and interrupted publication for each operation. The complete related host, first-use and profile group passes **155 tests**, with no skips, including the actual embedded-service HTTP sign-in and recording-control journey. The unchanged expiry/single-use test is included. Ruff and four installation-pin/matrix guards pass. All nine launchers pin the repair.

An isolated wheel installation matches all **197 canonical runtime inputs**. Its seven focused checks pass, including the new regressions and the actual HTTP sign-in/recording-control journey. Existing test dependencies are shared; this is not a fresh dependency installation or a repeat of the full 49-check launcher qualification.

Only `host.py` changes among the 197 runtime inputs, specifically the two code-store operations. Recall, schema, database engine and 3D inputs remain byte-identical. The [predecessor installation, five-platform native and R5 results](maturity-month-qualification-2026-11-07.md) retain their recorded runtime scope; those full workloads were not rerun for this repair. This report does not assert new recall timings or behavioral acceptance.

Full Verify [42378912858](https://github.com/chriswu727/memBrain/actions/runs/42378912858) is running at launcher head `fdbc80a6bff27ca1ab57c190466021445021651e`. The repair has not been promoted to integration. R4 remains failed, C5 incomplete and final review open; no main merge, tag, publication or new paid/subscription evaluation is authorized by these checks.

Build: `09051895b947ff192b1c277af3ca5fc2f5ac7f3d3021be66cb751201cf8f57b8`. Schema: `478061ac77337fd25d87174df1185ab1d40ad4d4216290078fb26fd2f519fe39`. Wheel SHA-256: `d82c2ad0f544c806e35598723b23e39a31dcc2cc41274b09ac8081676bbb52be`. [Checksummed evidence](evidence/maturity-ui-code-atomicity-2026-11-07/manifest.json) includes the baseline failures, successful results, package parity and runtime-scope comparison.
