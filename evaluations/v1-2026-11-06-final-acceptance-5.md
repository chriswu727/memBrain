# Final behavioral acceptance (R4), attempt 5, 2026-11-06: stopped, two invalid runs (owner decision)

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

## Evidence

The working files are kept under the session scratchpad and are not archived in the repository. Archiving them would publish N's replies, while N and O remain held out:
- the pre-checks and the date pre-check;
- both validity outputs and both `diagnose` outputs;
- the balances and the re-run's wrapper script.
