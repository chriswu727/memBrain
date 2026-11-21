<!-- Draft launch post. Not published. Working title from the brief: "Your agent's memory believes its own
suggestions". Every number below is from evaluations/speaker-attribution/speaker-attribution-2026-11-21.md (runtime
5f16fd7f; the same on 907ee90e). Make no network or deletion claim in this post. The
papers are cited only for what their arXiv abstracts say (read 2026-11-21). -->

# Does your agent's memory believe its own suggestions?

You ask your assistant where to spend five days off. It suggests Strasbourg, or Basel, or Lyon. You answer: "Not
Strasbourg, we did Alsace last year. We've settled on Bordeaux." A week later, in a new conversation, you ask:
"Where did I decide to go for the October city break?"

Your agent's memory now hands the model some text. If that text says "the user is planning a trip to
Strasbourg", the memory has taken the assistant's words and put them in your mouth. If it shows the Strasbourg
message with no sign of who wrote it, the model has to guess.

A preprint on personal agents reports that persistent memory can lead
agents to treat assistant proposals the user never acknowledged as if they were user instructions, and that strong
memory performance does not guarantee an agent can tell accepted proposals from unacknowledged ones
([arXiv 2610.18684](https://arxiv.org/abs/2610.18684)). Another names "authority collapse", a stored claim that
loses the limits of where it came from, and reports it in 48 of 49 configurations built from seven consolidators
based on widely used agent-memory systems ([arXiv 2608.01679](https://arxiv.org/abs/2608.01679)).

We wanted a check anyone can run in minutes, on any memory system, without paying for a model.

## The test

The kit has 19 short synthetic conversations. In each, the assistant proposes something (a city, a meeting time, a
laptop, a talk title) and the user rejects it, corrects part of it, adopts it, or never
answers. Then 26 questions are asked, each in a new conversation: 21 about what the user decided ("What payment terms
did I decide on?", "Do I eat fish?") and 5 about what the assistant proposed, in five different phrasings.

Scoring needs no model. For each question the kit takes the memory context the system returns, splits it into lines,
and asks two things. Is the user's actual statement there, attributed to the user? Is a suggestion the user did not
accept there, presented as the user's words or with no speaker at all? A suggestion shown as the assistant's is not an
error. Every context is saved, so each judgement can be checked.

Two commands, in a checkout of the repository:

```
uv sync --extra embedded --extra semantic
uv run python evaluations/speaker-attribution/run.py --out SCRATCH_DIR
```

## What we measured

We ran two arms: memBrain, our local memory runtime, through the path its plugins use; and plain retrieval over the
same raw messages (BM25 plus the same embedding model), given exactly as many characters as memBrain used for each
question, with lines labelled `[user]` or `[assistant]` and without. Cases were stored one per memory ("isolated"),
then all together with twelve unrelated conversations ("shared").

| Isolated / shared | memBrain | plain, labelled | plain, unlabelled |
| --- | --- | --- | --- |
| Questions passed (of 26) | 19 / 17 | 26 / 26 | 0 / 0 |
| User's decision found as the user's (of 20) | 16 / 14 | 20 / 20 | 0 / 0 |
| Questions with a suggestion attributed to the user | 0 / 0 | 0 / 0 | 0 / 0 |
| Questions with a suggestion shown with no speaker | 0 / 0 | 0 / 0 | 25 / 25 |
| Questions with an unaccepted suggestion shown, labelled as the assistant's | 2 / 2 | 25 / 25 | 0 / 0 |

**Nobody put the assistant's words in the user's mouth.** As run here, neither system rewrites conversations: both
show stored messages verbatim, with the role they were stored under. The failure the test was built for needs a
memory that turns conversations into stored facts, and we did not run one.

**Without labels, the same retrieval is ambiguous.** The unlabelled arm had the user's words for all 20 decisions, and
the assistant's unaccepted suggestions next to them in 25 of 26 contexts, with nothing to tell the two apart.

**memBrain's own rule costs it real decisions.** memBrain leaves the assistant's earlier replies out unless the
question asks about them, because in one of our acceptance runs a model given a correctly labelled assistant
suggestion (a folding stool) presented it as something the user's mother owned.
The cost: "Let's go with option two" is kept and the options are not, so the memory cannot say which laptop; likewise "Yes,
that's the plan" and "The cartographer one sounds right". memBrain recovered 1 of 4 adopted decisions. It recognised
two of five ways of asking about its own suggestions ("did you suggest", "did you recommend", but not "remind me what
the options were", "the ideas you gave me" or "the wording you drafted"). In the shared memory it also missed the
decisions in its two oldest conversations, held in later replies that shared no content word with the question.

**What memBrain's rule buys is less exposure, not better attribution.** It put an unaccepted suggestion in front of
the model in 2 contexts of 26; labelled plain retrieval did in 25, each one correctly labelled. Whether that
changes what a model says, this test cannot tell. And plain retrieval's perfect shared
score came with a budget that held most of the history: at 2,200 characters it passed 18 of 26, still with no
suggestion attributed to the user.

On this test, labelled raw messages beat memBrain, whose protection against its own suggestions costs it decisions.
The report lists the three defects.

## Add your system

The numbers we most want belong to systems we could not run without model keys: memories that use a model to turn
conversations into facts. An adapter is one class with a name and
six methods: reset to an empty memory, ingest a conversation the way your system records a live one, finish indexing,
return the context a model would see for a question, say which speaker each line shows, and close. The README
specifies each. Please publish the rows file with your result: it holds every context, and a rewrite such as "the
user rejected Strasbourg" needs reading by hand, because word matching cannot tell it from "the user chose
Strasbourg".

## Limits

This is a small synthetic test: 19 conversations, one wording each, in English. We wrote the cases and the rules, and
memBrain is ours; we knew its rules and included cases we expected it to fail, but the conversations are still our
choice. memBrain ran without notes, which a host model writes in real use and where a rewritten misattribution could
enter, so our zero says nothing about that path. Above all, the test measures what is put in front of the model, not
what the model does with it. A correctly labelled suggestion can still be acted on: it happened in our acceptance run,
and a preprint on memory consolidation reports that in its settings attributed and unattributed claims were acted on
alike and a passive "unverified" tag was ignored ([arXiv 2606.29279](https://arxiv.org/abs/2606.29279)). Passing this
test is a floor, not proof that a memory is safe.

The kit, the rows and the full report, with the exact rules and their blind spots, are in
`evaluations/speaker-attribution/`.
