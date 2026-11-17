# First two-arm companion attempt (maturity-c5-20261117b): preparation report

Prepared and frozen on 2026-11-17, 04:58–05:27 UTC. No paid call, no API key read, no push, no PR. Nothing changed in
`/home/yichen/src/memBrain` (clean, head `4936e6bb`, before and after) or in any earlier attempt's directory.
`control/freeze-review.json` was not written.

## Frozen state

- SOURCE `4936e6bb29a7c993d756628eaebf8f59628833f7` = local head of `integration/maturity-candidate` =
  `origin/integration/maturity-candidate` (fetched) = GitHub (`git ls-remote`). Main tree clean; no test running and
  the lock free at start; 54 GB free.
- Clone `/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/clone`, branch `acceptance/maturity-c5-20261117b`.
  **Frozen head `707edc57b4173f3837fb3edd893fe323d54b4db5`**: one commit on SOURCE, the binding
  `evaluations/maturity-c5-execution-2026-11-17.md` (sha256
  `edc3cf95a810578804cc1f1b296a19a35c98159f239be6dde842b2d106ece9ed`), nothing else. Tree clean. Private root
  `evaluations/.maturity-heldout-c5-20261117b/` mode 700 with `control/` (700), git-excluded, 0 tracked files.
- **Manifest** `evaluations/.maturity-heldout-c5-20261117b/control/manifest.json` (mode 600): sha256
  **`352f959bec58f2176ecfe6bccadddfb50c08b5089f7b008318bba6356310b980`**, **446 files** (439 tracked + 7 private: the
  allowed-models file, two assignments, two receipts, two scenarios). **Persona `esfp`** (seed
  `maturity-c5-20261117b`). **Order `c1`, `c2`**. One pair, gate `C5`, no practice mark. I re-hashed all 446 entries:
  0 mismatches. `freeze.py --gate C5` with `--binding`, `--allowed-models` and both `--assignment`: exit 0, stderr
  empty, `coverage_items` 7 + 6.
- `control/preparation.json`: sha256 `b1985dd6f44a5090564f6193e0e9ef172f60451d47639e1da551238d6151a255`, mode 600.
  The run script's `head` and `manifest_sha256` reads return the frozen values.
- Ports 8893 and 55533 free and bindable. 57.1 GB free. No ledger, no `runs/`. No process belongs to the attempt; the
  only memBrain-named processes are the owner's remote-control session.

## Measured on this source (decision 5)

- **Build and schema** (`membrain.build_identity` in the clone): build
  `6200f1e1452f6dc3080b4194f593492bff2a4fb7ebc17a11bf7c6b37c0d2ae8a`, schema
  `3a94d7b6ea6bfba8ff8a4d920aa83001123922f4f90b0a9d6430ef1997b6166d`.
- **Launcher pin.** All 9 launchers pin runtime `ef0e87276242595672c73a8558a0d905d50b712d` (pin commit `0b1c052d`).
  - `ef0e8727` and `55a88f1f` are ancestors of SOURCE, of `0b1c052d` and of the runtime pin.
  - `src/`, `migrations/` and `plugins/` are identical between `0b1c052d` and SOURCE; `src/` and `migrations/` also
    between `ef0e8727` and SOURCE.
  - So the clone's `src/` and the pin both contain both fixes.
- **Interpreter.** `uv sync --frozen`, uv 0.13.6, 79 packages, no system site-packages. CPython 3.12.16, binary
  `23bc148d…82b5`. `uv.lock` `0bc566ca…7e92`. ONNX Runtime 1.31.1. Embedding `model_quantized.onnx` `f80102d3…c193` and
  `tokenizer.json` `0b44a9d7…4c39`. Claude Code 2.1.322.
- **Tools offered to `P`** (both rehearsals' `tools.json`): 14 tools (the seventh attempt's names and order), 17,217
  characters of schemas, skill not in the prompt.
- **Server instructions:** 1,382 characters, sha256 `fc7492b4032558baf9b37ba778e08637a1bb40014114fbd9640f1f578ab8dc63`
  (measured directly and in the rehearsal).
- **Kit sha256:**

  | File | sha256 |
  | --- | --- |
  | `launch.py` | `da046e8a…c68e` |
  | `freeze.py` | `75848141…7ce2` |
  | `novelty.py` | `22e86044…b449` |
  | `assignment.py` | `529ce840…9193` |
  | `session-commands.json` | `906a3964…edc4` |
  | `c5-author-brief.md` | `d4ff7211…ee3f` |
  | `c5-reviewer-brief.md` | `174e8ed2…b701` |
  | `c5-verifier-brief.md` | `d6d42ac1…9ce1` |
  | `c5-fixer-brief.md` | `440ad821…066b` |
  | `c5-precheck.py` | `e77b6e50…b1f1` |
  | draft binding | `66f52128…03ca` |

  The full values are in the binding and in `preparation.json`.
- **Policy** `e7b91106…689f` (unchanged):
  - `deepseek-v4-pro` only, 80 CNY, 1 request in flight, 9/27 CNY per million, bounds 1,048,576/393,216 tokens;
  - each request reserves 9.437184 + 10.616832 = 20.054016 CNY;
  - the guard refuses once settled charges exceed 59.945984 CNY.
- **Cost estimate:** 124 turns (61 + 63) at 0.232 CNY per scenario-turn come to about 29 CNY on the guard's count.
  With the 25% uplift it is about 36 CNY (plausible 30–50), with about 1.7× headroom.

## Control files

| File | sha256 | Notes |
| --- | --- | --- |
| `control/allowed-models.json` | `1a1e8da4…eaf4` | `["sonnet"]`, byte-identical to the seventh attempt's |
| `control/c1-assignment.md` | `e0e6ecfb…c81e` | Prefix `C1`, English, one German session, 11 cases, 60–66 messages, at least 45 days, scenario-one items |
| `control/c2-assignment.md` | `dabfc500…809f` | Prefix `C2`, Chinese, one English session, the same size, scenario-two items |

- Both assignments copy the shape of the d2 diagnostic's assignment, with the coverage lines exactly as the brief
  gives them.
- `assignment.py` parses both.
- The launcher's stored copies (`c1/assignment.md`, `c2/assignment.md`) are byte-identical to the control files.

## Session table (launcher JSON only): 4 Sonnet sessions, all `--gate C5`, all exit 0, every `.err` empty

| # | Session | Launcher JSON |
| --- | --- | --- |
| 1 | c1 author 1 (05:00:10–05:03:05) | `{"cases": 11, "key": "c1", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 16, "sha256": "09522225bd1f86cba30334a7adacd5a1866e1a3ebd0598af4ee5e50ffd2ce181", "turns": 61}` |
| 2 | c1 reviewer, round 1 (05:03:12–05:04:22) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "d1654b205bf6f0b8dc503a6a2eb25c74ddfeedff3d77c020010f40dce4d4305a", "key": "c1", "produced": true, "receipt_sha256": "7ca18117f6be22955bcafbb3ad80c5418faa75601987f23167338e45867898ac", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "09522225bd1f86cba30334a7adacd5a1866e1a3ebd0598af4ee5e50ffd2ce181", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |
| 3 | c2 author 1 (05:04:50–05:10:34) | `{"cases": 11, "key": "c2", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 20, "sha256": "ec1de6c4a95c076534cd29571bb5980612d0939786afb184744a3d71df9a2b19", "turns": 63}` |
| 4 | c2 reviewer, round 1 (05:10:55–05:12:02) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "bf8bbbb23bf82d7814c2b774b36da21c430d179ac0a930656e9bd469c9d9b536", "key": "c2", "produced": true, "receipt_sha256": "5a170f3b2f044f39d5450c888270516d09ddbf2f19578e3284763e118d5fba7e", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "ec1de6c4a95c076534cd29571bb5980612d0939786afb184744a3d71df9a2b19", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |

- **Outcome.** Both scenarios passed the precheck first time and were approved by their one full review (2 findings,
  0 blocking each). No fixer, verifier or restart ran, and no precheck-only fix round was needed.
- **The equal `review_sha256`.** Both `review.json` files hold the same three values. The value also equals the d2
  diagnostic verifier's, for the same reason.
- **Not applied.** The two minor findings of each review: a fix would make a new version needing a verification.
- **Session directories.** Each directory under `/home/yichen/.local/state/acceptance-sessions/c5-20261117b` was
  emptied with `find -mindepth 1 -delete` right after its session, unopened, and kept empty (8 entries including the
  `nomemory-*` ones).
- **Logs.** The four session logs (35–45 bytes by size) were never opened.

## Scenarios and receipts

- **C1 (`c1`):** `09522225bd1f86cba30334a7adacd5a1866e1a3ebd0598af4ee5e50ffd2ce181`; receipt
  `control/c1-review-approved.json` `7ca18117f6be22955bcafbb3ad80c5418faa75601987f23167338e45867898ac`, with the
  fields `{approved true, cases 11, findings 2, gate C5, key c1, review_session 1, role reviewer, round 1, sessions 16,
  turns 61, sha256 = the scenario}`.
  - Final precheck `--c5 --require <the 7>`: ok, codes none.
  - Sessions 16, turns 61, actions 1, cases 11.
  - Span 91 days, coverage 7 of 7.
  - Intended unrecorded turns 0; off-the-record openings recognised 0 of 0 (no stretch).
- **C2 (`c2`):** `ec1de6c4a95c076534cd29571bb5980612d0939786afb184744a3d71df9a2b19`; receipt
  `control/c2-review-approved.json` `5a170f3b2f044f39d5450c888270516d09ddbf2f19578e3284763e118d5fba7e` (the same fields,
  key c2, sessions 20, turns 63).
  - Final precheck `--c5 --require <the 6>`: ok, codes none.
  - Sessions 20, turns 63, actions 3, cases 11.
  - Span 70 days, coverage 6 of 6.
  - Intended unrecorded turns 0; off-the-record openings recognised 0 of 0 (no stretch).
- **Coverage.** The precheck prints "coverage N of M" over the assignment's items: 7 of 7 plus 6 of 6 makes the 13.
  `freeze.py` confirmed that the pair's union is all 13.

## Novelty (10% largest 8-gram overlap)

- **`novelty.py` against SOURCE's public set** (21 files, `c5-practice-scenario.py` among them; 15,646 recorded
  hashes):

  | Scenario | Hash new | Largest overlap | Union | 8-grams |
  | --- | --- | --- | --- | --- |
  | C1 | true | 0.08% | 0.11% | 3,536 |
  | C2 | true | 0.14% | 0.28% | 5,676 |

  `ok` true.
- **`novelty.py` cannot take earlier files by path.** So that the diagnostics could be added as the brief asks, and
  the sixth and seventh attempts' held-out scenarios as the draft binding states, I used a wrapper outside the
  repository: `novelty_with_extras.py` (sha256 in `preparation.json`). It imports the kit's functions unchanged and
  prints numbers only. The 8 extra files were read by path, never displayed: the sixth attempt's `s1`, `s2` and
  `s2b`, the seventh's `s1b` and `s2b`, and the diagnostics `d2`, `d3` and `d1`.
  - **`d1` is an addition beyond the brief's two:** it is a public diagnostic too.
  - **All 29 together:** C1 largest 6.36%, union 7.10%; C2 largest 3.12%, union 3.42%. Both new, `ok` true.
  - **Each extra file alone:**

    | Scenario | 6th `s1` | 6th `s2` | 6th `s2b` | 7th `s1b` | 7th `s2b` | `d2` | `d3` | `d1` |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | C1 | 0.03% | 0.14% | 0.00% | 0.00% | 0.00% | **6.36%** | 0.82% | 0.96% |
    | C2 | 0.00% | 0.12% | 0.00% | 0.00% | 0.00% | 0.11% | **3.12%** | 0.19% |

  - **Why the two marked overlaps:** each is with the diagnostic written for the same items under the same criteria
    templates. They are within the threshold.
  - **Not compared:** the earlier attempt `…a`'s unapproved versions (its private root stays unopened).

## Tests and rehearsals

Everything ran in the clone, with keys and `C5_*` unset, under the shared lock (taken by `mkdir`, released by
`rmdir`).

- **Focused tests** (`focused_runner.py`; 04:59:52–05:11:39 at SOURCE `4936e6bb`): **1,004 passed, 0 failed, 0
  skipped**, 2 existing fork warnings, 688 s.
  - Files: every `tests/test_c5_*.py` and `tests/test_acceptance_*.py`, `test_companion_acceptance.py`,
    `test_evaluation_billing_guard.py` and `test_pause_request.py`.
  - Per file: driver 152, kit 71, kit novelty 4, review hardening 157, review pipeline 128, scenario path 18,
    companion validity 20, converge 70, c5 harness 56, harness hardening 79, c5 kit 77, proposal selection 7, review
    fixes 39, supervisor 7, companion acceptance 26, billing guard 55, pause request 38.
  - The database stopped. Its `database`, `pytest` and `.agent-memory-recovery` directories were removed (paths
    checked under `checks/checks-1-tests/`, no process using them).
  - Log `checks/checks-1-tests.log` and JUnit kept.
- **C5 stub rehearsal before freezing** (`checks/checks-1-c5-rehearsal`, 234 s, stderr empty): **ok**.
  - Freeze 441 files, gate C5, practice. Driver complete, `eligible` C5, c1 and c2 valid.
  - Dry-run checks 606 of 606 each.
  - Validity per scenario: 16 actions, 14 done, 2 not applicable, identical in `P` and `F`.
  - Persona mirroring 34 of 34. Host pauses: `P` 1, `F` 0. Coverage-report 13 of 13 made.
  - Sheets: 7 cases with all three blocks.
  - Gate C5 true (13 vs 13, one host-caused vs one reference critical).
  - 0 network events; ledger unchanged, 0 requests; ports closed; 2 databases removed.
- **C5 stub rehearsal on the frozen head `707edc57`** (`checks/checks-2-c5-rehearsal`, 311 s, stderr empty): **ok**,
  with the same results as before freezing but 442 files.
  - Its 439 tracked hashes equal the real manifest's (439 of 439).
  - The tree was clean before and after.
- **Not rerun:** the full suite. The binding cites 4,271 passed and 3 skipped on the pin commit `0b1c052d`
  (`persona-confirmation-2026-11-17.md`), whose `src/`, `migrations/` and `plugins/` equal SOURCE's.

## Run script (written, never run)

- **Files:** `run-live.sh` sha256 `d0655f20f2028245e508f76e6dc20b7e8f800e0d290edab6ddd1b0214448c251`, verbatim in the
  binding's run block (checked byte-identical); `bash -n` ok.
- **`balance.py`:** a byte copy of the seventh attempt's (`b34790e6…ad7a1`). Tested only without a key: it printed
  `{"error": "KeyError"}` and exited 1; no request was made.
- **Changes from the seventh attempt's script:**
  - attempt id, paths, `PRIV`, `run_id` and `C5_ATTEMPT_ID`;
  - a watcher on `runs/c2-P` that writes `balance-after-c1.json`;
  - refusals unless `control/owner-approval.json` and `control/provider-revalidation.json` exist and hold JSON objects;
  - the key is validated and the first balance read **before** the ledger is created, so a refused key or balance
    leaves no ledger;
  - the key is unset on every later refusal;
  - the ledger's policy hash is checked to be 64 hex characters.
- **Unchanged:** every other refusal before the ledger.

## Deviations from the brief, refusals, content exposure

- **The persona was drawn before the commit.** It was computed at 05:12:42 UTC, after both scenarios were final and
  while the binding was written, not after the commit. Step 6 lists it after the commit, but step 5 requires every
  placeholder filled, the draft's `<preset>` included. This follows the seventh attempt.
- **Novelty with extra files** used a wrapper, because `novelty.py` cannot take files by path. `d1` was added beyond
  the brief's two diagnostics.
- **Git identity.** The clone had no committer identity, so the commit used `git -c user.name=chriswu727 -c
  user.email=yichenwu727@gmail.com` (the main repository's own identity). This is not a permission refusal.
- **Ordering.** The c1 author ran while the focused tests and the first rehearsal ran, as the brief allows. `c2` was
  started only after `c1` was approved.
- **Binding text beyond the draft's placeholders:**
  - new limits for the one-reviewer approvals and for the absence of an off-the-record stretch;
  - a row in the comparability table for scenario review;
  - a "C5 only; earlier preparation `…a` froze nothing" paragraph;
  - the run-script changes listed.
- **Refusals: none.**
- **Content printed that should not have been: none.** I saw only hashes, counts, fixed codes, receipts, the
  manifest's paths and hashes, my own assignment files, the d2 assignment (allowed) and public practice output.

## Observations for the lead

- **Both reviews were fast.** Each scenario was approved in round 1 by one Sonnet reviewer, in about 70 s of session
  time. The diagnostic reviewer's speed is not on record for comparison.
- **What I cannot see.** I cannot check from outside whether the mandatory 61- and 63-line message scans were made.
  The binding states as a limit that each scenario's fitness beyond the precheck rests on that one reading.
- **Neither scenario has an off-the-record stretch**, so the pause path is not exercised in this attempt.

## What remains before the paid run

1. Independent freeze review, which writes `control/freeze-review.json` with `execution_may_start`.
2. The owner's approval of this run (80 CNY ceiling, subscription use for blind scoring and the final review),
   recorded as `control/owner-approval.json`.
3. Provider revalidation on the day of the run (`control/provider-revalidation.json`).
4. Start `run-live.sh` detached, as the binding shows. Then validity per scenario (`not_applicable` actions and
   host-pause turns by position), blind scoring, `gate … --companion`, the host-diligence table and the final
   review.
