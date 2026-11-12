# With cues, the plugin path answers 83.2% of held-out LoCoMo questions, up from 80.7%

Result of the [plan of 2026-11-11](locomo-cue-answers-plan-2026-11-11.md), run as written. Runtime `6a136d6`. DeepSeek paid calls approved by the owner with a 25 CNY ceiling. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Result

Seven held-out conversations, 1,155 questions, every question in a new session; answers by `deepseek-flash` with thinking off, judged by the same model with Mem0's judge prompt. The cues are the ones a model wrote for the [simulation](locomo-controls-and-cues-2026-11-11.md); attaching them made no model call. "Messages alone" is the same day's run on the same questions (runtime `933f4d8`), not repeated.

| | Questions | Messages alone | With cues | Gained | Lost | Exact two-sided p |
| --- | --- | --- | --- | --- | --- | --- |
| **All held-out questions** | 1,155 | 80.7% | **83.2%** | 69 | 40 | 0.007 |
| Several evidence turns | 321 | 67.6% | 72.9% | 30 | 13 | 0.014 |
| One evidence turn | 831 | 85.7% | 87.1% | 39 | 27 | 0.18 |
| Multi-hop | 208 | 67.3% | 75.0% | 24 | 8 | 0.007 |
| Temporal | 231 | 79.7% | 84.0% | 19 | 9 | 0.09 |
| Open-domain | 75 | 58.7% | 57.3% | 3 | 4 | 1.0 |
| Single-hop | 641 | 88.0% | 88.6% | 23 | 19 | 0.64 |

- **The gain is where the evidence gain was.** Questions that need several memories and multi-hop questions improve by five to eight points; questions answered from one turn barely move.
- **Every one of the seven conversations is ahead with cues**, by 0.6 to 4.5 points; none is significant on its own.
- **Above the whole conversation in the prompt.** The earlier full-context run (2026-10-29) scored 81.2% on these conversations; the same-day full-context control covered the development conversations only.
- Open-domain questions, which ask for an inference the conversation does not state, do not improve.
- The context is 18,211 characters on average against 17,873, and the host searched with the recall tool on 202 questions against 220.

## What this does and does not show

- It shows that attaching cues of this kind to the messages turns into more correct answers, on conversations the weights were not chosen on.
- **It does not show what an installation gets.** These cues were written by `deepseek-flash` from one prompt per finished session. In the product the host's own AI is to write them (in progress); cues written that way have not been measured.
- One run per arm. Gained and lost both include questions the answer model or the judge would have decided differently on a second try; the test above asks only whether gains outnumber losses beyond that.
- One benchmark: two people chatting, stored as one user's messages, English, no real elapsed time.

## Cost

**18.24 CNY** of the 25 CNY ceiling, priced at peak rates without cache discount: 2,513 `deepseek-flash` calls, 9.0 million input tokens. No request ended without usage accounting; none was refused. With the earlier work of the day (77.84 CNY) the day's paid total at ledger prices is 96.08 CNY.

Files are in [results-2026-11-11](locomo/results-2026-11-11/): `answers-cues-heldout.jsonl.gz`, `cue-answers-report.txt` and `cue-answers-ledger.json`; the answers on messages alone are the held-out rows of `answers-plain-all.jsonl.gz`.
