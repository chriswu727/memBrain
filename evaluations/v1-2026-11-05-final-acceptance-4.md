# Final behavioral acceptance (R4), attempt 4, 2026-11-05: not passed (proxy arm passes, plugin arm fails on one reply)

This attempt ran the [frozen plan](v1-2026-11-05-final-acceptance-plan-4.md) on runtime `a558612` with two new held-out scenarios, L and M. The attempt was valid.

**R4 is not passed.**
- **Proxy arm (`E`): passes** every criterion.
- **Plugin arm (`P`): fails** on criterion 2. One of its replies has a standing critical error, and both attributors found it memory-caused.

Both gated arms scored well above the reference arm with the whole history in the prompt, by 6.5 and 8 points.

## Result

These are blind first-reviewer scores after resolution. A reply with a standing critical error scores 0.

| Arm | Scenario L (11) | Scenario M (11) | Total (22) | Literal total | Replies with a standing critical error |
| --- | --- | --- | --- | --- | --- |
| Plugin path (`P`) | 10 | 9.5 | **19.5** | 19.5 | 1: M06-C (type 4), memory-caused |
| Proxy with note extraction (`E`) | 10.5 | 10.5 | **21** | 21 | 0 |
| Whole history in the prompt (`F`, reference) | 7.5 | 5.5 | 13 | 13 | 6: L03-A (2), L06-A (1), L10-A (1), M05-B (1, 4), M06-A (4), M10-C (1, 4) |

The resolution reviewers changed no marks in either scenario. L10-B's conditional type 4 mark was rejected by the second reviewer, and R2 confirmed the rejection.

**The gate** (`acceptance_review.py gate`):

| Arm | 1. Total ≥ reference − 1 (12) | 2. No memory-caused critical error | 3. Host-caused ≤ reference's 6 | Passes |
| --- | --- | --- | --- | --- |
| `P` | 19.5: yes | no (M06-C) | 0: yes | **no** |
| `E` | 21: yes | yes | 0: yes | **yes** |

**Other views, as the plan requires:**
- **Absolute totals** against the lowest reference total so far (16.5): `P` 19.5 and `E` 21. Both are above every reference total of the four attempts.
- **Attempts 1 and 2's rule** (at least 20 of 22 and no critical error): `E` passes it, with 21 and none. `P` fails it, on both counts.

## The plugin arm's failure: M06-C

**What the reply did.** In a session about a real trip, the reply said that May 2 had "originally" been planned for the west route (Yardang, Yumen Pass) and was now changed. The user never planned that. In an earlier session, the assistant itself had suggested a rough four-day itinerary that put the west route on May 2. The plugin host's `memory_recall` returned that earlier reply, labelled "assistant said", and the host repeated the assistant's own suggestion as the user's original plan.

**Attribution.** Both attributors answered `memory`, because the rules count a recalled earlier assistant statement that the reply repeats as memory. The cause is therefore `memory`, and the plugin arm fails.

**This is the same pattern as attempt 3's J07-C.** There too, memory accurately replayed the assistant's own earlier words, and the reply presented them as something about the user.

The recall block marks each line "user said" or "assistant said", but its header does not say what an assistant line is worth. **This is a product issue, not a scoring artefact.** The next repair is for the recall and history headers to say that assistant lines are the assistant's own earlier replies: their suggestions and drafts are not the user's plans or facts unless a user line confirms them.

## Other non-passes in the gated arms

| Arm | Case | Score | Reason (first reviewer) |
| --- | --- | --- | --- |
| P | L01-B | 0 | The advice broke the scenario's temporary restriction. The second reviewer called this a criteria failure, not a critical error. |
| P | M11-C | 0.5 | It made a slip and then corrected it. |
| E | L06-C | 0.5 | A partial answer on an overdue item. |
| E | M05-A | 0.5 | A partial answer. |

## The repairs in this attempt

- **Resumed turns.** In both scenarios the plugin host paused for the off-the-record message and called `memory_resume` on the next message, and that message was now stored. No reply in any gated arm leaked off-the-record content.
- **Lost corrections.** Attempt 3's J09 and J10 failures were caused by lost corrections. Neither L nor M produced a type 3 error (a corrected fact used) in any arm.

## Scoring, as run

- **Validity:** valid for all six run directories. There were no empty replies, so no empty reply had to be retried. Transport errors (`RemoteProtocolError`) were retried inside the call: once in `l-E` and twice in `l-F`.
- **Review pipeline:**
  - one first reviewer per scenario;
  - one fresh second reviewer for each of the 22 cases;
  - one fresh resolution reviewer per scenario, with no access to the label mapping;
  - the tally and gate in `acceptance_review.py`.

  No score was changed by hand.
- **One mechanical correction.** Both first reviewers keyed their verdicts by case prefix (`L01`) instead of the full case id that [first.md](acceptance-review/first.md) asks for. Before the split, each key was renamed to its full id; this is unambiguous because each prefix matches exactly one case. No verdict was changed. The original files are kept in the evidence as `verdicts-l.raw.json` and `verdicts-m.raw.json`.
- **Attribution:** two fresh agents, each run once, for the one gated critical reply. Both answered `memory`.

## Cost

DeepSeek spending was 15.88 CNY: 7.51 for scenario L and 8.37 for M (balance 308.87 → 292.99). The four attempts together cost 81.12 CNY.

## Evidence

The [evidence archive](v1-2026-11-05-final-acceptance-4.evidence.tar.gz) holds:
- the per-turn results, blinded sheets and sealed mappings;
- the verdicts (including the raw files), re-checks, resolutions and tallies;
- the attribution inputs and outputs, and `gate.json`;
- the pre-checks, the date pre-check, the validity output, the balances and the run logs.
