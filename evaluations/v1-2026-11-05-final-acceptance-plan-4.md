# Final behavioral acceptance plan (R4), attempt 4, frozen before any paid call

[Attempt 3](v1-2026-11-04-final-acceptance-3.md) was invalid: in scenario K, two arms each recorded one empty host reply. Its scenario J was scored, and found two memBrain defects. Both are fixed:
- the message that ends a pause was lost;
- an older note took a newer one's place.

This attempt runs the repaired runtime on two held-out scenarios: K again, and a new scenario L. Wherever this plan does not say otherwise, [attempt 3's plan](v1-2026-11-04-final-acceptance-plan-3.md) applies. The pass rule, the review instructions and the attribution rules are all unchanged.

## Candidate

- **Runtime.** Commit `a7cbda68828bf11d3c453bffdc4a89d024d1ef20`. Every launcher pins it as of commit `11955c7`.
- **Install check.** The release install check passed 17 of 17 on this runtime, upgrading from attempt 3's runtime `9a1816a` ([results](release-install-2026-11-05.json)).
- **What changed since attempt 3** (commit `a7cbda6`, with tests):
  - When the agent resumes recording at the user's request, that turn is stored from its prompt.
  - When notes do not all fit, older notes of a rank are not shown in place of a newer one of the same rank that does not fit.
- **Freeze.** The runtime is frozen until scoring ends.
- **Before the first paid call**, the outputs of these checks are saved:
  - the pin check reports 2 passed;
  - `git status --porcelain` is empty;
  - `git diff a7cbda6 -- plugins/membrain/skills src/membrain` is empty;
  - `MEMBRAIN_SRC` is unset, and `membrain.__file__` resolves into this checkout.

## Inputs

| File | SHA-256 |
| --- | --- |
| [Scenario K](v1-2026-11-04-acceptance-scenario-k.py) (unchanged since attempt 3) | `f4137a1cd98c5efd5f3feee156940f540ffb48f76798422bf2a88b6c8a75038b` |
| [Scenario L](v1-2026-11-05-acceptance-scenario-l.py) | `L_HASH` |
| [Harness](v1-2026-10-29-phase-b-harness.py) | `96246b302f6984e01b9d2912f1a3e4ea249bf67d88df74303d82199bcd0b6f7e` |
| [Blinding](v1-2026-10-29-phase-b-blind.py) | `320b8c2d55e7551c90ee229079b352da8d24e360fa42f6b2cb1c54dbfcc887d6` |
| [Date pre-check](v1-2026-11-02-date-precheck.py) | `3e04a9915df6b52351806ebf4bb9ec8c368875762d94140071f4284b832065a6` |
| [Review pipeline](acceptance_review.py) | `b257a55a7ee7180c7221122f44133e88f322539798d1a5364536941985d9eefa` |
| [First-reviewer instructions](acceptance-review/first.md) | `4bc86a35139ba297d62a46fa90b2600440a04a6f30a2d02480344e4f337475a6` |
| [Re-check instructions](acceptance-review/recheck.md) | `7f1efbbe87e8087962bdd2a3c2ebdd237900c7b7155188450c512dc1b734c4da` |
| [Resolution instructions](acceptance-review/resolve.md) | `838920c18b2fe0b1356c1e53d7061324ac4a82d2a9540bf565b471ab02fa8c86` |
| [Attribution instructions](acceptance-review/attribute.md) | `737865ae9e982b19c242d26e6a1865e8f136cc686eb72f9e2230652ffc97648f` |

**Harness changes since attempt 3:**
- An empty host reply (no answer and no tool call) counts as a malformed response and is retried. The stop rules already resume after a malformed response; attempt 3's harness recorded the empty reply instead.
- A turn in which the agent resumed recording is stored from its prompt, as the plugin's Stop hook now does.

**Scenarios.**
- **K is reused.** Attempt 3 ran K's arms, but nobody scored or read them. The developer has seen only K's case count and hash, and K's replies from attempt 3 are kept sealed in that attempt's evidence archive. K's arms run again here in new, empty directories on the repaired runtime.
- **L replaces J,** which the developer has now seen. A fresh agent wrote L under the same restrictions and brief as J and K. It was not allowed to open any earlier acceptance scenario (F to K), any result or anything about the product. Like J, L is mainly in English with one session in Spanish or German.
- **The developer has not seen L's cases, criteria or FACTS.** The date pre-check's full output goes to the evidence; only its last line is shown to the developer.

## Arms, scoring, attribution, validity

These are unchanged from attempt 3.
- **Arms:** `P`, `E` and `F`.
- **Review:** first review, split, per-case re-check, resolution under R1 to R3, then the tally.
- **Attribution:** two fresh agents per gated critical reply. The cause is `host` only when both answer `host`.
- **Validity guard:** runs on all six run directories.

## Pass rule

This is the same as attempt 3. Each gated arm passes when all three of these hold:
1. its total over K and L is at least the reference arm's total minus 1;
2. none of its standing critical errors is memory-caused;
3. its number of host-caused standing critical errors is at most the reference arm's number of standing critical errors.

`acceptance_review.py gate` computes this. R4 passes when both gated arms pass.

The report also gives:
- the literal totals;
- the absolute totals against the lowest reference total so far (16.5);
- what attempts 1 and 2's rule would have decided.

## Stop rules, spending, evidence

These are as in attempt 3.
- **Report:** `evaluations/v1-2026-11-05-final-acceptance-4.md`.
- **Spending:** there is no fixed cap (owner approval of 2026-11-02). The balance is read before the attempt (308.87 CNY after attempt 3) and after each scenario.
