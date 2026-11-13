# Does the host AI use the option to search its own replies? Thirty questions it had not been tried on

Runtime `75f3f49` (pin `df630c25`), the product as pushed in `0165297f`; nothing was changed for this run. It follows the [first answer check](assistant-replies-and-warm-up-2026-11-12.md), which had only five questions of the relevant kind and could not say whether the option helps. Paid: 1.02 CNY here, 1.78 CNY in all of a 10 CNY approval. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## What was asked

LongMemEval has 56 questions about something the assistant said earlier ("you recommended", "the list you gave me"). Thirty of them were drawn with a fixed seed from those beyond position 15 in the seeded order, so none had been used to develop or check the option ([ids](longmemeval/results-2026-11-12/assistant-set-ids.txt)). Each question's history, 454 to 589 turns, was stored once in its own local memory.

Two measurements on the same stored histories:

1. **Without a model:** does the evidence reach the host, in the block added automatically or through the recall tool with `my_replies` ([evidence_recall.py](longmemeval/evidence_recall.py))?
2. **With an answer model:** `deepseek-flash` answers from what the hooks add, may call the recall tool twice, and is judged with LongMemEval's own judge prompts ([answer_with_tools.py](longmemeval/answer_with_tools.py)). "Before" has the tool and the session notice as they were without the option; "after" has them as they are now.

The answer model stands in for a host. It is not Claude Code, Codex or any other host, and no real host ran this.

## Results

| | Questions | Result |
| --- | --- | --- |
| Marked evidence in the automatic block | 30 | 12 (40.0%) |
| Marked evidence returned by the tool with `my_replies`, asked with the question | 30 | 30 (100%) |

| Answers | Questions | Before | After |
| --- | --- | --- | --- |
| All | 30 | 19 (63.3%) | 24 (80.0%) |
| Evidence already in the automatic block | 12 | 11 | 11 |
| Evidence not in the automatic block | 18 | 8 | 13 |

Seven questions gained and two were lost.

- **The model used the option whenever it searched.** After the change it searched on 14 of 30 questions and set `my_replies` on all 14. All 14 were questions whose evidence was not in the automatic block.
- **Searching without the option found little.** Before the change the model searched on 11 questions and answered 2 of them correctly. After it, 10 of the 14 it searched on were correct, against 4 of the same 14 before.
- **It did not search when the block was enough**: none of the 12 questions with the evidence in the block led to a search, and 11 were answered correctly in both arms.
- **Thirty questions are few.** Seven gained against two lost is what a real gain looks like, but a difference of this size on this many questions could also be chance (an exact sign test gives about 0.18). The two losses do not look like an effect of the option: one was answered without a search in both arms, and the other lists the processes the reference answer names and was judged wrong.

## What it found that is not yet fixed

**Long replies come back cut.** Three of the four questions that were searched for and still answered wrong failed the same way: the reply holding the answer was found, but the recall tool shows at most 700 characters of one message (`host.MESSAGE_CHARACTERS`), and the answer lay outside the part shown. The three replies are 2,173, 2,557 and 2,879 characters long, with the answer 898, 1,505 and 2,252 characters in. One question asked for the 27th item of a list of 100; the model said which items it could see and that the 27th was not among them. The other two asked for a list and a figure from inside a long plan. The model did not invent an answer in any of them.

The evidence measure above counts a reply as returned when any part of it is shown, so it reports 100% here and overstates what the host can read. Next: show the part of a long message that matches the search, or let the host read one stored message in full; and count evidence as returned only when the answering part is.

**Four questions had the evidence outside the block and no search was made.** Three were answered correctly anyway from the user's own turns, one was wrong.

## Not known

- Whether a real host searches as often as this answer model, more, or less. The first check on other kinds of question saw the same model search on 2 of 30.
- Whether the gain holds on a larger set.
- What the option costs on a host: each search adds one model call and up to about 9,000 characters of results.

Evidence: [recall](longmemeval/results-2026-11-12/assistant-set-recall.jsonl.gz), [answers](longmemeval/results-2026-11-12/assistant-set-answers-before-after.jsonl.gz), [ledger](longmemeval/results-2026-11-12/assistant-set-answers-ledger.json).
