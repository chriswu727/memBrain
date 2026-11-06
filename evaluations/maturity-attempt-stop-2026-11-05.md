# Maturity attempt stopped: private scenario path

Attempt `maturity-20261105a` stopped as **invalid** at S1 on 2026-11-06 04:34:18 UTC (November 5 in Vancouver). S2, C1 and C2 did not run. Neither R4 nor C5 is eligible for scoring; no behavioral verdict exists. No merge, tag or release is authorized by this attempt.

The frozen candidate was `f9241471beb22d9ddaa7b1e94a35237ab8a0d601`, with runtime `cc2a60176499c97bc7423199363dbd9311452dcf`. Scenario authors and independent reviewers had completed four scenarios (257 user turns, 44 cases), with required fixes closed before execution. Real host/extractor calls and local semantic recall were enabled.

## Failure

The driver correctly passed the private nested scenario path to the runner. The validity tool subsequently reconstructed `evaluations/s1.py` from the result's scenario stem, losing its actual directory. It raised `FileNotFoundError`; the driver stopped, blocked the shared ledger and did not launch another scenario. The standalone diagnosis command had the same lookup defect. Existing driver tests substituted the validity command, while validity unit tests substituted its run loader, leaving this real boundary untested.

The original checkout, manifest, logs, replies, driver state and blocked ledger are retained unchanged. The repair was made in a separate worktree. A content-free postmortem diagnosis using the repaired path handling reports 66/66 turns in each S1 arm, with no reported harness events, empty replies or recognized error lines. This diagnosis does not resume the attempt, change its invalid state, score replies or establish memory quality. Hidden scenarios and replies remain sealed.

## Cost and shutdown

All 300 provider requests settled. Conservative ledger accounting is **23.151185 CNY**, with zero unsettled reservations. Account snapshots changed from **199.22 to 195.46 CNY**, a **3.76 CNY** difference; snapshots can include unrelated concurrent account activity and are separate from the conservative guard's accounting. No top-up, ledger reset or paid retry occurred. All four service/database ports (8893, 55533, 8894, 55534) were closed after termination. See the [safe evidence summary and hashes](maturity-attempt-stop-2026-11-05.json).

## Repair and verification

The default driver now supplies the exact manifest-bound scenario path to validity through `--scenario`. Validity and diagnosis accept that path, reject a mismatched recorded scenario identity, and retain the historical lookup when no path is supplied. Custom offline validity commands keep their existing arguments. Scenario-load failures emit only an allowlisted exception class, preventing a syntax error or exception message from exposing held-out source text.

Six initial regression cases failed before the repair. After the complete fix, the scenario-path, attempt-driver, review-pipeline and review-hardening suites pass **382 tests in 16.80 seconds**; Ruff and `git diff --check` also pass. These are offline checks with no model calls. Coverage includes a real driver-to-validity invocation on a nested path containing spaces, a manifest key different from its scenario stem, missing turns, mismatched identities, degradation events, empty-run diagnosis, legacy lookup and malformed arguments. An independent reviewer reproduced a source-disclosure issue with synthetic data; the final fix closes it for both commands, with regressions for syntax errors, runtime exceptions and `SystemExit`. The reviewer reported no remaining scoped findings.

The candidate's previous runtime/installation/performance evidence remains source-specific. This tooling repair has no runtime changes. A fresh paid attempt needs its own approval, frozen inputs and new held-out scenarios; the stopped ledger and output directories must never be reused.

## CI closeout (November 6)

Repair source `b419c34ee8cf1d3b2dba9ef40ef5069e535c305c` passes [Verify 42163852124](https://github.com/chriswu727/memBrain/actions/runs/42163852124): **7,553 Python tests, zero skips**, 50 TypeScript tests, strict types, Ruff, wheel and source archive builds. The full Python run took 1,789.68 seconds and retained three multiprocessing `fork()` deprecation warnings. The full job log, rather than the CLI's incomplete cached log, supplies these totals; its hash is in the evidence summary.

[Native qualification 42163852169](https://github.com/chriswu727/memBrain/actions/runs/42163852169) passes all five platform jobs. Two separate optional Linux compatibility jobs were not selected in this invocation and are recorded as skipped; they are not claimed as newly exercised. This completes engineering CI for the tooling repair. The original behavioral attempt remains invalid, and the published runtime pin, installation evidence and reference performance measurements are unchanged.

## Complete path rehearsal (November 6)

On the same repaired source, the unchanged public practice scenario was copied into a private nested directory and executed through the actual default attempt driver, shell supervisor, P/E/F harnesses and validity command. No runner or validity override was used. Local pinned embedding files were supplied; host and extractor used deterministic stubs, and the harness prohibited non-loopback connections. The attempt completed with strict validity and all **250 practice checks passing**, including persona proposals, feelings, mood, relationship controls, deletion, recording controls and scenario clock. All four ports were closed. [Frozen inputs and compressed public evidence](evidence/maturity-path-rehearsal-2026-11-06/manifest.json) are retained, with every gzip payload hash/round-trip checked.

This closes the missing default-driver/supervisor integration check with a nested scenario path. The driver explicitly labels it `offline_test_only`; its procedural eligibility flag is not a C5 behavioral pass. No paid request or subscription-backed reviewer was used. The stopped real attempt remains sealed and invalid.
