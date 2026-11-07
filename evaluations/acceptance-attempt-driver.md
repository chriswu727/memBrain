# Acceptance attempt driver

[`acceptance-attempt-driver.py`](acceptance-attempt-driver.py) turns the paid plan's prose run rules into checks: the run order, no new scenario after a failed or invalid one, every input frozen by hash and checked before each scenario, and scenario keys bound to gates. Offline tests use synthetic files, including a real validity CLI check with a fake runner; they make no model calls. Live execution needs separate approval. The first approved maturity attempt [stopped on a scenario-path defect](maturity-attempt-stop-2026-11-05.md); it is not accepted behavioral evidence.

```
python3 evaluations/acceptance-attempt-driver.py run --manifest M --out OUT_ROOT
    [--repo ROOT] [--runner CMD] [--validity CMD] [--ledger LEDGER] [--grace SECONDS] [--live]
```

The runner defaults to `evaluations/c5-run-scenario.sh` and is called as `RUNNER SCENARIO OUT_ROOT KEY`, with an absolute scenario path and `OUT_ROOT`. The validity check defaults to `python evaluations/acceptance_review.py validity`, using the driver's own interpreter, and receives `--scenario SCENARIO OUT_ROOT/KEY-P OUT_ROOT/KEY-E OUT_ROOT/KEY-F`. This is the same absolute, manifest-bound scenario path the runner receives, including private subdirectories. Offline custom validity commands still receive only the three run directories. Both run with the repository as their working directory and inherit the environment. Their output goes only to `OUT_ROOT/driver-logs/KEY.runner.log` and `KEY.validity.log`. `--grace` must be a finite number of seconds above 0 and at most 600; anything else, including NaN or infinity, is refused.

For diagnosis, `acceptance_review.py diagnose --scenario SCENARIO RUN_DIR...` uses the explicit scenario for turn positions without printing its content. Direct validity/diagnose commands without `--scenario` retain the historical `evaluations/<scenario>.py` lookup. An explicit path must match the result rows' scenario stem. A tooling repair never resumes a stopped attempt or converts its original invalid result into accepted evidence.

## Live mode

Live mode is on with `--live`, and whenever `C5_BILLING_LEDGER`, `C5_ATTEMPT_ID` or any provider credential (any `*_API_KEY` variable, even an empty one) is set. Without it, the driver is for offline tests only, which must clear such keys. A credential makes the run live instead of being refused separately. That way one rule covers every case where a provider call is possible: the full binding is required and overrides are refused.

| | Live mode | Offline (tests) |
| --- | --- | --- |
| Commands | Only the repository's `evaluations/c5-run-scenario.sh` and `<this python> evaluations/acceptance_review.py validity`; `--runner` and `--validity` are refused | Overrides allowed |
| Frozen command files | `evaluations/c5-run-scenario.sh`, `evaluations/acceptance_review.py` and `evaluations/c5-harness.py` must be in `files` | Any command file inside the repository must be in `files` |
| Ledger | `C5_BILLING_LEDGER`, required and absolute; a different `--ledger` is refused | Only with `--ledger` |
| Attempt binding | `C5_ATTEMPT_ID` required and equal to `attempt_id` (`attempt_binding`) | None |
| Policy binding | `C5_BILLING_POLICY_SHA256` required, 64 lowercase hex characters (`policy_binding`), and equal to the ledger's `policy_sha256` | None |
| Marked in the state file and summary as | `"mode": "live"`, `"evidence": "live_attempt"` | `"mode": "offline"`, `"evidence": "offline_test_only"` |
| Shared stop | Yes, see below | Never |

Wherever a ledger is read, before the start and before each scenario, it must hold `"blocked": false` and a `run_id` equal to `attempt_id`. When `C5_BILLING_POLICY_SHA256` is set, which is always in live mode, its `policy_sha256` must match too. Otherwise the attempt stops with `ledger_blocked` or `ledger_mismatch`.

**Shared stop.** On a stop the driver decides itself (`invalid`, `hash_mismatch`, which includes `inputs_changed`, `run_dir_exists` or `driver_error`), it blocks the shared billing run for every future provider call. It runs the harness's own entry point, `<C5_PYTHON or uv run python> evaluations/c5-harness.py --stop --reason CODE`, as the run script's supervisor does. CODE is the driver's own cause, so the ledger keeps it; the first recorded reason wins. The cause is `inputs_changed` when the stopped scenario's inputs changed while it ran, and otherwise the stop reason. If that call fails, as with an older harness that accepts only a bare `--stop`, the driver retries once without `--reason`. The ledger then records `arm_failed`, unless it already has a reason, and the state file records `reason_passed: false`. A signal does not cut either call short; after 300 s each is killed and recorded as failed. The driver never writes the ledger itself, and a failed stop is reported on stderr.

The driver adds no shared stop for `runner_failed`, because the supervisor blocks the ledger itself once any arm has started. Nor does it add one for `ledger_blocked`, `ledger_mismatch` or `interrupted`, or for any refusal before the first scenario.

## Manifest

This is the format shared with `acceptance_review.py`. Until that file's `load_manifest` is on this branch, the driver validates it locally, accepting and rejecting exactly the same manifests. A test compares the two validators once both are present.

```json
{"version": 1, "attempt_id": "...",
 "files": {"<repo-relative path>": "<sha256>"},
 "pairs": [{"gate": "R4", "scenarios": [{"key": "<key>", "path": "<repo-relative scenario path>", "sha256": "<sha256>"}]},
           {"gate": "C5", "scenarios": [{"key": "<key>", "path": "...", "sha256": "..."}]}],
 "order": ["<key>"]}
```

The driver checks the structure:
- Each object has exactly these keys.
- `version` is the integer 1, and `attempt_id` is a string that is not blank.
- Paths are normalised and repo-relative. They contain no `..`, and before any hashing they may not resolve outside the repository, even through a symlink.
- Each sha256 is lowercase hex.
- Each gate is `R4` or `C5` and has at most one pair, and each pair has at least one scenario.
- Keys match `[A-Za-z0-9][A-Za-z0-9_-]{0,63}`.
- Scenario paths end in `.py`, and keys, paths and file stems are unique.
- A scenario that is also listed in `files` has the same hash there.
- `order` names every key exactly once.

No scenario name is built in.

The driver also refuses:
- a runner or validity command that names a file inside the repository the manifest does not freeze;
- the driver itself, when it lives in the repository and is not frozen;
- a `C5_ATTEMPT_ID` that differs from `attempt_id`;
- a `--ledger` that differs from `C5_BILLING_LEDGER`.

## Order of work

1. **Before anything.** The driver validates the manifest, verifies the hash of the manifest file, every `files` entry and every scenario, and reads the ledger flag. It refuses when `OUT_ROOT` already has `attempt-state.json`, whether for this attempt or another, because it never overwrites, resumes or reuses one. It also refuses when any `KEY-P/E/F` directory exists. Then it creates the state file exclusively. Exit code 2 means nothing ran.
2. **Each key in `order`.** The driver first reads the ledger flag, re-verifies every hash and refuses an existing run directory. Then it runs the runner. A non-zero exit is `runner_failed`, which covers the supervisor's exits after a failed or refused arm, a port wait and a preflight. On a zero exit, it runs validity on the three directories, and a non-zero exit is `invalid`. Last, it re-verifies every hash; an input that changed while the scenario ran makes it `inputs_changed`. If any step fails, it stops. It never starts another scenario and never retries.
3. **Pairs.** A pair is `complete` when all its scenarios are `valid`. It stays complete whatever happens later. At the end, a pair with any started scenario that is not complete is `incomplete`, and a pair with none started is `not_run`. `eligible` lists the gates whose pair is complete. The driver never decides R4 or C5.

The driver only reads the ledger. Anything other than an explicit `"blocked": false` stops the attempt, and that includes a missing, malformed or unreadable ledger. The harness's guard and its `--stop` entry point write `blocked`.

**Signals.** On SIGINT or SIGTERM, the driver first sends SIGTERM to the runner alone, so the supervisor can block the ledger before it stops its arms. If the runner is still running after `--grace` seconds (default 60), its whole process group gets SIGTERM, and after twice that, SIGKILL. Whenever a runner or validity child exits, anything left in its process group gets SIGTERM, then SIGKILL after the grace period. The driver records `interrupted` and exits with 128 plus the signal number. It polls children and never uses `wait -n`. It uses only the standard library and the macOS system Python 3.

**Exit codes.**

| Code | Meaning |
| --- | --- |
| 0 | Every scenario ran and was valid |
| 1 | Stopped |
| 2 | Refused before start |
| 130 or 143 | Interrupted |

The last line of stdout is a one-line JSON summary of statuses: `mode`, `evidence`, `attempt_id`, `result`, the `stop` reason code, the status of each scenario and each pair, and `eligible`. Progress and stop details go to stderr. They name paths, keys and exit codes only.

## State file

`OUT_ROOT/attempt-state.json` is written to a temporary file, then fsynced and moved into place with `os.replace`. It holds:
- the attempt: `driver_state_version`, `mode`, `evidence`, `attempt_id`, `manifest` (path), `manifest_sha256`, `repo`, `out_root`, the `runner` and `validity` argument lists, `ledger`, `created_at` and `updated_at`;
- `shared_stop`: null, or an object with these fields:
  - `reason`, the driver's stop reason, and `ledger_reason`, the code passed to `--reason`;
  - `reason_passed`: true, false after the bare-`--stop` fallback, or null when no call succeeded;
  - `command` and `exit` for the last call, and `attempts`, each call's `command`, `exit`, `started_at` and `finished_at`;
  - `started_at`, `finished_at` and `log`;
- the outcome: `result`, which is `running`, `complete`, `stopped` or `interrupted`, and `stop`, which is null or holds `key`, `reason`, `detail` and `at`;
- `order`;
- `scenarios`, one entry per key, with these fields:
  - `gate`, `path` and `status`;
  - `sha256_verified_at`;
  - `started_at`, `runner_finished_at`, `runner_exit`, `validity_finished_at` and `validity_exit`;
  - `run_dirs_created`;
  - `logs`, the paths of the driver logs and each arm's `run.log`;
- `pairs`, each with `gate`, `keys` and `status`;
- `eligible`, a boolean for each gate.

A scenario's `status` is one of these values:

| Status | Meaning |
| --- | --- |
| `pending` | Not yet reached |
| `running` | The runner is running |
| `validating` | The validity check is running |
| `valid` | Ran and passed validity |
| `runner_failed` | The runner exited non-zero |
| `invalid` | The validity check failed |
| `inputs_changed` | A frozen input changed while it ran |
| `interrupted` | Stopped by a signal |
| `not_run` | Never started |

The stop `reason` is one of `hash_mismatch`, `run_dir_exists`, `ledger_blocked`, `ledger_mismatch`, `runner_failed`, `invalid`, `interrupted` or `driver_error`. The stdout summary also has `shared_stop`: null, `blocked` or `failed`. Neither file holds scenario content, a child's output or a validity finding.

## Left to the operator

The driver deliberately does none of the following:
- **Pre-checks.** It does not check the pin, a clean `git status`, `MEMBRAIN_SRC`, the port state or leftover memBrain services before the first call.
- **Choosing the frozen files.** Apart from the three live-mode command files, it does not decide which files to freeze, such as review instructions or the runtime pin. It only enforces what the manifest lists.
- **Billing.** It does not set any `C5_*` billing variable, create the ledger or write it directly, read balances, or reconcile cost. It does not recompute the ledger's policy hash; the harness's guard does.
- **Results.** It does not decide what a stopped attempt means, re-run anything after an invalid run or a port-wait failure (use a fresh `OUT_ROOT` and the plan's rules), or run `diagnose`.
- **Scoring.** It does not run blinding, any scoring step, `gate`, or the R4 or C5 decision.
