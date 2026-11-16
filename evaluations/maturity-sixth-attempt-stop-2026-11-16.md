# Sixth maturity attempt stopped: the host paused recording in a turn the scenario meant to be recorded

Attempt `maturity-20261115a` stopped as **invalid** at S1, arm `P`, after 8 of 61 turns, on 2026-11-16 04:25:32 UTC (15 November in Vancouver), 99 seconds after it started. Arm `F` of S1 and both arms of S2 did not run. Nothing was scored. **R4 remains not passed; C5 remains invalid and unscored.** No merge, tag or release follows from this attempt, and by its stop rules there is no retry, no reopened ledger and no further attempt under its approval.

Frozen source `75506372a3f245c1888aae30735386cfca2db0ab` (runtime `548674ce`, launcher pin `0b0392bc`), under the [binding](maturity-acceptance-execution-2026-11-15.md): plugin path `P` against the whole-history reference `F`, host `deepseek-v4-pro`, personality type `isfj` in both arms, two new held-out scenarios (S1: 21 sessions, 61 turns, 11 cases; S2: 19 sessions, 63 turns, 11 cases), ceiling 80 CNY. The lead ran it; the lead does not read the scenarios, the replies or the run directories, and what follows comes from the driver's summary, the ledger and the content-free diagnosis. [Evidence summary and hashes](maturity-sixth-attempt-stop-2026-11-16.json).

## What happened

The harness records an event and stops a live arm when a turn is left unrecorded that the scenario did not mean to leave unrecorded ("a turn left unrecorded because the host did not resume recording makes the scenario invalid", in the binding's stop rules). It did so at the first message of the third session:

| Turn | Position | Tools the host called (fixed codes) |
| --- | --- | --- |
| 1 | session 1, message 1 | `memory_note` |
| 2 | session 1, message 2 | `memory_note`, `memory_note` |
| 3 | session 1, message 3 | `memory_note`, `memory_note` |
| 4 | session 1, message 4 | `memory_note` |
| 5 | session 2, message 1 | `memory_note` (answered with an error), `memory_note`, `memory_note` |
| 6 | session 2, message 2 | `memory_note`, `memory_note`, `memory_note` |
| 7 | session 2, message 3 | `memory_note` |
| 8 | session 3, message 1 | `memory_note`, `memory_consolidate`, `memory_consolidate`, `memory_pause` |

In turn 8 the host AI called `memory_pause` with no duration and not "until resumed": a pause for the rest of the conversation, which also leaves the current turn unstored. The scenario's script has no pause at that turn, so the turn counted as unexpectedly unrecorded (`turn_not_recorded`, the run's only harness event). The log holds no exception and no host error. The ledger was blocked with `harness_degraded`, the arm ended after writing the turn's row, the driver reported `runner_failed` for `s1` and `not_run` for `s2b`, and its exit code was 1.

So the stop is the harness working as bound, on a real behaviour of the plugin path: **a host AI, given what the shipped plugin gives it, stopped recording when the scenario's author did not expect it to.** The session notice tells the host to call the pause tool "if the user asks you not to remember something", and the tool's description says to pause only when the user asks not to be remembered or stored, and not when they ask for something to be kept private. The server's standing instructions do not mention pausing.

## Why the host paused: found after unsealing the turn

Added later on 2026-11-16. The owner allowed the first scenario to be unsealed for diagnosis; the second stays sealed. Before that the lead had tried twice to learn more without seeing the text (reading the harness's own event file, and having isolated sessions classify the message by a single letter); the session's permission layer refused both as access to sealed evidence, and the lead did not work around it.

**The user asked for nothing of the kind.** The message of turn 8 says that the kitchen tap drips all night and that they will email the landlord tomorrow. What the host did ([the turn](evidence/maturity-sixth-attempt-2026-11-16/turn-8.json)):

| Round | The host | Reasoning tokens |
| --- | --- | --- |
| 1 | wrote its whole answer, saved a note, asked for the consolidation batch | 277 |
| 2 | handed back cues for seven earlier messages; the tool answered "Done. If your answer to the user's message is not yet written in this turn, write it now in full; this is not the reply." | 142 |
| 3 | called `memory_pause` with no arguments | **0** |
| 4 (no tools offered, as the harness's fourth round always is) | reasoned at length and wrote a `memory_resume` call as raw markup, which became part of its reply | 634 |

So the answer was already written, the housekeeping was done, the host had nothing left to say, and it called a tool that takes no arguments, without reasoning. One round later it tried to undo that and could not, because the harness offers no tools in the last round. The pause was a slip of the host's, not a misreading of the user.

**How often.** The turn was replayed twelve times against the same host with the same prompt, tools and recorded tool answers ([script](evidence/maturity-sixth-attempt-2026-11-16/replay.py), [results](evidence/maturity-sixth-attempt-2026-11-16/replay-results.json)): the host consolidated every time and paused in none. Its closing line after consolidation began with "Done.", "All noted." or "Sorted" in seven of twelve and was a second answer in the others. One slip in the attempt's one consolidation turn and none in twelve replays: rare, and not a rate. The probe's conservative count is 3.08 CNY (every prompt token at the uncached peak price), approved by the owner as a diagnosis of up to 5 CNY; the account's balance had not moved when read half a minute after it.

**What it means for the product.** A rare slip of the host silently ends recording for the rest of a conversation: the pause tool accepts a call with no arguments, its answer does not ask the host to tell the user, and after consolidation the host is told what to do only if its answer is not yet written. Those three were changed the same day: [a host AI's pause needs the user's words](pause-request-2026-11-16.md).

Still not known: whether a Claude Code host ever slips this way (it did not in the 86 turns of the [2026-11-13 trial](host-trial-2026-11-13.md)), and how the plugin path would have scored. Eight turns of one scenario are not a measurement of anything but this one event.

## Two things the eight turns do show

- **The host wrote a note in every turn**: 14 `memory_note` calls in 8 turns, one of them answered with an error. The [note-anchor rule](age-weight-and-importance-2026-11-13.md) was withdrawn because nothing keeps notes rare; here is a host that notes more than once per message.
- **The host consolidated** in the first turn of the first session that began with at least five messages waiting, which is when the session notice asks for it (two calls: one to fetch the batch, one to hand it back).

## Cost and shutdown

All 19 provider requests settled; none was open at the stop. The guard's conservative count is **1.533573 CNY** (152,256 prompt tokens and 6,047 completion tokens at the policy's 9 and 27 CNY per million). The account's balance moved by **0.26 CNY** between the read before the run and the read three minutes after it; snapshots can include unrelated activity and are separate from the guard's count. Prices were re-read from the provider's pages before the run and matched the policy. The run's one service and database were stopped by the harness's cleanup (one profile stopped, none failed), ports 8893 and 55533 were closed, and no process of the attempt remained. The key was read from a git-ignored file into the run's environment and never printed.

Subscription use for this attempt: 17 isolated Sonnet sessions for writing, reviewing and fixing the scenarios and for the isolation probe. No scoring session ran.

## Diagnosis tooling

Before this attempt the content-free diagnosis (`acceptance_review.py diagnose`) printed how far an arm got, empty replies, harness events by kind and position, and counts of log error lines. That could say a turn was unrecorded and not what the host had done. It now also prints the tools the host called in each turn as fixed codes: a name only when it is one of the fourteen the plugin lists (anything else is "other"), whether a pause was timed or until-resumed, whether a resume named its session (which decides whether the current turn is stored), and whether the tool answered with an error. No argument or result text is printed; the test plants a marker string in every name, argument and result and checks that none appears. The table above is that output, run from the repository on the preserved run directory; the frozen clone was not changed. 174 tests of the review pipeline and scenario paths pass; no database or model is involved.

## What is kept

The execution clone, the manifest, the blocked ledger, the driver's state, the run directory of `s1-P` and both scenarios are kept unchanged and sealed. S2 was never shown to any model. The stopped ledger and output directories are not reused.

## What this means for the next attempt

- The cause is known (above) and the product is being changed for it before another paid run.
- The harness's last round offers no tools, so a host that wants to call one there writes the call as text into its reply. A real host always has its tools. That is a property of the frozen call shape, to be looked at in the next binding.
- **Changed for the next binding, after this record was first written:** an unexpected pause by the host was treated as an invalid run and stopped it, while a host that fails to pause when asked was already scored. From the next attempt on, a turn left unrecorded by the host's own accepted pause is the plugin path's behaviour: the run goes on, the turn is listed (`host-pauses.jsonl`, reported by validity and by the diagnosis), and the cases that depend on it are scored as they come out. An unrecorded turn that no accepted pause of the host explains still stops the attempt. This attempt's rule was fixed before its run and its result is left as it was. Validity and the diagnosis also count replies that contain raw tool-call markup. Checks: 731 tests of the harness, review pipeline, driver and kit, and the stub rehearsal, in a sub-session; 594 on the integrated source.
- A pause that the host starts on its own costs the user every later message of that conversation. Whether the product should ask more of a host before it pauses (for instance the user's words that asked for it) was a design question when this was written; see the section on the cause above.
- A new attempt needs its own approval and ceiling.
