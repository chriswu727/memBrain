# LoCoMo on the current runtime: 82.5% of answers, level with full context; and cues attached to messages find the evidence notes could not

Result of the [plan of 2026-11-11](locomo-controls-plan-2026-11-11.md), run as written. Runtime `933f4d8`. DeepSeek paid calls approved by the owner. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Answers on messages alone

The plugin path as shipped, no notes, every question in a new session; answers by `deepseek-flash` with thinking off, judged by the same model with Mem0's judge prompt.

| | Questions | 2026-10-29 / 11-01 runs | This runtime |
| --- | --- | --- | --- |
| **Held-out conversations** | 1,155 | 76.2% | **80.7%** |
| Development conversations | 385 | 77.1% | 88.1% |
| **All ten conversations** | 1,540 | 76.4% | **82.5%** |
| Full context, held out / all (earlier run) | | 81.2% / 81.4% | not repeated |
| Mem0 open source, all (earlier run) | | 81.3% | not repeated |

By category on all ten conversations: single-hop 89.1%, temporal 82.2%, multi-hop 69.5%, open-domain 64.6%. On the held-out conversations: one evidence turn 85.7%, several 67.6%. The host searched with the recall tool on 296 of the 1,540 questions. The context averaged 17,881 characters, against about 95,000 for the full conversation.

- **The held-out score is the one that counts.** The changes of the last two days were chosen on the development conversations, and it shows: they gained eleven points there and four and a half on the conversations they were not chosen on.
- **On the held-out conversations the plugin path is now level with the full conversation in the prompt** (80.7% against 81.2% in the earlier run), at about a fifth of the context.

### Same-day full-context control

The whole dated conversation in the prompt, development conversations, same model, judge and day: **80.0%** (385 questions), against 81.8% on 2026-10-29. The answer model and the judge have not moved by more than a run's noise, so earlier and current scores can be compared.

Same day and same questions, messages alone against full context: 88.1% against 80.0% (53 gained, 22 lost). That is on the development conversations and overstates the difference; the held-out comparison above is the fair one. Full context was strongest where the answer sits in one turn (single-hop 92.5% for both) and weakest on temporal questions (71.1% against 88.9%).

## Cues attached to the original messages

The [notes result](locomo-consolidation-2026-11-11.md) and the owner's remark that notes are not how memory works led to a different kind of consolidation: do not write something for the host to read; attach cues to the original memories so that recall finds them, and keep showing the original message.

Simulated with a plain index ([cue_enrichment_simulation.py](locomo/cue_enrichment_simulation.py)). One `deepseek-flash` call per session names, for each turn that holds a lasting fact, whom it is about and what kind of fact it is ("Melanie hobbies and activities"), without restating it. 2,198 of 5,882 turns got cues, 3,233 phrases in all. Share of questions with all their evidence in the first 40 messages:

| | Development (291 one, 92 several) | | Held out (831 one, 321 several) | |
| --- | --- | --- | --- | --- |
| | One evidence turn | Several | One evidence turn | Several |
| No cues | 86.9% | 35.9% | 85.9% | 29.9% |
| Cues added to each turn's indexed text | 93.1% | 45.7% | 91.6% | 43.0% |
| Cues as an extra meaning route | 91.4% | 51.1% | 91.8% | 53.9% |
| Cues as extra keyword and meaning routes, half weight | 92.1% | 55.4% | 91.7% | 50.2% |
| Cues as extra keyword and meaning routes, full weight | 88.3% | 52.2% | 91.1% | **54.5%** |

- **On the held-out conversations, questions with several evidence turns go from 29.9% to between 50% and 55% with all their evidence found**, and questions with one evidence turn gain about six points. The mean share of evidence found for several-turn questions rises from 54.5% to as much as 78.6%.
- **The instructions were written after reading the development conversations**, and their examples name categories those conversations ask about. The held-out conversations have other people and other questions, and gain as much, so the effect is not an artefact of those examples.
- **Cost: 0.89 CNY for all ten conversations** (272 calls), about 0.00015 CNY a turn: about a thirtieth of note extraction after every turn, and about a sixtieth of the Pro consolidation per turn covered.

This is a simulation at message level with BM25 and whole-message embeddings, not the product's recall and not answers. It says the direction is worth building and measuring properly.

## Cost

All paid work of 2026-11-11 in one ledger, priced at peak rates without cache discount: **77.84 CNY** of an 85 CNY ceiling. The provider's actual charge was not read and is lower where cached input applied.

| Phase | Calls | CNY |
| --- | --- | --- |
| Answers on messages alone, all ten conversations | 3,376 | 24.47 |
| Notes after every turn, three conversations, and their answers | 2,293 | 13.20 |
| Notes after every session, three conversations, and their answers | 913 | 18.77 |
| Full-context control, three conversations | 770 | 20.52 |
| Cues, ten conversations | 272 | 0.89 |

7,555 Flash calls (32.0 million input tokens) and 71 Pro calls. No request ended without usage accounting; none was refused.

## Notes on the run

- The comparison script's report function gained two filters after the consolidation plan recorded its hash; the code that makes calls and scores answers did not change.
- The three paid runs share one ledger and ran one after another.

## Limits

- One benchmark: two people chatting, stored as one user's messages, no assistant replies, no real elapsed time, English. One answer model and a judge of the same family; one run per arm.
- The full-context and Mem0 scores for the held-out conversations are from the earlier run; the same-day control covers the development conversations only.
- Nothing here measures how a real host behaves with the product. R4 does, and it has not passed.

Files are in [results-2026-11-11](locomo/results-2026-11-11/): `answers-plain-all.jsonl.gz`, `answers-full-development.jsonl.gz`, `cues.json.gz`, the two `cue-simulation-*.txt` and `ledger-final.json`.
