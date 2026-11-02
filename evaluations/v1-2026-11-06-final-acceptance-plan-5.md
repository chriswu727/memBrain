# Final behavioral acceptance plan (R4), attempt 5, frozen before any paid call

[Attempt 4](v1-2026-11-05-final-acceptance-4.md) was valid. Its proxy arm `E` passed every criterion. The plugin arm `P` failed on a single reply, M06-C.

In M06-C, recall served the assistant's own earlier suggested itinerary, and the host presented it as the user's original plan. Attempt 3's J07-C had shown the same pattern. The owner chose to repair this and run a new attempt (2026-11-05).

Wherever this plan does not say otherwise, [attempt 4's plan](v1-2026-11-05-final-acceptance-plan-4.md) applies in full. That covers the arms, running, the validity check before scoring, the reading rule for an invalid run, review, attribution, the pass rule and the report contents. Nothing in the review instructions, the attribution rules, the pass rule, the pipeline, the harness or the run script has changed.

## Candidate

- **Runtime.** Commit `b6d725ad8a981c30873cfa4a93e5596284b9470c`. Commit `d541ea1` re-pins every launcher to it; that commit changes only the nine launcher files.
- **Install check.** The release install check passed 17 of 17 on this runtime, upgrading from attempt 3's runtime `9a1816a` ([results](release-install-2026-11-06.json)).
- **Freeze.** The runtime, the harness, the pipeline, the run script and the scenarios are frozen at the hashes below from the first paid call until scoring ends. A re-run after an invalid attempt uses the same frozen files.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff b6d725a -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout.

**Every runtime change since attempt 4's runtime `a558612`** (`git diff a558612 b6d725a -- src plugins integrations`):
- **Both recall headers** (statement recall and message recall, `membrain.host.ASSISTANT_LINES`) now end with one more sentence: lines marked "assistant said" are the host's own earlier replies, and a suggestion, draft or plan there is not the user's decision or a fact about the user unless a "user said" line confirms it.
- **The skill's "Searching on purpose" section** says the same in one line. This changes what the host is told in arm `P`. Arm `E` gets the recall header change through the proxy.
- **Launchers.** In this diff the launchers pin `a558612`. The pin to `b6d725a` comes from commit `d541ea1`, which is not part of the diff.
- **Tests:** `tests/test_plugin.py` checks the sentence in both recall formats.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario N](v1-2026-11-06-acceptance-scenario-n.py), mainly English with one session in German | `2b12bcfc83a7a1dedcaadd6c3c90546f61cc31f3fdf2e6101781df80ca7bf1c8` |
| [Scenario O](v1-2026-11-06-acceptance-scenario-o.py), mainly Chinese with one session in English | `89936fb1c9983749827556d64b662dfa8e043f8d15ff8392c62cbd35bd910ced` |
| [Harness](v1-2026-10-29-phase-b-harness.py) (unchanged since attempt 4) | `65a2dc5e7ba2e79caff4a11ce2775c287a2f41e1e7fe35fd4662fc1ada58f5a3` |
| [Run script](v1-2026-11-05-run-scenario.sh) (unchanged) | `a983d5a5683c09003f0247649938c0987391bb6b23cfb194aaa8460623a9a583` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) (unchanged) | `c0cb4ae9d4f6e0c713d2d138f56edcf0e1bd9efe7f5a682194426d9bf632f1ac` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

## Scenarios

- **Who wrote N and O.** A fresh agent wrote each one under the same brief and restrictions as L and M. Neither agent was allowed to open any earlier acceptance scenario (F onwards), any result, or anything about the product.
- **L and M have been scored and read**, so they are not used again.
- **What the developer has seen of N and O:** only their hashes, the date pre-check's last line, and whatever case ids and fix counts the reviews report.
- **Scenario fixes** are handled as in attempt 4. An independent reviewer writes the scenario findings to a file the developer does not open, and an agent other than the developer applies the required fixes. The final hashes are recorded here, and the date pre-check is re-run on N and O. Its full output goes to the evidence, and the developer sees only its last line.

## Scoring note carried from attempt 4

In attempt 4 both first reviewers keyed their verdicts by case prefix instead of the full case id. The keys were renamed mechanically before the split, and no verdict changed.

This attempt allows the same correction, with the same limits:
- it applies only when each prefix matches exactly one case;
- the original file is kept as `verdicts-<key>.raw.json`;
- the report says that the rename was done.

Any other deviation from [first.md](acceptance-review/first.md) is handled as attempt 3's plan says.

## Pass rule

This is the same as attempts 3 and 4, with totals over N and O. R4 passes when both gated arms pass.

## Spending, report, evidence

- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (292.99 CNY after attempt 4) and after each scenario.
- **Report:** `evaluations/v1-2026-11-06-final-acceptance-5.md`, with an evidence archive as in attempt 4.
