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

## What is not known

**Why the host paused.** That needs the user's message of turn 8, and perhaps what the consolidation batch returned. Three explanations are open and cannot be told apart from codes: the message asks for privacy and the host took that for a request not to remember; the message quotes or mentions such a request without making one; or nothing in the message relates to it. The lead tried twice to learn more without seeing the text (reading the harness's own event file, and having isolated sessions classify the message by a single letter); the session's permission layer refused both as access to sealed evidence, and the lead did not work around it. Whether S1 is unsealed for diagnosis is the owner's decision.

Also not known: whether the same host pauses this way often, whether a Claude Code host does (it did not in the 86 turns of the [2026-11-13 trial](host-trial-2026-11-13.md)), and how the plugin path would have scored. Eight turns of one scenario are not a measurement of anything but this one event.

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

- The cause has to be known before another paid run: the same host would meet the same turn.
- **A question for the next binding, not changed here:** an unexpected pause by the host is treated as an invalid run and stops it. It may be better scored as a recording failure of the plugin path, since it is the path's behaviour and not a fault of the harness; but then every later turn of that conversation is unrecorded too, and the cases that depend on them fail with it. The rule was fixed before this run and is left as it was.
- A pause that the host starts on its own costs the user every later message of that conversation. Whether the product should ask more of a host before it pauses (for instance the user's words that asked for it) is a design question to settle once the cause is known.
- A new attempt needs its own approval and ceiling.
