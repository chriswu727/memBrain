# The host's own AI writes the cues: a consolidation tool, with no model of memBrain's own

Base: pin `7f27eb6d` (runtime `6a136d6`). Runtime commits `dd68f74c`, `2c1a3151` and `139c15f3`; pin commit `7ba42aed` points all nine launchers at the last. Migration `036_cue_progress.sql`. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Everything ran on WSL2 Linux with task-owned embedded PostgreSQL 16.15 and pgvector 0.8.6. **No model was called.** GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## The decision this follows

[Cues attached to messages](message-cues-2026-11-11.md) raise evidence recall and, in a [paid check](locomo-cue-answers-2026-11-11.md), answers; but nothing in an installation wrote them. The owner fixed the product line on 2026-11-11: a user who adds memBrain to an AI agent tool can use it at once; every function of memBrain is exercised by that tool's own AI; memBrain ships no second AI and never asks the user to configure one. A background step with a separately configured model, which had been proposed, was dropped.

## What was built

- **A queue of messages to index.** The service lists the user's messages that have not been reviewed for cues, oldest first (`GET /v1/brains/{brain_id}/message-cues/pending`), and records how far they have been read (`memory_cue_progress`), so a message that needs no cue is not offered again. Messages that are hidden, erased, superseded or already cued are never offered; nothing is offered while recording is paused.
- **A tool the host AI calls twice.** `memory_consolidate` without arguments returns a batch of at most 20 messages (6,000 characters), each with a short numeric id and its date, and the instructions: name whom a lasting fact is about and what kind of fact it is, not the detail. The second call returns the cues and the number the batch gave; memBrain saves them and moves the mark. Ids beyond the batch, a missing number and malformed entries are refused with a reason.
- **One sentence at the start of a session**, only when messages await indexing and the host has the tool: how many there are, and to call the tool once, after answering the user's first message.
- **A section in the plugin skill** telling the host AI what the cues are for, not to interrupt the user's task, and to leave what remains for a later session.
- The TypeScript and Python clients expose the two service calls.

memBrain makes no model call anywhere in this. What the host AI spends is the batch it reads and the cues it writes; the owner set no ceiling on that for now and asked that the function be made good first.

## Verification

- **Full local source suite on the pin commit `7ba42aed`**, with the local embedding model: 8,532 passed, 4 skipped (the Docker journeys), none failed, in 54 minutes. Source and migrations were unchanged during the run, and the pin test passes.
- **End to end on a real local service** ([test](../tests/test_memory_consolidation.py)): two exchanges are recorded; the next session's opening says two earlier messages have not been indexed and names the tool, and a host without tools is not told; the tool hands out both messages with ids, dates and instructions; wrong ids, a missing number and malformed entries are refused; the cue for the message with a fact is saved and the greeting is passed over; nothing is offered again and the sentence is gone from the following session; recall by the cue's words returns the original message and never the cue; while recording is paused the tool refuses and the sentence is not shown.
- Service tests: messages are offered oldest first within limits; a reviewed message is not offered again whether or not it got a cue; progress never moves back and cannot pass what is recorded; hidden, erased and already cued messages are left out; row security on the new table.
- Before the commit, the test files for hosts, tools, the plugin, the API and the schema (717 tests) passed on a fresh database. TypeScript client: 57 tests and the strict type check pass. Ruff is clean on `src`, `tests` and `examples`.

## Not known yet

- **Whether a real host does it.** No host AI has been run against this. Whether Claude Code, Codex or WorkBuddy act on the sentence, at the asked moment, and how visible it is in the conversation, needs a trial on real hosts.
- **How good the cues are.** The measured gains used cues one model wrote from one prompt per finished session. A host AI working from 20-message batches in the middle of other work may write better or worse ones.
- **What it costs the host.** The batch is at most about 6,000 characters in and a few hundred out per session; it has not been measured in tokens on a host.
- **A long backlog is indexed slowly**: 20 messages a session unless the host AI continues on its own.
- **Hosts without the tool write no cues**: OpenClaw, AstrBot and the proxy path.
- Only the user's messages are offered; the assistant's replies are not.
