# LoCoMo evidence recall, 2026-11-10: a model-free baseline against raw-record retrieval

Runtime `ede5769` (pin `77adbe69`). This is the shared measurement for memory-quality work: it costs nothing to run, calls no model, and compares the plugin path with the plain alternative at the same size. It is a retrieval measurement on a public benchmark, not behavioural acceptance: **R4 remains failed and C5 invalid/unscored.**

## Result

LoCoMo marks the turns that hold each answer. For all 1,540 questions in categories 1 to 4 (ten conversations; 1,535 have usable evidence), the harness builds the context a host would receive and checks whether **every** evidence turn is in it.

| | Questions | memBrain recall block | memBrain whole context | Raw retrieval, same size as the recall block | Raw retrieval, 9,000 characters | Raw retrieval, same size as the whole context |
| --- | --- | --- | --- | --- | --- | --- |
| All | 1,535 | 52.7% | 55.1% | 67.5% | 73.6% | 77.4% |
| Single-hop | 841 | 66.5% | 69.0% | 81.5% | 87.4% | 90.6% |
| Temporal | 320 | 62.2% | 64.4% | 78.8% | 81.9% | 85.0% |
| Multi-hop | 282 | 10.3% | 11.7% | 24.1% | 33.0% | 39.0% |
| Open-domain | 92 | 23.9% | 29.3% | 33.7% | 42.4% | 47.8% |
| One evidence turn | 1,122 | 67.4% | 70.1% | 82.9% | 87.9% | 90.6% |
| Several evidence turns | 413 | 12.8% | 14.3% | 25.7% | 34.6% | 41.6% |

- **The plugin path retrieves less of the evidence than plain retrieval over the stored messages at the same size.** At the size of memBrain's own recall block (4,839 characters on average) raw retrieval has all the evidence for 67.5% of questions against 52.7%. BM25 alone at 9,000 characters reaches 64.0%.
- **The recall block uses about half its budget.** It averages 4,839 of 9,000 characters, because it shows at most twelve source messages (and up to eight following messages) however short they are. The session-start part of the context adds 9,285 characters of notices and recent history, which holds the evidence for 37 further questions.
- **Multi-hop questions are where both are weak**, and where the gap is widest in relative terms.
- Per question: both have all the evidence on 801, raw retrieval only on 387, memBrain only on 45, neither on 302 (whole context against the same size).
- The split used for later tuning is the one of the 2026-10-29 answer run: conversations 1 to 3 are for development, 4 to 10 are held out. Recall block: 54.3% development, 52.2% held out; raw retrieval at the same size: 70.8% and 66.4%.

Time for the two context calls on this machine (WSL2, four cores, 370 to 690 stored messages per conversation): session start 239 ms median; per-prompt recall 324 ms median, 350 ms at the 95th percentile. These are not R5 measurements.

## Where the evidence is lost (development conversations)

For the 519 evidence turns of the three development conversations ([stage_breakdown.py](locomo/results-2026-11-10/stage_breakdown.py)):

| Stage | Evidence turns |
| --- | --- |
| Selected into the recall block | 236 (45.5%) |
| Not among the statements the service returned (51 at the median) | 205 (39.5%) |
| Returned by the service, then dropped by the host's selection | 78 (15.0%) |

Changing only the host's limits in process, without a source change ([selection_sweep.py](locomo/results-2026-11-10/selection_sweep.py), 383 development questions, recall block only):

| Limits | All evidence | Several-turn questions | Characters | Median ms |
| --- | --- | --- | --- | --- |
| 12 messages, 8 following, 32,000-token recall budget (current) | 54.3% | 9.8% | 4,803 | 129 |
| 24 messages | 60.8% | 14.1% | 7,333 | 130 |
| 40 messages | 63.2% | 17.4% | 8,413 | 129 |
| 40 messages, 30 meaning-only | 62.9% | 16.3% | 8,671 | 131 |
| 40 messages, no following messages | 57.4% | 16.3% | 8,178 | 122 |
| 40 messages, 64,000-token budget | 65.5% | 17.4% | 8,934 | 193 |
| 60 messages, 96,000-token budget | 65.8% | 19.6% | 8,956 | 194 |

Raw retrieval at 9,000 characters has all the evidence for 76.2% of these development questions. Filling the budget the hook already allows recovers about nine points at no cost in time; the following messages are worth keeping; a larger service budget buys two more points for half again the time. The rest of the gap is in which statements the service ranks first, and is not closed by any of these limits.

## Method

- **Data**: `locomo10.json` from `snap-research/locomo`, downloaded for the run and not stored here. Categories 1 to 4; category 5 (adversarial) is excluded, as in the answer runs.
- **Ingestion**: the same as [run_locomo.py](locomo/run_locomo.py): each conversation in its own embedded installation, every turn stored as the hooks store a message, with its session date and speaker in the text. The pinned local embedding model is installed and every message is embedded before any question; recording is then paused.
- **memBrain arm**: for each question a new session, `host.session_context` followed by `host.prompt_context`, as the plugin path does. No recall tool call is made, because no model is there to make one.
- **Raw retrieval arm**: the same stored turn texts, ranked by reciprocal-rank fusion (constant 60) of BM25 (k1 1.2, b 0.75) and cosine similarity under the same embedding model with its query and document prefixes, taken in rank order up to a character count. It has no notes, history, cue, adjacency or time logic.
- **Matching**: a turn is present when its date and speaker prefix plus the first 60 characters of what was said occur in the context. In one conversation none of 45 missed evidence turns had any other 30-character slice in the context, so the rule does not under-count memBrain there; the longest stored turn in it is 449 characters, under the 700 at which a recalled message is cut.
- **Harness**: [retrieval_recall.py](locomo/retrieval_recall.py). Per-question rows and the summary are in [results-2026-11-10](locomo/results-2026-11-10/); raw retrieval at other sizes comes from [raw_budgets.py](locomo/results-2026-11-10/raw_budgets.py).

## Limits

- **Retrieval, not answers.** Having the evidence in the context is not the same as a correct reply, and a host model can also search. The 2026-10-29 run scored the plugin path at 76.4% of answers with tool searches allowed; this measurement cannot be compared with that number directly. The effect of a larger recall block on a host's replies, including replies that misuse irrelevant lines, is not measured here.
- **The raw arm at "same size as the whole context" spends everything on records**, while memBrain spends two thirds of that on notices and recent history, which a question about an arbitrary past session cannot use. The recall-block comparison is the like-for-like one.
- **LoCoMo is not a memBrain conversation.** Two people talk to each other; both are stored as the user's messages, there are no assistant replies, no notes and no corrections, and everything is stored within minutes, so age plays no part.
- **One benchmark, one run per arm, one machine.** The runs are deterministic apart from timing. Tuning on the development conversations and reporting the held-out ones guards against fitting, but it is still one dataset.
- The 2026-10-29 answer results, their second run and the Mem0 comparison are unchanged and were not repeated.
