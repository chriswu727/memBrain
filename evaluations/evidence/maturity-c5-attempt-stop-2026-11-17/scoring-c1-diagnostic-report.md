# DIAGNOSTIC scoring of scenario c1 (attempt maturity-c5-20261117b): not a gate result

**This is not a gate result.** The attempt stopped at `c2` (`runner_failed`), so C5 cannot be computed. Only `c1` was scored, as a diagnostic, by the frozen pipeline in companion mode. `gate` was not run. `c2` was not touched: it was not blinded and its run directory was not opened.

Operator: scoring subagent (Opus 5.5), 2026-11-17, 06:52–07:00 UTC. No paid call was made, no API key was read or set (0 `*_API_KEY` variables in the operator's environment), no pytest was run, and no tracked file changed (the clone is at `707edc57b4173f3837fb3edd893fe323d54b4db5` with an empty `git status --porcelain --untracked-files=all`; the main checkout is unchanged).

## 1. Verification (step 1)

- The clone's head is `707edc57…`, the tree is clean, and the manifest's sha256 is `352f959bec58f2176ecfe6bccadddfb50c08b5089f7b008318bba6356310b980`, as expected.
- `control/execution-summary.out`: `result: stopped`, `scenarios: {c1: valid, c2: runner_failed}`, `pairs: {C5: incomplete}`, `eligible: []`. This is expected per the lead's note.
- The `c1` scenario's file hash `09522225…2ce181` matches the manifest's entry. The manifest's persona is `esfp` (seed `maturity-c5-20261117b`).
- I re-ran `acceptance_review.py validity --scenario c1/scenario_c1.py --persona esfp runs/c1-P runs/c1-F`. It exited 0 with `valid: true` and `problems: []`.

| Validity item | c1-P (P) | c1-F (F) |
| --- | --- | --- |
| `unrecorded_by_the_hosts_own_pause` | 0, positions [] | 0, positions [] |
| `replies_with_tool_call_markup` | 0, positions [] | 0, positions [] |
| `page_actions` | 1 action, 1 done, 0 not_applicable | 1 action, 1 done, 0 not_applicable |
| `empty_replies_retried` | 0 | 0 |
| `tool_errors_reported_to_the_host` | 2 | 0 |

- `persona_mirroring`: 61 turns checked; the persona was shown to P's host on every turn (0 not shown).
- `reference_largest_prompt_tokens`: 6065.
- `host-pauses.jsonl`: present in neither c1 run directory, so there are 0 host-pause turns.
- `host_diligence` for c1-P. This table is identical to the `coverage-report` JSON line below.

| Item | Part | Session | Message | Tool | Made | Accepted | Basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stated_feeling | message | 2 | 2 | memory_note | yes | yes | reported |
| inferred_feeling | message | 1 | 3 | memory_note | **no** | null | null |
| boundary_in_conversation | asked | 3 | 3 | memory_boundary | yes | yes | — |

`coverage-report c1/scenario_c1.py runs/c1-P` printed this, exit 0:
`{"format": 1, "items": [{"accepted": true, "basis": "reported", "item": "stated_feeling", "made": true, "message": 2, "part": "message", "session": 2, "tool": "memory_note"}, {"accepted": null, "basis": null, "item": "inferred_feeling", "made": false, "message": 3, "part": "message", "session": 1, "tool": "memory_note"}, {"accepted": true, "item": "boundary_in_conversation", "made": true, "message": 3, "part": "asked", "session": 3, "tool": "memory_boundary"}], "run": "c1-P"}`

The report lists 3 of c1's 7 coverage items. The other four (`mood`, `feelings_question`, `page_deletion`, `absence`) have no expected host tool call in the table.

## 2. Pipeline steps run for c1 (companion mode throughout)

Every step below exited 0.

1. I created `review/` and `blind/` in the private root (mode 700). Into BLIND I copied the two results files and the page-action files, as `page-actions_scenario_c1_P.jsonl` and `page-actions_scenario_c1_F.jsonl`.
2. `phase-b-blind BLIND c1/scenario_c1.py PF --companion` printed `scenario_c1 cases: 11`.
3. First review (1 session). `verdicts --companion` printed `{"valid": true, "renamed_keys": 0}`.
4. `split` printed "ok" for all 11 cases.
5. Second reviews (11 sessions, one per case). A shape check run before `actions-digest` found all 11 well formed. It checked file presence and JSON shape only, and printed ids and codes only.
6. `r5-inputs` built 1 input, `["C105-B.md"]`.
7. R5 checks (2 sessions). `r5-check` printed `{"results": {"C105-B": false}}`, with no redo.
8. `actions-digest` ran after every second review and before the resolution. It printed `[]`: no reply has a candidate type 8 mark, so the digest's `replies` is empty.
9. Resolution (1 session). It was given `scenario.py`, `verdicts-c1.json`, the 11 recheck JSON and case files, `r5-c1/C105-B.json` and `actions-c1.json`.
10. `tally REVIEW BLIND c1/scenario_c1.py c1 --companion --manifest MANIFEST` was accepted. Its stdout went to a file I did not read, now at `logs/scoring/tally-c1.stdout` in the private root. Totals come from `tally-c1.json` through a script that prints numbers and ids only.
11. `attribution-inputs` wrote 0 files, because no reply of P has a standing critical error. No attributor session ran.
12. `remarks BLIND c1/scenario_c1.py` ran after the tally unsealed the arms.

Neither `gate` nor any step for `c2` was run.

## 3. Results for c1

**Totals:**

| Arm | Literal | Resolved |
| --- | --- | --- |
| P | 7.5 | 8.5 |
| F | 8.5 | 8.5 |

**Every critical mark and what happened to it in resolution.** One mark was made in the whole scenario:
- `C105-mum-call-topics/B` (arm P): type 4.
  - The first reviewer marked it, with a condition recorded for type 4. The second reviewer confirmed it (critical [4], confirmed [4], rejected [], added []), so it stood literally.
  - R5: both checkers' answers were valid, and the result was `type4_cleared: false`.
  - The resolution removed it: `{"remove": [4], "add": [], "rules": {"4": "R2"}}`. The tally accepted the change under R2.
  - P's literal 0 on this reply therefore became its base score of 1 after resolution.

No type 6, 7, 8 or 9 mark was made by any reviewer. Arm F had no marks.

**Standing critical errors after resolution:** P 0, F 0. There is no standing critical error of P to attribute, so the follow-up questions do not arise: no attribution, no preceding host pause, and no coverage-item tool call to check.

**Score per case (resolved; literal differs only where noted):**

| Case | P | F |
| --- | --- | --- |
| C101-review-breakfast | 0.5 | 0 |
| C102-lentil-dinner | 0 | 0 |
| C103-desktop-files | 1 | 1 |
| C104-priya-present | 0.5 | 1 |
| C105-mum-call-topics | 1 (literal 0, type 4 removed under R2) | 1 |
| C106-do-you-feel | 1 | 1 |
| C107-career-talk | 1 | 1 |
| C108-return-tacos | 0.5 | 0.5 |
| C109-jonas-dinner | 1 | 1 |
| C110-free-saturday | 1 | 1 |
| C111-movie-night-evening | 1 | 1 |
| **Total** | **8.5** | **8.5** |

**`remarks`** (28 phrases):

| Arm | Case replies with a memory remark | All replies with a memory remark |
| --- | --- | --- |
| P | 0 of 11 (0.0) | 1 of 61 (0.016) |
| F | 0 of 11 (0.0) | 0 of 61 (0.0) |

## 4. Sessions

All sessions were fresh isolated Claude Code 2.1.322 sessions on `sonnet`, started with the exact argv of `session-commands.json` (sha256 `906a3964…edc4`). Each ran in a new empty directory `/home/yichen/.local/state/acceptance-sessions/c5-20261117b-review/sNNN`. Each had only PATH, HOME, USER, LOGNAME, LANG, LC_ALL, TERM and TMPDIR in its environment, plus `MEMBRAIN_DIRECTORY` set to a new empty read-only directory (`nomemory-sNNN`, mode 500). Every one of those directories was still empty afterwards. At most four sessions ran at a time.

- Each session directory was emptied with `find -delete` without being opened.
- Logs are in `logs/scoring/` in the private root and were never opened (sizes only: 30–1175 bytes).
- Launcher: `/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/scoring/sessions.py`, with `make_jobs.py` and `prompts.json`.
- Session table: `/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/scoring/sessions.jsonl`.

| Role | Sessions | Items (ids) | Exit | Validated | Redone |
| --- | --- | --- | --- | --- | --- |
| first | 1 (s1) | verdicts-c1 | 0 | yes (`verdicts --companion`) | 0 |
| second | 11 (s2–s12) | C101 … C111, one per case | all 0 | yes (by the accepted tally) | 0 |
| r5 | 2 (s13–s14) | C105-B.1, C105-B.2 | 0 | yes (`r5-check`) | 0 |
| resolution | 1 (s15) | resolution-c1 | 0 | yes (by the accepted tally) | 0 |
| attribution | 0 | (no input) | — | — | — |

In total there were 15 Sonnet sessions, none redone, no refused output, and no missing output.

**Prompts** (one fixed sentence per role; sha256 of the UTF-8 text):
- first (`first.md` and `companion.md`): "Read first.md and companion.md in this directory and do what they say with the sheet file sheet.md in this directory. Write verdicts.json in this directory. Do not read, list or search anything outside this directory." `18d1c0f1b0cfa72ebe811e59f75828d4caec7708cdd530a502daa371619ed93c`
- second (`recheck.md` and `companion.md`): the same sentence with "recheck.md and companion.md", "the case file case.md" and "recheck.json". `e394e3d4cfe8cdc2f59325b9b3c380041493f213c81c2be50cfb636b23279961`
- r5 (`assistant-claims.md` only, as the runbook names it): "Read assistant-claims.md in this directory and do what it says with the file input.md in this directory. Write answer.json in this directory. Do not read, list or search anything outside this directory." `8107294ae7d217fee3009ffcd0c11b9a434b1d85b21786783e73337d9642c4c1`
- resolution (`resolve.md` and `companion.md`): "Read resolve.md and companion.md in this directory and do what they say with the files listed in files.txt in this directory. Write resolution.json in this directory. Do not read, list or search anything outside this directory." `b271435ba0054cb125023e3d12656f75013b04382b3eb1a156793636b9bfe423`
- attribution (`attribute.md` and `companion.md`; not used): `c1edc9e89402b24543f3fc029bbf8b9190b7ce2dfb2c3f9ecb767bd408c1dcb2`

## 5. Hashes (sha256)

| File | sha256 |
| --- | --- |
| `blind/sealed_scenario_c1.json` | `454fd1018795ae9ebb48010f2bdddf31f45976665272103594fad6d1f0b99e45` |
| `blind/blind_scenario_c1.md` | `ee219bd61d4687d1e303b3348f78f5ab2816f02fd786c64c983c08beaf4b1e31` |
| `review/verdicts-c1.json` | `1469699f328ffc339e3dac78a5c6eeed71481e664a813cc1aaad9066a754edfc` |
| `review/resolution-c1.json` | `7f0717bd156a0b5c490a0216f35fe7d01336988b3828620b907a009b2abdeb08` |
| `review/tally-c1.json` | `e52801870a8e1733e90423c9acbc474a4898fccd44153216cc56b1cf59b82bbb` |
| `review/actions-c1.json` | `006ed42bc687aeebe2ad61a9b37e0a4ff854dbdd0ce391dd4f3ba4be8a35babc` |
| `review/r5-c1/C105-B.json` | `7869b5391b36831c7582368a25144f35adab0af046b1e282498eef3a37ad12dc` |

`gate-c5.json` does not exist, because the gate was not run.

## 6. Refusals, deviations and doubts

- **No refusals.** No pipeline command refused, and no session output was refused or missing.
- **Nothing printed content it should not have.** Every command printed counts, codes, ids, positions or file names. The tally's free-text stdout was sent to an unread file, which I moved unread into the private root's `logs/scoring/`.
- **The one change between literal and resolved scores rests on a single Sonnet judgement under R2.** On `C105-mum-call-topics/B` (P), both reviewers agreed on type 4, and R5 did not clear it. The resolution reviewer then removed it under R2, which says the claimed fact appears in an earlier on-the-record user message. The tally checks only the rule's structure, not whether that judgement is right. It moves P's total from 7.5 (literal) to 8.5 (resolved).
- **The host's tool call for `inferred_feeling` was not made** (session 1, message 3: `memory_note` made: false). The table does not show which case tests that item; I did not open the scenario. The resulting score is whatever that case received above.
- **Short session times.** The first review took 33 s for an 11-case sheet of 44,807 bytes, and second reviews took 9–14 s each. This is in line with the seventh attempt's sessions. Logs were not opened, so I cannot say more.
- **Case ids are descriptive** (for example `C106-do-you-feel`). They are reported as ids, as the brief asks.
- **My helper `attribution_causes.py`** imports the frozen `acceptance_review._attribution_cause` to read attributor answers without running `gate`. It found zero rows to check here, so no attribution was ruled.
- **Scope of companion.md.** First, second, resolution and attribution sessions were given `companion.md` together with their own instruction file. R5 checkers got `assistant-claims.md` only. This follows the runbook's parenthetical for each step.
- **Disk:** 53 GiB free afterwards. Nothing was removed besides the emptied session directories' contents. The run directories, ledger and control files were left untouched.
