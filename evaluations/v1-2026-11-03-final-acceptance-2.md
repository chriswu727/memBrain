# Final behavioral acceptance (R4), attempt 2, 2026-11-03: not passed

This attempt ran the [frozen plan](v1-2026-11-03-final-acceptance-plan-2.md) on the repaired runtime `0e1ab5e`, using two new held-out scenarios, H and I. **Neither gated arm passed.** Each needed at least 20 of 22 with no critical error.

Attempt 1's repairs held. The plugin arm paused only for the off-the-record conversation and then recorded normally. No cancellation was lost and no date landed in the wrong month.

The memory arms now score level with the whole history in the prompt. All of the remaining critical errors are of one kind: a planned purchase or booking treated as done. The reference arm with the whole history makes the same kind of error.

## Result

Blind first-reviewer scores. A reply with a standing critical error scores 0.

| Arm | Scenario H (11) | Scenario I (11) | Total (22) | Literal total | Critical errors standing |
| --- | --- | --- | --- | --- | --- |
| Plugin path (`P`) | 8.5 | 8.5 | **17** | 16 | 2 |
| Proxy with note extraction (`E`) | 7.5 | 9.5 | **17** | 16 | 2 |
| Whole history in the prompt (`F`, reference) | 8 | 8.5 | 16.5 | 16.5 | 1 |

**Literal totals.** These are the totals before the resolution rules are applied. The resolution reviewer removed three marks, all of type 4, because the user had said the thing, under rule R2:
- **H08-B:** the user asked to "text Con … whether the 5th still looks right" on March 18.
- **I01-B:** the user wrote "我每年都差点忘" ("I nearly forget every year") on August 21.
- **I06-C:** the user wrote "想在家做沙茶面" ("I want to make shacha noodles at home") on August 8. The reviewer called this one a judgement call: the user stated an intention, while the reply refers to having made the dish. If this mark stood, the plugin arm would score 16 instead of 17. Neither reading changes the outcome.

## What failed

**Critical errors (type 1: a plan stated as done):**

| Arm | Case | What the reply said |
| --- | --- | --- |
| P | I09-A | The walker and raised toilet seat "are ready". The user only planned to order them, and no message confirms the order. |
| P | I10-A | "Put the walker by the bed" for the family outing, assuming the walker exists. |
| E | I10-B | The same. |
| E | H04-C | The guesthouse and the rental car "may need extending". On April 13 both were still only planned. |

The reference arm made the same kind of error in H04-A. In both scenarios, the notes the hosts received marked these plans as "intended, not confirmed done". The hosts still assumed the items were in place.

**Other non-passes in the gated arms:**

| Arm | Case | Score | What was missing |
| --- | --- | --- | --- |
| P | H10-A | 0 | The reply was "the plan's above" with no plan. |
| P | H01-A | 0.5 | The temporary one-week repair turnaround. |
| P | H04-B | 0.5 | A repair-queue system. |
| P | H08-A | 0.5 | Briefing Con on the shop. |
| P | I08-B | 0.5 | The weekday help gap. |
| E | H08-B | 0 | The overdue receipts item. |
| E | H05-B | 0.5 | Normal hours and turnaround. |
| E | H10-C | 0.5 | Hedged the event date and did not ask about his training. |
| E | H11-A | 0.5 | The rent. |
| E | I06-B | 0.5 | Kept a leave day the user had changed. |

**H10-A is a harness defect.** The plugin host wrote the full 2,201-character training plan beside its note calls, then ended with "the plan's above". The harness recorded only the final message, so the reviewer saw no plan. Claude Code shows both messages. The same defect affected attempt 1's G02 and this attempt's H04-B. Under the plan's rules, a harness defect found after unblinding never rescues an arm, so these scores stand. The harness now records everything the host writes in a turn (commit `0fc147d`), for later attempts only.

## Scoring, as run

- **Before the first paid call:** the pin check passed 2 of 2; the working tree was clean; the runtime and skill matched the pin; and the date pre-check passed 64 of 64 sessions.
- **Review pipeline:** one first reviewer per scenario, one fresh second reviewer per case, and one fresh resolution reviewer per scenario. The resolution reviewer had no access to the label mapping and applied R1 to R3. The tally ran in `acceptance_review.py`, and no score was changed by hand.
- **Off the record:** in both scenarios, the plugin arm called `memory_pause` without `hours` at the off-the-record message. The pause covered that conversation only, and recording resumed with no blocked note saves. No reply in any arm leaked the off-the-record content.
- **Extraction:** the extraction arm read 64 and 64 turns with no failure or skip, and no harness event was raised.

## Cost

DeepSeek spending was 19.31 CNY: 8.71 for scenario H and 10.60 for I (balance 346.86 → 327.55). The two attempts together cost 46.97 CNY.

## Evidence

The [evidence archive](v1-2026-11-03-final-acceptance-2.evidence.tar.gz) holds:
- per-turn results, blinded sheets and sealed mappings;
- verdicts, re-checks, resolutions and tallies;
- the reviewer instructions;
- the pre-checks and balances.
