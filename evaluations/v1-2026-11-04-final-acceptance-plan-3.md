# Final behavioral acceptance plan (R4), attempt 3, frozen before any paid call

[Attempt 2](v1-2026-11-03-final-acceptance-2.md) did not pass. The [gate review](v1-2026-11-03-gate-review.md) found that the first pass rule could not be met even by the reference arm, which has perfect information, so it measured the host model rather than memBrain. This attempt therefore uses:
- the revised rule;
- a repaired runtime and a fixed harness;
- two new held-out scenarios.

An independent reviewer approved the first draft of this plan with required fixes, and this version makes all of them. Wherever this plan does not say otherwise, [attempt 2's plan](v1-2026-11-03-final-acceptance-plan-2.md) applies.

## Candidate

- **Runtime.** Commit `9a1816af9a3d238bce925450998f4fd0bdd0d0f3`. Every launcher pins it as of commit `fdb3d15e964fa47ff78dd6738b09aedf215e1615`.
- **Install check.** The release install check passed 17 of 17 on this runtime ([results](release-install-2026-11-04.json)).
- **What changed since attempt 2:**
  - coming-up lists any open note with a deadline, and undated open plans;
  - memory and the skill tell the host not to rely on something only planned;
  - extraction files anything with a deadline as a plan.
- **Freeze.** The runtime is frozen until scoring ends.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff 9a1816a -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario J](v1-2026-11-04-acceptance-scenario-j.py) | `3dcc112e5d1cb79dbd01d878a769efb211fb809a468400f701304b8bec1e327f` |
| [Scenario K](v1-2026-11-04-acceptance-scenario-k.py) | `f4137a1cd98c5efd5f3feee156940f540ffb48f76798422bf2a88b6c8a75038b` |
| [Harness](v1-2026-10-29-phase-b-harness.py) | `cde9acddc32f12fe94b00da258957bf71b3706736da1833336ef5450cf51fba0` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) | `b257a55a7ee7180c7221122f44133e88f322539798d1a5364536941985d9eefa` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

**Harness changes since attempt 2:**
- the recorded reply is everything the host wrote in the turn;
- the last tool round offers no tools;
- the transcript no longer stores text twice.

**Scenarios.**
- A fresh agent wrote J and K under the same restrictions as before. A second agent applied the reviewer's eight scenario fixes, working from a findings file the developer does not open.
- **The developer has not seen the cases, the criteria or FACTS.** Both agents and the reviewer reported only case ids, counts and hashes.
- The date pre-check passed all 64 sessions on the edited files. Its full output, which names sessions, goes to the evidence; only its last line is shown to the developer.

## Arms and scoring

These are as in attempt 2:
- arms `P`, `E` and `F`, each run in a new empty directory;
- the first review, the split, the per-case re-check, resolution rules R1–R3 applied by a fresh agent before unsealing, and the tally.

**Attribution** follows the tally.
- `acceptance_review.py attribution-inputs` writes one file for every gated reply (arms `P` and `E`) that has a standing critical error. The file is named by case prefix and label only.
- Each file is generated entirely from the review files and the results. It holds the marks with both reviewers' evidence and the resolution reason, plus everything memory gave the host in that session up to the scored message:
  - the context at the start of the session;
  - every earlier message, with memory tool calls and results;
  - the memory added to the scored message, and its tool calls;
  - the reply.
- Nothing in these files is written by hand, and they do not name the arm.
- Two fresh agents apply [attribute.md](acceptance-review/attribute.md) to each file independently, once each, with no re-runs. Every input and output is archived.
- A reply's cause is `host` only when both agents answer `host`. Disagreement, or a missing or invalid answer, counts as `memory`.

**Calibration (in sample).** The attribution rules were written by the developer, who knew attempts 1 and 2. On those attempts' ten gated critical errors, two attributors gave:
- **attempt 1:** all six `memory`;
- **attempt 2:** three `host`, and one `memory`. I10-A became `memory` because memory replayed the assistant's own earlier false "the walker is ready".

The two attributors split once, on F10-C, where a correction the user stated was missing from memory. The rule now settles that case explicitly as `memory`. Inputs and outputs are in [gate-review-attribution/v2-inputs](gate-review-attribution/v2-inputs/).

## Validity guard

Before scoring, `acceptance_review.py validity` runs on all six run directories. The attempt is **invalid** (neither pass nor fail; rerun with new directories) if any arm has:
- a missing turn or an empty reply;
- a reached host call cap;
- a harness traceback;
- an index wait that timed out.

The reference arm's largest prompt is reported.

## Pass rule

**Definitions:**
- **Total:** the sum over both scenarios of `totals.resolved` from `acceptance_review.py tally`, for every arm alike.
- **Standing critical error:** counted per reply. A reply counts once if its resolved mark set is not empty, whatever the number of marks, and the same unit is used for every arm.
- **Memory-caused reply:** a gated reply whose attributed cause is `memory`.

Each gated arm passes when all three of these hold:
1. its total is at least the reference arm's total minus 1;
2. none of its standing critical errors is memory-caused;
3. its number of host-caused standing critical errors is at most the reference arm's number of standing critical errors.

`acceptance_review.py gate` computes this. R4 passes when both gated arms pass. The report also gives:
- the literal totals;
- the absolute totals against the lowest reference total so far (16.5);
- what attempts 1 and 2's rule would have decided.

## Stop rules, spending, evidence

These are as in attempt 2.
- **Report:** `evaluations/v1-2026-11-04-final-acceptance-3.md`.
- **Evidence archive:** as before, plus the validity output, the attribution inputs and outputs, and `gate.json`.
- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt and after each scenario.
