# Final behavioral acceptance (R4), attempt 6, 2026-11-07: not passed (one memory-caused reply in each gated arm)

This attempt ran the [frozen plan](v1-2026-11-07-final-acceptance-plan-6.md) on runtime `a551100` with held-out scenarios Q and R.
- **Run 1 was invalid.** A container restart stopped scenario R's proxy arm at 60 of 66 turns. As the plan requires, nothing was scored, and the owner chose to run both scenarios again.
- **Run 2 was valid** and was scored in full.

**R4 is not passed.** Both gated arms clear criterion 1 by a wide margin and have no host-caused critical error, but each has exactly one memory-caused critical reply:
- **Plugin arm (`P`):** 19.5 against the reference's 15. It fails criterion 2 on R11-B.
- **Proxy arm (`E`):** 20 against the reference's 15. It fails criterion 2 on R04-B.

## Result (run 2)

These are blind first-reviewer scores after resolution. A reply with a standing critical error scores 0.

| Arm | Scenario Q (11) | Scenario R (11) | Total (22) | Literal total | Replies with a standing critical error |
| --- | --- | --- | --- | --- | --- |
| Plugin path (`P`) | 10.5 | 9 | **19.5** | 18.5 | 1, memory-caused: R11-B (4) |
| Proxy with note extraction (`E`) | 11 | 9 | **20** | 19 | 1, memory-caused: R04-B (4) |
| Whole history in the prompt (`F`, reference) | 7.5 | 7.5 | 15 | 15 | 5: Q05-A (1, 4), Q09-B (1), Q11-C (1), R06-A (4), R10-C (2) |

**Resolution changes** (made before unsealing): Q06-A and Q06-B each lost a type 4 mark under R2. That user fact had been stated on the record, and R2 alone gives the same result.

**Rule R5:**
- **R5 cleared no mark.** Nine replies had a candidate type 4 mark (Q05-A, Q06-A, Q06-B, R04-B, R06-A, R07-A, R07-B, R07-C and R11-B).
- **All 18 checker answers were valid,** and none cleared its mark. R2 then decided every one of the nine, exactly as it would have without R5.
- **What R2 decided:** Q06-A, Q06-B, R07-A, R07-B and R07-C do not stand, because the facts were stated in earlier user messages. Q05-A, R04-B, R06-A and R11-B stand.

**The gate:**

| Arm | 1. Total ≥ 14 | 2. No memory-caused critical error | 3. Host-caused ≤ 5 | Passes |
| --- | --- | --- | --- | --- |
| `P` | 19.5: yes | no (R11-B) | 0: yes | **no** |
| `E` | 20: yes | no (R04-B) | 0: yes | **no** |

**Comparisons the plan requires:**
- **Absolute totals:** `P` 19.5 and `E` 20, against the attempts 1–2 benchmark of 16.5 and the lowest reference total so far of 13. Both are the highest totals of any attempt.
- **Attempts 1 and 2's rule** (at least 20 of 22 and no critical error) fails both arms. Each arm has one critical error, and `P` also misses the score bar by half a point.

## The two memory-caused replies

Both are the same pattern as attempt 4's M06-C. The host turned the assistant's own earlier suggestion into a fact about the user's life.

**R11-B (plugin arm).** The reply referred to "妈妈的轻便折叠小凳（之前提过的那个）", Mum's light folding stool, "the one mentioned before". In earlier replies the assistant had suggested bringing a light folding stool. The user never said her mother has one. Recall served those suggestions as "assistant said" lines, and the reply presented the stool as the mother's.

**R04-B (proxy arm).** The user asked for a message that keeps a layoff secret. In an earlier reply the assistant had suggested a cover story, that the husband's company now allows flexible work. The draft stated that story as fact ("他们现在比较弹性…"), together with a detail about picking the child up early.

**Why the fixes did not catch these.**
- **The header did not stop it.** Since attempt 5, recall marks these lines as the assistant's own earlier replies and says that a suggestion in them is not a fact about the user. The host still used them as facts.
- **R5 correctly did not clear either reply.** Neither is a statement that the assistant said something; both present the content as true of the user's life (`user_fact`).

**What remains.**
- In attempts 4 to 6, every memory-caused critical error in either gated arm came from recalled assistant speech: M06-C, N06-C, N08-C, R04-B and R11-B. Attempt 5's O09-C is the one exception, the "done" note.
- In attempt 6, no failure came from notes, history, corrections, pauses or plan status.

## Other non-passes in the gated arms

| Case | Arm | Score | Reason (first reviewer) |
| --- | --- | --- | --- |
| Q09-A | P | 0.5 | It offered delivery to a venue that was not confirmed. |
| R01-A | E | 0 | It did not account for the user's temporary dietary restrictions. |
| R05-A | P | 0 | It left out the reminder that was due that day. |

## Scoring, as run

- **Validity:** valid for all six run-2 directories.
  - One empty reply was retried in `r-E`.
  - Transport errors were retried in `q-F` (1), `r-P` (1), `r-E` (2) and `r-F` (1).
- **First reviews:** `verdicts` accepted both. It renamed R's 11 prefix keys to full case ids; Q's keys were already full ids.
- **Second review:** 22 second reviewers, one per case.
- **R5:** 9 inputs and 18 answers. `r5-check` found no invalid answer.
- **Resolution:** two resolution reviewers, one per scenario.
- **Attribution:** two attributors for each of the two gated critical replies. They agreed on both.
- **No score was changed by hand.**
- **One procedural note.** The R resolution reviewer reported writing, and then deleting, a temporary dump of the scenario's user messages in the review folder. The scenario file was one of its permitted inputs, so this exposed nothing it was not allowed to read.

## Cost

| Item | CNY |
| --- | --- |
| Run 1 (sealed, not scored), from the balance at the start of the attempt | 268.69 → 235.24 = 33.45 |
| Run 2: scenario Q | 235.24 → 218.95 = 16.29 |
| Run 2: scenario R | 218.95 → 199.53 = 19.42 |
| **Attempt 6** | **69.16** |

Run 2 cost about twice as much per scenario as earlier runs. It ran in DeepSeek's daytime peak hours (Beijing time); earlier runs had fallen in the discounted overnight hours.

## Evidence

The [evidence archive](v1-2026-11-07-final-acceptance-6.evidence.tar.gz) holds run 2:
- the per-turn results, blinded sheets and sealed mappings;
- the verdicts (with the raw first-review file), re-checks, R5 inputs, answers and results, resolutions and tallies;
- the attribution inputs and outputs, and `gate.json`;
- the pre-checks, the date pre-check, the validity output, the balances and the run logs.

Run 1 is sealed and not archived.
