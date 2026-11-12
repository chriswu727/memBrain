# Plan: are cues written through the product's batch format any good?

Written before the run. Paid DeepSeek calls, approved by the owner on 2026-11-11 with a ceiling of **3 CNY**. Runtime `139c15f` (pin `7ba42aed`). It closes no release gate.

## Question

The measured gains from cues ([evidence](message-cues-2026-11-11.md), [answers](locomo-cue-answers-2026-11-11.md)) used cues one model wrote from one prompt per finished session. The product now hands the host's AI batches of at most 20 messages with [its own instructions](host-consolidation-2026-11-11.md). Do that format and those instructions yield cues that help recall as much?

## Design

- [host_consolidation_replay.py](locomo/host_consolidation_replay.py): on the stored LoCoMo brains, the cues written earlier are removed; `deepseek-flash` stands in for a host AI and is given exactly what `memory_consolidate` returns, through the real tool and service, batch after batch until nothing is left. Counted: batches, messages offered and cued, replies the tool refuses, and replies that return the wrong `reviewed_through`.
- Then the model-free [evidence-recall harness](locomo/retrieval_recall.py) on the same brains, compared with no cues (74.1% all, 72.2% held out) and with the session-level cues (79.5%, 78.5%).
- Reported on the held-out conversations first. The tool's instructions were written from the earlier prompt, which was written after reading the development conversations.

## What it cannot show

Whether a real host calls the tool, at what moment, and how its own model follows the instructions while doing something else. That needs the trial on a real host, which the owner has also approved and which follows.

## Cost

About 300 calls of roughly a thousand input tokens: 1.5 to 2 CNY expected at ledger prices, in its own run directory with a 3 CNY ceiling.
