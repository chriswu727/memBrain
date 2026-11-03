# Final behavioral acceptance (R4), attempt 3, 2026-11-04: invalid

This attempt ran the [frozen plan](v1-2026-11-04-final-acceptance-plan-3.md) on runtime `9a1816a` with two new held-out scenarios, J and K.

**The attempt is invalid** under the plan's validity guard, so it neither passes nor fails. In scenario K, two arms each recorded one empty reply:
- the proxy arm `E`, at `f08-mapo-tofu` turn 1;
- the reference arm `F`, at `s02-salt-well-project` turn 0.

In both turns the host model returned thinking but no answer. For example, `F` spent 2,263 completion tokens and produced no text.

**Scenario J was valid and fully scored first.** Its scoring found two real memBrain defects, which are now fixed. Scenario J alone already decided the plugin arm: it had memory-caused critical errors, so it would have failed the revised rule whatever K showed.

## Scenario J

These are blind first-reviewer scores after resolution. A reply with a standing critical error scores 0.

| Arm | Scenario J (11) | Literal | Replies with a standing critical error |
| --- | --- | --- | --- |
| Plugin path (`P`) | 8 | 8 | 3: J07-C, J09-C, J10-B |
| Proxy with note extraction (`E`) | 10.5 | 10.5 | 0 |
| Whole history in the prompt (`F`, reference) | 6 | 6 | 4: J02-B, J04-A, J05-B (type 4), J10-C (type 1) |

**Attribution.** Two fresh agents attributed each of `P`'s three critical replies independently, and both answered `memory` for all three.

| Case | Type | What happened | Cause |
| --- | --- | --- | --- |
| J09-C, J10-B | 3: a corrected fact used | On July 6 the user wrote "back on the record" and moved the return flight from Monday 27 to Tuesday 28 September. The plugin host resumed recording and saved a note. Later sessions still showed the May 12 message with the old date, and never showed the correction. | memBrain defects 1 and 2 below |
| J07-C | 4: an invented fact | The reply said "you mentioned back in August I'd flagged it [the CORU renewal] and it was still open". In this arm the assistant really had flagged it, in its reply of August 16, and memory recalled that reply accurately. The ground truth covers only what the user said, so the reviewers marked the claim as invented. The attribution rules settle an unclear case as `memory`. | Counted as memory; the memory content was accurate |

**Defect 1: the message that ends a pause was lost.**
- Sequence: the plugin host had paused for the off-the-record message, and the next message opened with "back on the record". The prompt hook staged that message while recording was still paused, so it was not kept. The host then called `memory_resume` in the same turn, but the turn stayed unrecorded.
- Effect: the correction never entered history or recall.
- Fix: the agent's resume now marks the current turn, and the turn is stored from its prompt. Claude Code and the harness take the prompt from the transcript; OpenClaw sends it with the stop hook. A resume from the memory page or the command line still stores nothing from a turn in progress, and neither does a turn that is paused again during the message.

**Defect 2: an older note took a newer one's place.**
- The host saved the correction as a separate note without replacing the old one, which was a host mistake.
- When the notes did not all fit, selection skipped the newer, longer note and showed the older, shorter "flights booked … return Mon 27 Sep" note of the same rank.
- Fix: once a note of a rank does not fit, older notes of that rank are left out too.

Both fixes are in commit `a7cbda6`, with tests.

**Other observations from J:**
- The proxy arm `E` scored 10.5 of 11 with no critical error.
- The reference arm, with the whole history in the prompt, scored 6. Its host invented or misplaced details in four replies.
- The plugin arm paused for the off-the-record message only, and no reply leaked its content.

## Scenario K

All three arms ran to the end. The validity guard then found the two empty replies, so K was not scored.

While diagnosing the empty replies, the developer printed both rows in full, including the first 800 characters of each transcript. That showed one of K's user messages and part of a memory block, so K is no longer held out:
- attempt 4 replaces it with a new scenario, M;
- K's attempt-3 results are never scored or used.

## Changes for the next attempt

These are set out in [attempt 4's plan](v1-2026-11-05-final-acceptance-plan-4.md):
- **Harness.** An empty host reply (no answer and no tool call) is now treated as a malformed response and retried. The harness also mirrors the Stop hook for a resumed turn.
- **Run procedure.** A run script starts each scenario's arms in new directories and never reuses one.
- **Validity.** Validity runs on all six directories before anything is blinded or scored. If it fails, a `diagnose` command shows only error lines and turn positions, never case content.
- **Scenarios.** New held-out scenarios L and M replace J and K. Fresh agents wrote them under the same restrictions, and two independent reviews checked them.
- **Unchanged:** the pass rule, the review instructions and the attribution rules.

## Cost

DeepSeek spending was 18.27 CNY: 8.10 for scenario J and 10.17 for scenario K (balance 327.14 → 308.87). The three attempts together cost 65.24 CNY.

## Evidence

The [evidence archive](v1-2026-11-04-final-acceptance-3.evidence.tar.gz) holds:
- J's per-turn results, blinded sheet and sealed mapping;
- J's verdicts, re-checks, resolution and tally;
- J's attribution inputs and both attributors' outputs;
- the pre-checks, balances and K's validity output.

K's run directories are kept sealed in the archive and are not opened.
