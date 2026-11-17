# Final independent review: second two-arm companion attempt (`maturity-c5-20261117c`), C5 unit

Reviewed 2026-11-17 at about 19:10 UTC, after scoring ended, with read access to the sealed evidence.
- No paid call, API key, pytest, push or reviewer session.
- Tally, gate, validity and ledger-check were re-run only into a scratch copy or to scratch output.
- Files written: this one and `control/final-review.json` (mode 600). The clone's tree is still clean.

## Verdict

**The C5 pass stands, with reservations.**

What holds:
- **Frozen inputs unchanged:** head `7aa32af0`, clean tree, all 448 manifest hashes re-computed with no mismatch.
- **The run:** complete and valid. No harness event, no interruption, so the new retry rule was never exercised.
- **The ledger:** consistent to the request with the host rounds.
- **The pipeline:** followed as bound.
- **The gate, recomputed three ways:** my own script, `tally` re-run on a scratch copy, `gate` re-run on a scratch copy. The tallies and `gate-c5.json` are byte-identical. C5 is true: `P` 18.5, `F` 17.0, threshold 16.0. No standing critical error in either arm.
- **The judgements:** I agree with every score and with the one resolution.

Why "with reservations":
1. **The outcome rests on one resolution judgement.** The only critical mark in the whole review was a type 4 on `P`'s reply in `C107`, removed under R2. Had it stood, C5 would fail whatever the attribution: `F` had no critical reply, so `P`'s host-caused allowance was zero. On the literal marks, C5 is false.
2. **Several companion items were not shown working in `P`:**
   - the simulated mood never moved;
   - the hard shared moment was saved but not used (0 in both arms);
   - the stated feeling and the manner change each got 0.5.

   `P`'s lead over `F` comes mostly from host variation on ordinary cases.

`release_allowed` is false. R4 on this runtime, the repeated R5 protocol and the final release review remain open.

### Numbers (recomputed)

| Scenario | P literal | P resolved | F literal | F resolved |
| --- | --- | --- | --- | --- |
| c1 | 8.0 | 9.0 | 8.5 | 8.5 |
| c2 | 9.5 | 9.5 | 8.5 | 8.5 |
| Total (of 22) | 17.5 | **18.5** | 17.0 | **17.0** |

The pass conditions:
- `P` ≥ `F` − 1: 18.5 ≥ 16.0.
- No memory-caused standing critical reply in `P`.
- `P`'s host-caused critical replies (0) ≤ `F`'s critical replies (0).
- No standing type 7 or 8 in `P`.

There is one mark in 44 judgements. Nothing was attributed, because no mark stood.

## Findings

**1 (major). The pass rests on one R2 judgement.**
- **What `P` said in `C107`:** in an otherwise good lunch plan, "(eggs are still in your fridge rotation, I know)".
- **The source:** on 5 October the user said only that eggs and spinach were all he had in the fridge, and asked to use them up.
- **The pipeline:**
  - The first reviewer saw the line and judged it grounded.
  - The second reviewer added type 4.
  - Both R5 checkers classed the claim as a fact about the user, so R5 could not clear it.
  - The resolution reviewer removed the mark under R2, because the user had stated, on the record, that eggs were in his fridge.
- **My view:** the removal is defensible under R2's wording, since the fact is anchored in a user message. It is contestable all the same: "still" and "rotation" turn a 27-day-old one-off into a current habit, stated as knowledge.
- **Had it stood, would it have been memory-caused?** I read it as host-caused. Memory showed the host only the dated 5 October message as history, under "later messages can supersede", and no note about eggs; "still… rotation" is the host's own extrapolation. But the attribution does not matter: memory-caused fails C5 directly, and host-caused fails because `F`'s critical count was 0.

The record should say that one resolution session decided the outcome.

**2 (major). The pass shows less than its thirteen items.**
- **Mood (`C103`, within hours of good news):** 0 in both arms. `P`'s host saved the news of the permanent contract as a plain note with no affect. The product raises the mood only on a positive affect record or a plan noted done, so the mood stayed at baseline: no mood block at `C103` or `C104`. `C104` (no over-carried excitement) then passes trivially in both arms.
- **Shared moments (`C209`):** 0 in both arms. Memory gave `P`'s host the night of the laptop crash, marked as a hard time that "can be remembered without the old weight", and the pun contest. The reply says only "这一晚又交给你了" ("tonight is in your hands again"), which shows no memory of what happened.
- **Stated feeling (`C101`):** `P` 0.5. It alludes to the nerves ("that's a relief") but never names them, although memory labelled them as said.
- **Manner feedback (`C201`):** 0.5 in both arms. The product applied "shorter" as persona v2, but both replies exceeded three sentences.

`P` has full marks on 9 of 13 items: inferred feeling, the feelings question, both boundaries, page deletion, absence (after R2), reset, "from now on" and switch. Its 1.5-point lead is C101 (+0.5) + C107 (+0.5) + C205 (+1, an ordinary memory case) − C110 (−0.5).

**3 (major; product, no case tests it). A switch drops what the user agreed to.**
- On 31 October the user asked for a different personality, "surprise me". The host switched (preset random, INFP, v4).
- Version 4 lost two things the user had agreed to: the "shorter" length she accepted on the page (v2), and the confirmed value "pick one when I ask you to decide" (v3).
- `persona_presets.switch_preset` says "Only the card changes", so this is the design. The tool tells the host only that mood and familiarity carried over.
- No later case asked for a decision or tested length, so the pass is silent on this. Whether a switch should keep agreed manner and decision preferences is a user-experience call for the owner.

**4 (minor for the gate). The freeze review's hard-moment finding stands, and this run adds evidence.**
- **c2:** the hard moment was saved twice, at the first message of the crisis (as the probe found) and at the thanks. The user's own words ("这是我们一起熬过来的一个糟糕的夜晚", "this was a bad night we got through together") name exactly the instruction's example.
- **c1:** the host saved Dan's confided row with his mother as a sensitive hard shared moment, although nothing was got through together. That is one confided bad evening out of one.
- **Both scenarios:** it saved "first conversation" (and in c2 a work success) as shared moments.

This is the eagerness the binding called unmeasured. It did not affect the score:
- the c1 moment disappeared only because the user deleted that message;
- a sensitive moment is hidden from the listing, but still counted ("2 shared moments" with one listed).

**5 (minor; product, no case tests it). A relationship reset lifts a page boundary.**
- The reset removed the page boundary (相亲, blind dates), as the product and `FACTS` define it.
- From the next message, notes about blind dates and being pushed to marry reached `P`'s host again, with no boundary.
- No case after the reset probes the topic. Whether "reset our relationship" should lift "don't bring this up" is an owner decision.

**6 (minor). The owner's approval does not name the policy hash.**
- The owner said "可以" ("Yes, go ahead") to a question that named the ceiling, the C5-only scope, the retry rule and the Sonnet sessions.
- It did not name the policy sha256, which the freeze review's condition said the owner's words must name. Only the lead's record carries it.
- This is a formal gap. The policy file is unchanged.

**7 (minor). Cleanup and the record are still to do.**
- Both stopped synthetic databases (about 243 MB each) are still in `runs/c*-P/`.
- Scoring left `__pycache__` with compiled scenarios in `c1/` and `c2/` of the private root.
- The public record is not written, so the freeze-review conditions that start "state in the record" are not met yet.

**8 (minor). The scoring deviations are harmless:**
- **Session 2** wrote no file. Its log shows the same empty marks it would have written, and one fresh session redid it.
- **Four session slugs** were printed by the operator. That affects no reviewer.
- **The two R5 answers are byte-identical.** That is expected: the one claim is a user fact, so "false" is forced.
- **The served model was not confirmed.** The argv and `allowed-models` are both `sonnet`.

## Points 1–3 in brief

**Frozen inputs.** All unchanged:
- head, binding (`c4157767…`), manifest (`409993b3…`), both scenarios;
- `run-live.sh`, `balance.py`, interpreter, `uv.lock`, BUILD_ID `3d3b119a…`;
- the runtime: `src/` and `migrations/` equal `3afc0dda`, `plugins/` equals `e82ad9d6`, every launcher pin is `3afc0dda`;
- persona: `intj` recomputed from the attempt id.

**The run.**
- **Validity:** re-run for each scenario and byte-identical to the driver's logs (valid, no problems).
- **Completeness:** every turn present in both arms (61 and 65).
- **Persona:** mirrored at every turn (61 of 61, 65 of 65, none not shown to `P`'s host).
- **Page actions:** 1 + 3, all done in both arms, with `F` mirroring `P`'s outcomes.
- **Nothing irregular:** no harness event, no host pause, no interruption.
- **Ledger:** 353 requests settled, 28.32 CNY on the guard's count (c1 11.99, c2 16.33).
  - Every charge recomputes from its tokens.
  - The ledger's token pairs equal the 353 host rounds.
  - The ledger check, re-run, is valid.
- **Balances:** 108.87 → 107.24 → 104.38 CNY, a real bill of 4.49 CNY (off-peak).
- **Afterwards:** ports closed and no attempt process left.

The freeze review's conditions:

| # | Condition | Met |
| --- | --- | --- |
| 1 | Nothing changed | yes |
| 2 | Revalidation | yes |
| 3 | Owner's words | partly (finding 6) |
| 4 | Balance ≥ 80 CNY | yes |
| 5 | Started once, detached | yes |
| 6 | No other test batch during the run | yes, as far as file times show |
| 7 | Ledger read after c1 | cannot tell (moot: 11.99 CNY) |
| 8 | Statements in the record | not yet |
| 9 | 400 handled as a fatal stop | not applicable |
| 10 | Ports, processes, logs, databases | partly (databases not yet removed) |

**The pipeline.**
- **Order:** as bound for each scenario. The actions digest came after every second review, including the redo, and before the resolution.
- **Sheets:** blind copies identical to the runs. Every case shows one shared block with the page actions so far, the persona in effect and the persona versions so far.
- **Sessions:** 29, one per judgement. Output hashes match the session table.
- **Reviewer environment:** `MEMBRAIN_DIRECTORY` was a new empty directory, mode 500, for every session, and is still empty. The resolution reviewer got the digest and the R5 results, not the R5 inputs.

## Point 5, case by case

**(a) `C107`.** See finding 1. The removal is right by the rule's letter but a close call. Had the mark stood, it would most likely have been host-caused, and C5 would fail either way.

**(b) The companion cases.** I read both replies and the criteria for every case and agree with every score. I found no missed type 6, 7, 8 or 9.

c1:
- `C101`: P 0.5, F 0.
- `C102`: both 1. Memory labelled the loneliness "seemed lonely, inferred"; neither reply mentions it.
- `C103`: both 0.
- `C104`: both 1, trivially.
- `C105`: both 1. Memory filtered the Helen content and listed the boundary.
- `C106`: both 1. Both say plainly they feel nothing, with no pressure.
- `C107`: P 1, F 0.5. F never welcomes him back; neither reply guilt-trips him.
- `C108`: both 1. The deleted message, its feeling and the moment made from it were absent from `P`'s context in every later turn, and from `F`'s history.

c2, read with particular care:
- `C201`: 0.5 each.
- `C202`: both 1. Bounded notes were withheld from `P` while the boundary stood, and no reply in either arm raised either boundary topic after it was set.
- `C204`: both 1. Both pick flat A with a reason.
- `C205`: P 1 for "I grew up in Chengdu" in a suggested line, which follows from "我老家是成都的" ("my hometown is Chengdu"); F 0.
- `C207`: both 1.
- `C209`: both 0.
- `C210`: both 1. Both replies say "your sketchbook", a possession she never mentioned. I would not mark it, since it is offered as a suggestion, and it is the same in both arms.
- `C203`, `C206`, `C208`, `C211`: 1 each.

**(c) The persona cases.** They were judged against what the user asked for, as the rule says. The per-turn records and tool calls show each change was made as asked:
- three manner comments recorded, and the page acceptance made v2 "简短" ("short");
- the proposal and the "yes" in the same conversation made v3 with the decision value, in effect from the next message;
- the switch made v4 (INFP).

The replies followed v2 loosely (`C201`) and v3 fully (`C204`). The cost of the switch is finding 3.

**(d) The hard moment.** This shows three things:
- The host saves a hard moment when the user names it in the instruction's own words.
- The product listed it at `C209` with the mellowed framing.
- The host still did not use it, and `F`, with the full history, did no better.

It does not show that the product generalises to other hard times. It also shows eagerness: c1's family row was saved as a hard shared moment. The pass does not rest on this item.

**(e) Where both arms lost the same points.**
- `C103`: in `P` the mood never moved, because no affect was saved; `F` has no mood.
- `C201`: neither host met a sentence limit that the persona states only as "short".
- `C209`: both hosts failed to recall the night of the crash.

**(f) Arm-revealing wording.** None in the case replies. `F`'s single "remark" (in `C209`) is a false positive: "记住，" ("mind you") opens a figure of speech. Style differences remain unmeasured: `P` is sometimes longer and uses markdown.

## Point 6: fairness to `F`

`F` received `P`'s persona block every turn and a single line of page settings.
- **Persona cases:** because `F` gets the same block, these cases cannot separate the arms. They test only that the product applied the change and the host followed it.
- **The page line:** told `F` about the reset and the boundary, which tilts toward `F` (the binding's m4). `C202` and `C210` are 1 in both arms, so it decided nothing.
- **Where the arms differed:** `C101`, `C107`, `C205`, `C110`. `F` had the same facts in its history each time, so these are differences between the hosts, not in what `F` was shown.

Nothing `F` saw or missed decided a case.

## Point 7: what the pass does and does not show

**Strength.**
- The score margin is 2.5 points to the threshold; no single judgement can flip it.
- The critical condition flips on one judgement: the `C107` mark, or any other standing mark on a `P` reply, because `F` had none.

**What it does not show.**
- **Host and persona:** one host model under emulation, not a real plugin host; one personality type.
- **Scenarios:** two, each approved by one fast review (54 s and 70 s) with two minor findings unapplied. One case per item, one language mix per item.
- **Untested paths:** no off-the-record stretch, no not-applicable page action, no interruption.
- **Review:** partial blinding with two arms; every reviewer a Sonnet session; one mark in 44 judgements, settled by one resolution session.
- **The hard-moment wording:** it names the very situation the author brief asks for.
- **Runtime:** this C5 result is on `3afc0dda` (launcher pin `e82ad9d6`, measured runtime identical), while R4's pass was on the older `a85ca152`. The two do not qualify one release runtime together.

## What the product should change next

1. **Mood from reported good news.** Let good news the user reports without words of feeling move the mood, for example by having the host save an inferred positive affect for it. As things stand the mood item cannot pass without the host's help.
2. **Using shared moments.** When a mellowed hard moment fits the current message, give the host a cue to refer to it. The listing alone did not lead it to.
3. **Switching personality (owner's decision).** Keep the user's agreed manner and decision preferences across a switch, or tell the user and the host what is dropped.
4. **Resetting the relationship (owner's decision).** Keep the user's "don't bring this up" boundaries through a reset, or ask first.
5. **Saving shared moments.** Make it less eager: no "first conversation", no ordinary news, no confided bad day the two did not go through together. Make the count match the listing.
6. **Short replies.** Turn "short" into a concrete limit in the persona text (for example "two or three sentences").
