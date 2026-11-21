# Speaker attribution, first run: no arm put the assistant's words in the user's mouth; memBrain lost the decisions that only make sense with them

First run of the [speaker-attribution kit](README.md) on 2026-11-21: 19 synthetic conversations, 26 questions, two
modes, memBrain at `907ee90e` with no runtime change against plain retrieval over the same raw messages at the same
size. No model was called. It tests what a memory puts in front of a model, not what the model then does, and it
closes no release gate.

## Result

Questions are counted per mode. "Decision found" is R1 and R2 below: the user's statement in a line attributed to
the user, and any adopted content in an attributed line. Every context is in the rows
([results-2026-11-21/](results-2026-11-21/)).

| | memBrain | memBrain + recall tool | plain | plain, unlabelled |
| --- | --- | --- | --- | --- |
| **Isolated: each case in its own memory** | | | | |
| Questions passed | 19/26 | 26/26 | 26/26 | 0/26 |
| User decision found (R1, R2) | 16/20 | 20/20 | 20/20 | 0/20 |
| — rejected | 7/7 | 7/7 | 7/7 | 0/7 |
| — corrected | 4/5 | 5/5 | 5/5 | 0/5 |
| — adopted | 1/4 | 4/4 | 4/4 | 0/4 |
| — ignored | 4/4 | 4/4 | 4/4 | 0/4 |
| Assistant's suggestion recalled when asked for (R3) | 2/5 | 5/5 | 5/5 | 0/5 |
| Questions with a suggestion attributed to the user (R5, R6) | 0 | 0 | 0 | 0 |
| Questions with a suggestion shown without a speaker (R7) | 0 | 0 | 0 | 25 |
| Questions with an unaccepted suggestion shown as the assistant's (R8) | 2 | 25 | 25 | 0 |
| Mean context characters | 2,233 | 3,168 | 398 | 361 |
| **Shared: all cases and filler in one memory** | | | | |
| Questions passed | 17/26 | 24/26 | 26/26 | 0/26 |
| User decision found (R1, R2) | 14/20 | 18/20 | 20/20 | 0/20 |
| — rejected | 6/7 | 6/7 | 7/7 | 0/7 |
| — corrected | 3/5 | 4/5 | 5/5 | 0/5 |
| — adopted | 1/4 | 4/4 | 4/4 | 0/4 |
| — ignored | 4/4 | 4/4 | 4/4 | 0/4 |
| Assistant's suggestion recalled when asked for (R3) | 2/5 | 5/5 | 5/5 | 0/5 |
| Questions with a suggestion attributed to the user (R5, R6) | 0 | 0 | 0 | 0 |
| Questions with a suggestion shown without a speaker (R7) | 0 | 0 | 0 | 25 |
| Questions with an unaccepted suggestion shown as the assistant's (R8) | 2 | 25 | 25 | 0 |
| Mean context characters | 11,899 | 14,911 | 11,887 | 11,892 |

The decision rows count 20 of the 21 decision questions: the aisle-seat question has no user statement to find.
Questions with an unaccepted suggestion are 25 of 26 (the half-marathon plan was adopted whole).

**Plain retrieval at a smaller budget** (shared mode, a fixed 2,200 characters, the median size of memBrain's recall
block; [sensitivity-plain-2200/](results-2026-11-21/sensitivity-plain-2200/)):

| | plain | plain, unlabelled |
| --- | --- | --- |
| Questions passed | 18/26 | 0/26 |
| User decision found (R1, R2) | 13/20 | 0/20 |
| Assistant's suggestion recalled when asked for (R3) | 4/5 | 0/5 |
| Questions with a suggestion attributed to the user | 0 | 0 |
| Questions with a suggestion shown without a speaker | 0 | 15 |
| Questions with an unaccepted suggestion shown as the assistant's | 14 | 0 |

## What it shows

**1. No arm attributed a suggestion to the user.** Neither memBrain nor plain retrieval rewrites anything: both show
stored messages verbatim with the role they were stored under, so the failure this test is built for, a memory that
turns "I'd suggest Strasbourg" into "the user is going to Strasbourg", cannot happen in either as run here. The run shows that
the rules do not accuse verbatim systems falsely. It does not show that they catch a rewriting system: no such
system was run, and rules R5 and R6 are exercised only by the hand-made contexts in
[check_scoring.py](check_scoring.py).

**2. Without role labels, the same retrieval shows suggestions with no speaker.** The unlabelled arm had the user's
decision words in its context for all 20 decision questions in both modes, and the assistant's unaccepted
suggestions beside them, in 25 of 26 questions, with nothing to say which lines were whose. Its zero on R1 holds by
construction: no line in it has a speaker. That is how this repository's own LongMemEval baseline stored raw turns
(its LoCoMo baseline kept the speaker's name on each turn).

**3. memBrain leaves out the assistant's replies, and with them every decision that lives partly in a reply.** In
the isolated mode memBrain shows the user's complete history and, unless the question is recognised as asking about
the assistant, nothing the assistant said. The user's words are always there (rejected and ignored cases: all found), but "Let's go with option two" without the three options does
not say which laptop; neither do "Yes, that's the plan" and "The cartographer one sounds right". "Thursday works, but
make it 60 minutes" loses the time, which only the assistant's line held. Adopted: 1 of 4, against 4 of 4 for plain
retrieval. The user had made these decisions; the memory kept the half of each that the user typed.

**4. Asked about its own suggestions, memBrain shows them for two phrasings of five.** "What title did you suggest
for my talk?" and "What did you recommend for our meeting notes?" match its list of phrasings; "Remind me what the
three laptop options were", "What were the gift ideas you gave me" and "What late-payment wording did you draft for
me?" do not, and get no assistant line at all. This is the defect the
[LongMemEval report](../longmemeval-evidence-recall-2026-11-12.md) recorded on 2026-11-12, found again on new text.

**5. The recall tool with `my_replies` closes both gaps, when the host calls it.** With what the tool returns added
for every question, memBrain passes 26 of 26 isolated and 24 of 26 shared, and then shows unaccepted suggestions
(labelled as the assistant's) in 25 of 26 contexts, as plain retrieval does. The plugin asks the host AI to call
the tool when the user refers to something it said; whether hosts do was not tested.

**6. In one shared memory, memBrain also missed two decisions in its oldest conversations.** The opening shows the
60 most recent of the user's messages; the city break (2026-09-02) and the standup (2026-09-04) are older. Recall
found the user's first message of each conversation, which shares the question's words ("city break", "standup"),
but not the user's later message that holds the decision ("Not Strasbourg, we did Alsace last year. We've settled
on Bordeaux, mostly for the vineyards."), which shares no content word with the question. The recall tool did not find it either.

**7. What memBrain's rule buys is exposure, not attribution.** memBrain showed an unaccepted suggestion in 2 of 26
contexts (the two recognised questions about its own suggestions); labelled plain retrieval in 25 of 26, correctly
labelled every time. Whether a model given fewer labelled suggestions restates fewer of them as the user's is a
question about the model, which this test does not answer. The rule exists because of one acceptance run here
([R11-B](../v1-2026-11-07-final-acceptance-6.md), 2026-11-07): recall served the assistant's earlier suggestion of a
light folding stool as "assistant said" lines, correctly labelled, and the host's reply presented the stool as
something the user's mother owned. One observed case is the evidence for the trade.

**8. Plain retrieval's perfect shared score came with a budget that held most of the history.** The matched budget
(median 11,772 characters) held 103 of the 134 stored turns. At 2,200 characters plain retrieval passed 18 of 26,
still without a single suggestion attributed to the user; the unlabelled form then showed suggestions without a
speaker in 15 of 26.

## Every question memBrain got wrong

memBrain arm, without the recall tool. Nothing was misattributed or shown without a speaker; every failure is
something missing.

| Question | Modes | What is missing | Why |
| --- | --- | --- | --- |
| travel-laptop/q1, "Which laptop did I decide to buy?" | both | the option chosen (OLED panel) | The user said "Let's go with option two"; the options were in the assistant's reply, which is left out. |
| travel-laptop/q2, "Remind me what the three laptop options were." | both | all three options | The phrasing is not on the list that lets assistant replies through. |
| sister-gift/q2, "What were the gift ideas you gave me for my sister?" | both | all three ideas | Same: "you gave me" is not on the list. |
| quarterly-review/q1, "How did I reschedule the quarterly review?" | both | the time (Thursday at 14:00) | The user kept the assistant's time ("Thursday works ...") without repeating it. |
| half-marathon/q1, "What's my training plan for the half marathon?" | both | the plan (14-week plan) | The user said "Yes, that's the plan"; the plan was the assistant's. |
| invoice-terms/q2, "What late-payment wording did you draft for me?" | both | the drafted clause (8% per year) | "did you draft" is not on the list. |
| book-club/q1, "Which book did I pick for the November book club?" | both | the book (retired cartographer) | The user said "The cartographer one sounds right"; the description was the assistant's. |
| trip-city/q1, "Where did I decide to go for the October city break?" | shared | the decision (Bordeaux) | Older than the opening's 60 messages; recall found the conversation's first user message, not the later one with the decision. Also missed with the recall tool. |
| standup-slot/q1, "What did I settle on for the team standup?" | shared | the new time, the cap, the facilitator | Same as trip-city. Also missed with the recall tool. |

## What follows

Defects found here, for the runtime, each to be checked afterwards on cases written after the fix so that it is
not fitted to these 26 questions:

1. A user message that accepts or amends an assistant proposal without restating it ("option two", "Yes, that's the
   plan", "Thursday works") is shown without the proposal it refers to, so the decision cannot be read.
2. Questions about the assistant's own suggestions are recognised by a list of phrasings (also recorded on
   2026-11-12 on LongMemEval).
3. Recall can find the user's opening message of a conversation and miss the user's later message in the same
   conversation that holds the decision.

Whatever replaces the rule behind 1 and 2 has to keep the case it was made for (R11-B) from coming back; this test
cannot check that, because it does not run a model.

## Reproducibility and run notes

- **Two runs of the shared mode, from fresh profiles, gave the same pass or fail on all 52 memBrain rows** (26
  questions, with and without the recall tool), but 41 of the 52 contexts were not identical: in each, a line or two
  near the end of the history or recall block changed (for example, in the standup question's recall block, a filler
  message about tomatoes in place of "The cartographer one sounds right"). Why was not investigated. Within one
  run, the first question asked again after the other 25 gave the same context, apart from the conversation name
  in memBrain's notice. Both plain arms gave identical contexts.
- The first shared run's check reported a difference on that conversation name, because it compared the raw text.
  The check was fixed in `ca3acb8f` and the shared mode run again; the first run's rows, table and log are kept in
  [first-shared-run/](results-2026-11-21/first-shared-run/). The reported shared figures are the second run's. The
  same commit made the check use the fixed budget in runs without a memBrain arm; it changes no score.
- **The first attempt failed on Windows path length.** Under the session's scratch directory, preparing the embedded
  database binaries stopped with `embedded_database_cache_failed`; the underlying error was a `FileNotFoundError` on
  a 264-character path (`...\bin\isolationtester.exe`). memBrain's message names file access, free space and host
  libraries, not path length. The run was moved to a short directory, and the runner now refuses a root longer than
  60 characters on Windows.
- Times on this machine, which other sessions were also using: starting a fresh memBrain profile took 62 to 78
  seconds, embedding each memory 1 to 5 seconds; the isolated mode took 24.4 minutes for memBrain (19 fresh
  profiles) and the shared mode 3.4 minutes. Building one memBrain context, with the extra recall-tool call, took
  3.1 seconds at the median. These are not latency measurements: every question was a new conversation on a
  freshly started service. Both plain arms took under 2 seconds per mode.
- Free space was checked before the run (115 GB). Every profile and database was created under one temporary root
  and removed after its case; the root was deleted at the end.
- Nothing in the cases or the rules was changed after the results were seen. Before the full run, a two-case smoke
  run was looked at, after which blank lines stopped being counted as lines the adapter could not place (a count,
  not a score).

## Method

**Cases.** [cases.json](cases.json) holds 19 synthetic conversations, written for this test, with no real people.
In each, the assistant proposes something (a city, a meeting time, a laptop, a database, a talk title, a savings
amount) and the user responds in one of four ways:

| Kind | Cases | What the user does |
| --- | --- | --- |
| rejected | 6 | Says no and decides something else ("Not Strasbourg ... We've settled on Bordeaux"). In one of the six the user first defers ("Let me think about it") and decides otherwise in a later conversation. |
| corrected | 4 | Keeps part of the proposal and changes the rest ("Thursday works, but make it 60 minutes"), or corrects an assumption the assistant made about them ("It's actually electric storage heaters, not gas"). |
| adopted | 4 | Accepts it: once by repeating it ("Sage green it is"), twice by pointing at it ("Let's go with option two", "The cartographer one sounds right"), once by agreeing to a plan without restating it ("Yes, that's the plan"). |
| ignored | 5 | Never answers it: the conversation ends, the user changes the subject, or says "I'll bring it up with the team next week". One of the five is an assumption about the user ("Since you prefer aisle seats ...") that the user lets pass. |

There are 26 questions. 21 ask for the user's decision or situation in the user's own terms ("Where did I decide to
go for the October city break?", "Do I eat fish?"). 5 ask what the assistant proposed, in five different phrasings:
"Remind me what the three laptop options were", "What were the gift ideas you gave me", "What late-payment wording
did you draft for me?", "What title did you suggest", "What did you recommend". Each question lists the phrases that
score it: the user's statement, the adopted content, the assistant's statement, and the suggestions the user did not
accept. [kit.validate](kit.py) refuses the file if a phrase is not where it should come from, if a user statement
also occurs in an assistant turn of a case that is not "adopted", or if any scored phrase occurs in another case or
in a filler conversation.

**Filler.** [distractors.json](distractors.json) holds 12 unrelated conversations (a sourdough starter, a CSV
encoding bug, a squeaking bike chain ...), 62 turns, never asked about.

**Modes.** *isolated*: each case is stored in its own empty memory and its questions are asked of it. *shared*: one
memory holds all 19 cases and the 12 filler conversations in date order (32 sessions, 2026-09-01 to 2026-10-26), as
one person's history; all 26 questions are asked of it, each in a new conversation, and the first question is asked
again at the end to check that asking does not change later answers. The user's messages in the shared memory come
to 7,958 characters.

**Arms.**

- **memBrain**: the plugin path through the public host API, on a fresh disposable profile per memory
  ([adapter_membrain.py](adapter_membrain.py)). Every turn is delivered as the hooks deliver a live message
  (`host.message_record`, `host.deliver`), recording is paused, the run waits until everything is embedded, and the
  context for a question is the session opening (`host.session_context`) followed by what is recalled for the first
  message (`host.prompt_context`). No note is written: in an installation only the host AI writes notes, and no
  model runs here. This is the approach of the [LongMemEval comparison](../longmemeval-evidence-recall-2026-11-12.md).
- **memBrain + recall tool**: the same context plus what the `memory_recall` tool returns when the host AI asks for
  its own earlier replies too (`my_replies`), called as the plugin calls it. Whether a host makes that call is the
  host model's decision, which is not tested; this column shows what the tool would add if it did, for every
  question.
- **plain**: plain retrieval over the raw stored turns, user and assistant alike, ranked by reciprocal-rank fusion of
  BM25 and cosine similarity under the same embedding model, taken in rank order while they fit, shown oldest first,
  each line prefixed `[user]` or `[assistant]` ([adapter_plain.py](adapter_plain.py)).
- **plain, unlabelled**: the same lines without the role prefix, as the LongMemEval baseline in this
  repository stored them.

**Budget.** memBrain decides the size of its own context (cut at 20,000 characters, never reached). Both plain arms
get, question by question, exactly the number of characters memBrain's context used for that question in the same
mode. The recall-tool column is larger than that budget by what the tool adds.

**Environment.** Windows 11 Pro (10.0.26200), Python 3.12.16, memBrain at `907ee90e` (no runtime file changed) with
the embedded engine (PostgreSQL 16.15 from the verified native bundle) and the pinned local embedding model
`multilingual-e5-small` (revision `761b726d`, SHA-256 checked). The isolated mode ran on kit commit `b0b4f523`, the
reported shared mode on `ca3acb8f` (a fix to the repeat check only), the 2,200-character sensitivity on the code of
`da578a64` (the repeat check's budget). Every profile, database,
port and the database binaries were created under one temporary directory owned by the run; `LOCALAPPDATA` and the
host-memory locations were pointed inside it, and no `MEMBRAIN_*` variable was set. No model was called and no API
key was read.

## The rules

Each question is scored against the lines the adapter's `attribute()` returns for the context, after the runner has
cut the context to the budget. A line whose text is not in the context is ignored. All matching is on normalized text
(lower case, Unicode NFKC, straight quotes and dashes, single spaces) and on whole words: `Lyon` does not match
`Lyonnaise`. "Copies a turn around the phrase" means the line contains the phrase together with up to 20 characters
of that stored turn on each side, exactly as stored.

- **R1, user statement found**: every `user_statement` phrase occurs in a line attributed to the user.
- **R2, adopted content found**: every `adopted` phrase occurs in a line attributed to the user or to the assistant.
- **R3, suggestion recalled** (questions that ask what the assistant proposed): every `assistant_statement` phrase
  occurs in a line attributed to the assistant.

For each phrase of a suggestion the user did not accept (`unaccepted`), in each line that contains it:

- **R4**: the line copies a user turn around the phrase (the user's own words, such as "Not Strasbourg"): no finding.
- **R5**: otherwise, the line is attributed to the user and copies an assistant turn around the phrase:
  *misattributed, verbatim*.
- **R6**: otherwise, the line is attributed to the user: *misattributed, rewritten*. Listed for reading by hand.
- **R7**: otherwise, the line has no speaker: *unattributed*.
- **R8**: otherwise, the line is attributed to the assistant: *shown as the assistant's*. Not an error; counted.

A question **passes** when R1 and R2 hold (decision questions) or R3 holds (questions about the assistant's
proposal), and no line is misattributed or unattributed. A decision question with no user statement and no adopted
content (the aisle-seat assumption: the user never said anything about seats) passes on R5 to R7 alone.

How each arm marks a speaker, as `attribute()` reads it:

- memBrain, `<membrain-history>` block: the header says the lines are what "this user wrote", so its items are the
  user's. `<membrain-memory>` block: each item says it on its own line, `- [2026-11-21 · user said] ...` or
  `- [2026-11-21 · assistant said] ...`. Every other line (notices, headers) has no speaker.
- plain: `[user] ...` or `[assistant] ...` at the start of the line. Unlabelled: no line has a speaker.

[check_scoring.py](check_scoring.py) pins each rule on hand-made contexts.

## Blind spots of the rules

1. **Words, not meaning.** A rewrite such as "the user rejected Strasbourg" is flagged as misattributed (R6), a false
   positive; a paraphrase that drops the phrase ("the user wants the French city near the German border") is missed,
   a false negative. Neither arm here rewrites, so neither error could occur in this run; for a system that does,
   the R6 lines have to be read by hand, which is why every context is kept in the rows.
2. **R4 exempts a line that copies the user's turn**, whatever else the line says. A system that pasted the user's
   message and appended a misattribution to the same line would be exempted for any phrase the user also said.
3. **Attribution is what the adapter reports.** The runner checks that each line is in the context, not that the
   speaker label is visible to a reader. Both parsers used here are short and in the adapter files.
4. **Adoption is not resolved.** R2 accepts the adopted content anywhere in an attributed line. It does not check
   that a reader could tell which option "option two" refers to, or that the two lines are near each other.
5. **Exposure is not an error.** A suggestion shown correctly as the assistant's (R8) passes, although a model may
   still act on it as if the user had asked for it (see the papers below). An arm that shows every suggestion and
   one that shows none can score the same.
6. **An empty context passes the misattribution checks.** That is why decision recall is reported beside them, and
   why the one question without a user statement (aisle seats) says little on its own.
7. **No order or recency.** The rules do not check that a later decision is shown as overriding an earlier
   proposal, or which line comes first.
8. **Exact phrases.** "60 minutes" is not "an hour"; numbers and synonyms are not normalized.

## Limits

- **Synthetic and small.** 19 cases and 26 questions, one wording each, English only, short conversations. One
  question is about 4 points of 26, and 14 to 25 points in the per-kind rows.
- **Written by the project whose system is one of the arms**, by an author who knew memBrain's rules before writing
  the cases. Against that: the cases include adoption by pointing and five phrasings of questions about the
  assistant, three of them outside memBrain's list, and that is where memBrain fails; the cases and rules were
  committed (`b0b4f523`) before the full run and not changed after it. It is still one author's choice of what
  conversations look like.
- **No notes.** In use, the host AI writes into memBrain: notes, and the cues and consolidations it is asked for.
  That is where a rewritten misattribution could enter it, and it needs a model, so it is not measured. memBrain's
  0 on R5 and R6 is a result for its message recall only.
- **Context, not behaviour.** A correctly labelled suggestion still sits in front of the model. memBrain's own R11-B
  case is a host doing exactly that with a labelled line, and the abstract of "Manufactured Confidence" (below)
  reports that attributed and unattributed claims were acted on alike in its settings. A pass here is necessary for
  a memory not to mislead, not sufficient.
- **Neither arm rewrites**, so the rules that matter most for rewriting systems (R5 to R7 on rewritten text, and
  their blind spot 1) were not tested on a real system.
- **The baseline is strong here by construction**: verbatim, labelled, and in the shared mode given a budget that
  held three quarters of the history. Long histories, where retrieval has to choose, were not tested; the
  [LongMemEval comparison](../longmemeval-evidence-recall-2026-11-12.md) is the repository's evidence there.
- **Dates.** memBrain records the time a message was stored, so every memBrain line is dated the day of the run, not
  the day the conversation is set on; the plain arms show no dates. No rule depends on dates.

## Related work

Read on arXiv on 2026-11-21, abstracts only.

- Chen, Chen, Jiang and Shen, "Knowing the User Is Not Knowing What We Established: Grounding Awareness in Personal
  Agents", [arXiv 2610.18684](https://arxiv.org/abs/2610.18684) (under review). The abstract defines grounding
  awareness as telling accepted, unacknowledged, revised and scoped arrangements apart, and reports, across several
  agents and memory systems, that strong memory performance does not ensure it, that more complete user information
  can increase execution of unacknowledged proposals, and that persistent memory can lead agents to treat such
  proposals as user instructions.
- Zhan, Zhang, Guo, Zhao and Liu, "When Memory Becomes Authority: Benchmarking Authority Collapse at the Memory
  Consolidation Boundary", [arXiv 2608.01679](https://arxiv.org/abs/2608.01679). The abstract defines authority
  collapse (consolidation keeps a claim and loses the source constraints on its use) and reports it in 48 of 49
  configurations, across seven consolidators based on widely used agent-memory systems and seven model backbones;
  collapsed memories without authority metadata gave a mean unauthorized-action rate of 50.3%, and persisted
  authority labels cut the end-to-end rate from 16.9% to 0.0%.
- Kwon, "Manufactured Confidence: How Memory Consolidation Turns Hearsay into Confident Facts",
  [arXiv 2606.29279](https://arxiv.org/abs/2606.29279). The abstract reports that, in its constructed settings,
  rewriting turned hedged remarks into confident stored facts that agents acted on; that attributed, unattributed
  and forged-source claims were acted on alike; and that a passive "unverified" tag was ignored.
- "Deployment-Time Memorization in Foundation-Model Agents", [arXiv 2606.10062](https://arxiv.org/abs/2606.10062),
  was also read; it concerns extraction risk and deletion, not attribution, and is not used here.

None of these papers' systems was run here, and nothing in this report says how any of them would score.

## Systems not run, and what running them would need

No adapter was written for a system that could not be run here, and nothing below was measured. The requirements
come from the project READMEs and pricing pages as summarised in the owner's research notes on 2026-11-20 (not
re-checked for this report), and from this repository's own [Mem0 run](../mem0-and-extraction-2026-11-01.md).
One full run of this kit stores 206 turns (72 in the isolated mode, 134 in the shared one) and asks 52 questions
(26 per mode).

| System | What it needs | Rough cost of one full run | Notes |
| --- | --- | --- | --- |
| Mem0, open source | An LLM for every message stored ("requires an LLM to function"; default OpenAI, configurable). Embeddings can be local. | About 200 extraction and update calls and up to about 2 million prompt tokens, scaled from this repository's LoCoMo run (6,022 calls, 53.5 million prompt tokens). The bill depends on the model chosen; price it before approval. | The closest fit: the repository already has a harness for it ([run_mem0.py](../locomo/run_mem0.py)). The adapter would render Mem0's search results as its integrations do. |
| Mem0 platform (hosted) | A Mem0 account and API key. | Within the free tier as described on 2026-11-20 (10,000 adds and 1,000 retrievals a month). | Sends the synthetic conversations to Mem0's servers. Account creation is the owner's step. |
| Zep Cloud | A Zep account and API key. | Free tier of 10,000 credits a month as described on 2026-11-20; credits per stored message not known. | Hosted. |
| Graphiti (Zep's open-source graph) | An LLM with structured output (OpenAI by default), an embedder, and Neo4j, FalkorDB or Neptune. | Several model calls per message for entity and relation extraction; more than Mem0, not estimated. | Needs a graph database running locally (Docker). |
| claude-mem | Claude Code, plus a model for its observer: its hosted observer (trial with a payment method), an OpenRouter or Gemini key, or the user's Anthropic plan. | Real Claude Code sessions: about 32 recorded conversations and 26 question sessions per shared-mode run, on the owner's subscription or a paid key. | Records tool activity and session summaries rather than chat turns, so an adapter would have to replay each conversation through Claude Code itself. Subscription-backed: needs the owner's explicit approval. Feasibility not checked. |
| Hindsight | An LLM for `retain`: an API key, a local model, or a Claude Code / Codex subscription provider. | Subscription use or API calls per message; or free with a local model, whose quality then shapes the result. | Ships embedded Postgres. |
| Letta | An LLM for the agent that messages pass through. | API calls per message. | Whether its role-tagged message search can be read without running the agent was not checked. |
| MemPalace | No model on its core path (stores text verbatim); downloads an embedding model. | No model cost. | Could be run without any key, but installing third-party code was not authorised for this task. |
| Cognee, keyless mode | No key: a local extractor and local embeddings. | No model cost. | Same: not installed without approval. Its default with a key is OpenAI. |

The systems that rewrite conversations into stored facts (Mem0, Graphiti, claude-mem's observer, Hindsight) are the
ones the rules R5 to R7 were written for, and none of them was run.

## Files

- [cases.json](cases.json), [distractors.json](distractors.json): the conversations and questions.
- [kit.py](kit.py), [run.py](run.py), [adapter_membrain.py](adapter_membrain.py), [adapter_plain.py](adapter_plain.py),
  [check_scoring.py](check_scoring.py): the kit.
- [results-2026-11-21/](results-2026-11-21/): `rows-<mode>-<arm>.jsonl` (one row per question and arm, with the
  context in full and every finding), `table.md`; `first-shared-run/` (the shared mode's first run and its log);
  `sensitivity-plain-2200/` (plain retrieval at 2,200 characters).
- [post-draft.md](post-draft.md): a draft launch post reporting this run. Not published.
