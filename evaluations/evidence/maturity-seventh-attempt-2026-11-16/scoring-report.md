# Blind scoring of the seventh maturity attempt (`maturity-20261116a`, R4 unit): operator's report

Date: 2026-11-16 (scoring from about 18:00 UTC). Operator: the scoring subagent working from the lead's brief
`attempt7-scoring-brief.md`. This report does not write the public record and does not run the final independent review.

## Result

**The R4 gate passes**: `R4: true`, `acceptance_review.py gate REVIEW s1b s2b --manifest MANIFEST` exited 0.

`review/gate.json` (sha256 `95842bc9b7cb40b7c56db0d36b3b1bad6ac3356b7d25f0f6382cdef786b48891`), verbatim:

```json
{
 "arms": {
  "P": {
   "total": 16.5,
   "reference": 16.0,
   "not_worse": true,
   "memory_caused": [],
   "host_caused": [
    "S201-tooth-eve/A"
   ],
   "reference_critical": 2,
   "host_within_reference": true,
   "passes": true
  }
 },
 "attributions": {
  "S201-tooth-eve/A": {
   "answers": [
    "host",
    "host"
   ],
   "cause": "host"
  }
 },
 "frozen_arms": [
  "P",
  "F"
 ],
 "gated": [
  "P"
 ],
 "reference_arm": "F",
 "R4": true,
 "manifest": {
  "attempt_id": "maturity-20261116a",
  "sha256": "a27d7ca878cd86483b79e0e682fb788847bafa4f41647b98b44304216aa534de",
  "scenarios": [
   {
    "key": "s1b",
    "path": "evaluations/.maturity-heldout-20261116a/s1b/scenario_s1b.py",
    "sha256": "aec260c21694c4a9c10fde3825fbe04e1fba5998894fc572449875140c8beab6"
   },
   {
    "key": "s2b",
    "path": "evaluations/.maturity-heldout-20261116a/s2b/scenario_s2b.py",
    "sha256": "4c6c0404fab7de758f9592fd65b76c3d4f949761a85e52b5d3c902b214a15358"
   }
  ]
 }
}
```

## Totals (out of 11 per scenario per arm)

| Scenario | P literal | P resolved | F literal | F resolved |
| --- | --- | --- | --- | --- |
| `s1b` | 9.0 | 9.0 | 7.0 | 7.0 |
| `s2b` | 7.5 | 7.5 | 7.5 | 9.0 |
| **Overall (resolved)** | | **16.5** | | **16.0** |

`P` 16.5 ≥ `F` 16.0 − 1.

## Standing critical errors (after resolution)

- **P: 1 reply.** `S201-tooth-eve/A`, type 1. Attributed **host** by both attributors (answers `host`, `host`).
- **F: 2 replies.** `S110-offrecord-offer-not-recalled/B` (type 2) and `S201-tooth-eve/B` (types 1 and 4).
- Host-caused `P` replies (1) ≤ `F` replies with a standing critical error (2). No memory-caused `P` reply.

Resolution changes (all type 4, all rule R2, all removals): `s1b` none (empty resolution); `s2b` three:
`S203-mom-arrival-corrected/B` (F), `S210-off-record-not-remembered/A` (P; its base score was already 0, so its score
does not change) and `S210-off-record-not-remembered/B` (F; raises F's `s2b` total from 7.5 to 9.0).
R5: `s1b` had no reply with a candidate type 4 mark (`r5-inputs` wrote no file); `s2b` had four inputs (`S201-B`,
`S203-B`, `S210-A`, `S210-B`), all eight checker answers valid on first try, **none cleared** (`type4_cleared` false
for all four). No R5 result changed a mark.

Freeze-review condition (host pauses): no run directory has a `host-pauses.jsonl`, and validity lists 0 turns
unrecorded by the host's own pause in every run. So for the one `P` reply with a standing critical error
(`S201-tooth-eve/A`, scenario `s2b`), **no listed turn precedes it**; both attributors ruled `host`. The
cross-check of listed positions against `diagnose`'s tool codes has nothing to check (no listed turn).

## Memory remarks (`remarks`, after unsealing; 28 phrases)

| Scenario | Arm | Case replies with a remark | Share | All replies with a remark | Share |
| --- | --- | --- | --- | --- | --- |
| `s1b` | P | 0 of 11 | 0.0 | 2 of 61 | 0.033 |
| `s1b` | F | 0 of 11 | 0.0 | 1 of 61 | 0.016 |
| `s2b` | P | 0 of 11 | 0.0 | 1 of 63 | 0.016 |
| `s2b` | F | 0 of 11 | 0.0 | 0 of 63 | 0.0 |

## Step 1: verification and validity

- Clone head `c5232a043d650824c7d12982893d876e88d57877`, tree clean (`git status --porcelain --untracked-files=all`
  empty) before and after scoring; manifest sha256 `a27d7ca8…534de` matches.
- `control/execution-summary.out`: `result: complete`, `eligible: ["R4"]`, `pairs: {"R4": "complete"}`, `s1b` and
  `s2b` `valid`, no stop; `control/execution-done`: `driver exit 0`, `ports closed`, `2026-11-16T17:56:10Z`.
- `validity --scenario <manifest path> --persona estj RUN_P RUN_F` (as the driver runs it), re-run by me: both
  scenarios `valid: true`, `problems: []`, exit 0.

| Run | Unrecorded by the host's own pause | Replies with tool-call markup | Empty replies retried | Tool errors shown to host |
| --- | --- | --- | --- | --- |
| `s1b-P` | 0, positions [] | 0, positions [] | 0 | 0 |
| `s1b-F` | 0, positions [] | 0, positions [] | 0 | 0 |
| `s2b-P` | 0, positions [] | 0, positions [] | 0 | 0 |
| `s2b-F` | 0, positions [] | 0, positions [] | 0 | 0 |

Reference largest prompt tokens: `s1b` 5,218; `s2b` 8,277.

## Reviewer sessions

All sessions were fresh Claude Code 2.1.322 print sessions with exactly `session-commands.json` → `claude.argv`, model
`sonnet` (allowed-models `["sonnet"]` checked), each in a new numbered directory
`/home/yichen/.local/state/acceptance-sessions/20261116a-review/sNNN` (names neither product nor arm), environment
limited to the kept variables (observed on session 1 via `/proc`: HOME, LANG, LOGNAME, PATH, TERM, USER; LC_ALL and
TMPDIR were unset in the operator's environment so were not passed). Only the role's instruction file and its input
were copied in; logs went to `PRIVATE_ROOT/logs/scoring/sNNN.log` (never opened); each directory was emptied after its
output was moved (all 37 directories are now empty). At most four ran at once. Launcher:
`/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/scoring/sessions.py`, jobs from `make_jobs.py`, records in
`scoring/sessions.jsonl`, prompts in `scoring/prompts.json`.

Prompts (one fixed sentence per role) and sha256:

| Role | Prompt | sha256 |
| --- | --- | --- |
| first | Read first.md in this directory and do what it says with the sheet file sheet.md in this directory. Write verdicts.json in this directory. Do not read, list or search anything outside this directory. | `1bc265b07fc000de88d7e202fa5393b4b3a999a562160a48abcaefbcd2b44270` |
| second | Read recheck.md in this directory and do what it says with the case file case.md in this directory. Write recheck.json in this directory. Do not read, list or search anything outside this directory. | `7a0c01c9d0a248899df71f627d68a9fcd40ecadfacef71d9b06c72457b131906` |
| R5 | Read assistant-claims.md in this directory and do what it says with the file input.md in this directory. Write answer.json in this directory. Do not read, list or search anything outside this directory. | `8107294ae7d217fee3009ffcd0c11b9a434b1d85b21786783e73337d9642c4c1` |
| resolution | Read resolve.md in this directory and do what it says with the files listed in files.txt in this directory. Write resolution.json in this directory. Do not read, list or search anything outside this directory. | `52fa147d5826822bdbf1357a65866c03ed71d55ed8438c87581dee99ad5ea736` |
| attribution | Read attribute.md in this directory and do what it says with the file input.md in this directory. Write attribution.json in this directory. Do not read, list or search anything outside this directory. | `ccc721009c8afabb18c845a22f36a8b58e0af9c7942ee582c869cb0846313f6b` |

Summary: **37 Sonnet sessions** in all, all exit 0.

| Role | `s1b` | `s2b` | Redone |
| --- | --- | --- | --- |
| First review | 1 | 1 | 0 |
| Second review | 11 | 11 + 1 redo | 1 (`S206-saturday-reunion-cancelled`) |
| R5 checkers | 0 (no input) | 8 (4 inputs × 2) | 0 |
| Resolution | 1 | 1 | 0 |
| Attribution | 0 (no gated critical reply) | 2 (1 input × 2) | 0 |

Full table (ids only):

| # | Role | Key | Item | Exit | Output sha256 | Validated |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | first | s1b | first | 0 | `33bc1fa1…6402` | yes (`verdicts`, 0 renamed) |
| 2–12 | second | s1b | S101–S111 (one each) | 0 | see `scoring/sessions.jsonl` | yes (provisional `tally`, then final `tally`) |
| 13 | resolution | s1b | resolution | 0 | `ca3d163b…2356` | yes (`tally --manifest`) |
| 14 | first | s2b | first | 0 | `ce991300…89ba` | yes (`verdicts`, 0 renamed) |
| 15–19, 21–25 | second | s2b | S201–S205, S207–S211 | 0 | see `sessions.jsonl` | yes |
| 20 | second | s2b | S206-saturday-reunion-cancelled | 0 | none (no output written) | **refused** (`tally`: file not found) |
| 26 | second (redo) | s2b | S206-saturday-reunion-cancelled | 0 | `ef98b0c9…f84d` | yes |
| 27–34 | R5 | s2b | S201-B, S203-B, S210-A, S210-B × 1, 2 | 0 | see `sessions.jsonl` | yes (`r5-check`, no redo) |
| 35 | resolution | s2b | resolution | 0 | `1a8d4b14…22be3` | yes (`tally --manifest`) |
| 36–37 | attribution | s2b | S201-A.1, S201-A.2 | 0 | see below | valid (gate read both as `host`) |

Attribution output hashes: `9d0546c71225d4955f17dac06e6198d851ec01eca0e75f8201f59097ff16054c`,
`e978fc8b8afb7530dac71b9e8bf2e82812e20990d881d7b5ccebcd4a2f5125a8`.

## Refusals, deviations and doubts

1. **One refused output, redone once, accepted.** The second reviewer for `S206-saturday-reunion-cancelled`
   (session 20) exited 0 but wrote no `recheck.json`; the pipeline (`tally`) refused it (missing file). One fresh
   session (26) redid it and its output was accepted. This was the only refusal; no output was refused twice, so the
   stop rule did not trigger. I did not open session 20's log or directory, so why it wrote nothing is unknown.
2. **Extra validation run before resolution.** The R4 runbook has no command that validates second reviews before
   `tally`. To catch a malformed second review before the resolution reviewer saw it, I ran `tally … --manifest`
   once per scenario before resolution with **stdout discarded** (it names arms) and only the exit code and stderr's
   last line read, then deleted the provisional `tally-KEY.json` it wrote. The final `tally` was run after resolution
   as the runbook says.
3. **`tally` prints resolution reasons.** Its stdout lists rows with arms and the resolution reviewer's free-text
   reason. I redirected it to `review/tally-KEY.stdout` (mode 600) and did not read it; I read the totals and the rows'
   case, label, arm, base and marks from `tally-KEY.json` by a script that does not print reasons. The resolution
   entries were read only as rule tags and mark numbers.
4. **Case ids are descriptive.** `split` prints case ids such as `S206-saturday-reunion-cancelled`; they carry
   topic words from the held-out scenarios. They are what the pipeline prints and the brief asks for (ids only); the
   lead should consider this when publishing.
5. **Session environment.** I followed the brief exactly (only the eight kept variables). The kit's `launch.py`
   used for authoring also sets `MEMBRAIN_DIRECTORY` to an empty read-only directory as a second barrier behind
   `--safe-mode`; my launcher did not set it. A memBrain plugin data directory exists in the owner's Claude Code
   configuration (`~/.claude/plugins/data/membrain-inline`); the isolation probe of 2026-11-15 observed that
   `--safe-mode` loads no plugin, and I did not re-verify that.
6. **Session directories and file names.** Because the sessions have only Read, Write and Edit (no listing tool),
   the resolution reviewer was given a `files.txt` (written by `make_jobs.py`, names only) listing its inputs: the
   scenario as `scenario.py`, `verdicts-KEY.json`, `recheck-KEY/<case>.json` and `.md`, `r5-KEY/<prefix>-<label>.json`.
   Sheets and inputs were renamed in the session directory (`sheet.md`, `case.md`, `input.md`); content was copied
   byte for byte.
7. **Two identical R5 answers.** `S201-B.1` and `S201-B.2` (sessions 28 and 29, separate directories) wrote
   byte-identical outputs (141 bytes each). Plausible for a short structured answer; I did not open them.
8. **Order.** Each key's steps ran in the runbook's order, `s1b` fully before `s2b` (no interleaving). Attribution
   for `s1b` had no input. `remarks` ran for both scenarios before `gate`; both are after unsealing.
9. Validity for `s1b` and `s2b` was re-run and consulted; `diagnose` was not run (not needed: nothing was invalid).

**Did anything print content it should not?** No. Every command I read printed counts, codes, positions, case ids,
file names, hashes or refusals. The one command that prints reviewer free text (`tally`) was redirected unread (item 3).
I did not open any scenario file, run-directory result, blinded sheet, case file, R5 or attribution input, reviewer
output or session log.

## Hashes

| File (under `PRIVATE_ROOT`) | sha256 |
| --- | --- |
| `review/gate.json` | `95842bc9b7cb40b7c56db0d36b3b1bad6ac3356b7d25f0f6382cdef786b48891` |
| `review/tally-s1b.json` | `8bcf98495fbf1d103abbde3d74d28efee2092f772101a1978ba3d9e9310c7610` |
| `review/tally-s2b.json` | `44a2b86c38546bbe1830577fe0003158f32640fddbd59ac9192a4355d72da9da` |
| `blind/sealed_scenario_s1b.json` | `ad0cd29fde7a8d2c30bc9134abc4c6e2f368f5e64b1b79751267518237cf17da` |
| `blind/sealed_scenario_s2b.json` | `e0ad032fa8123f65b7f8ca38faf763b3a233e982d29c71cea0271d83fb9c6e82` |
| `review/verdicts-s1b.json` | `33bc1fa1c4ec1a8a58d342b087c74afc3d4d6e3022465fb7433d01fc835c6402` |
| `review/verdicts-s2b.json` | `ce99130097ed4e32d2aad57b2ac4e08993e8b9b078eb6f145c86ccd5471a89ba` |
| `review/resolution-s1b.json` | `ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356` |
| `review/resolution-s2b.json` | `1a8d4b148870bbfec9b3223f83ae2116a27ef93de6d8aea921a0e00200022be3` |

`PRIVATE_ROOT` = `/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/clone/evaluations/.maturity-heldout-20261116a`;
`review/` and `blind/` are mode 700. No tracked file of the clone was edited, nothing in `/home/yichen/src/memBrain`
changed, no paid call, no API key read, no pytest, no push. Ports 8893 and 55533 closed; no reviewer session remains.
