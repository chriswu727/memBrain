# One experience: no companion switch, a search that reaches old memories, and the first unused code removed

Base: pin `df630c25` (runtime `75f3f49`). Runtime commits `5881bdd3` to `b46417e1` (fourteen, with three evaluation commits between them); pin commit `68729eb3` points all nine launchers at the last. No migration. The contract gains one optional field. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Paid model calls in this batch: 1.55 CNY for an answer check (2.31 CNY in all of the owner's 10 CNY approval). Everything else called no model.

## A correction first

The [previous batch](parallel-work-2026-11-12.md) added a switch that turned the companion layer (persona, simulated mood, familiarity) off and on, and recorded it as the owner's decision. That was the lead's misreading: the owner had asked what such a switch would be for, not for one. Asked again, the owner said that memBrain must not be split into parts the user toggles, because to a user it is one experience, and that the switch should go.

The switch is removed here, one day after it was added and before any release carried it. The previous record is left as written.

## How this batch was made

Five sub-sessions worked in their own working copies: two removal slices, a measurement of recall by age, the manner-feedback tool on two more hosts, and two test runs. The lead removed the switch, built the hard shared moment, made the two recall changes from the measurements, reviewed every diff and merged them.

## What changed

**The companion switch is gone.** Removed: the `/membrain:companion` command in Claude Code, the `memory_companion` tool, `membrain plugin companion`, the page route and its hint, the setting's reader, and the separate boundaries block that existed only for the off state. The companion layer is part of memBrain and always on. What a user can do is unchanged: pause recording, set a boundary, cap familiarity, pin or reset the mood, edit or reset the persona, reset the relationship, delete anything.

**A search the host AI makes on purpose reaches old memories.** The owner's rule: nothing is forgotten; an old memory lies deeper and takes more effort to reach, so that recent and important ones come first. Measured with messages stored at their real dates, the recall tool was ranked exactly like automatic recall, so searching reached no deeper. The recall request gains an optional `ranking` field and every host's search tool asks for `relevance`; automatic recall keeps recent memories first. On 383 LoCoMo questions asked a day after the last session, a search now shows all the evidence for 80.4%, against 77.5% before. [Report](time-depth-recall-2026-11-12.md).

**Replies the host AI asked for are shown at length.** On 30 LongMemEval questions about the assistant's earlier words that had not been used before, a stand-in answer model searched on 14 and set `my_replies` on all 14, and answers rose from 19 to 24 correct. Three of the four it searched for and still got wrong had the answer outside the 700 characters shown of one message. The two closest replies are now shown up to 3,000 characters when the host asks for replies; on the same questions 27 were then correct, which is not an independent check, because the lengths were chosen on them. [Report](assistant-replies-answers-2026-11-12.md).

**The host AI says what kind of shared moment it saves.** A shared moment can carry `moment`: `play`, `hard` or `other`. Until now the simulated mood told a joke from an achievement with a fixed list of English and Chinese words, which misses paraphrases and every other language. The host AI's judgement now decides; the word list remains for moments saved without the field.

**A hard time together is a shared moment too, and it mellows.** The owner's view: an unhappy time together can later be recalled without the unhappiness, as time passes and the two keep each other's company. A moment marked `hard` (a disagreement between the user and the agent, a time the agent let them down, a rough stretch it kept them company in):

- counts toward familiarity like any shared moment;
- does not make the simulated mood glad or playful (what the user felt is recorded as a feeling on the note when they expressed one, and moves the mood as any feeling does);
- is listed in the relationship block as something to leave alone unless the user brings it up, while it is recent;
- once 30 days have passed and the user has talked on 5 later days, is listed as something the two came through together. The two numbers are the lead's first choice and have not been tried with people.

**The host AI reports the user's feedback on its manner, on every host.** A tool (`memory_manner_feedback`; `membrain_manner_feedback` on OpenClaw and AstrBot): when the user comments on how the agent talks (shorter, less formal, more playful, and so on), the host AI records which kind, with the message as its source. The persona's rule already turns three comments of one kind into a suggestion the user accepts or rejects on the memory page; until now only a fixed phrase table could notice them. Refused while recording is paused. By the owner's answer, a natural reply is enough: the host AI does not announce that it recorded feedback.

**The mood's "easing" no longer resends context.** The session context is sent again when its fingerprint changes. The simulated mood's "easing" wording changed with the clock alone, so a session received the whole context again hours after a trigger with nothing new in it. The fingerprint now leaves it out. The skill gains a section on what the persona and mood blocks are.

**The first unused code is removed** (slices 1 and 2 of the [plan](audits-2026-11-12/unused-code-removal-plan.md)): pattern views, which only the frozen learning path wrote, with 525 source lines and their tests; and moves that let the plugin path run without importing the frozen modules (shared validators, the settings policy, snapshot checks, a worker for capture and embedding jobs that does not load the learning engine). Rows that older runtimes stored are still cleared when their sources are edited or forgotten: the clearing SQL is kept in one module, and new tests write such rows the old way and check erasure, isolation, recall and archive restore. No migration was touched. In source: 367 lines added, 920 removed. A plugin-path start now loads 34 of the package's modules where it loaded 45.

## Verification

- **Full local source suite on the pin commit `68729eb3`**, with the local embedding model: 8,475 passed, 4 skipped (the Docker journeys), **1 failed**, in 55 minutes; source and migrations unchanged during the run.
  - The failure: `tests/test_model_activation.py::test_model_activation_never_interrupts_requests_in_flight` stopped at its first step, starting a service ("The native transition did not finish"). In the same minute another sub-session of this work was running tests that start services outside the lock that test sessions on this machine share, on the same fixed default port; its temporary directories carry that timestamp. The file passed when run alone straight afterwards (4 passed).
  - That is the likely cause, not a proven one: the transition replaces the underlying error with a general message, so the log does not say what stopped it. This is recorded as a failed run with an explained failure, not as a clean pass.
- Before the merge each line's own tests passed in its working copy: the removal slices with their own full suite (8,445 passed, the one failure being the pin test that every unpinned change fails); the switch removal with 538 tests of the companion, host, plugin and MCP files; the hard moment and the two hosts' tool with 232.
- The age-weight and reply-length changes were measured as reported above; their tests are in the suite.
- TypeScript client: 57 tests pass and the type check is clean. OpenClaw plugin: 9 pass, 2 skipped there (they need a real runtime and run through the Python suite, where they passed).
- New tests cover: rows of removed features written the old way and then erased, isolated, recalled around and restored from an archive; a hard time that does not gladden the mood, counts toward familiarity and mellows by both time and later conversation; the manner-feedback tool on each host, its refusal while paused before a client is opened, and three reports becoming one suggestion; a reply deep in a long message shown when asked for; the `ranking` field accepted, refused when unknown, and sent by every host's search tool and not by automatic recall.

## Not done, not known

- **No real host ran any of this.** Whether a host AI marks a moment `hard`, reports manner feedback at the right times, searches when the user refers to something old, or sets `my_replies` as the stand-in model did, is not known.
- The mellowing rule's numbers and the reply length were chosen by the lead; the first is untested with people, the second was chosen on the questions it is reported on. Eleven questions about the assistant's words remain unused.
- Automatic recall still ranks by age alone besides relevance. "Important memories first" is not built: nothing marks a captured message as important.
- A long history with newer memories on top of old ones was not built, so the cost of the age weight a year on is not measured where it would be largest.
- The memory page shows a tag on a hard time and offers the kind in the note form; it was not opened in a browser for this batch beyond the suite's browser tests.
- Persona switching and persona edits proposed by the host AI are not built; the owner's answers to three questions come first.
- Most of the roughly 17,000 frozen lines the plan counts are still in the package; the next slices remove the extraction model, metered embeddings, the cognition pipeline and the bundled chat mode.
- Verify, native Windows, macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.
