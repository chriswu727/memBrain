# A real host on the last three days' changes: what it did, and what it never did

The owner approved a trial on Claude Code with its subscription, on models other than the largest. Claude Code 2.1.322, headless, `claude-sonnet-5-5` (42 turns) and `claude-haiku-5-5` (11 turns), on WSL2, against a frozen copy of runtime `4b0f977` (commit `3251d227`). A copy of the plugin whose hooks and tool server run that copy directly; four memories with ports of their own; every message synthetic, about one invented user. Nothing of the owner's own memory or configuration was read or written by memBrain. A sub-session of the lead drove it; the lead set the scenarios. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Turn-by-turn summaries with paths removed, the message scripts and the per-turn costs are in [evidence](evidence/host-trial-2026-11-13/).

## Summary

**Worked:** the personality type picked at random was mentioned once with how to switch, and not again; `/membrain:persona` ran headless and switching worked by command and in words, with the user's message cited; mood and familiarity carried over a switch; a shared joke was saved as a playful moment; the host consolidated every time the notice asked; it searched its own earlier replies with `my_replies` when the answer was not already in its context; a fact needed only by implication (a shellfish allergy, for a seafood suggestion) was in the automatic block and was used.

**Never happened:**

- **A proposed change to the persona.** Asked "From now on, when I'm confused, walk me through it step by step", Sonnet saved a preference note, three times out of three, and once told the user "I can't promise a change to my underlying personality". The persona tool's `propose` was never called, so confirming and declining were never reached.
- **Manner feedback.** "That was way too long.", "Shorter, please." and "Still too wordy." led to shorter replies and, once, a note. The manner-feedback tool was never called, so no suggestion formed after three comments.
- **A hard shared moment.** When the user said they were frustrated with the agent and the two sorted it out, nothing was saved as a shared moment and no feeling was recorded.

**The likely cause, inferred and not proven:** the host never saw the instructions for these three. In Claude Code the plugin's tools are loaded on demand, so their descriptions are read only after the host looks a tool up by name; the plugin's skill, which holds the long instructions, was not opened once in 53 turns; and the session notice names only notes, recall, pausing and consolidation. Everything the notice names worked. Everything it does not name did not.

## What else it showed

- **Dates disagree inside one context.** Notes, history and familiarity are dated from UTC times, the mood line from local time: a note written on the evening of 13 November read "2026-11-14".
- **Command lines are kept as the user's words.** `/membrain:persona reset` is recorded as the user's message and then appears in the history block and in consolidation batches.
- **The notice is wrong about the agent's own replies.** It says they "are not shown unasked"; they are shown when the user's wording is recognised, which is why two questions about an earlier reply were answered without a search. The automatic block cut a 12-item list inside item 10; asked for item 12 the host searched without `my_replies`, found nothing and said so without guessing.
- **Wrong kinds and one invented note.** A pet was saved as kind `relationship`, a job as `constraint`, and a `plan` for a trip the user had not said they were planning.
- **It says when it saves.** "I've saved a note…", "Memory's tidied up." closed many replies. The owner has said short visible mentions are welcome; none was a report.
- **The per-message block repeats itself.** With 150 earlier messages, each turn's block held 23 to 34 lines, 14 to 28 of them the same as the turn before.
- **Emoji.** After a switch to ENFP, whose card says "emoji now and then", almost every reply had one.
- **Haiku went elsewhere.** Asked for the lasting change, Haiku wrote the preference into Claude Code's own memory files instead of memBrain, told the user the notes about them "may belong to another person" because the workspace's account had another name, and took "Yes, do that." as leave to remove those notes; it looked three of them up and deleted nothing. The account mismatch is an effect of a trial with an invented user; that Haiku reaches for the host's own memory first is not.

## Cost on the host

By the host's own accounting: 42 Sonnet turns, 88 model calls, 1.80 USD; 11 Haiku turns, 31 calls, 0.03 USD. A plain resumed turn is one call and about 0.01 to 0.016 USD.

| Feature | Extra model calls | Extra cost against a plain turn |
| --- | --- | --- |
| A note | 1, and 1 more the first time a tool is looked up in a session | about 0.011 USD |
| A persona switch | 1 | about 0.01 USD |
| The persona's one-time line | 0 | about 350 characters of context, once |
| Consolidation, 5 messages | 3 | about 0.025 USD |
| Consolidation, 40 messages | 3 | about 0.055 USD |
| A search of its own replies | 2 | about 0.034 USD |

In headless use every resumed turn runs the session-start hook again and adds the whole session context again (2,200 to 9,400 characters); that is how `--resume` works and is not seen in an interactive session.

## Second round, after the fixes: the three behaviours happened

Runtime `fca414b0`: standing instructions from the tool server, two sentences in the session notice, local dates, command lines left out of history, note guidance. The same host and models, fresh memories, 26 Sonnet turns and 7 Haiku turns ([summaries](evidence/host-trial-2026-11-13/round2/)).

| Expected | Round 1 | Round 2 |
| --- | --- | --- |
| Propose a lasting change, ask, change nothing before a yes | never (0 of 3) | happened twice on Sonnet, once on Haiku |
| Confirm with the user's "yes" as its source; a new persona version | not reached | happened (Sonnet and Haiku) |
| Decline after "No, leave it" | not reached | happened |
| No proposal for a passing complaint | (nothing proposed at all) | no proposal |
| Record manner feedback, no note in its place, no announcement | never (0 of 3) | three of three on Sonnet, two of two on Haiku |
| A suggestion after the third comment | no | an open suggestion to be shorter |
| A hard time saved as a shared moment marked hard | no | yes, saved when the two had sorted it out |
| The user's feeling recorded with it | no | **no** |
| Search its own replies with `my_replies` for item 11 of a 12-item list | searched without it | set it; the reply came back at length; answered correctly |
| Command lines absent from history; one local day throughout | no | yes |
| Haiku writing the preference into the host's own memory files | yes | no |

The inference of the first round is as good as confirmed: once the instructions were where the host reads them, it followed them. Whether it was the server's instructions or the notice that did it cannot be told apart from the logs: the stream does not show the system prompt, so the server's instructions are known to be sent (a handshake with the same server returns them) and not seen to arrive.

**New in this round, and what was done:**

- **A turn whose visible reply was only "Memory's updated."** The host consolidated in a turn where the user had asked a question, and its answer stayed in its reasoning. The tool's result now says to write the answer if it is not yet written. Not tried again.
- **A proposal cost extra calls and bent the card.** Two of five `propose` calls were refused for form (the voice given as a sentence; a phrase over 60 characters), and Sonnet then squeezed the behaviour into the voice's 60-character register. A proposed list would also have replaced the personality type's own values. Proposed traits, values and boundaries are now added to the card's, and the tool says a behaviour goes into values as one sentence. Not tried again.
- **No feeling was recorded** for "I'm frustrated". The instructions now say a hard moment is saved with what the user felt. Not tried again.
- Lines such as "Memory's tidied up." still end replies after consolidation; Haiku repeated an answer after one.
- After a confirmed change the persona is listed as the user's own card based on the type, no longer as the type itself, which is as designed and was read as a loss by the tester.

**Cost of the new behaviours on the host:** a proposal 2 to 4 extra calls (mostly the refused attempts), about 0.04 to 0.05 USD; a confirmation or a refusal 1 call, about 0.016 USD; manner feedback 1 call, 0.014 to 0.028 USD; the round as a whole 1.07 USD on Sonnet and 0.02 USD on Haiku.

## What remains untried

A confirmation attempted in the same turn as its proposal (the host never tried one); the three wordings changed after the second round; a hard moment mellowing; the mood after a hard moment when the resting mood is not already playful; an interactive session; Codex, WorkBuddy and CodeBuddy; a first start with the service down; old dates, since every message was recorded on the day.
