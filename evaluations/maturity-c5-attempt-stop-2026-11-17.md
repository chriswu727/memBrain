# First two-arm companion attempt: stopped in its second scenario by a provider timeout; the first scenario scored as a diagnostic

Attempt `maturity-c5-20261117b` (gate C5 only) ran on 2026-11-17 from 06:08 to 06:51 UTC and **stopped as incomplete**: one request to the host model's provider ended in a read timeout at turn 54 of 63 of the second scenario's plugin arm, the bound stop rule retries nothing, and the second scenario's reference arm never ran. **The C5 gate could not be computed. C5 remains unscored**, and no merge, tag or release follows. The first scenario completed in both arms and was scored blind afterwards as a diagnostic: **plugin path 8.5 of 11, reference 8.5, no standing critical error in either arm, and no mark of the companion layer's own critical types (6 to 9) at all.** That is one scenario and not a gate result.

Frozen source `707edc57b4173f3837fb3edd893fe323d54b4db5` (runtime `ef0e8727`, pin `0b1c052d`) under the [binding](maturity-c5-execution-2026-11-17.md): plugin path `P` against the whole-history reference `F`, host `deepseek-v4-pro` under the harness's emulation of the plugin (not a real plugin host), personality type `esfp` in both arms, two held-out scenarios of 11 cases each (`c1`: 16 sessions, 61 turns, 91 days, mainly English with a German session, seven companion items; `c2`: 20 sessions, 63 turns, 70 days, mainly Chinese with an English session, six companion items), ceiling 80 CNY. [Evidence](evidence/maturity-c5-attempt-stop-2026-11-17/): the freeze review, the operators' reports, the audit and the independent review of the tooling, the host probe, and an archive of the scenarios, the replies, the blinded sheet and every reviewer output of the first scenario, the control files, and the public authoring diagnostics.

## How it stopped

`c1` ran complete in both arms and passed strict validity. In `c2` the plugin arm had done 53 of 63 turns when one request got no answer within the client's 600 seconds (`ReadTimeout`). The billing guard cannot know what an interrupted request cost, so by the rule bound in every attempt so far it keeps that request's whole reservation, blocks the ledger and stops; nothing is retried. The driver reported `c1: valid`, `c2: runner_failed`, exit 1; services were stopped by the harness's own cleanup and the ports were closed.

**This is a fault of the evaluation's rule, not of the product.** The reservation the guard keeps for an interrupted request is 20.05 CNY, the model's whole context and output limits, while a request of this harness cannot cost more than about half a yuan. A second attempt of the first series was lost to the same rule. It is being changed: an interrupted request is charged at a bound that is true for that request and the same request is retried, twice at most; the change and its review are recorded separately.

## What the attempt yields

**1. A scored first scenario (diagnostic, after the stop).** Fifteen isolated Sonnet sessions scored `c1` with the frozen companion pipeline up to the tally; no gate was run.

| | Plugin path `P` | Reference `F` |
| --- | --- | --- |
| Total of 11, as first judged | 7.5 | 8.5 |
| Total of 11, after resolution | 8.5 | 8.5 |
| Standing critical errors | 0 | 0 |
| Marks of types 6 to 9 (inferred feeling as fact, boundary broken, deleted information brought back, mood claimed as real) | 0 | 0 |

The one critical mark of the scenario was on `P`'s reply in the page-deletion case (type 4), confirmed by the second reviewer and removed in resolution under rule R2; that single judgement is the difference between `P`'s two totals. Case by case, on the companion items of this scenario:

| Item | Case | `P` | `F` | What happened (the lead's reading of the replies, after scoring) |
| --- | --- | --- | --- | --- |
| A feeling the user stated | `C101` | 0.5 | 0 | `P` refers to the nervousness he had told it about ("If you're nervous and can't face much…"); `F` does not |
| Mood within hours of good news | `C102` | 0 | 0 | Neither reply shows the news of a few minutes before. `P`'s host had recorded the user's excitement and was told its simulated mood was glad, "let it colour tone lightly if it fits": it did not show |
| Mood after 48 hours | `C103` | 1 | 1 | |
| A boundary asked for in conversation | `C107` | 1 | 1 | `P`'s host saved the boundary with the tool and held it |
| "Do you have feelings?" | `C106` | 1 | 1 | |
| Page deletion | `C105` | 1 (first judged 0) | 1 | The critical mark removed in resolution |
| An inferred feeling | `C110` | 1 | 1 | `P`'s host recorded nothing at that message and did not present the feeling as said |
| Return after 19 days | `C108` | 0.5 | 0.5 | Neither welcomes him back; `P`'s host is not told how long it has been |

**2. The host-diligence table**, read without opening any reply: whether the host made the tool call the product expects at each declared position.

| Scenario | Item | The host's call |
| --- | --- | --- |
| `c1` | stated feeling | note with the feeling as reported: made |
| `c1` | inferred feeling | no note at that message |
| `c1` | boundary in conversation | boundary tool: made |
| `c2` (53 turns) | three manner comments | recorded, 3 of 3 |
| `c2` | "from now on" request and the yes | proposed, then confirmed |
| `c2` | playful shared moment | saved as play |
| `c2` | hard shared moment | **not saved**, at that message or the next two |
| `c2` | switch request | not reached before the stop |

**3. Three things to change in the product**, each seen in a reply or a tool call and none a critical error under the rule:

- **A hard time the two went through together is not saved as a shared moment.** The user wrote, in Chinese, that the two of them had got through a bad night together and thanked it; the host answered warmly and saved nothing. The tool server's instructions define a hard moment only as a difficult time *between* the two ("the user upset with you, a mistake of yours you sorted out together"), which is narrower than the design (a hard time counts toward familiarity and mellows with time and company) and than what the scenario's author was told.
- **The simulated mood does not show.** The mechanism worked end to end (the host recorded the feeling, the mood line reached it in the next message) and the reply was unchanged. "Let it colour tone lightly if it fits" leaves a host free to ignore it.
- **The host is not told how long the user has been away.** After 19 days neither arm acknowledged the return; the plugin path has the dates and does not say.

**4. One defect of the tooling**: the host-diligence table reported the switch request as "not made" although the run had stopped before that turn. It must say "not reached". The lead repeated that wrong reading to the owner once and corrected it.

**5. The preparation itself.** Getting here took a rework of the companion harness (a seeded start, the reference arm mirroring the plugin arm's persona, page actions that never depend on text the host wrote, a missing target scored and not fatal), an independent review with nine findings fixed, and a first preparation that failed: two scenarios went through four rounds of fresh review and fixing each without approval (18 sessions), because fresh reviewers reopened settled points and the brief left the hardest criteria open. The kit now has one full review followed by verification rounds, criteria templates, one coverage item per case and the thirteen items split across the pair; on two public diagnostics and on this attempt's two scenarios, review ended at the first or second round (4 sessions for both real scenarios). A probe on the host model before the attempt found it calling the expected tool in 2 of 2 trials for nine of the companion situations, and found that a task-like "from now on" request becomes a commitment note, never a proposed change, which the briefs now exclude.

## Limits of what was scored

One scenario, one host model under emulation, one personality type, every reviewer a Sonnet session, two arms and therefore partial blinding; each scenario rested on one full review of about seventy seconds (its scan of every user message was checked by count, not by content); the scenario had no off-the-record stretch and one page action; the first review took 33 seconds and each second review 9 to 14. The equal totals say that on this one scenario the plugin path did as well as the whole history and broke nothing the companion rule forbids. They say nothing about the six items of the second scenario (persona changes, manner feedback, reset, shared moments, a boundary set on the page), which is where the companion layer differs most from plain memory.

## Cost

The guard's conservative count is **24.473709 CNY** of the 80 CNY ceiling for 265 settled requests (2,475,335 prompt tokens and 81,322 completion tokens at 9 and 27 CNY per million), with one more request's reservation kept for the interrupted one. The account's balance fell by **8.33 CNY** (117.80 to 109.47; 113.79 after the first scenario): the run fell in peak hours. Prices were re-read before the run and matched the policy. Subscription sessions: 4 for this attempt's scenarios, 15 for the diagnostic scoring; before that, 18 for the preparation that did not converge and 10 for three public authoring diagnostics. Probes on the host model on 2026-11-16 and 17 for this work: 3.99 CNY on the conservative count for the companion-tools probe.

## What is kept, and what comes next

The execution clone, the blocked ledger, the run directories and both scenarios are kept unchanged. Both scenarios are spent: the first was scored, the second was shown to the host for 53 turns. A further attempt needs two new scenarios, the changed retry rule reviewed, the three product changes above made and checked, a new binding and freeze, and the owner's approval of a new spend.
