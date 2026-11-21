# Speaker-attribution test for agent memory

A small, runnable test of one failure: a memory system that stores what the **assistant suggested** as if the
**user had said it**. The assistant proposes a city, a time, a laptop or a database; the user accepts, rejects,
corrects or ignores the proposal; later, in a new conversation, the user asks "what did I decide about X?". The
test reads the memory context the system returns for that question and checks, without any model:

1. Is the user's actual statement there, attributed to the user?
2. Is a suggestion the user did not accept there, presented as the user's words or with no speaker at all?

The results of the first run, the exact rules and their blind spots are in the
[report](speaker-attribution-2026-11-21.md).

## Run it

From the repository root, with [uv](https://docs.astral.sh/uv/):

```
uv sync --extra embedded --extra semantic
uv run python evaluations/speaker-attribution/run.py --out SCRATCH_DIR
```

`SCRATCH_DIR` is a directory the run owns. memBrain's disposable profiles, its embedded database, the database
binaries and the embedding model cache (about 130 MB, downloaded once from Hugging Face at a pinned revision and
checked against its SHA-256) all go there; nothing touches an existing memBrain installation. Stopped databases are
deleted after each case unless you pass `--keep`. On Windows keep `SCRATCH_DIR` short (for example
`C:\Users\you\AppData\Local\Temp\sa`): the database archive holds paths that pass Windows' 260-character limit under
a deep directory, and the runner refuses a root longer than 60 characters. The run checks for 2 GiB of free space.

No model is called and no API key is read. Most of the run time is memBrain starting a fresh database for each
case in the isolated mode; the report gives the measured times.

Other options: `--arms membrain,plain,plain-unlabelled`, `--modes isolated,shared`, `--only CASE,CASE` for a smoke
run, `--report` to print the table from existing rows, `--no-embeddings` for a BM25-only baseline. The scoring rules
check themselves with `python evaluations/speaker-attribution/check_scoring.py`.

## What is here

| File | What it is |
| --- | --- |
| [cases.json](cases.json) | 19 scripted conversations and 26 questions. Synthetic; no real people. |
| [distractors.json](distractors.json) | 12 unrelated conversations mixed into the shared memory; never asked about. |
| [kit.py](kit.py) | Case loading and validation, the adapter contract, the scoring rules, the table. |
| [adapter_membrain.py](adapter_membrain.py) | memBrain through its public host API, the path its plugins use. |
| [adapter_plain.py](adapter_plain.py) | Plain retrieval over the raw messages, with and without role labels. |
| [run.py](run.py) | The runner. |
| [check_scoring.py](check_scoring.py) | Hand-made contexts that pin each scoring rule. |
| [results-2026-11-21/](results-2026-11-21/) | Rows (with every context in full) and the table of the first run. |

Each case has a `kind`: **rejected** (the user says no and decides something else), **corrected** (the user keeps
part of the proposal and changes the rest, or corrects an assumption the assistant made about them), **adopted**
(the user accepts, sometimes only with "option two"), **ignored** (the user never answers it). Questions ask either
for the user's decision (`user_decision`) or for what the assistant proposed (`assistant_suggestion`).

Two modes. **isolated**: each case gets its own empty memory. **shared**: one memory holds every case and the filler
conversations in date order, as one person's history, and every question is asked of it.

## Add your memory system

Write one class with these methods (the contract is `kit.Adapter`) and add it to `make()` in `run.py`:

| Method | Must do |
| --- | --- |
| `name` | A short arm name for the table. |
| `reset(workdir)` | Start a new, empty memory. Write only under `workdir`. |
| `ingest(session)` | Record one conversation, turn by turn in order, the way your system records a live conversation: the same API, the same extraction, the same defaults. `session.id` is unique; `session.date` is the date it is set on; `session.turns` are `(role, text)` with role `user` or `assistant`. |
| `ready()` | Called once after the last session. Finish indexing or background extraction. The questions that follow must not be stored. |
| `context(question, budget=N)` | Return the memory text a host model would be given for this question at the start of a new conversation, at most `N` characters (the runner cuts anything longer). Return what the model would really see, rendered as your system renders it, not a structured dump of your store. |
| `attribute(context)` | Split the context into lines and give each a speaker: `"user"`, `"assistant"` or `None`. A speaker counts only if a reader of the context can see it, on the line itself or in the header of the block that holds the line. Lines whose text is not in the context are ignored. |
| `close()` | Stop whatever `reset` started. |

Two optional methods: `variants()` returns further contexts computed in the same `context` call, scored as arms of
their own (the memBrain adapter uses it for its recall tool); `details(context)` adds fields to each row.

When you report a result, please publish the rows (`results/rows-*.jsonl`): they hold every context in full, so
anyone can check how a line was attributed. If your system rewrites conversations into facts, read the
`misattributed_rewritten` findings by hand: the rules cannot tell "the user rejected Strasbourg" from "the user
chose Strasbourg" (see the blind spots in the report).

### Budget

memBrain decides the size of its own context. In the same run, every other arm gets, question by question, exactly
the number of characters memBrain used for that question, as in the
[LongMemEval comparison](../longmemeval-evidence-recall-2026-11-12.md). Without a memBrain arm, `--budget` (default
9,000) is used for every question. Report the budget with the result.

### Systems not run here

No adapter is included for a system that was not run: most extraction-based memories need a model key and spend
model calls on every stored message, and none was authorised for this test. The report lists what running Mem0,
Zep/Graphiti, claude-mem and others would need.

## Limits

Synthetic and small: 19 cases, 26 questions, one wording each, English only. The rules were written by the project
whose system is one of the two arms. The test measures what is put in front of a model, not what the model does with
it: a correctly labelled suggestion can still be acted on as if the user had asked for it. Details in the report.
