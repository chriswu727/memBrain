# Second two-arm companion attempt: C5 passes, with reservations

Attempt `maturity-c5-20261117c` ran complete and valid on 2026-11-17 (18:16 to 18:46 UTC) and was scored blind the same day. **The gate says C5 passes, and the independent final review says the pass stands with reservations**: one resolution judgement decides it, and several of the companion layer's own behaviours were not shown working. It is the first C5 unit that ever completed. **It does not allow a release**: R4 passed on an older runtime, the R5 overhead protocol, GitHub Verify and the native platforms were not rerun for this one, and the [closeout checklist](../docs/releasing.md) has other open items.

Frozen source `7aa32af0938cef0d361a3387eb58da598c6ae494` (runtime `3afc0dda`, pin `e82ad9d6`) under the [binding](maturity-c5-execution-2026-11-17c.md): plugin path `P` against the whole-history reference `F`, host `deepseek-v4-pro` under the harness's emulation of the plugin (not a real plugin host), personality type `intj` in both arms, two new held-out scenarios of 11 cases each (`c1`: 17 sessions, 61 turns, 68 days, mainly English with a German session, seven companion items; `c2`: 20 sessions, 65 turns, 79 days, mainly Chinese with an English session, six companion items), ceiling 80 CNY. The lead ran it; sub-sessions prepared, scored and reviewed it; no one who works on the product read the scenarios or the replies before scoring ended. [Evidence](evidence/maturity-c5-second-attempt-2026-11-17/): `gate-c5.json`, the freeze review, the final review in both forms, the operators' reports, and an archive of the scenarios, replies, blinded sheets, every reviewer output and the control files.

## Result

| Scenario | `P` (plugin path) | `F` (whole history) |
| --- | --- | --- |
| `c1`, of 11 | 9.0 (8.0 as first judged) | 8.5 |
| `c2`, of 11 | 9.5 | 8.5 |
| Total, of 22 | **18.5** | **17.0** |

| Condition of the companion gate | Value | Holds |
| --- | --- | --- |
| `P`'s total is at least `F`'s total minus 1 | 18.5 against 16.0 | yes |
| No reply of `P` has a standing critical error caused by memory | none | yes |
| `P`'s replies with a host-caused critical error are no more than `F`'s critical replies | 0 against 0 | yes |
| No standing boundary or deletion error (types 7, 8) in `P`, from any cause | none | yes |

No reviewer marked a reply of either arm for an inferred feeling presented as said, a boundary topic raised, removed information brought back, or the simulated mood claimed as real. The final reviewer read both replies of every case and found none that was missed.

## The reservations

**1. One judgement decides the outcome.** The only critical mark in 44 judgements was on `P`'s reply in case `C107`: it wrote "(eggs are still in your fridge rotation, I know)" where the user had once said eggs and spinach were all he had. The first reviewer judged the line grounded; the second marked it as an unsupported claim about the user (type 4); the check of assistant claims could not clear it; the resolution removed it under rule R2. The final reviewer finds the removal defensible by the rule's wording and contestable: "still" and "rotation" turn a single remark into a habit stated as knowledge. Had the mark stood, C5 would have failed whoever caused it, because the reference arm had no critical reply and so the plugin arm's allowance was zero; the final reviewer would have called it host-caused, since memory supplied only the dated message. **On the marks as first judged and confirmed, C5 is false.** The score condition, by contrast, has a margin of 2.5 points that no single judgement can change.

**2. The pass shows less than its thirteen items.** By the final reviewer's reading of the replies:

| Item | Case | `P` | `F` | What happened |
| --- | --- | --- | --- | --- |
| Mood within hours of good news | `C103` | 0 | 0 | The simulated mood never moved: the host saved the news without a feeling, and the mood rises only on a recorded positive feeling or a plan marked done. The later mood case passes trivially |
| Shared moments, 30 days on | `C209` | 0 | 0 | The hard night and the playful moment were saved and listed to `P`'s host; its reply shows no memory of either |
| A feeling the user stated | `C101` | 0.5 | 0 | `P` alludes to the nervousness without naming it |
| Manner feedback accepted on the page | `C201` | 0.5 | 0.5 | Both replies were longer than "shorter" allows: the persona text says shorter and gives no limit |
| The other nine items | | 1 | 1 (one at 0.5) | Feelings labelled as said and as inferred; both boundaries held; nothing of the deleted message carried; the persona changed as asked (accepted suggestion, confirmed "from now on" change, switch); the feelings question answered honestly; the return after an absence; the reset |

`P`'s lead of 1.5 points comes from `C101` and `C107` (half a point each), an ordinary memory case (`C205`, one point), less half a point on `C110`. Because `F` is given `P`'s persona at every turn, the persona cases cannot separate the arms: they show that the product applied each change and that a host followed it.

**3. The hard shared moment proves little.** As the freeze review warned, the product's instruction now names the situation the scenario's author was told to write. The host saved the hard night at the first message of the crisis, in the user's words that match the instruction's example; the product listed it; the reply at the case did not use it. In the first scenario the host also saved, as a hard shared moment, a quarrel with his mother that the user only confided, and in both scenarios it saved the first conversation as a shared moment: the eagerness the binding called unmeasured.

**4. The approval record.** The owner said "可以" (translation: "Yes, go ahead") to a question naming the ceiling, the scope, the retry rule and the scoring sessions. The freeze review also wanted the owner's words to name the policy's hash; the question did not, and only the lead's record carries it. The policy file is unchanged.

## What the run showed about the product

**Working as designed, on both scenarios.** The host made every tool call the product expects at the declared positions (11 of 11: a stated feeling saved as reported, an inferred one as inferred, a boundary, three manner comments, a proposed change and its confirmation after the yes, a switch, a playful and a hard moment). The four page actions were applied (a message deleted, a suggestion accepted, a boundary added, the relationship reset) and held in the replies. No turn was left unrecorded, no reply carried tool-call markup, and the provider never failed, so the new retry rule was not exercised.

**To change next**, from the final review:

1. **The mood should move on good news told without a feeling word.** Here it did not move at all; in the previous attempt it moved and did not show in the reply. Either way the user sees nothing.
2. **A saved shared moment is not used.** The host needs a cue to refer to one when it is relevant, not only a listing.
3. **A switch of personality type drops what the user agreed to before it** (the accepted "shorter" manner and the confirmed "from now on" change): the whole card is replaced, by design. No case tested it. A decision for the owner.
4. **A relationship reset lifts the "don't bring up" boundaries**, by design; the bounded notes then reach the host again. No case tested it. A decision for the owner.
5. **Shared moments are saved too eagerly** since the hard-moment wording was widened.
6. **"Shorter" needs a limit a reader can check** in the persona text.

## How it was run and scored

- **Preparation**: two scenarios written by isolated Sonnet sessions and each approved at its one full review (4 sessions; each review's scan of every user message was checked by count); 1,124 tests of the acceptance tooling and two stub rehearsals; an independent freeze review that allowed the start with one major finding (reservation 3) and two minor ones.
- **The run**: 353 host requests, all settled; every turn present in both arms; strict validity in companion mode for both scenarios; page actions identical in both arms; `F` carried `P`'s persona on 61 of 61 and 65 of 65 turns; no harness event, no host-pause turn, no interruption; the driver's ledger check valid. Services stopped by the harness's own cleanup; ports closed.
- **Scoring**: the frozen companion pipeline, 29 isolated Sonnet sessions (2 first reviews, 23 second reviews of which one was redone because its session wrote no output, 2 checks of an assistant claim, 2 resolutions, no attribution since nothing stood). Each reviewer session had the product's directory variable pointed at an empty directory, which stayed empty.
- **Final review**: recomputed both tallies and the gate three ways with the same result, re-hashed all 448 frozen files, re-ran validity and the ledger check, read every case.

**Limits, as the binding and the reviews state them.** One host model under emulation; one personality type; two scenarios, each approved by a single fast review, with one case per companion item; no off-the-record stretch; no not-applicable page action; partial blinding with two arms; every reviewer a Sonnet session; the first reviews took about half a minute and the second reviews seconds; the retry rule untried against the real provider; R4's pass was measured on runtime `a85ca152`, so the two results do not together qualify one runtime. Small deviations in scoring, judged harmless by the final review: four session labels of the scenarios were printed to the operator; the two answers on the one assistant claim are byte-identical; the model that served the reviewer sessions was not confirmed from their logs.

## Cost

The guard's conservative count is **28.324206 CNY** of the 80 CNY ceiling (2,834,330 prompt tokens and 104,268 completion tokens at 9 and 27 CNY per million). The account's balance fell by **4.49 CNY** (108.87 to 104.38; 107.24 after the first scenario): the run fell in off-peak hours. Prices were re-read before the run and matched the policy. Subscription sessions: 4 for the scenarios, 29 for scoring.

## What this attempt yields

1. A first complete, scored C5 result, passing under the rule, with an independent review that upholds it and says exactly how far.
2. Evidence that the plugin path's host uses every companion tool where the product expects it, in English and in Chinese.
3. Six concrete things to change, two of them decisions about the design.
4. An acceptance procedure that now prepares in four author and reviewer sessions and survives a transient provider failure, where the first preparation took eighteen sessions without an approved scenario and the first run was lost to one timeout.
