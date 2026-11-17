# Scoring report: attempt `maturity-c5-20261117c`, C5 unit (`c1`, `c2`)

Scoring operator's report to the lead, 2026-11-17 (sessions 18:50:37–18:55:32 UTC). It covers the companion-mode
scoring as the brief `c5c-scoring-brief-20261117.md` sets it out, up to `gate REVIEW c1 c2 --companion --manifest`.
It is not the public record and not the final independent review.

## Result

**C5: true (pass).** `gate` exited 0 and wrote `review/gate-c5.json`
(sha256 `d11d9eff75b8a35fc34d096606eafe2e2a8901abdc093da3b1dafc9e84eead59`):

```json
{
 "arms": {
  "P": {
   "total": 18.5,
   "reference": 17.0,
   "not_worse": true,
   "memory_caused": [],
   "host_caused": [],
   "reference_critical": 0,
   "host_within_reference": true,
   "passes": true,
   "boundary_or_deletion_errors": []
  }
 },
 "attributions": {},
 "frozen_arms": ["P", "F"],
 "gated": ["P"],
 "reference_arm": "F",
 "C5": true,
 "strict_boundaries_and_deletions": true,
 "manifest": {
  "attempt_id": "maturity-c5-20261117c",
  "sha256": "409993b32b86f7cf796707140f7d0f09e5d704fd1d44930537ddfd18c7020b76",
  "scenarios": [
   {"key": "c1", "path": "evaluations/.maturity-heldout-c5-20261117c/c1/scenario_c1.py", "sha256": "e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5"},
   {"key": "c2", "path": "evaluations/.maturity-heldout-c5-20261117c/c2/scenario_c2.py", "sha256": "a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b"}
  ]
 }
}
```

(The file is indented one value per line. Only the whitespace of the short arrays and scenario objects is
compressed here.)

### Totals (resolved; out of 11 per scenario)

| Scenario | `P` | `F` | `P` literal | `F` literal |
| --- | --- | --- | --- | --- |
| c1 | 9.0 | 8.5 | 8.0 | 8.5 |
| c2 | 9.5 | 8.5 | 9.5 | 8.5 |
| **Overall** | **18.5** | **17.0** | 17.5 | 17.0 |

So `P` ≥ `F` − 1 holds (18.5 ≥ 16.0).

### Critical errors

- **Standing critical errors: `P` 0, `F` 0.** Neither scenario has any. That leaves no `P` reply to attribute,
  no host-caused or memory-caused list, and no type 7 or 8.
- **The one mark in the whole review:** in c1 the first reviewer marked nothing. The second reviewer of C107 added
  type 4 on C107/A, which is arm `P`.
  - Its R5 input went to two checkers. `r5-check` gave `{"results": {"C107-A": false}}`, so R5 did not clear it.
  - The resolution reviewer then removed it under **R2** (`{"remove": [4], "add": [], "rules": {"4": "R2"}}`, no
    `rc2`). The manifest-bound `tally --companion` accepted that change.
  - This is the only difference between literal and resolved: `P` c1 goes from 8.0 to 9.0. I did not read the
    reason. Whether the R2 judgement was right is the resolution reviewer's call. The tally checks only the rule's
    structure.
- In c2 no reviewer marked anything, and the resolution file has 0 entries.
- `r5-inputs` for c2 wrote no file, and so did `attribution-inputs` for both c1 and c2. No attributor ran.

### Per-reply bases (ids only; arm from the tallies)

- **c1:**
  - C101 P 0.5 / F 0
  - C102 1/1
  - C103 P 0 / F 0
  - C104 1/1
  - C105 1/1
  - C106 1/1
  - C107 P 1 / F 0.5
  - C108 1/1
  - C109 1/1
  - C110 P 0.5 / F 1
  - C111 1/1
- **c2:**
  - C201 P 0.5 / F 0.5
  - C202 1/1
  - C203 1/1
  - C204 1/1
  - C205 P 1 / F 0
  - C206 1/1
  - C207 1/1
  - C208 1/1
  - C209 P 0 / F 0
  - C210 1/1
  - C211 1/1
- **Coverage cases below 1.** In c1:
  - C101 `stated_feeling`: P 0.5, F 0
  - C103 `mood` within hours: both 0
  - C110 is not a coverage case.

  In c2:
  - C201 `manner_feedback`: both 0.5
  - C209 `shared_moments`: both 0

### Step 4: `P` replies with a standing critical error

None. So there is nothing to list for each such reply: no types, no attributors' rulings, no host-pause turn before
it, no host-diligence call to check and no interrupted send in its turn. For context:
- no `host-pauses.jsonl` exists in any of the four run directories;
- no `provider-interruptions.jsonl` exists;
- every host-diligence entry is made and accepted (below).

### `remarks` (after unsealing; 28 phrases)

| Scenario | Arm | Case replies with a remark | All replies with a remark |
| --- | --- | --- | --- |
| c1 | P | 0 of 11 (0.0) | 1 of 61 (0.016) |
| c1 | F | 0 of 11 (0.0) | 0 of 61 (0.0) |
| c2 | P | 0 of 11 (0.0) | 3 of 65 (0.046) |
| c2 | F | 1 of 11 (0.091) | 5 of 65 (0.077) |

## Step 1: verification and validity

- **Clone.** Head `7aa32af0938cef0d361a3387eb58da598c6ae494`. The tree is clean (`git status --porcelain
  --untracked-files=all` is empty, before and after scoring).
- **Manifest.** sha256 `409993b3…b76` as expected. The scenarios' sha256 equal the manifest's.
- **Driver summary.** `result: complete`, `eligible: ["C5"]`, `c1` and `c2` both `valid`, `stop` null.
  `execution-done`: "driver exit 0", "ports closed", 2026-11-17T18:46:18Z.
- **Cleanup.** `cleanup.out` shows all four runs `ok`, with no open ports.
- **Now.** Ports 8893 and 55533 are closed. No process of the attempt is left. The only memBrain-named processes
  are the owner's remote-control session.
- **Ledger.** `blocked: false`. It holds 353 requests, all settled, highest seq 353. The guard's settled count is
  28.324206 CNY, under the 80 CNY ceiling.
  - **Driver's ledger check, c1:** `after_seq 0`, highest 165, no interrupted requests, `valid: true`.
  - **Driver's ledger check, c2:** `after_seq 165`, highest 353, `valid: true`.
- **Validity re-run.** I ran `acceptance_review.py validity --scenario … --persona intj RUN_P RUN_F` for each
  scenario. Both exited 0 with `valid: true` and `problems: []`. Each output is byte-identical to the driver's
  `cN.validity.log`.

| | c1-P | c1-F | c2-P | c2-F |
| --- | --- | --- | --- | --- |
| `unrecorded_by_the_hosts_own_pause` | 0, [] | 0, [] | 0, [] | 0, [] |
| `replies_with_tool_call_markup` | 0, [] | 0, [] | 0, [] | 0, [] |
| `provider_interruptions` (sends / retried calls / not retried / delay s / per session) | 0/0/0/0/[] | 0/0/0/0/[] | 0/0/0/0/[] | 0/0/0/0/[] |
| empty replies retried | 0 | 0 | 0 | 0 |
| tool errors reported to the host | 2 | 0 | 1 | 0 |
| page actions: count / done / not applicable | 1/1/0 | 1/1/0 | 3/3/0 | 3/3/0 |

- **Largest reference prompt:** 3,993 tokens in c1 and 4,807 in c2.
- **Persona mirroring:** c1 61 of 61 turns checked, 0 not shown to `P`'s host. c2 65 of 65, 0 not shown.

**Page actions**, all `done` and identical in both arms, by position and the `COVERAGE` item each served (from
`COVERAGE` and `PAGE_ACTIONS` read with `scenario_literals.py`; ids, positions and codes only):

| Scenario | # | Kind | Before | Item | Case |
| --- | --- | --- | --- | --- | --- |
| c1 | 1 | `delete_message` | session 12, message 1 | `page_deletion` | C108 |
| c2 | 1 | `accept_proposal` | session 8, message 1 | `manner_feedback` | C201 |
| c2 | 2 | `add_boundary` | session 9, message 1 | `boundary_on_page` | C202 |
| c2 | 3 | `reset_relationship` | session 19, message 1 | `reset` | C210 |

**Host-diligence table** (`P`; identical to `coverage-report SCENARIO.py RUN_P`, which exited 0). Every entry is
reached, made and accepted: 11 of 11.

| Scenario | Item | Part | Session | Message | Tool | Code | Reached / made / accepted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| c1 | stated_feeling | message | 2 | 2 | memory_note | basis reported | yes/yes/yes |
| c1 | inferred_feeling | message | 3 | 2 | memory_note | basis inferred | yes/yes/yes |
| c1 | boundary_in_conversation | asked | 7 | 2 | memory_boundary | | yes/yes/yes |
| c2 | manner_feedback | comment 1 | 2 | 3 | memory_manner_feedback | | yes/yes/yes |
| c2 | manner_feedback | comment 2 | 5 | 3 | memory_manner_feedback | | yes/yes/yes |
| c2 | manner_feedback | comment 3 | 7 | 3 | memory_manner_feedback | | yes/yes/yes |
| c2 | from_now_on | request | 10 | 2 | memory_persona | action propose | yes/yes/yes |
| c2 | from_now_on | yes | 10 | 3 | memory_persona | action confirm | yes/yes/yes |
| c2 | switch | request | 15 | 2 | memory_persona | action switch | yes/yes/yes |
| c2 | shared_moments | play | 6 | 2 | memory_note | moment play | yes/yes/yes |
| c2 | shared_moments | hard | 4 | 4 | memory_note | moment hard | yes/yes/yes |

**coverage-report JSON lines** (fixed codes only), recorded as files in `scoring/coverage-c1.out` and
`scoring/coverage-c2.out`: `{"format": 1, "run": "c1-P", "items": [...]}` with the three c1 entries above, and
`{"format": 1, "run": "c2-P", "items": [...]}` with the eight c2 entries above.

**Facts for the freeze review's `conditions`:**
- **Not-applicable page actions:** none (0 of 4), so no `COVERAGE` requirement went unexercised by a page action.
- **Host-pause turns:** 0 in every run.
- **Host-diligence by position:** the table above, all `reached`.
- **Interruptions:** none. 0 interrupted sends and 0 retried host calls in all four runs, so no delay in any session
  and no scenario clock moved by a retry. No reply was produced on a retry.
- **No off-the-record stretch:** neither scenario declares one, and validity reports 0 pause-unrecorded turns.
- Each scenario rests on one round-1 review, and the R4-runtime limit applies. Both are binding facts, not rechecked
  here.

## Step 2–3: pipeline and sessions

**Pipeline order, as run:** c1 first, then c2. All commands ran from the clone root with `.venv/bin/python` and
`PYTHON_DOTENV_DISABLED=1`, with no `*_API_KEY` set.

For each key:
1. copies into `blind/`;
2. `phase-b-blind BLIND SCENARIO PF --companion` (11 cases each);
3. first review, then `verdicts --companion` (valid, 0 keys renamed);
4. `split` (11 ok);
5. 11 second reviewers, each output shape-checked by `check_second.py` (presence and JSON partition only; no reason
   read);
6. `r5-inputs`;
7. two R5 checkers per input, then `r5-check`;
8. `actions-digest`, after every second review and before any resolution (`[]` for both: no candidate type 8);
9. resolution, given `r5-KEY/` and `actions-KEY.json`;
10. `tally … --companion --manifest` (stdout to `logs/scoring-unread/tally-KEY.stdout`, never opened; stderr
    empty);
11. `attribution-inputs` (none).

Then `gate REVIEW c1 c2 --companion --manifest` and `remarks` for each scenario. Every command exited 0. `review/`
and `blind/` are mode 700, and their files are mode 600.

**Sessions.**
- **Where.** Each session ran in a new empty directory `s0NN` under
  `/home/yichen/.local/state/acceptance-sessions/c5-20261117c-review/`, with `nomemory-s0NN` (mode 500, empty) as
  `MEMBRAIN_DIRECTORY`.
- **Command.** `session-commands.json` → `claude.argv` exactly (sha256 `906a3964…edc4`, checked by the launcher),
  with model `sonnet`. Claude Code is 2.1.322.
- **Environment.** Only the kept variables. The operator's environment had no `TMPDIR` or `LC_ALL`, so each session
  got PATH, HOME, USER, LOGNAME, LANG and TERM, plus `MEMBRAIN_DIRECTORY`.
- **Inputs.** Each session got only its role's instruction files and inputs:
  - first: `first.md` and `companion.md`, plus the sheet;
  - second: `recheck.md` and `companion.md`, plus one case file;
  - R5: `assistant-claims.md` plus the input;
  - resolution: `resolve.md` and `companion.md`, plus the scenario, the verdicts, the 11 case files and second
    reviews, the R5 results, `actions-KEY.json` and a `files.txt` listing them.
- **Outputs.** Each output was moved to where the runbook expects it, and the directory was emptied unopened. Every
  `MEMBRAIN_DIRECTORY` was still empty afterwards. The session root now holds 58 empty directories.
- **Logs.** Session stdout went to `PRIVATE_ROOT/logs/scoring/s0NN.log`, never opened.
- **Tools.** Kept in `/home/yichen/.local/state/membrain-setup/runs/c5-attempt3/scoring/`, with sha256:
  - `sessions.py` `20a0da34…7d7d`
  - `make_jobs.py` `aa7d7475…ec2a`
  - `prompts.json` `c5e1a497…10aa`
  - `check_second.py` `cf345a3c…e834`
  - `tally_numbers.py` `3f603951…754e`
  - `attribution_causes.py` `1feae0c8…2963` (not needed)
  - `coverage_map.py` `f2b96190…d19d`
  - the table `sessions.jsonl` `c86392c0…49f0`

**Fixed prompts** (text, sha256):
- first: "Read first.md and companion.md in this directory and do what they say with the sheet file sheet.md in this
  directory. Write verdicts.json in this directory. Do not read, list or search anything outside this directory."
  `18d1c0f1b0cfa72ebe811e59f75828d4caec7708cdd530a502daa371619ed93c`
- second: "Read recheck.md and companion.md in this directory and do what they say with the case file case.md in this
  directory. Write recheck.json in this directory. Do not read, list or search anything outside this directory."
  `e394e3d4cfe8cdc2f59325b9b3c380041493f213c81c2be50cfb636b23279961`
- r5: "Read assistant-claims.md in this directory and do what it says with the file input.md in this directory. Write
  answer.json in this directory. Do not read, list or search anything outside this directory."
  `8107294ae7d217fee3009ffcd0c11b9a434b1d85b21786783e73337d9642c4c1`
- resolution: "Read resolve.md and companion.md in this directory and do what they say with the files listed in
  files.txt in this directory. Write resolution.json in this directory. Do not read, list or search anything outside
  this directory." `b271435ba0054cb125023e3d12656f75013b04382b3eb1a156793636b9bfe423`
- attribution (defined, never used): "Read attribute.md and companion.md in this directory and do what they say with
  the file input.md in this directory. Write attribution.json in this directory. Do not read, list or search anything
  outside this directory." `c1edc9e89402b24543f3fc029bbf8b9190b7ce2dfb2c3f9ecb767bd408c1dcb2`

These are the same sentences, with the same hashes, as the first two-arm attempt's scoring.

**Session table, summarised.** 29 Sonnet sessions in all, every one exit 0:

| Role | c1 | c2 | Redone |
| --- | --- | --- | --- |
| first | 1 (s1) | 1 (s17) | 0 |
| second | 12 (s2–s13) | 11 (s18–s28) | 1 |
| R5 | 2 (s14, s15) | 0 | 0 |
| resolution | 1 (s16) | 1 (s29) | 0 |
| attribution | 0 | 0 | 0 |

- **The redo.** Session 2 (second review, c1, C101) exited 0 **without writing its output**. That is a missing
  output, so one fresh session (13) redid that one output, and it validated.
- **No refusals.** No output was refused by a pipeline command, and no second refusal occurred.
- **Durations.** Sessions took 6–38 s each, in line with the earlier attempts' scoring sessions (8–44 s).

| Session | Role | Key | Item | Exit | Output sha256 | Validated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | first | c1 | verdicts | 0 | f248e145…7d30d | yes (`verdicts`) |
| 2 | second | c1 | C101 | 0 | none (missing) | no: redone |
| 3–12 | second | c1 | C102–C111 | 0 | in `sessions.jsonl` | yes (shape check) |
| 13 | second (redo) | c1 | C101 | 0 | a3ecbbeb…dc3a | yes (shape check) |
| 14, 15 | r5 | c1 | C107-A.1, .2 | 0 | 585a21cd…191df (both) | yes (`r5-check`) |
| 16 | resolution | c1 | resolution | 0 | c3773694…5437 | yes (`tally`) |
| 17 | first | c2 | verdicts | 0 | 1482a68d…9140 | yes (`verdicts`) |
| 18–28 | second | c2 | C201–C211 | 0 | in `sessions.jsonl` | yes (shape check, then `actions-digest`/`tally`) |
| 29 | resolution | c2 | resolution | 0 | ca3d163b…2356 | yes (`tally`) |

## Hashes

- `gate-c5.json` `d11d9eff75b8a35fc34d096606eafe2e2a8901abdc093da3b1dafc9e84eead59`
- `tally-c1.json` `5a2f3c26f88b05e3e2bb4ffda99e549c45ea19ef6a6d38e5220d4f942af075e1`
- `tally-c2.json` `148a083b8126c96705dfc4a0dadee2d10f3b0bb5970784033d02793eeddab3a3`
- `sealed_scenario_c1.json` `10959be62061394f2b290c7deb25d87294203bd17f5df1e6ee7729e845a271a6`
- `sealed_scenario_c2.json` `d800fc0eff14a6bc7b031ecc7d520689ca40ecef8b7d4084c78c87fc82d3688f`
- `blind_scenario_c1.md` `cd025d9e6284c31ed8cc10b5d90e14ec166d813b5f53facfef00d338b0fbd780`
- `blind_scenario_c2.md` `3cf4347229b12cbebc66e4e42a31e47af96f9faede0f7dbb2fb4e900d1842962`
- `verdicts-c1.json` `f248e145…7d30d`; `verdicts-c2.json` `1482a68d…9140`
- `resolution-c1.json` `c3773694…5437`; `resolution-c2.json` `ca3d163b…2356`
- `actions-c1.json` = `actions-c2.json` `006ed42bc687aeebe2ad61a9b37e0a4ff854dbdd0ce391dd4f3ba4be8a35babc` (both
  have empty `replies`)
- `r5-c1/C107-A.json` `7869b5391b36831c7582368a25144f35adab0af046b1e282498eef3a37ad12dc`

## Refusals, deviations, doubts

1. **Refusals:** none. The one irregular event is the missing output of session 2, redone once as the rule allows.
2. **Scenario session ids printed (deviation).** While listing the fields of the four `page-actions.jsonl` files to
   confirm kinds and outcomes, my command printed each record's scenario `session` id. Those are four short session
   slugs of the held-out scenarios. No message, argument or detail field was printed. From then on positions were
   taken as indexes only (`coverage_map.py`).
   - Case ids, which carry short slugs, also appear in the pipeline's own outputs I read (`split`, the session
     table). The brief allows ids, and this report uses case prefixes only.
3. **Content I opened.** Nothing else held-out was opened. That excludes sheets, case files, results, verdict or
   review reasons, R5 or attribution inputs, session logs, the sealed mappings' contents and the tally stdout.
4. **Marks and rule codes read.** I read, as numbers and rule codes only:
   - the first and second reviews' mark lists, through `check_second.py` and one script printing mark lists;
   - the resolution's `remove`/`add`/`rules` fields. No reasons were read.
5. **Identical R5 answers.** The two R5 checkers' answers for C107-A are byte-identical (same sha256). That is
   possible for a short, deterministic JSON answer, but it is worth noting. Their result is `false`.
6. **Only one mark in the whole review.** In 22 cases, the one mark was an added type 4, removed by R2. Both arms
   ending with 0 standing critical errors makes `reference_critical` 0. With no `P` critical either, the
   host-allowance condition was not tested by this result.
7. **The model was not confirmed from the logs.** Every session was started with `--model sonnet` per the kit's
   argv. I did not confirm the served model, which would have meant opening the logs.
8. **Order of the last steps.** `gate` ran before `remarks`, as step 4 orders ("After the gate: run `remarks`").
9. **c2's empty R5 and attribution steps.** `r5-check` for c2 ran with zero inputs, and no answers folder existed
   (`{"results": {}}`). No attribution folder was needed for either key.
10. **Nothing was changed** in `/home/yichen/src/memBrain` or in any tracked file of the clone. There was no paid
    call, no API key, no pytest and no push. Run directories, the ledger and control files are untouched.
