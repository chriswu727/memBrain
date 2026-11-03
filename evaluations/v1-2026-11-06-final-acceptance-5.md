# Final behavioral acceptance (R4), attempt 5, 2026-11-06: not passed

This attempt ran the [frozen plan](v1-2026-11-06-final-acceptance-plan-5.md) on runtime `b6d725a` with held-out scenarios N and O.
- **Runs 1 and 2 were invalid** because of a port left in TIME_WAIT. They are described [below](#runs-1-and-2-stopped-two-invalid-runs).
- **The owner chose to fix the run procedure and run again.**
- **Run 3** used the revised run script (Revision 2 of the plan). It was valid and was scored in full.

**R4 is not passed:**
- **Plugin arm (`P`): fails criterion 2.** Its total of 19 is above the reference's 17.5, but three of its replies have memory-caused critical errors. Two of those three are truthful references to the assistant's own earlier replies; see below.
- **Proxy arm (`E`): fails criterion 1.** Its total of 16 is below the reference's 17.5 minus 1. Its three critical errors were all host-caused.

## Run 3 result

These are blind first-reviewer scores after resolution. A reply with a standing critical error scores 0.

| Arm | Scenario N (11) | Scenario O (11) | Total (22) | Literal total | Replies with a standing critical error |
| --- | --- | --- | --- | --- | --- |
| Plugin path (`P`) | 9 | 10 | **19** | 19 | 3, all memory-caused: N06-C (4), N08-C (4), O09-C (1) |
| Proxy with note extraction (`E`) | 9 | 7 | **16** | 15 | 3, all host-caused: N06-B (1), O09-A (1), O10-C (1, 4) |
| Whole history in the prompt (`F`, reference) | 11 | 6.5 | 17.5 | 17.5 | 4: O05-B (4), O08-A (1), O09-B (1, 4), O10-B (4) |

**Resolution changes** (made before unsealing):
- N06-B lost its type 4 mark under R2. Its type 1 still stands.
- N08-B lost its type 4 mark under R2 and now has no mark.
- O10-C gained a type 1 mark under R2.

**The gate:**

| Arm | 1. Total ≥ 16.5 | 2. No memory-caused critical error | 3. Host-caused ≤ 4 | Passes |
| --- | --- | --- | --- | --- |
| `P` | 19: yes | no (3) | 0: yes | **no** |
| `E` | 16: no | yes | 3: yes | **no** |

**Comparisons the plan requires:**
- **Absolute totals:** `P` 19 and `E` 16, against the attempts 1–2 benchmark of 16.5 and the lowest reference total so far of 13.
- **Attempts 1 and 2's rule** (at least 20 of 22 and no critical error) fails both arms.

## The plugin arm's memory-caused errors

**N06-C and N08-C are truthful references to the assistant's own earlier replies.**
- **N08-C:** the reply said "we talked ideas (recording his stories, a '70 memories' book)" and "flagged this back on May 19". The assistant really had said both, and recall served those replies as "assistant said" lines.
- **N06-C:** the reply said the passport and travel insurance were "flagged back in March, never confirmed". That is also true of the assistant's March reply. The same reply also invented a meeting time ("May 18 at 4 pm"), and both attributors traced that to the host.

The reviewers' ground truth records only what the user said, so they marked these references as invented facts (type 4). Under the frozen attribution rules, a reply that repeats a recalled earlier assistant statement is memory-caused, even when the statement is true. As the plan anticipated, this is conservative against memBrain. The same pattern decided attempt 3's J07-C. Attempt 4's M06-C was different: there, the host presented the assistant's own suggestion as the user's plan.

**O09-C is a real memory problem.** The plugin host had saved a note marking a plan as done: the user ordered and paid for a massage chair, with delivery booked for May 8 ("…定于5月8日送货…", status `done`, dated 2027-05-08). A later reply listed the chair as "5月8号已送到妈家" (delivered to Mum's on May 8), which the user never confirmed. The note's single `done` status covered both the payment, which was done, and the delivery, which was only scheduled. The reply took the whole note as done.

## The proxy arm

The proxy arm lost most of its points in scenario O, where it scored 7 to the reference's 6.5. Its non-passes:

| Case | Score | Reason (first reviewer) |
| --- | --- | --- |
| N02-A | 0 | It left out the camp registration reminder the user had asked for. |
| N06-B | 0 | It overstated a meeting as set (critical 1). Host-caused: the note said "intended, not confirmed done". |
| O06-A | 0.5 | It planned no rest before the night shift. |
| O08-B | 0 | It ignored the mother's type 2 diabetes when suggesting a cake. |
| O09-A | 0 | It stated a plan as done (critical 1). Host-caused. |
| O10-C | 0 | A drafted message claims an action that never happened (critical 1 and 4). Host-caused. |
| O11-A | 0.5 | The reminder was framed as if registration had already passed. |

## Scoring, as run

- **Validity:** valid for all six run directories.
  - One empty reply was retried in `o-F`, and transport errors were retried twice in `o-F`.
  - Before scenario O, the run script waited 60 seconds for the ports. This is the TIME_WAIT that broke runs 1 and 2.
- **First reviews:** `acceptance_review.py verdicts` accepted both first reviews. It renamed N's 11 prefix keys to full case ids; O's keys were already full ids.
- **Second review:** one fresh second reviewer per case, 22 in all.
- **Resolution:** one resolution reviewer per scenario, with no access to the mapping.
- **Attribution:** two attributors for each of the six gated critical replies. They agreed on all six.
- **No score was changed by hand.**

## Cost of run 3

DeepSeek spending for run 3 was 15.14 CNY: 7.47 for N and 7.67 for O (balance 283.83 → 268.69). With runs 1 and 2, the attempt cost 23.65 CNY.

## Runs 1 and 2 (stopped, two invalid runs)


This attempt ran the [frozen plan](v1-2026-11-06-final-acceptance-plan-5.md) on runtime `b6d725a` with held-out scenarios N and O. Both runs were invalid.

As the plan requires, **the attempt stops without a pass or fail**, and this diagnosis goes to the owner for a decision. Nothing was scored or blinded. Nothing in the run directories was read beyond what `acceptance_review.py validity` and `diagnose` print, so N and O are still unseen.

## What happened

**Run 1:**
- All three arms of scenario N finished cleanly: 65 of 65 turns each, no retries.
- Scenario O's arm `E` then failed at startup with `LocalProfileError: The requested local port is already in use`.
- The attempt was already invalid at that point, so arms `o-P` and `o-F` were stopped early, after 4 and 3 turns, to save time and cost.

**Run 2 (the re-run in new directories, with the same frozen files):**
- Arm `n-P` failed the same way, at startup.
- The re-run was stopped. No arm recorded a turn.

**Diagnosis (from `diagnose` and the runtime source, no case content).**
- The harness gives arms `P` and `E` fixed ports (8893/55533 and 8894/55534). At startup, `local_profile._available_port` checks a requested port by binding to it without `SO_REUSEADDR`.
- On Linux that bind fails while recently closed connections on the port are still in TIME_WAIT, which lasts about 60 seconds after a service stops.
- **In run 1,** O's arms started as soon as N's arms ended. Arm `E`'s port still held TIME_WAIT connections from `n-E`'s service.
- **In run 2,** `o-P`'s leftover service from run 1 had just been stopped, which left TIME_WAIT connections on port 8893.
- Before the re-run, the operator waited for the ports to have no listener, which they had none. That check does not see TIME_WAIT, so the wait was not enough.

**Attempt 4 was not affected.** There, the two scenarios happened to start far enough apart.

The failures are in the test procedure, not in memBrain's behaviour. Still, the plan allows one re-run, and both runs are invalid.

## Proposed fix (needs a revised plan and a new review)

The run script should wait before starting each arm until both of its ports pass the same bind test the runtime uses, with a time limit. The fixed ports stay as they are.

Nothing else would change:
- the runtime, the harness, the pipeline and the review rules stay as frozen;
- N and O can be used again, because nobody has seen them.

## Cost

DeepSeek spending in this attempt was 8.22 CNY (balance 292.34 → 284.12), almost all of it on run 1's complete N arms, which will not be scored. The balance had been read as 292.99 at the end of attempt 4, and the 0.65 CNY difference before this attempt began is not accounted for by any run.

The five attempts together cost 89.99 CNY, counting from the 0.65 difference onwards as spent.

## Evidence of runs 1 and 2

The working files are kept under the session scratchpad and are not archived in the repository. Archiving them would publish N's replies, while N and O remain held out:
- the pre-checks and the date pre-check;
- both validity outputs and both `diagnose` outputs;
- the balances and the re-run's wrapper script.

## Evidence of run 3

The [evidence archive](v1-2026-11-06-final-acceptance-5.evidence.tar.gz) holds run 3 only:
- the per-turn results, blinded sheets and sealed mappings;
- the verdicts (with the raw first-review files), re-checks, resolutions and tallies;
- the attribution inputs and outputs, and `gate.json`;
- the pre-checks, the date pre-check, the validity output, the balances and the run logs.

Runs 1 and 2 stay sealed and are not archived.
