# A personality from the first session: sixteen types, switching, and changes the user confirms in conversation

Base: pin `68729eb3` (runtime `b46417e`). Runtime commits `1f27c392` to `bb55fb0f` (twelve, with one evaluation commit and an intermediate pin between them); pin commit `c6c313ff` points all nine launchers at the last. No migration. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## The decisions this follows

Until now the persona card was empty in the plugin path unless the user wrote one on the memory page, so most users never met the companion's character. The owner's answers on 2026-11-12:

- a new user starts with one persona, picked at random;
- the user is told that they can switch it with a command;
- mood and familiarity are shared: one relationship, not one per persona;
- when the host AI proposes a change to the persona, the user confirms it in the conversation.

**A first draft was wrong and was replaced.** The lead first drew up five presets of tone (Steady, Bright, Wry, Gentle, Blunt). Shown them on 2026-11-13, the owner said that this is not what a persona is: it is a personality type, as in MBTI. The owner also said that resetting the persona should pick a type again, at random or by name, not return to the first one. Both are as described below; the five presets were never released.

Built by a sub-session in its own working copy; the lead wrote the design, reviewed the diffs and merged them.

## What was built

**Sixteen personality types** (the four-letter types familiar from MBTI: INTJ, ENFP and so on). Each type's card is composed from its four letters: every letter contributes one trait and one value, and two of them set the voice, so that the types differ in the standard ways (outgoing or reserved, practical or imaginative, logical or tactful, organised or flexible). Each has a one-line summary in the project's own words, in English and Chinese, and a resting mood. No type has a name of its own (the host keeps its name), none claims real feelings, and none says anything about how well the agent does its work: a flexible type is not a careless one, and a logical type is candid, never unkind. A test keeps nicknames from commercial type sites and the trademarked names out of the cards. memBrain is not affiliated with the owners of the MBTI trademark, and the types are used as a familiar vocabulary, not as an assessment of anyone.

**A random one at the start.** A memory that has no persona record of any kind is given one type at its first session, on every host. That includes installations that existed before and never had a persona. A user who deleted their persona history, or saved an empty card, is not given one again. It is not done for a role-play memory, whose character is the persona, or while recording is paused. In that session the host AI is asked to mention the persona once, briefly, and to say how to switch.

**Switching and resetting.** In Claude Code, `/membrain:persona` lists the types, `/membrain:persona intj` switches to one, and `/membrain:persona reset` picks another at random (`reset intj` picks that one). Resetting no longer returns to an earlier card or to an empty one. On every host the user can ask in words and the host AI switches with the persona tool (`memory_persona`; `membrain_persona` on OpenClaw and AstrBot), citing the user's request. The memory page shows which type is current, can switch, and has "Pick another at random" where the reset button was. No other host has a command format in this repository, and none was invented.

**One relationship.** Switching changes the card only. A test shows the mood's triggers, pin and reset marker, familiarity, shared moments, boundaries, support style and commitments identical before and after; only the mood's resting point follows the new card.

**Changes the host AI proposes.** When the user asks the agent to behave differently from now on, beyond the seven kinds the manner-feedback tool records, the host AI may propose a change to the card. Nothing changes until the user says yes. The rule that keeps the host AI from confirming its own proposal is checked by the service: a confirmation cites exactly one message, and it must be the user's own message, recorded after a reply of the same conversation that was itself recorded after the proposal. A confirmation in the turn the proposal was made in, or one that cites an older message or the assistant's own, is refused. The saved version records which message confirmed it. The memory page lists the proposal too and can accept or reject it; earlier versions can be restored there at any time.

## Verification

- **Full local source suite on the pin commit `c6c313ff`**, with the local embedding model: 8,515 passed, 4 skipped (the Docker journeys), none failed, in 56 minutes; source and migrations unchanged during the run. No other test session ran on the machine during it.
- **The suite before it found a defect, which is fixed.** On `ab8559a4`, with the first draft of presets, 8,511 passed and 1 failed: after a user deleted their last note, the refresh notice no longer said "No saved notes are currently shown". It had said so only when the whole snapshot was empty, and with a persona for every user the snapshot is never empty. It now says so whenever no note is shown (`d92ca72a`), with a test.
- The sub-session's own runs under the shared lock: 573 of 574 on the first version (the one failure a count in a test, fixed), then 611 of 613 on the sixteen types (two expectations in tests, fixed; both files passed on rerun).
- TypeScript client: 58 tests pass and the type check is clean. OpenClaw plugin: 10 pass, 2 skipped there (they need a real runtime and passed through the Python suite).
- New tests cover: all sixteen cards valid, within limits and composed from their letters, with no claim of feelings and no nickname or trademark in them; each type's resting mood; the first assignment made once, also under six concurrent calls, and not after a deleted history or an empty card; the one-time line shown once and not resent; a switch that leaves the mood's triggers and the whole relationship unchanged; reset picking another type, a named one, or a host's own default; a new type after erasing all memory; a proposal refused when confirmed in its own turn, by an older message, by the assistant's message or through another conversation's reply, and applied by the user's next message; refusals while paused; the tool on each host with matching descriptions; the command file and manifest; every page string translated.

## What a persona costs the session context

Whatever the companion blocks take comes out of the room for recent history in the session context (about 9,500 characters in all). Measured without a model on the three LoCoMo development conversations, 383 questions, with a persona block of 716 characters from the first draft (the sixteen types' blocks are 747 to 775) ([script and rows](locomo/results-2026-11-13-persona-cost/)):

| Session context holds | History shown | All evidence in the whole context | In the recall block |
| --- | --- | --- | --- |
| no persona | 7,898 characters, 40.8 messages | 84.1% | 83.3% |
| a persona | 7,261 characters, 38.0 messages | 83.8% | 83.3% |
| a persona, a fresh mood and a relationship block | 6,115 characters, 31.8 messages | 83.6% | 83.3% |

One question of 383 lost its complete evidence to the persona block and one more to the mood and relationship blocks; none gained. The cost is small because most evidence reaches the host through the recall block, which does not change: of 519 evidence turns only 36 were in the history part, and only 3 of those were not in the recall block as well. What the shorter history costs in the flow of a conversation, as opposed to evidence for a question, is not measured.

## Not done, not known

- **No real host ran this.** Whether a host AI mentions the persona once and naturally, switches when asked, proposes only when the user asked for a lasting change, and waits for a yes, is not known. Whether a preset changes how well a coding agent does its work is not known either.
- The sixteen summaries and the phrases each letter contributes are the project's own first wording; the owner has seen the summaries.
- A random pick may be any of the other fifteen types, including the opposite one.
- A "yes" given in a new conversation before the host AI has asked again there is refused, and the host AI has to ask again (the owner agreed).
- After "erase all memory" a user is given a new random type at the next session, as a new user is (the owner agreed).
- A host that saved its own default card keeps the old meaning of reset: it returns to that card.
- `evaluations/c5-harness.py` still models reset as a return to the host's default; a live companion evaluation that resets a memory would now see a random type.
- A proposal that only removes the resting mood is refused as an empty change (the request drops empty fields).
- The evaluation harnesses now leave their memories without a persona, so that runs stay comparable; reports before this batch had none either.
- Verify, native Windows, macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.
