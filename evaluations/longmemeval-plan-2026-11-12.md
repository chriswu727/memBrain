# Plan: an evidence-recall test on a benchmark memBrain was not tuned on

Written on 2026-11-12, before any result on this benchmark exists. Runtime `75f50fd` (pin `59c6bc63`), unchanged. No model is called. It closes no release gate.

## Why

Every ranking weight, the recall block, and the cue rules were chosen on LoCoMo, and the held-out LoCoMo conversations have by now been looked at many times. LoCoMo is also far from use: two invented people chatting, a history short enough to paste whole, no assistant replies, everything stored on one day. The owner asked whether the measured gains are real or a false positive. A benchmark the system has never seen is the first honest answer.

[LongMemEval](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) (cleaned version, MIT licence): 500 questions, each with its own history of about 48 user-assistant sessions and 490,000 characters, about five times a LoCoMo conversation, with the turns that hold the answer marked.

## What is measured

[evidence_recall.py](longmemeval/evidence_recall.py), the same measure as on LoCoMo: a history is stored as the plugin's hooks would store it, the context of a new session is built for the question as the plugin path builds it, and the share of questions whose evidence turns are all shown is counted, in the recall block and in the whole context.

- **Arm M**: memBrain as it stands. No cues: only a host AI writes them, and none runs here. No notes.
- **Arm R**: plain retrieval over the same stored turns (BM25 and the same embedding model, fused by rank), each turn cut to 700 characters, filling the same number of characters.
- A turn counts as shown when any 50-character piece of it, taken every 200 characters, is in the context.

## Sample

Ten questions of each of the six types (60 in all), drawn with the fixed seed in the script, excluding abstention questions, which have no evidence. One question outside the sample is run first, only to learn how long a history takes to store. If the sample takes more than about a day of machine time it is cut to five per type, the first five of each type in the seeded order; that is the only change allowed after this is written.

## Rules

- **Nothing is tuned on this benchmark.** No constant, prompt or rule is changed in response to its results before they are reported. What they suggest goes into later work, measured separately.
- The result is reported whatever it is, by question type, with M against R paired.
- Dates: each stored message carries its session's date at the start of its text, as in the LoCoMo harness, because the benchmark's sessions happened on other days than the day they are stored here.

## What it can and cannot show

- If M is level with or ahead of R, the ranking chosen on LoCoMo carries over to another kind of history. If M is clearly behind R, it was fitted to LoCoMo, and that is the more important finding.
- Evidence recall is not answers. An answer run on this benchmark is a separate, paid step that needs the owner's approval with a stated ceiling.
- Assistant replies hold the evidence of some questions. memBrain's recall shows the assistant's own earlier words only when the question asks about them; how that rule fares here is part of what is measured.
- Still one more benchmark, in English, with invented histories. It is a second opinion, not use.
