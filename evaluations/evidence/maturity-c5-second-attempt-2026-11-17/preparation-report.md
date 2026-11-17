# Second two-arm companion attempt (maturity-c5-20261117c): preparation report

Prepared and frozen on 2026-11-17, 09:30–09:58 UTC.
- No paid call, no API key read, no push, no PR.
- Nothing changed in `/home/yichen/src/memBrain` (clean, head `6ffcbbbe`, before and after).
- Nothing changed in any earlier attempt's directory.
- `control/freeze-review.json` was not written.
- I stopped once, at step 5, because the brief's binding name was the previous attempt's binding. The lead then named
  it `maturity-c5-execution-2026-11-17c.md`. The interim report is kept as `preparation-report-interim.md`.

## Frozen state

- **SOURCE** `6ffcbbbe397463b67840e48d58cf5d7bac674982`. It is the local head of `integration/maturity-candidate`,
  equal to `origin/integration/maturity-candidate` after a fetch and to GitHub (`git ls-remote`). The main tree was
  clean, no test was running, the lock was free and 52 GB were free.
- **Clone** `/home/yichen/.local/state/membrain-setup/runs/c5-attempt3/clone`, branch `acceptance/maturity-c5-20261117c`.
- **Frozen head `7aa32af0938cef0d361a3387eb58da598c6ae494`.** It is one commit on SOURCE, adding only the binding
  `evaluations/maturity-c5-execution-2026-11-17c.md` (sha256
  `c4157767fe77793259ad1b1d44774721e85c8f6e014b3615d7e5b6d80cf68f98`).
  - The previous attempt's binding `maturity-c5-execution-2026-11-17.md` is unchanged, and the new one links to it.
  - The tree is clean.
  - The private root `evaluations/.maturity-heldout-c5-20261117c/` (mode 700) with `control/` is git-excluded.
  - The commit had no permission refusal. The clone has no git identity, so I committed with `-c user.name/-c
    user.email` set to the main repository's identity.
- **Manifest** `control/manifest.json` (mode 600):
  - sha256 **`409993b32b86f7cf796707140f7d0f09e5d704fd1d44930537ddfd18c7020b76`**;
  - **448 files**: 441 tracked plus 7 private (the allowed-models file, two assignments, two receipts and two
    scenarios); I re-hashed all 448 with 0 mismatches;
  - **persona `intj`** (seed `maturity-c5-20261117c`), **order `c1`, `c2`**;
  - one pair, gate `C5`, no practice mark.

  `freeze.py --gate C5` was run with `--binding`, `--allowed-models` and both `--assignment`. It exited 0 with empty
  stderr and printed `coverage_items` 7 + 6.
- **`control/preparation.json`** (mode 600): sha256 `14f526c44cd0b052bab56a34a6926d1deb4548322a0572b0dab0e5b2b0867db5`.
  The run script's reads of `head` and `manifest_sha256` return the frozen values.
- Ports 8893 and 55533 are free and bindable. 55.5 GB are free. There is no ledger and no `runs/`, and no process
  belongs to the attempt.

## Measured on this source (decision 5)

- **Build and schema:** build `3d3b119ae710eaf66455aa0245e36d4da36ecf891393b68fec5ddc1a8a942220`; schema
  `3a94d7b6…166d`, unchanged.
- **Launcher pin.** All 9 launchers pin runtime `3afc0dda274b21caff72fe5bcda97ec12298ce7e` (pin commit `e82ad9d6`).
  - `ef0e8727` and `55a88f1f` are ancestors of the runtime, of the pin and of SOURCE.
  - `src/` and `migrations/` are identical across `3afc0dda`, `e82ad9d6` and SOURCE.
  - `plugins/` is identical between `e82ad9d6` and SOURCE.
- **Interpreter.**
  - uv 0.13.6, 79 packages, no system site-packages, `uv.lock` `0bc566ca…7e92`.
  - CPython 3.12.16, binary `23bc148d…82b5`; ONNX Runtime 1.31.1.
  - Embedding model and tokenizer as before (`f80102d3…`, `0b44a9d7…`).
  - Claude Code 2.1.322.
- **Tools offered to `P`:**
  - 14 tools, with the same names and order;
  - 17,217 characters of schemas, 16,425 bytes in shortest JSON;
  - server instructions of 1,388 characters, sha256 `1067d3f9…6a1d`;
  - measured directly and in both rehearsals' `tools.json`.
- **Kit sha256: every file is identical to attempt b.** That covers `launch.py`, `freeze.py`, `novelty.py`,
  `assignment.py`, `session-commands.json`, the four C5 briefs, `c5-precheck.py`, `c5-stub-rehearsal.py` and
  `scenario_literals.py`. The full values are in the binding and in `preparation.json`.
- **Policy** `e7b91106…689f`:
  - each request reserves 20.054016 CNY;
  - the guard refuses above 59.945984 CNY;
  - an interruption bound is 0.589824 CNY + 18 micro-CNY per body byte + 0.5913 CNY with `P`'s schemas, at most
    9.879552 CNY.
- **Cost estimate:** 126 turns come to about 29 CNY. With the uplift it is about 37 CNY (30–50), with about 1.6×
  headroom without interruptions and room for roughly 3–9 interruptions at 3.3 CNY.

## Session table (launcher JSON only): 4 Sonnet sessions, all `--gate C5`, all exit 0, every `.err` empty, every session dir emptied unopened

| # | Session | Launcher JSON |
| --- | --- | --- |
| 1 | c1 author 1 (09:31:31–09:35:02) | `{"cases": 11, "key": "c1", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 17, "sha256": "e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5", "turns": 61}` |
| 2 | c1 reviewer, round 1 (09:35:15–09:36:09) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "cbfe9be8b17a188ee3601f97a387824adb185d0b71d820db728197d244878d61", "key": "c1", "produced": true, "receipt_sha256": "97f52910c02b9386f95c798379a83ad2282ba493e1f20c67250d843449bd6a4c", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |
| 3 | c2 author 1 (09:36:19–09:41:41) | `{"cases": 11, "key": "c2", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 20, "sha256": "a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b", "turns": 65}` |
| 4 | c2 reviewer, round 1 (09:41:57–09:43:07) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "9a192be4a5a298bcd97e0b106d4c575985a1a058840ca0a6c8cbec6b93324250", "key": "c2", "produced": true, "receipt_sha256": "07247a775e2f6a20e98d70da4aeaf7c41b7755fb4989af9d005d1ba8fbabfc9c", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |

- Both authors passed the precheck at once, and both full reviews approved with 2 findings and 0 blocking.
- No fixer, verifier or restart ran, and no precheck-only round was needed.
- The minor findings were not applied.
- The session logs were never opened.

## Scenarios, receipts, final prechecks

- **C1 (`c1`):** `e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5`; receipt `97f52910…a4c`
  `{approved true, cases 11, findings 2, gate C5, key c1, review_session 1, role reviewer, round 1, sessions 17, turns
  61, sha256 = the scenario}`.
  - Precheck `--c5 --require <7>`: ok, no codes.
  - Sessions 17, turns 61, actions 1, cases 11, span 68 days, coverage 7 of 7.
  - Intended unrecorded turns 0; off-the-record openings recognised 0 of 0 (no stretch).
- **C2 (`c2`):** `a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b`; receipt `07247a77…c9c` (the same
  fields, key c2, sessions 20, turns 65).
  - Precheck `--c5 --require <6>`: ok, no codes.
  - Sessions 20, turns 65, actions 3, cases 11, span 79 days, coverage 6 of 6.
  - Intended unrecorded turns 0; off-the-record openings recognised 0 of 0 (no stretch).
- **Coverage:** 7 + 6 = 13; `freeze.py` confirmed the union is all 13.
- The control files `allowed-models.json` (`1a1e8da4…`), `c1-assignment.md` (`e0e6ecfb…`) and `c2-assignment.md`
  (`dabfc500…`) are byte-identical to attempt b's. The launcher's stored copies are identical to them.

## Novelty (10% threshold)

**Public set at SOURCE** (21 files, 15,688 recorded hashes): `ok` true.

| Scenario | Hash new | Largest overlap | Union | 8-grams |
| --- | --- | --- | --- | --- |
| C1 | yes | 0.08% | 0.11% | 3,640 |
| C2 | yes | 0.11% | 0.26% | 5,319 |

**With 10 extra files by path** (attempt b's wrapper `novelty_with_extras.py`, copied unchanged, `1574aebd…`). The
extra files are the 6th attempt's `s1`, `s2` and `s2b`, the 7th's `s1b` and `s2b`, the diagnostics `d2`, `d3` and
`d1`, and attempt b's spent `c1` and `c2`.
- All 31 together: C1 largest 6.24%, union 6.59%; C2 largest 4.96%, union 6.81%. Both new, `ok` true.
- Each extra file alone:

  | Scenario | 6th `s1` | 6th `s2` | 6th `s2b` | 7th `s1b` | 7th `s2b` | `d2` | `d3` | `d1` | spent `c1` | spent `c2` |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | C1 | 0.03% | 0.16% | 0.00% | 0.00% | 0.00% | 5.74% | 0.69% | 0.93% | **6.24%** | 0.30% |
  | C2 | 0.00% | 0.15% | 0.04% | 0.00% | 0.04% | 0.11% | 4.47% | 0.19% | 0.36% | **4.96%** |

The highest overlaps are with the scenario written for the same items under the same templates. All are within the
threshold. Attempt a's versions were not compared.

## Tests and rehearsals (clone, keys and `C5_*` unset, under the shared lock)

- **Focused runner** at SOURCE (09:31:28–09:43:23): **1,124 passed, 0 failed, 0 skipped**, 702 s, 6 fork warnings.
  - The brief's set: **1,011**. Per file: driver 155, kit 71, kit novelty 4, review hardening 157, review pipeline 128,
    scenario path 18, companion validity 20, converge 70, c5 harness 56, harness hardening 80, c5 kit 77, proposal
    selection 7, review fixes 40, supervisor 7, companion acceptance 26, billing guard 57, pause request 38.
  - Added: `test_provider_interruption_retry.py` 80 and `test_billing_review_fixes.py` 33.
  - The database stopped. Its `database`, `pytest` and `.agent-memory-recovery` directories were removed (path
    checked, no process using them).
  - Log and JUnit kept in `checks/`.
- **C5 stub rehearsal before freezing** (`checks/checks-1-c5-rehearsal`, 244 s, stderr empty): **ok**.
  - Freeze 443 practice files, gate C5. Driver complete, c1 and c2 valid.
  - Dry-run 606 of 606 each.
  - Validity per scenario: 16 actions, 14 done, 2 not applicable (11 `boundary_not_present`, 13
    `message_not_recorded`), the same in `P` and `F`.
  - Persona mirroring 34 of 34. Host pauses: `P` 1, `F` 0. Coverage-report 13 of 13.
  - Sheets: 7 cases with all three blocks.
  - Gate C5 true (13 vs 13, one host-caused vs one reference critical).
  - 0 network events; ledger unchanged, 0 requests; ports closed; 2 databases removed.
- **C5 stub rehearsal on frozen head `7aa32af0`** (`checks/checks-2-c5-rehearsal`, 09:54:31–09:57:29, 178 s, stderr
  empty): **ok**, with the same results and 444 files.
  - Its 441 tracked hashes equal the real manifest's (441 of 441).
  - The tree was clean before and after.
- **Full suite (cited, not rerun):** 4,576 passed and 3 skipped on `3b3c32ef`. The one later commit is documentation
  and evidence only.

## Run script (written, never run)

- `run-live.sh` sha256 `d09bd7371302e7076e691801df656c9bf2f9ae19106671fa61bfa770c96f1326`. It is verbatim in the
  binding's run block (checked byte-identical), and `bash -n` passes.
- It is attempt b's script with only these changes: the id, `R`, `PRIV`, `run_id`, `C5_ATTEMPT_ID`, and "first" →
  "second" in its header.
  - It keeps every refusal: the head and manifest from `preparation.json`, a clean tree, the freeze review allowing
    execution, owner approval and provider revalidation present, ports free, 5 GiB free, no ledger, no `runs/`.
  - The ledger is created only after the key is validated and the first balance read.
  - The watcher waits for `runs/c2-P`.
- `balance.py` is a byte copy (`b34790e6…`). Tested with no key, it printed `{"error": "KeyError"}`, exited 1 and
  made no request.

## Binding content beyond the draft's placeholders

- A section on the earlier attempts a and b, linking b's binding and record.
- A second comparability table against attempt b: the runtime and the hard-moment definition, the provider retry, the
  `reached` field, new scenarios and persona, the test counts.
- The hard-moment probe in "What was measured beforehand".
- **Limits carried from b's freeze review that still apply:**
  - each scenario rests on one review, with no kit path for a second reading;
  - how to stop early: SIGTERM to the driver only, in Stop rules;
  - the owner's approval must name the ceiling and the policy hash, since the policy file is still labelled
    draft/R4;
  - the account must hold at least the ceiling, because the script checks only that the records parse;
  - the R4 runtime differs;
  - a tool call in the last round gives an empty reply;
  - no upper bound on cost.
- **New limits:**
  - the retry is untested against the real provider;
  - the two billing assumptions;
  - the eager hard-moment definition.
- "Preparation notes, as they happened", with the deviations below.

## Deviations from the brief, refusals, content exposure

- **Binding name.** It is `maturity-c5-execution-2026-11-17c.md` (the lead's decision after my stop), because the
  brief's name was attempt b's binding.
- **The persona was drawn before the commit**, at 09:49:43 UTC, after both scenarios were final, because the binding
  must name it. Attempt b did the same.
- **Earlier private root.** I listed the file names of attempt b's two scenarios and passed them by path to the
  novelty wrapper; they were never displayed. I also ran `cmp` on attempt b's three control files against mine,
  which opened files in an earlier private root; only "identical" was printed. Both are stated in the binding. The
  lead said these are fine.
- **Two retry test files** were added to the focused run, with counts given separately.
- **Novelty extras** include `d1` and the 6th and 7th attempts' held-out scenarios, as attempt b's operator did,
  beyond the brief's two diagnostics.
- **Git identity** was given with `-c` on the commit, because the clone has none. This is not a refusal.
- **Ordering.** The c1 author ran while the focused tests ran, as the brief allows. `c2` started after `c1` was
  approved.
- **Refusals: none.** **Content printed that should not have been: none.** I saw only hashes, counts, codes,
  receipts, the manifest's paths and hashes, my own assignment files, the d2 assignment and public practice output.

## Observations

- Both reviews were again fast (54 s and 70 s), and both approved in round 1 with 2 minor findings. Attempt b's
  freeze review judged that pace to be the reviewers' normal pace, but noted that nothing beyond the precheck stands
  behind the wording.
- Neither scenario has an off-the-record stretch, as in attempt b.

## What remains before the paid run

1. The independent freeze review, which writes `control/freeze-review.json` with `execution_may_start`.
2. The owner's approval, recorded as `control/owner-approval.json`. It should name the 80 CNY ceiling and policy sha256
   `e7b91106b206412c608b33b0f43adc1d6f7db7c19da0c05a82a620198fb5689f`, and the subscription use for scoring and the
   final review.
3. Provider revalidation on the day (`control/provider-revalidation.json`), and a balance of at least 80 CNY.
4. Start `run-live.sh` detached, as the binding shows. To stop early, send SIGTERM to the driver only.
5. Then: validity and the ledger check per scenario, blind scoring, `gate … --companion`, the host-diligence table and
   the final review.
