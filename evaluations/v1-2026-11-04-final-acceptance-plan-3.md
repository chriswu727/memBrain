# Final behavioral acceptance plan (R4), attempt 3, frozen before any paid call

[Attempt 2](v1-2026-11-03-final-acceptance-2.md) did not pass. The [gate review](v1-2026-11-03-gate-review.md) found that the first pass rule could not be met even by the reference arm, which has perfect information, so it measured the host model rather than memBrain. This attempt therefore uses the revised rule, a repaired runtime, a fixed harness and two new held-out scenarios. Wherever this plan does not say otherwise, [attempt 2's plan](v1-2026-11-03-final-acceptance-plan-2.md) applies.

## Candidate

- **Runtime.** Commit `9a1816af9a3d238bce925450998f4fd0bdd0d0f3`. Every launcher pins it as of commit `fdb3d15e964fa47ff78dd6738b09aedf215e1615`.
- **Install check.** The release install check passed 17 of 17 on this runtime ([results](release-install-2026-11-04.json)).
- **What changed since attempt 2.**
  - Coming-up lists any open note with a deadline and undated open plans ("Planned, not confirmed done").
  - Memory and the skill tell the host not to rely on something only planned.
  - Extraction files anything with a deadline as a plan.
- **Freeze.** The runtime is frozen until scoring ends.
- **Before the first paid call**, the checkout must show all three of these, and their outputs are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff 9a1816a -- plugins/membrain/skills src/membrain` is empty.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario J](v1-2026-11-04-acceptance-scenario-j.py) | `d15bd20e55e9f35fc1369b9192db97f936a0a237b2e00167f3b1ba63673e9eca` |
| [Scenario K](v1-2026-11-04-acceptance-scenario-k.py) | `d88fe99266c98947db09c420a17e6d0933677c4ccf22cd71a61695cb654ebd7b` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (now records everything the host writes in a turn) | `4f799cf6231c246a76459edef3ffc48a7837e05a2f034d08e90fff1e4b6cf7ae` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) (split, tally, context) | `2deaa643f083ef1abaa23c1dc6174b8141ddea27428585d633a13bdf8aa08e47` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `3c0d846393f5f77728349a3cb77efd02b25085d2005943b37d71b744d5fcc64d` |

**How the scenarios were written.**
- A fresh agent wrote them under the same restrictions as before. It could not read the product, its docs and reports, or the earlier acceptance scenarios.
- The brief named the behaviours to cover. That included a confidential fact, an off-the-record message, a date given without a month, and a purchase or booking that was only planned. Criteria may require only what the user's request plainly calls for.
- The author was told not to describe the cases in its reply. It did not, so **the developer has not seen the cases, the criteria or FACTS**.
- The date pre-check passed all 64 sessions.

## Arms and scoring

These are the same as attempt 2: arms `P`, `E` and `F`; reviewers; split; re-check; resolution rules R1–R3 applied by a fresh agent before unsealing; tally. One step is added after unsealing.

**Attribution.**
- For every standing critical error in a gated arm, `acceptance_review.py context` writes what memory gave the host for that turn: the session-start context, the per-message context, memory tool calls and their results, and the reply.
- A fresh agent per error applies [attribute.md](acceptance-review/attribute.md) and decides one thing: did the memory the host received contain what it needed to avoid the error (`host`), or did memory miss or misstate it (`memory`)?
- No reviewer changes a score at this step.
- The method was calibrated on all ten gated critical errors from attempts 1 and 2. It agreed with the manual diagnosis in every case ([results](gate-review-attribution/)).

## Pass rule

The revised rule from the [gate review](v1-2026-11-03-gate-review.md) applies. Each gated arm (`P` and `E`) passes when all three hold:
1. its total over both scenarios is at least the reference arm's total minus 1;
2. no standing critical error in that arm is attributed to `memory`;
3. its number of standing critical errors attributed to `host` is no greater than the reference arm's number of standing critical errors.

R4 passes when both gated arms pass. The report also gives:
- the absolute totals;
- what attempts 1 and 2's rule would have decided;
- the literal totals, before resolution.

## Stop rules, spending, evidence

These are as in attempt 2.
- **Report:** `evaluations/v1-2026-11-04-final-acceptance-3.md`.
- **Evidence archive:** as before, plus the attribution files.
- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt and after each scenario.
