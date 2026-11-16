# Seventh maturity attempt: R4 passes on the plugin path, by a thin margin

Attempt `maturity-20261116a` ran complete and valid on 2026-11-16 (17:23 to 17:56 UTC) and was scored blind the same day. **The gate says R4 passes, and the independent final review says the pass stands and is thin.** It is the first R4 pass, and the first complete scored run of the product as it now is: the plugin path alone, no model of memBrain's own, a personality in both arms. **It does not allow a release**: C5 is invalid and unscored, the R5 overhead protocol and the native platforms have not been requalified for this runtime, and the other items of the [closeout checklist](../docs/releasing.md) are open.

Frozen source `c5232a043d650824c7d12982893d876e88d57877` (runtime `a85ca152`, pin `4513d133`) under the [binding](maturity-acceptance-execution-2026-11-16.md): plugin path `P` against the whole-history reference `F`, host `deepseek-v4-pro` through the harness's emulation of the plugin's hooks and tools (not Claude Code), personality type `estj` in both arms, two held-out scenarios of 11 cases each (`s1b`: 17 sessions, 61 turns, mainly English with a German session, written for this attempt; `s2b`: 19 sessions, 63 turns, mainly Chinese with an English session, frozen for the [sixth attempt](maturity-sixth-attempt-stop-2026-11-16.md) and never run there). The lead ran it; sub-sessions prepared, scored and reviewed it; no one who works on the product read the scenarios or the replies before scoring ended. [Evidence](evidence/maturity-seventh-attempt-2026-11-16/): `gate.json`, the freeze review, the final review in both forms, the operators' reports, and an archive of the scenarios, replies, blinded sheets, every reviewer output and the control files.

## Result

| Scenario | `P` (plugin path) | `F` (whole history) |
| --- | --- | --- |
| `s1b`, of 11 | 9.0 | 7.0 |
| `s2b`, of 11 | 7.5 | 9.0 (7.5 before resolution) |
| Total, of 22 | **16.5** | **16.0** |

The pass rule, unchanged since it was revised after the second attempt of the first series, has three conditions:

| Condition | Value | Holds |
| --- | --- | --- |
| `P`'s total is at least `F`'s total minus 1 | 16.5 against 15.0 | yes |
| No reply of `P` has a standing critical error caused by memory | none | yes |
| `P`'s replies with a host-caused critical error are no more than `F`'s replies with a standing critical error | 1 against 2 | yes |

`P` has one standing critical error: in case `S201-tooth-eve` its reply says the user "already prepared the soft food" when she had only asked whether to stock porridge and pudding. Two independent attributors both answered that the host caused it. `F` made the same assumption with the whole history in front of it, and that is one of its two standing critical errors; the other is a leak of something the user had asked not to be remembered (`S110`), which `P` did not make.

## How strong the pass is

- **One judgement decides it.** Had either attributor of `S201` answered "memory", the attempt would have failed. The final reviewer read that turn and agrees with "host": memory had supplied the user's own messages and a note, and nothing saying the food was stocked. No single score judgement could flip the result; two could.
- **The margin over the reference is half a point**, and 16.5 of 22 is lower than the plugin path's 19 to 20 in the earlier scored attempts. Those ran other scenarios, a different prompt (the whole skill text in every call) and no personality, so the totals are not comparable; this one says only that on these two scenarios the plugin path did as well as the whole history.
- **`P` lost 5.5 points over eight cases** (`S105`, `S106`, `S107`, `S201`, `S202`, `S204`, `S208`, `S210`); `F` lost 6.0 over nine. By the final reviewer's reading `P`'s losses are missed "should" items, a constraint that memory supplied and the host ignored (`S107`), a wrong side-detail (`S204`), a plan stated as done (`S201`), and the off-the-record case below (`S210`).
- **One sample.** One host model under emulation, one personality, two scenarios, every reviewer a Sonnet session, two arms and therefore partial blinding.

## What the run showed about the product

**Working as designed.**

- **The off-the-record stretch held in both scenarios.** The host paused with the user's exact words (the argument that became required the day before), resumed naming the conversation when asked, and the off-the-record messages are absent from later contexts and from the stopped databases. The reference arm leaked in one scenario.
- **No slip of the kind that ended the sixth attempt**: no turn was left unrecorded by a pause of the host's own, so the stop rule changed for this attempt was never exercised and the result is the same as under the old rule.
- The host called tools in about half the turns (30 of 61 and 32 of 63): 30 and 33 notes, 14 consolidation calls in each scenario, and a search made on purpose 3 times and once. No tool answered with an error.

**Two defects to fix, found by the final review. Neither is a critical error under the rule; both are visible to a user.**

- **After an off-the-record stretch the agent is not honest that there was one.** Asked later about what was said then, the host acted as if nothing had been said: "the other print place?" in `S110`, "you probably didn't say why, or mixed up the day" in `S210`. Nothing was leaked, and that is what the stretch is for; but the user's own later line ending the stretch was in front of the host, and nothing tells it that part of that conversation was kept out at the user's request. `S210` scored 0 for this; `S110` kept its point.
- **Doubled replies.** In 11 of 124 turns the user of `P` is shown two answers one after the other, written in separate rounds of the same turn (an answer, then tool calls, then a second answer or a closing line). `F` never does it. The same was seen in the sixth attempt's replays, where the host closed 5 of 12 consolidation turns with a second answer.

## How it was run and scored

- **Preparation**: a new execution clone; the first scenario written, reviewed and fixed by six isolated Sonnet sessions and approved in the third and last allowed round (four minor findings left unapplied, since a fix would need a new review); the second scenario copied by path with its approval, byte-identical to what was frozen for the sixth attempt; 760 tests of the acceptance tooling and two stub rehearsals; an independent freeze review that allowed the start with eight minor findings.
- **The run**: 327 host requests, all settled; every turn present in both arms; strict validity passed for both scenarios; no harness event, no empty reply, no retry, no reply with raw tool-call markup. Services stopped by the harness's own cleanup; ports closed.
- **Scoring**: the frozen pipeline's R4 unit, 37 isolated Sonnet sessions (2 first reviews, 23 second reviews of which one was redone because its session wrote no output, 8 checks of assistant claims, 2 resolutions, 2 attributions). Three critical marks were removed in resolution, all of the same type and under the same rule, against the scenario's own messages; two of the three favoured the reference arm (1.5 points and two critical errors fewer for `F`), so they made the gate harder for `P`.
- **Final review**: recomputed the tallies and the gate three ways with the same result, re-hashed all 437 frozen files, re-ran validity, read the deciding cases, and found nothing blocking or major.

**Deviations, all judged harmless by the final review, recorded here as they were:**

- The reviewer sessions were started with the kit's isolation flags but without the extra variable that points the product at an empty directory. No trace was found that a session reached the product or that held-out text was recorded into a real memory (no service running, no profile touched, no tool-server log for any review directory); what a session did not read cannot be proven from outside.
- The scoring operator ran the tally once per scenario before resolution to check the second reviews, read only its exit code, and deleted the provisional file.
- The count of memory wording in case replies (0 of 22, from a fixed phrase list) undercounts: the final reviewer found such wording in three of `P`'s case replies and one of `F`'s, and one doubled answer among `P`'s. With two arms that can tell a reviewer which reply is which. None plausibly changed a judgement.
- The lead's first start of the run, at 07:16 UTC, was refused by the session's permission layer because the owner had approved the plan and not yet this spend; nothing ran. The owner approved it in words later that day and the run started at 17:23 UTC. The times written inside the approval and price-check files are a few minutes later than the files' own times; the order required by the binding holds.
- The freeze review asked the record to state a limitation the binding does not: **the requirement that a pause carry the user's words had not been run on any real host before this attempt.** A probe on the same host model the same morning (ten of ten pauses with the user's exact words, in English, Chinese and German) and the two pauses of this run are all there is. A host that paraphrases or translates the user's request would be refused; that has not been seen and has not been tested.

## Cost

The guard's conservative count is **28.785141 CNY** of the 80 CNY ceiling (2,860,255 prompt tokens and 112,698 completion tokens at the policy's 9 and 27 CNY per million). The account's balance fell by **4.76 CNY** (125.34 to 120.58): the run fell in off-peak hours and most input was served from the provider's cache. Prices were re-read from the provider's page twice that day and matched the policy. Subscription use: 43 isolated Sonnet sessions (6 for the scenario, 37 for scoring); the session launchers do not report their cost.

## What this attempt yields

1. A first valid, scored result for the product as it is, and an R4 pass that an independent review upholds with its limits stated.
2. Evidence that the fix made after the sixth attempt works where it was needed: two pauses, both with the user's words, both ended when asked.
3. Two concrete defects to fix next: the agent's honesty about an off-the-record stretch, and doubled replies.
4. Acceptance tooling that ran a whole attempt, scoring and two independent reviews without a stop.

## What stays open

R4 is one gate. C5 (the companion layer) has never had a valid scored run. The R5 overhead protocol, the five native platforms and GitHub Verify were not rerun for this runtime. No real plugin host other than Claude Code has been tried, and Claude Code only in headless trials. "Important memories first" is not built. A repeat of R4 on other scenarios, another host model or a real host would say how far this result carries; one pass on two scenarios does not.
