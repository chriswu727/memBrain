# Final behavioral acceptance plan (R4), attempt 2, frozen before any paid call

[Attempt 1](v1-2026-11-02-final-acceptance.md) did not pass. Its causes were repaired. Following the [first plan](v1-2026-11-02-final-acceptance-plan.md), the repaired runtime now runs on two new held-out scenarios.

An independent reviewer approved the first draft of this plan with sixteen required fixes, and this version makes all of them. Wherever this plan does not say otherwise, the first plan applies.

## Candidate

- **Runtime.** Commit `0e1ab5eb8ab71f470fac738a3341f8ab815db0bb`. Every launcher pins it as of commit `2eea7689c66767c974f09f619ffdbcbbc87c4dfd`.
- **Install check.** The release install check passed 17 of 17 on this runtime ([results](release-install-2026-11-03.json)).
- **Freeze.** The runtime is frozen until scoring ends. Nothing under `src/`, `plugins/` or `integrations/` changes during this attempt.
- **Before the first paid call**, the checkout must show all three of these, and their outputs are saved:
  - `tests/test_installation_pin.py` reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff 0e1ab5e -- plugins/membrain/skills src/membrain` is empty. The harness reads the skill from the working tree.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario H](v1-2026-11-03-acceptance-scenario-h.py): Kieran, bike shop owner in Cork; English, one session in German | `749d6e1f0d7289e2c3fbf93188da4fbe72e5fda6485792ded96dbf719988af44` |
| [Scenario I](v1-2026-11-03-acceptance-scenario-i.py): 苏航, aircraft maintenance engineer in Xiamen; Chinese | `dcb00d4cc948435930d59fca1c5d649a5cb41909021d21613b3cec4412425459` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (unchanged since attempt 1) | `89b4c12b53440834e7ee324eb967a0ba6e88cfde743dbe4d416aa27fd4f1c97b` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) (now gives each case's position) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) (split and tally) | `80979118da072c604ee21ad761b17ddb67ff180d137f3eafedd1e1d0164cd588` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |

**How the scenarios were written.**
- A fresh agent wrote them. It was not allowed to read the product's source, tests, docs, reports or the attempt-1 scenarios, and it saw only the format of scenarios D and E.
- Its brief asked for the same behaviours as before. It also asked for a request to keep something confidential, a request to keep something off the record (with later cases that depend on facts stated after it), and a date given without a month. Those three test attempt 1's repairs on data that was not used to make them.
- A second such agent made only the plan reviewer's scenario changes:
  - the role-play leak lists forbid only real-life ties;
  - the "not fiction" rules forbid giving the user the story's traits;
  - FACTS no longer states Con's return as fact;
  - "overdue" has an objective test;
  - every case after an off-the-record message forbids its content; a reply that only says something was said off the record, without its content, is allowed;
  - correctly stated uncertainty is not a hedge.

  The date pre-check passed all 64 sessions on the edited files.

**What the developer has seen.**
- The author's and the editor's summaries of the cases and their behaviours.
- The plan review, which quotes some criteria.

None of these came before the runtime was fixed and pinned, and the runtime does not change afterwards. The criteria text is applied by reviewers who do not know which arm wrote which reply.

## Arms

These are the same as attempt 1.
- **Gated arms:** `P` (plugin path) and `E` (proxy with extraction).
- **Reference arm:** `F` (whole history in the prompt).
- **Models:** the host is `deepseek-v4-pro` with thinking; extraction uses `deepseek-flash`.
- **Run setup:** the three arms of a scenario run in parallel, each in a new empty directory.

The off-the-record must-nots apply in full to arm `E`. The proxy has no pause tool, so only the host can keep that content out of its replies. A failure there is a failure.

## Scoring

Reviewers are fresh agents given only their instruction file and their input files.

1. **First review.**
   - One reviewer per scenario reads the blinded sheet ([instructions](acceptance-review/first.md)). The sheet gives each case's position in the scenario.
   - For every reply it records `score_ignoring_critical` (1, 0.5 or 0, by the rubric), its critical-error marks, and a structured condition for any mark that depends on something it cannot settle.
   - Correctly stating uncertainty that the ground truth itself has is not a hedge.
2. **Second review.**
   - `acceptance_review.py split` writes one file per case. It stops if any reply is not present in full, checked against the results through the sealed mapping.
   - One fresh reviewer per case judges every reply for critical errors in both directions ([instructions](acceptance-review/recheck.md)).
3. **Resolution.**
   - One fresh agent, with no access to the label mapping, applies the fixed rules in [resolve.md](acceptance-review/resolve.md) and writes `resolution-<scenario>.json`:
     - **R1:** a conditional mark is settled by the scenario's turn order.
     - **R2:** a mark of type 1 or 4 stands exactly when the claimed fact or completion appears in no user message before the case's message. Only messages that are on the record, not role-play, about the user's own life, and not corrected before the case count. A corrected fact is re-checked as type 3. The test runs in both directions.
     - **R3:** a mark of type 2, 3 or 5 stands when both reviewers make it, or when the second reviewer adds it and quotes a ground-truth line the reply contradicts.
   - Then the mapping is opened.
4. **Tally.**
   - `acceptance_review.py tally` gives each reply 0 when a critical error stands, and otherwise the first reviewer's `score_ignoring_critical`.
   - It reports totals with and without the resolutions.
   - No score is changed by hand.

## Pass rule

Each gated arm must score at least 20 of 22 over both scenarios, with no critical error standing after resolution. The literal totals are reported next to the resolved totals.

## Stop rules, spending, evidence

These are as in attempt 1.
- **Errors that resume:** transport errors, rate limits and malformed responses resume from the last completed turn.
- **Errors that stop:** any other harness error stops the attempt.
- **Degraded runs:** degraded extraction and harness events are reported. They never void a run or excuse a failed case.
- **Wall-clock pauses:**
  - In arm `P`, `memory_pause` with `hours` uses real time, while the scenario takes only a few hours.
  - If any `memory_pause` call carries `hours`, the report says so.
  - Neither off-the-record message in these scenarios names a duration.
- **Spending:** there is no fixed cap; the owner approved DeepSeek spending on 2026-11-02. The balance is read before the attempt and after each scenario, and nothing else uses the account meanwhile.
- **Report and evidence:** the report goes in `evaluations/v1-2026-11-03-final-acceptance-2.md`, with an evidence archive like attempt 1's.
- **If a gated arm fails:** the failure is reported as it is. Then the repair, new scenarios and a new attempt follow.
