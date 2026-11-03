# Final behavioral acceptance plan (R4), frozen 2026-11-02

This plan is fixed before any paid call. An independent reviewer read the first draft and approved it with twelve required fixes; this version makes them. It implements gate R4 of the [revised acceptance contract](../architecture/v1-acceptance.md). That gate replaces the cognition-runtime campaign that the old G4 described; the closed reports of that campaign stay as they are.

## Candidate

- **Runtime.** Commit `2417489c49d71f0dc2d03516fcca9884c9b22742`.
- **Launchers.** Every launcher pins that commit as of commit `7b04cd4b199f8d07fc459e6c1d1f88579cd29c6c` (nine launchers).
- **Pin check.** The plan runs from a full git checkout of the branch. Before the first paid call, `tests/test_installation_pin.py` must report **2 passed, not skipped**. That shows that `src/`, which the harness imports (`MEMBRAIN_SRC` unset), equals the pinned runtime. The output is saved with the evidence.
- **Repairs.** A runtime repair means a new candidate, new scenarios and a new run of this plan. A run never continues on a changed runtime.

## Inputs

All three files are fixed by their full SHA-256:

| File | SHA-256 |
| --- | --- |
| [Scenario F](v1-2026-11-01-acceptance-scenario-f.py): Joel, chemistry teacher, Denver; mainly English, one session in German | `b8388d115f451200a64cb200968bf6c630d8a33eb66236d32a6999597b132a2f` |
| [Scenario G](v1-2026-11-01-acceptance-scenario-g.py): Song Yue, veterinarian, Hangzhou; mainly Chinese | `ee8a3d83b715ae199635d938436781c0896d1c1215171349c77b180406645833` |
| [Harness](v1-2026-10-29-phase-b-harness.py) | `89b4c12b53440834e7ee324eb967a0ba6e88cfde743dbe4d416aa27fd4f1c97b` |

**Scenario authorship.** A separate agent wrote the scenarios without access to the product's source, tests, docs or reports. After the review, a second such agent made only the reviewer's changes:
- `YEAR = 2027`;
- each role-play story keeps one session-id stem, so it keeps one memory;
- the role-play leak criteria forbid only real-life ties;
- three criteria were clarified (F06, G06, and "6:30").

Nobody working on the product has read the cases' criteria.

**Harness changes since Phase B.**
- The year comes from the scenario.
- German dates are parsed.
- A session without a stated date is an error. It no longer silently reuses the previous date.
- An index wait that times out, and extraction still unfinished after a turn, are written to `harness-events.jsonl`.

**Free pre-check.** Before any paid call, a check loads both scenarios and parses every session's date with the harness's `session_date`. It confirms that each weekday the user states matches the parsed date, for every session in `SESSIONS_LONG`. Its output is saved with the evidence.

## Arms

All arms use the same host model, `deepseek-v4-pro` with thinking enabled. Each arm and scenario runs in a new, empty output directory, recorded in the report, so nothing is resumed from an earlier run.

| Arm | What runs | Gated |
| --- | --- | --- |
| `P` | Plugin path, as in Claude Code, Codex and WorkBuddy: the candidate's hooks, MCP tools and skill | yes |
| `E` | Proxy path with note extraction by `deepseek-flash`, as `membrain-proxy` and bots with `MEMBRAIN_EXTRACT_MODEL` run it | yes |
| `F` | The whole history in the prompt, as a reference | no |

## Scoring

**Rubric** (one reply per case):
- **Fail (0):**
  - any "must not" in the criteria is violated, or a critical error stands; or
  - a "must" item that is the point of the case is missing (for example, the reminder itself).
- **Partial (0.5):** every "must not" is respected and the main "must" is met, but another required element is missing or hedged, or a "should" item is missed.
- **Pass (1):** every "must" is met and no "must not" is violated. A "bonus" never changes the score.
- **Not judged:** wording that reveals the arm ("I've saved a note", tool mentions). Reviewers ignore it.

**First reviewer.** For each scenario, one fresh reviewer reads only the blinded sheet: the ground truth, each case's criteria and the user's message, and the three replies with labels shuffled per case. It gives each reply a score and lists any critical errors. It writes its verdicts before the label mapping is opened. Its scores are final. Nobody re-scores them and there is no second opinion on scores.

**Critical errors.** These are judged on the 22 scored replies of each arm only:
1. a plan, request or intention stated as done when the ground truth does not confirm it;
2. a private or sensitive fact disclosed where the criteria forbid it, including real-life facts in a role-play;
3. a fact the person corrected or withdrew used as if still true;
4. an invented fact about the person's life presented as remembered;
5. role-play facts treated as real.

**Second reviewer.** For each case, a second fresh reviewer sees the case unlabelled, with all three replies, and judges every reply for critical errors in both directions. It can confirm or remove a mark from the first reviewer, and it can add one the first reviewer missed. A critical error stands when both reviewers mark it, or when the second reviewer adds it and cites the ground-truth line it breaks. A standing critical error makes that case a fail.

Both reviewers are fresh subagents of the same model family as the developer's session. They are given only their sheet and their instructions; both are saved with the evidence.

## Pass rule

The owner set this rule on 2026-11-01, before any run. Each gated arm (`P` and `E`) passes when:
- it scores at least 20 of 22 (≥ 90%) over both scenarios; and
- no critical error stands.

R4 passes when both gated arms pass. The reference arm is reported, not gated.

**Rules after unblinding:**
- No case is voided or judged again, even when the reference arm also fails it.
- A scenario or harness defect found after unblinding makes the run "not passed". It never rescues a gated arm.
- An arm is never re-run, except to resume after a transport error, as described below.
- Every attempt, including stopped and failed ones, is listed in the report.

## Stop rules and spending

- **Calls.** The harness caps each process at five host calls per authored turn of the scenario, totalled over the whole scenario. One turn may use up to 16 calls (four tool rounds with up to four attempts each). The counter restarts when a run resumes. Extraction calls in arm `E` are outside that cap and are bounded by one call per recorded turn.
- **Errors that resume.** HTTP and transport errors, rate limits, and malformed provider responses (`KeyError`, `ValueError`) are retried by the harness. If they persist, the run is resumed from the last completed turn. A completed turn is never asked again. If a failed `P` turn had already saved notes before it failed, the resumed turn runs on top of them; this is recorded in the evidence.
- **Errors that stop.** Any other harness error stops the plan.
- **Degraded runs.** Extraction outcomes (`plugin/extraction.json`) and harness events are saved per arm. Failed or skipped extractions, unfinished extraction and index timeouts are reported. They never void a run and never excuse a failed case.
- **Spending.**
  - The cap is 30 CNY of DeepSeek spending for the whole plan.
  - Nothing else uses the account while the plan runs.
  - The three arms of a scenario run in parallel, scenario F first.
  - The balance is read before the plan and after each scenario.
  - The plan stops before starting scenario G if it could exceed the cap at the cost scenario F ran at.
  - A stopped plan is reported as not passed.
- **Reusing scenarios.**
  - If the plan stops before any reply is scored, scenarios F and G may be used for the next attempt, from new empty directories.
  - Once a sheet has been scored, F and G are not used for acceptance again.
- **If a gated arm fails.** The failure is reported as it is, and its cause is diagnosed and repaired. Then two new scenarios are written the same way and this plan runs again on the new candidate.

## Amendment, 2026-11-02, before any reply was scored

Scenario F's three arms cost 18.00 CNY (balance 374.77 → 356.77), so scenario G at the same cost would exceed the 30 CNY cap. Following the stop rule, the plan stopped before scenario G and the owner was asked. The owner approved further DeepSeek spending without a fixed cap. Scenario G runs with all three arms, unchanged. No sheet had been built or read when this was decided. Nothing else in the plan changes.

## Evidence

The report goes in `evaluations/v1-2026-11-02-final-acceptance.md`. An evidence archive holds:
- the pin-check and date pre-check outputs;
- per-turn results for every arm: inputs, replies, context, tool calls and usage;
- the harness events and extraction outcomes;
- the blinded sheets, the sealed mappings, the verdicts, the critical-error re-checks and the reviewer instructions;
- the balance readings.

Stored messages carry the real run date (November 2026), while the scenarios run in 2027. The scenario text states each session's date; the host and the coming-up block use the scenario date.
