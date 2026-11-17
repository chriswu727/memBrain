# Billing-review fixes: report (2026-11-17)

## Branch and commit

- **Worktree:** `/home/yichen/src/memBrain/.claude/worktrees/agent-a2f074721ca3903e8`, branch `worktree-agent-a2f074721ca3903e8`.
- **Base:** `integration/maturity-candidate` at `e82ad9d6`; I reset the worktree to it first.
- **Commit:** one commit, `3b3c32ef` "Fix the billing review's findings on the provider-interruption retry". Not pushed. The commit went through, so I wrote no patch file.
- **Scope:** files under `evaluations/` and `tests/` only. Nothing under `src/` changed.

Files changed:
- `evaluations/evaluation_budget.py`, `evaluations/c5-harness.py`, `evaluations/acceptance_review.py`, `evaluations/acceptance-attempt-driver.py`
- `evaluations/evaluation-billing.md`, `evaluations/c5-harness.md`, `evaluations/acceptance-attempt-driver.md`, `evaluations/maturity-c5-execution-DRAFT.md`
- `tests/test_evaluation_billing_guard.py`, `tests/test_provider_interruption_retry.py`, `tests/test_c5_harness_hardening.py`, `tests/test_acceptance_attempt_driver.py`
- new: `tests/test_billing_review_fixes.py`

I made no model call, sent nothing to any provider, used no key, and did not touch `c5-attempt1/`, `c5-attempt2/`, `r4-attempt6/` or `r4-attempt7/`.

## Findings: what I did and where

**F1. A complete 2xx body with no billing JSON is now an interruption.**
- New guard function `evaluation_budget.incomplete_body(content)` classifies the body:
  - `blank`: only whitespace or empty lines, including an empty body;
  - `not_json`: does not parse (also covers `RecursionError` from very deep nesting);
  - `no_usage`: JSON with no `usage` key, including an error object or a value that is not an object.
- `_settle` returns that reason instead of settling. `handle_request` then calls `_interrupted` with `{"kind": "provider_incomplete_body", "http_status": <2xx>, "body": <reason>}`. The request is charged at its bound, the ledger stays open, and `ProviderInterrupted` is raised. The harness retries it like any other interruption, and after the third send it blocks the ledger with this kind.
- Still fatal: usage that is present but null, empty, inconsistent, malformed or above the context; `completion_tokens > max_tokens`; an unexpected or missing response model when usage is present.
- New constants in the guard: `INCOMPLETE_BODIES` and `INTERRUPTED_KINDS`, plus `interruption_code()`, which gives one fixed code per cause: the class name, `http_<status>` or `body_<reason>`.
- The kind is in every allowlist:
  - validity's line parser (`_interruption_cause`);
  - `diagnose`'s log-code list (`INTERRUPTION_LOG_CODES`);
  - the harness's log line, which now delegates to the guard's `interruption_code`.
- One test checks that all of these agree: the guard's and the review's constant sets are equal, and the codes the harness can log equal `INTERRUPTION_LOG_CODES` and equal what the validity parser and the ledger check accept.

**F3. Only HTTP 429, 500, 502, 503 and 504 are retried.**
- `retriable_status` now tests membership in `RETRIED_STATUSES`. Any other 5xx is fatal, as is a body cut short after one.
- Validity's line parser accepts only those five statuses.

**F4. Ledger entries and interruption lines can now be lined up.**
- **Ledger entries** gain:
  - `seq`: computed under the lock as `1 + max(number of entries, highest seq)`, so it increases in reservation order across all processes sharing the ledger;
  - `reserved_at`;
  - `settled_at`: epoch seconds rounded to milliseconds, written on a success, on an interrupted bound, and on a retained failure.
- **Interruption lines** move to `INTERRUPTION_FORMAT` 2 and gain `request_bytes`, taken from the guard's ledger entry via `ProviderInterrupted.request_bytes`.
- **New check:** `acceptance_review.ledger_check(ledger, run_dirs, after_seq)`, also available as the command `acceptance_review.py ledger-check --ledger L --after-seq N RUN_DIR...`, which exits 1 on a mismatch.
  - It compares the multiset of `(code, request_bytes)` from the ledger's interrupted entries with `seq > N` against the run directories' lines.
  - It reports counts per code on both sides, `only_in_ledger` and `only_in_lines`, and a "harness defect" problem. Its output is codes, counts and sizes only.
- **Driver:** whenever it has a ledger and uses the default validity (always in live mode), `acceptance-attempt-driver.py`:
  - records `ledger_seq_before`, the highest `seq` before the runner starts;
  - runs the check after validity, logging to `driver-logs/KEY.ledger-check.log`;
  - records `ledger_check_exit` and `ledger_check_finished_at`.
  - A non-zero exit gives status `invalid` and stop reason `invalid` (detail: "the ledger check exited N … a harness defect"), so the live shared stop runs. Offline runs with their own `--validity` run no check.
- **Older ledgers:** the ledger `version` stays 1 and the policy hash is unchanged, because the fields only add. What happens with an older ledger:
  - the guard numbers new reservations after the existing entries, so numbers never repeat;
  - an older guard ignores the new fields;
  - the ledger check refuses any entry without `seq` ("cannot be checked"), so a scenario run against an older ledger becomes invalid. That fails closed, and a new attempt always gets a new ledger anyway.

**F5. Texts.**
- **`maturity-c5-execution-DRAFT.md`, Billing:**
  - the review's formula, with the per-send figures recomputed from code and policy (below);
  - the absolute maximum, 9.879552 CNY;
  - three bounds for a host call that fails on all three sends;
  - the headroom effect, ending with `reservation_limit`;
  - the 1.6× figure, now explained (59.945984 / 37) and qualified for interruptions.
- **Same file, Stop rules:** the new kinds, the retried statuses, what stays fatal, three bounds, and `reservation_limit`.
- **`evaluation-billing.md`:**
  - the old "host and extractor transports" sentence is corrected;
  - the three interruption kinds are listed with the provider's empty-lines and 10-minute wording, as the review quotes it;
  - "rendered as sent" is now labelled an assumption: not documented, and the published template is V3-style;
  - the schema argument is rewritten. Escaping alone does not cover pretty-printing. The real reasons are whitespace merging (the review measured 5,000 spaces as 40 tokens) and the body being counted twice.
  - F2's exact documentation wording and the repository evidence;
  - recomputed charges, the ledger fields and version handling, the ledger check, and the F7 handler.

**F6. Delay per session.**
- Interruption lines gain:
  - `send_seconds`: the failed send's monotonic duration;
  - `wait_seconds`: 30 or 120 when retried, otherwise 0. Validity checks this against the send number.
- Validity's `provider_interruptions` per run directory gains:
  - `delay_seconds` in all;
  - `delay_by_session`, a list of `{session index, seconds}`;
  - `delay_seconds` on each `at` entry.
- `diagnose` prints "interruption delay (failed sends plus waits; in P on the scenario clock): X s in all; session i of n: Y s".
- This is a count only; it never invalidates a run. The draft's Limits section asks the record to name the affected sessions.

**F7. The signal handler no longer deadlocks.**
- `evaluation_budget._locked` raises a thread-local depth before asking for the lock and lowers it only after the lock file is closed. `lock_held()` reports it.
- The harness's `interrupted()` calls `BILLING.stop()` only when `lock_held()` is false; it always raises `SystemExit(128+signum)`. While the lock is held or awaited, the request in flight keeps its full reservation. The run script's `--stop`, which runs from another process on any nonzero arm exit, blocks the ledger.
- Why this cannot deadlock: the signal handler runs in the main thread. Inside a guarded section it never calls `flock`, so it cannot wait for its own process. Outside one, the main thread holds no lock.
- One case still blocks: another process holds the lock while the handler calls `stop()`. That wait ends when the other process releases the lock, so it is not a deadlock.

**F2:** no code change. The text change is under F5.

## Recomputed cost figures (from `evaluation_budget.py` and the 2026-11-14 policy)

Rates: 9 CNY and 27 CNY per million tokens, which is 9 and 27 micro-CNY per token. `max_tokens` is 16,384. The bound in micro-CNY is `min(1,048,576, 2b + 4s + 16,384) × 9 + 16,384 × 27`, where b is the body bytes and s the schema bytes.

| Item | Arithmetic | Result |
| --- | --- | --- |
| Fixed part | 16,384 × 27 = 442,368 (output); 16,384 × 9 = 147,456 (allowance) | 589,824 µCNY ≈ 0.59 CNY |
| Per byte of body | 2 × 9 = 18 µCNY | 0.018 CNY per KB of 1,000 bytes |
| Per byte of schema | 4 × 9 = 36 µCNY | — |
| `P`'s schemas | 14 tools, 16,425 bytes in shortest JSON at `e82ad9d6` × 36 | 591,300 µCNY ≈ 0.59 CNY |

The schema size was measured offline with `create_server(...).list_tools()` and no service, using `/tmp/claude-1000/-home-yichen-src-memBrain/28b99b83-ddec-55d7-af95-9d2753217c08/scratchpad/schema_size.py`. The earlier figure of 17,217 is the character count with spaced separators; 17,217 × 36 = 0.62 CNY, the review's figure. The httpx body also uses compact separators, so the schemas take 16,425 bytes in the body too.

Examples:

| Request | Arithmetic | Charge |
| --- | --- | --- |
| 40 KB body, no tools | 0.589824 + 0.72 | 1.309824 ≈ 1.31 CNY |
| 40 KB `P` body with the schemas | 0.589824 + 0.72 + 0.5913 | 1.901124 ≈ 1.90 CNY |
| 150 KB body | 0.589824 + 2.7 | 3.289824 ≈ 3.29 CNY |

- **Absolute maximum:** 1,048,576 × 9 + 442,368 = 9,879,552 µCNY = 9.879552 CNY.
  - Without tools it is reached when 2b + 16,384 ≥ 1,048,576, so b ≥ 516,096 bytes.
  - With `P`'s schemas, 2b ≥ 1,048,576 − 16,384 − 65,700, so b ≥ 483,246 bytes.
- **A host call that fails on all three sends:** three bounds. At 150 KB that is 3 × 3.289824 = 9.87 CNY; at most 3 × 9.879552 = 29.638656 CNY.
- **Refusal point:** a reservation is 1,048,576 × 9 + 393,216 × 27 = 9,437,184 + 10,616,832 = 20,054,016 µCNY. The guard refuses once settled charges exceed 80 − 20.054016 = 59.945984 CNY.
- **Free headroom** at the expected 30–50 CNY: 59.945984 − 50 = 9.945984 and 59.945984 − 30 = 29.945984, so about 10 to 30 CNY.
  - At 3.3 CNY per interruption: 9.95 / 3.3 ≈ 3.0, so about 3 at the top of the range; 29.95 / 3.3 ≈ 9.1, so about 9; 22.95 / 3.3 ≈ 6.95, so about 6 at the 37 CNY point estimate.
  - Running out ends the attempt with `reservation_limit`.
- **F2 exposure, if reasoning is not counted against `max_tokens`:** (393,216 − 16,384) × 27 = 10,174,464 µCNY = 10.174464 CNY per send.
- **The rejected alternative of charging `max_output_tokens`:** at least 10.616832 CNY on the output side, about 11.1–13.5 CNY in all. At most two interruptions would fit, and none at the top of the range. I corrected the review's "one to three" to this in `evaluation-billing.md`.

## What the harness sends of `reasoning_content` today

- **`P`, within one turn's rounds:** each assistant message with tool calls is appended with `role`, `content`, `tool_calls` and `reasoning_content` (`c5-harness.py`, the `messages.append` after `check_billing()` in the round loop). Later rounds of the same turn therefore get the earlier rounds' reasoning.
- **`P`, earlier turns of the same session:** each turn goes into `current` as its transcript with `reasoning_content` removed (`transcript = [{k: v … if k != "reasoning_content"}]`). That covers the tool-call messages and tool results, plus the final reply as `{"role": "assistant", "content": …}` with no reasoning. So every later turn's requests, which offer `tools` in rounds 1 to 3, carry earlier assistant messages without reasoning.
- **`P`, earlier sessions:** never sent. `current` is new for each session.
- **`F`:** `schemas` is None, so `F` is never offered tools. Its history (`Reference.history`) holds only user text and replies, with no tool calls and no reasoning. The rule does not apply to `F`.
- **Not stored anywhere:** neither `host-rounds.jsonl` nor the results rows keep reasoning.
- **Exposure:** if the provider enforces the rule, the first 400 comes at `P`'s first request after a turn with a tool call. If the rule covers every earlier assistant message, it comes at a session's second turn. That is early in the first scenario. A 400 is fatal: the request keeps its whole reservation, the ledger is blocked, and the attempt is invalid.
- **Where it is stated:** the draft binding's Stop rules and Limits, a new bullet in `c5-harness.md` (Harness events, stops and the log), and the harness module docstring. Nothing sent was changed.

## New formats

- **Ledger entry** (version 1, additive): `seq`, `reserved_at`, `model`, `max_tokens`, `reserved_micros`, `request_bytes`, `tools_bytes`, then `settled_at` together with one of:
  - `actual_micros`, `prompt_tokens`, `completion_tokens`;
  - `actual_micros` and `interrupted`;
  - `failure`.
- **`interrupted` / `failure` cause:** `provider_transport` with `error_class`; `provider_http_status` with `http_status`; or `provider_incomplete_body` with `http_status` (2xx) and `body` (`blank`, `not_json` or `no_usage`).
- **`provider-interruptions.jsonl`, format 2:** `format`, `time`, `session`, `turn`, `round`, `kind`, the cause (`error_class`; `http_status`; or `http_status` and `body`), `request_bytes`, `send_seconds`, `wait_seconds`, `send`, `retried`. Format 1 is refused as malformed. Only the stub practice ran the format-1 harness, and the stub never interrupts, so no format-1 file exists in any live run.
- **Log code:** `provider interrupted body_<reason> …` is added.
- **Validity `provider_interruptions[run]`:** `interrupted_sends`, `retried_host_calls`, `not_retried`, `delay_seconds`, `delay_by_session: [{"session", "seconds"}]`, and `at[]` entries that each now carry `delay_seconds`.
- **`ledger-check` output (format 1):** `format`, `valid`, `problems`, `after_seq`, `ledger_highest_seq`, `ledger_interrupted` (code → count), `interruption_lines` (code → count), `only_in_ledger` and `only_in_lines` (each `[{code, request_bytes}]`).
- **Driver state, per scenario:** `ledger_seq_before`, `ledger_check_finished_at`, `ledger_check_exit`. The driver version is unchanged, and `acceptance-attempt-driver.md` is updated.

## Existing tests changed, and why

**`tests/test_evaluation_billing_guard.py`**
- `test_provider_failures_never_release_money_for_an_automatic_retry`: `malformed` (a 200 that is not JSON) is now an interruption, so I replaced it with `inconsistent` usage, and added `http_501`, now fatal.
- `test_provider_stop_records_safe_cause_without_releasing_reservation`: `malformed` became `malformed_usage` (usage present, with a string token count), for the same reason.

**`tests/test_provider_interruption_retry.py`**
- `Provider`: new `inconsistent` failure.
- `test_a_timeout_then_success…`: the line's key set and its expected values now use format 2 (`request_bytes`, `send_seconds`, `wait_seconds`).
- `test_other_failures_keep…`: `malformed` replaced by `inconsistent`; added 501, 505 and 599, plus a body cut short after a 501.
- `test_the_guard_settles_each_interruption…`: dropped 599, now fatal; added `malformed`, now `provider_incomplete_body` `not_json`.
- `line()` helper: writes format 2.
- `test_validity_reports_retried_interruptions…`: expects the delay fields.
- `test_validity_refuses_malformed_interruption_evidence`: the old `format: 2` variant became `format: 1`. Added variants: 501, an unknown body reason, `body` with a 503, `request_bytes` missing, `request_bytes` 0, negative `send_seconds`, a wrong wait, and a wait after the last send.
- `test_diagnose_prints…`: expects the delay line.
- `test_the_review_and_the_guard_agree…`: extended to statuses, bodies, kinds, waits, format and the full code-set equality.

**`tests/test_c5_harness_hardening.py`**
- `test_a_live_arm_retries_a_transient_provider_failure…`: added assertions for `request_bytes` on the line, the sequence numbers 1 to 5, and the real `ledger_check` passing end to end.

**`tests/test_acceptance_attempt_driver.py`**
- The fake `VALIDITY` now answers `ledger-check`, recording its arguments and failing for keys in `ledger_mismatch`.
- The fake `RUNNER` can add sequenced ledger entries (`reserve`).
- Three new tests: the live check runs with the correct `--after-seq` (0, 3, 5, 5); a mismatch gives `invalid` plus the shared stop; an offline run with its own `--validity` runs no check.

**New file `tests/test_billing_review_fixes.py` (33 tests):**
- six 2xx bodies without billing JSON (blank lines, empty, truncated, text, error object, list), each then a success;
- three incomplete bodies in a row blocking the ledger;
- eight present-but-wrong usage cases staying fatal;
- the reason classifier, including deep nesting;
- 502 retried and 501 fatal; the retried-status set;
- `seq` and times under two forked processes sharing a ledger;
- an older ledger without `seq`: numbering after its entries, and the check refusing it;
- the ledger check passing, with the command exiting 0;
- four damage variants failing, with the command exiting 1;
- the `after_seq` window;
- unusable input and usage errors;
- the delay per session from real `Host` lines through validity and `diagnose`;
- F7: a SIGTERM inside `_reserve`'s lock exits promptly with the ledger untouched, and `--stop` then works;
- a control proving the old behaviour hangs (killed at 3 s);
- a SIGTERM while waiting for a lock another process holds exits without waiting;
- a SIGTERM outside a guarded section still blocks the ledger with `arm_interrupted`;
- `lock_held` nesting.

## Test runs

**Before the lock.** These files use only fakes and subprocess fakes: no service and no database. I had read all of them.
- `test_evaluation_billing_guard` plus `test_provider_interruption_retry`: 137 passed.
- `test_billing_review_fixes`: 33 passed. The first version of one F7 test hung: the child took the lock before the parent did, which was a test-ordering bug. I fixed it before the counted runs.
- `test_acceptance_attempt_driver`: 155 passed.

**Under the lock, `focused-1`, uncommitted tree with the content identical to `3b3c32ef`:** **1086 passed, 0 failed**, 699.8 s, database stopped.

| File | Passed |
| --- | --- |
| `test_acceptance_attempt_driver` | 155 |
| `test_acceptance_kit` | 71 |
| `test_acceptance_kit_novelty` | 4 |
| `test_acceptance_review_hardening` | 157 |
| `test_acceptance_review_pipeline` | 128 |
| `test_acceptance_scenario_path` | 18 |
| `test_billing_review_fixes` | 33 |
| `test_c5_companion_validity` | 20 |
| `test_c5_converge` | 70 |
| `test_c5_harness` | 56 |
| `test_c5_harness_hardening` | 80 |
| `test_c5_kit` | 77 |
| `test_c5_proposal_selection` | 7 |
| `test_c5_review_fixes` | 40 |
| `test_c5_supervisor` | 7 |
| `test_companion_acceptance` | 26 |
| `test_evaluation_billing_guard` | 57 |
| `test_provider_interruption_retry` | 80 |

- **Checks:** `ruff check` on all changed Python files passed, and `git diff --check` is clean.
- **Logs:** `/home/yichen/.local/state/membrain-setup/runs/billing-fixes-20261117/focused-1.log` and `focused-1-junit.xml`.

## Rehearsals (committed tree `3b3c32ef`, under the lock)

Both exited 0.

| Rehearsal | Driver | Validity | Ledger check | Ledger | Network and ports |
| --- | --- | --- | --- | --- | --- |
| `c5-stub-rehearsal.py` | complete, C5 eligible | both scenarios valid: 16 page actions per arm, 14 done and 2 not applicable; persona mirroring 34 of 34 | ran on the real code: valid, 0 interruptions (`driver-logs/c1.ledger-check.log`) | unchanged, 0 requests | 0 network events; ports closed |
| `r4-stub-rehearsal.py` | complete, R4 eligible | valid; dry-run checks 179 of 179 per scenario | — | unchanged, 0 requests | — |

The rehearsals cannot exercise an interruption, because the stub has no guard. Logs are `c5-rehearsal.log` and `r4-rehearsal.log` in the same folder.

**Cleanup:**
- I removed `focused-1/database`, `focused-1/.agent-memory-recovery` and `focused-1/pytest`, after checking each was under my run root.
- The rehearsals had already deleted their own synthetic databases. 4.1 MB of logs and evidence remain.
- I removed my scratch pytest temp directories, released the lock, and left no test process running.

## Disagreements and limits

- **Alternative's headroom count:** the review says the `max_output_tokens` alternative would let "one to three" interruptions fit. Recomputed, it is at most two, and none at the top of the range. The text says that.
- **Schema size:** the review's 0.62 CNY schema term rests on 17,217 characters. The shortest-JSON bytes that the guard uses are 16,425, giving 0.59 CNY. The texts say "about 0.59–0.62".
- **Ledger check:** it matches by `(code, request_bytes)` as briefed, not by an exact `seq` on each line. Writing `seq` into the line would make the pairing exact; I did not add it, to stay within the brief.
- **Older ledgers:** they fail the ledger check rather than being skipped. I chose to fail closed; such a ledger cannot be audited.
- **Format-1 interruption lines:** now refused as malformed. No live run used the format-1 harness.
- **Unverified claims carried from the review:** I did not re-verify the provider documentation's wording or the statement that past runs got no 400. Both are cited as the review's.
- **Reasoning unchanged:** as instructed, nothing sent was changed for `reasoning_content`.
