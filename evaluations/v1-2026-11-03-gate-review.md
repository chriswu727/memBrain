# Review of the R4 pass rule, 2026-11-03

After two failed attempts, the owner asked whether the R4 pass rule (at least 20 of 22 and no critical error) is a sound test of memBrain, or whether chasing it is wasted work. The rule was set before any data existed. This review checks it against the data from both attempts.

## What the reference arm shows

The reference arm `F` puts the user's whole history in the prompt. It is the best case for memory: nothing can be forgotten, crowded out or mis-filed. It ran with the same host, scenarios and reviewers.

| Attempt | Reference total | Reference critical errors | Plugin `P` | Proxy with extraction `E` |
| --- | --- | --- | --- | --- |
| 1 (F, G) | 17 of 22 | 3 | 16.5 | 19.5 |
| 2 (H, I) | 16.5 of 22 | 1 | 17 | 17 |

The host with perfect information failed the rule in both attempts, on score and on critical errors. Most lost points are answer completeness under a strict rubric: a rent figure not repeated, shop hours not stated, one item of a requested list missing. None of those depend on memory. So the absolute rule measures the host model (DeepSeek-V4-Pro) and the rubric at least as much as memBrain.

Pushing memBrain toward 20 of 22 would mean tuning prompts to one model's answering habits. That is the wasted work the owner asked about.

## What the critical errors show

A fresh agent attributed every standing critical error in the gated arms. It used [attribute.md](acceptance-review/attribute.md) and saw only what memory gave the host for that turn, plus the reply. It answered one question: did the memory the host received contain what it needed to avoid the error?

| Attempt | Memory-caused | Host-caused |
| --- | --- | --- |
| 1 | 6: the pause after "this stays between us" lost later updates (P ×4); a cancellation crowded out (E); a visit filed in the wrong month (E) | 0 |
| 2 | 0 | 4: a planned walker or booking treated as existing, while the notes said "intended, not confirmed done" |

This matches the manual diagnosis in both reports. Attempt 1's errors were real memBrain defects, and they were fixed. Attempt 2's errors happened with correct memory in front of the host, and the reference arm makes the same kind of error.

## Revised rule (used from attempt 3)

memBrain is responsible for what it gives the host. It is not responsible for the host's own answer quality. Each gated arm passes when all three of these hold:

1. **Not worse than the whole history.** Its total is at least the reference arm's total minus 1. One point is the reviewer noise measured in attempt 1, where the same replies scored 18.5 and 17.5.
2. **No memory-caused critical error.** A standing critical error counts against memBrain when the attribution finds `memory`.
3. **No more host-caused critical errors than the reference arm.**

The absolute scores and every critical error are still reported. Host-caused errors remain product work wherever memory can make the right answer easier: attempt 2's walker errors led to the "Planned, not confirmed done" change.

The rule was revised after attempts 1 and 2 had been scored, at the owner's request. It applies only to attempt 3 onward and does not reclassify attempts 1 or 2: under the revised rule, attempt 1 still fails on its memory-caused errors.
