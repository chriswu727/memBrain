# Final behavioral acceptance plan (R4), attempt 2, frozen before any paid call

[Attempt 1](v1-2026-11-02-final-acceptance.md) did not pass. Its causes were repaired. Following the [first plan](v1-2026-11-02-final-acceptance-plan.md), the repaired runtime now runs on two new held-out scenarios. This plan keeps the first plan's arms, rubric, critical errors, pass rule and rules after unblinding unless a section below says otherwise. Every change is listed in [Changes from attempt 1](#changes-from-attempt-1).

## Candidate

- **Runtime.** Commit `0e1ab5eb8ab71f470fac738a3341f8ab815db0bb`. Every launcher pins it as of commit `2eea7689c66767c974f09f619ffdbcbbc87c4dfd`.
- **Freeze.** The runtime is frozen from now until scoring ends. Nothing under `src/`, `plugins/` or `integrations/` changes during this attempt.
- **Pin check.** As before, `tests/test_installation_pin.py` must report 2 passed in the checkout used, and its output is saved.
- **Repairs.** A runtime repair means a new candidate and new scenarios.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario H](v1-2026-11-03-acceptance-scenario-h.py): Kieran, bike shop owner in Cork; English, one session in German | `d78cb3287c886ab040d09ed93c8c077051e41c9f039b760a42efc5d6ac04f4ec` |
| [Scenario I](v1-2026-11-03-acceptance-scenario-i.py): 苏航, aircraft maintenance engineer in Xiamen; Chinese | `521a4019e79ea77ff06d0a9ac9ebf027ff93b9479dabcacc048f14581c91007a` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (unchanged since attempt 1) | `89b4c12b53440834e7ee324eb967a0ba6e88cfde743dbe4d416aa27fd4f1c97b` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `9759d61558d9fb521cff60cc437eb5fc516e4253f0fa0fafc1f540570f9955c6` |

**How the scenarios were written.**
- A fresh agent wrote them. It was not allowed to read the product's source, tests, docs, reports or the attempt-1 scenarios, and it saw only the format of scenarios D and E.
- Its brief asked for the same behaviours as before. It also asked for a request to keep something confidential, a request to keep something off the record (with later cases that depend on facts stated after it), and a date given without a month.
- Those three were added so that attempt 1's repairs are tested on data that was not used to make them. The report states this.

**What the developer has seen.** The author's summary named each case and its behaviour. The developer saw that summary, but not the criteria text or FACTS. The runtime had already been fixed and was pinned before then, and nothing in the runtime changes afterwards.

**Date pre-check.** The free date pre-check passed all 64 sessions of H and I. It is run again, and its output saved, before the first paid call.

## Arms, scoring, pass rule

These are the same as in [attempt 1's plan](v1-2026-11-02-final-acceptance-plan.md).
- **Arms:** `P` (plugin path) and `E` (proxy with extraction) are gated; `F` (whole history) is the reference. The host is `deepseek-v4-pro` with thinking, and extraction uses `deepseek-flash`.
- **Run setup:** the three arms of a scenario run in parallel, each in a new empty directory.
- **Pass rule:** each gated arm must score at least 20 of 22 over both scenarios, with no critical error standing. The reviewers, rubric and critical-error types are unchanged.

## Changes from attempt 1

1. **Splitting cases for the second review.** The sheet is split only at the case headings the blinding script writes. Before any re-check runs, each case file must show all three replies, `### A`, `### B` and `### C`. Attempt 1's first split cut replies short.
2. **Resolution rules, fixed now and applied before the labels are unsealed** (attempt 1 had to settle these cases as they came up):
   - **Conditional marks.** A mark that a reviewer makes conditional on the order of events is settled by the scenario's turn order (`SESSIONS_LONG`, then the turn index). If the condition is false, the mark does not stand, and the reply gets the score the first reviewer gave for that case (or its score without the mark, if none was given).
   - **Uncited additions.** A mark the second reviewer adds stands only if it cites a ground-truth line that the reply contradicts. An addition that rests only on a fact missing from the ground truth does not stand.
   - **Invented-fact marks.** A mark of type 4, whether from the first or the second reviewer, is checked against the user's own messages in the scenario. If the user stated the fact, the mark does not stand.
   - **Recording.** Each resolution is written down with its reason, applies the same way whichever arm wrote the reply, and is made before the mapping is opened. The report gives totals both with and without the resolutions.
3. **Spending.** There is no fixed cap: the owner approved DeepSeek spending on 2026-11-02. The balance is read before the attempt and after each scenario, and nothing else uses the account while the attempt runs.

## Stop rules and evidence

These are as in attempt 1.
- **Errors that resume:** transport errors, rate limits and malformed responses resume from the last completed turn.
- **Errors that stop:** any other harness error stops the attempt.
- **Degraded runs:** degraded extraction and harness events are reported. They never void a run or excuse a failed case.
- **Report and evidence:** the report goes in `evaluations/v1-2026-11-03-final-acceptance-2.md`, with an evidence archive like attempt 1's.
- **If a gated arm fails:** the failure is reported as it is. Then the repair, new scenarios and a new attempt follow.
