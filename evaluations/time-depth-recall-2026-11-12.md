# Old memories lie deeper, not gone: what the age weight costs, and a search that reaches them

The owner's rule, set on 2026-11-12: memBrain never really forgets. An old memory sinks to a deeper layer that takes more effort to reach, so that recent and important memories come first. This report measures what the existing age weight does to recall, and records the one change made from it: **a search the host AI makes on purpose is now ranked by relevance alone.** Automatic recall is unchanged.

Measured on runtime `75f3f49` (pin `df630c25`) by a sub-session of the lead, LoCoMo development conversations 0, 1 and 2 (`conv-26`, `conv-30`, `conv-41`), categories 1-4; 383 questions have evidence turns (2 of the 385 have none). No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Until now every evaluation stored a whole history within minutes, so every message had the same age and the weight (`dynamics.rank_weight`) could not act. Here each message is stored at its session's date ([time_depth_recall.py](locomo/time_depth_recall.py)).

## Summary

- **A day after the last session, the weight costs automatic recall 2.9 points**: all the evidence is shown for 77.5% of questions, 80.4% with the weight off. The loss is on evidence older than 90 days; evidence from the last 90 days gains about a point.
- **A year after the last session it costs nothing**: every memory is at the same floor, so the order does not change.
- **A search through the recall tool was ranked exactly like automatic recall** (the same result for 383 of 383 questions). Searching on purpose did not reach deeper, which is against the owner's rule.
- **Changed:** the recall request gains an optional `ranking` field, and every host's search tool asks for `relevance`. Asked a day after the last session, a search now shows all the evidence for 80.4% of questions, the same as with the weight off, question for question. The session notice, the tool description and the skill tell the host AI that a search reaches older conversations as easily as recent ones.
- **Not changed:** automatic recall keeps the weight. Putting recent memories first is the owner's design; what it should weigh besides age (importance, use) is not built.

## How the message dates were applied and checked

- The supported scenario clock was used (`src/membrain/evaluation_clock.py`). Each new installation got its own free API and database ports (`ensure_profile(..., free_port())`). Each one was marked disposable (`mark_disposable`), and `MEMBRAIN_EVALUATION_CLOCK` pointed at its `evaluation-clock.json`. Then it was started the normal way (`host.start`, a separate service process). Its `service.log` confirmed `evaluation_clock_enabled`.
- Before each session was delivered, the clock was moved to that session's LoCoMo date and time, read as UTC. Sessions are in strict date order in all three conversations. The clock then runs at wall speed, so the turns of a session are seconds apart.
- Turns were stored exactly as `run_locomo.ingest` stores them: `host.message_record(session, "user", "(date) speaker: text", turn_id=dia_id, producer="locomo-ingest")` and then `host.deliver`. After that came `host.pause` and a wait until all embeddings were done.
- The service stamps `system_time.recorded_at` from the clock. A captured statement copies its event's `system_time` (`cognition.py:319`), and `access_state` measures age from that.
- **Checked:**
  - Recorded times were read back through the timeline for every stored turn (`dates-check.json`). 1,450 of 1,451 turns were matched.
  - Recorded time minus session date was between 0 and 27.5 s, median 0.1-0.2 s. For example, conv-26 D1:1 was recorded at 2023-05-08T13:56:27Z for a session at 13:56, and D19:15 at 2023-10-22T09:55:00.24Z.
  - The read-back did not match one turn, conv-30 D13:17, although `ingested.json` counts 369 delivered. That turn is not evidence for any question, and why it failed to match was not looked into.
  - The ages of the candidate statements during recall match the formula. The recorded weights differ from 0.15 + 0.31875·2^(−age/28) by at most 3.7e-6 over 2,208 evidence statements.
- Questions were asked with the service inside the harness process (`recall_processes=0`, as in `block_sweep.py`). The same clock was enabled in that process and moved to last session + 1 day, and later to last session + 365 days. `helpers.now()` was recorded for each question.

## Arms

| Arm | What it is |
| --- | --- |
| `auto` | `host.recall_context(client, question, current_conversation=…, limit=9000)`: the automatic block as shipped. `prompt_context` would subtract its notice length from the 9,000. |
| `auto_flat` | The same, with `rank_weight` returning 1.0, patched in `candidates` and `dynamics` inside the process only. Tiers, the summary/full presentation choice and cognition's recency term are unchanged. |
| `tool` | What the plugin's `memory_recall` sends without `my_replies`: `host.recall_context(client, scrub(question), replies=False)`, the question as the query. |
| `tool_replies` | `memory_recall` with `my_replies=True`. This sends intent `episode`, which `candidates.py:465` treats as `direct`, so the weight is 1.0. |
| `searches` / `searches_flat` | The host model's recorded `memory_recall` queries from the 2026-11-11 plain answer run (runtime `933f4d8`, `answers-plain-all.jsonl.gz`), replayed through `tool`. 75 of the 383 questions have such queries. |

## Tables

"All" is the share of questions with every evidence turn shown; "share" is the mean share of evidence turns shown.

**Now = last session + 1 day**

| | n | auto all / share | auto_flat | tool | tool_replies |
| --- | --- | --- | --- | --- | --- |
| all | 383 | 77.5% / 83.5% | 80.4% / 85.7% | 77.5% / 83.5% | 80.7% / 85.8% |
| one evidence turn | 291 | 91.8% / 91.8% | 92.8% / 92.8% | 91.8% | 92.8% |
| several | 92 | 32.6% / 57.6% | 41.3% / 63.2% | 32.6% / 57.6% | 42.4% / 63.7% |
| oldest evidence < 30 d | 73 | 90.4% / 92.5% | 89.0% / 91.1% | same as auto | same as flat |
| 30-90 d | 98 | 85.7% / 89.3% | 84.7% / 87.4% | same as auto | same as flat |
| 90-180 d | 164 | 75.6% / 81.9% | 80.5% / 86.2% | same as auto | 81.1% / 86.5% |
| > 180 d | 48 | 47.9% / 64.1% | 58.3% / 72.0% | same as auto | same as flat |

Evidence turns shown, by each turn's own age (+1 day):

| | turns | auto | auto_flat |
| --- | --- | --- | --- |
| < 30 d | 97 | 87.6% | 85.6% |
| 30-90 d | 138 | 82.6% | 81.2% |
| 90-180 d | 222 | 71.2% | 77.9% |
| > 180 d | 62 | 56.5% | 64.5% |

- Paired: 15 questions have all evidence only with the weight off. Their oldest evidence is 62-243 days old, and 14 of the 15 have evidence older than 88 days.
- 4 questions have all evidence only as shipped. Their evidence is 3-35 days old.

**Now = last session + 365 days.** Every arm gives 80.4% / 85.7% overall (tool_replies 80.7% / 85.8%):

| | n | auto | auto_flat |
| --- | --- | --- | --- |
| one evidence turn | 291 | 92.8% | 92.8% |
| several | 92 | 41.3% / 63.2% | 41.3% / 63.2% |
| oldest evidence 365-395 d | 78 | 87.2% | 87.2% |
| 395-455 d | 95 | 86.3% | 86.3% |
| 455-545 d | 162 | 80.2% | 80.2% |
| > 545 d | 48 | 58.3% | 58.3% |

- By turn age: 84.6%, 81.3%, 78.1% and 64.5%, identical across arms.
- At +365 days, `auto` equals `auto_flat` question for question (383 of 383).
- `auto_flat` at +1 day equals `auto_flat` at +365 days question for question. This is expected, since without the weight the ranking does not depend on time.
- The falling recall with age in the flat arm is therefore not caused by time. Early-session evidence is simply harder to retrieve in these conversations.

**Recorded host searches (75 questions):**

| | auto | auto_flat | searches | searches_flat | auto + searches | flat + searches |
| --- | --- | --- | --- | --- | --- | --- |
| +1 day | 70.7% | 73.3% | 81.3% | 82.7% | 81.3% | 84.0% |
| +365 days | 73.3% | 73.3% | 82.7% | 82.7% | 84.0% | 84.0% |

**Rank weights in the `auto` candidate lists** (about 278 candidates per question, before the cut to the candidate limit):

- **+1 day:**
  - Mean weight of evidence statements: 0.2354, from 1,104 evidence statements in 371 questions.
  - Mean weight of other candidates: 0.2357 (mean of per-question means).
  - Per-question ratio of evidence to other: mean 0.999, median 0.823. The distribution is skewed: questions about recent sessions have a high ratio, questions about old ones a low ratio.
  - Evidence tiers: deep 594, cue 293, everyday 217.
  - Weight range of evidence: 0.1508 to 0.4610.
- **+365 days:** every candidate is `deep`, with weights between 0.15000 and 0.15004, ratio 1.0.
- Of the 519 evidence turns, 481 are in the candidate list at either time. 392 (+1 day) and 408 (+365 days) are shown.

## What the current weighting costs

- **One day after the last session (automatic recall):**
  - It costs 2.9 points of all-evidence questions (77.5% against 80.4%) and 2.2 points of evidence share.
  - The cost falls on old evidence: −4.9 points for questions whose oldest evidence is 90-180 days old, and −10.4 points beyond 180 days. Questions with several evidence turns lose 8.7 points.
  - It gives a small gain on recent evidence: +1.4 points under 30 days, +1.0 points at 30-90 days.
- **One year after the last session (automatic recall):** it costs nothing in this setting. Every stored memory is at the 0.15 floor, so the weight is the same for all of them and the ranking is unchanged.
  - The one-year recall (80.4%) is higher than the one-day recall (77.5%). Uniformly old memories are not buried; what buries old evidence is newer memories competing with it.
- **Deliberate search:**
  - The plugin's `memory_recall` without `my_replies` is not free of the age weight. It uses the default `explore` intent and returned exactly the same block as automatic recall at both times (0 differences in 383 questions).
  - Only `my_replies=True` escapes the weight, through intent `episode`. It then returns almost exactly the unweighted result: 80.7% at both times, differing from `auto_flat` on 1 question. It also includes the assistant's own replies, which LoCoMo does not have.
  - The `with_ids` path (`host.recall`) also uses `explore`; This was read in the code, not measured.
  - Replaying the host's recorded searches: weighted 81.3% against unweighted 82.7% at one day, equal at one year.
- The non-plugin MCP `memory_recall` (no profile directory) lets the caller pass `exact_quote`, `episode`, `timeline` or `cue_recovery`, which are also direct. This was read in the code, not measured.

## Code against the audit's description of decay

The [audit](audits-2026-11-12/)'s formula and numbers match the code and the measured weights:

- Activation 0.5, retention 0.5, `episode_fragment`, half-life 28 days, utility 0.5.
- Weight 0.4688 new, 0.3094 at 28 days, 0.1843 at 90 days, 0.1500 at a year.
- The weight is applied before the candidate cut, and only the four direct intents escape it.
- The floor seen is 0.15, not the `distinctive_event` floor of 0.25, consistent with "nothing protects a captured statement".

No contradiction was found. Three points it does not state, or states loosely:

1. **Tier thresholds.** "everyday" lasts until about 20.6 days, "cue" until about 85.6 days, and after that a memory is "deep". At +1 day, 54% of evidence statements were already "deep".
2. **"A year-old message ranks at about a third of today's" is true only as an absolute weight.** The weight changes the ranking only between candidates of different ages, and beyond about 180 days it is flat. So it pushes old memories down only when newer memories compete, and it cannot tell a 6-month-old memory from a 3-year-old one.
3. **The recency term in `cognition.recall` (`cognition.py:796-818`) is zeroed for every item that has rank signals.** It affects only unsignalled items, and it was not measured separately.

## Not measured

- **A brain one year later with new memories in it.** The +365 runs contain only the old history, so they show no cost. A real installation a year on would also hold a year of newer messages that outrank all of this, and that mixture is where the floor would bite. Simulating it needs added filler history, which was not done.
- **What a host model would actually search for at these ages.** The recorded queries come from a run with no age spread. Using new queries would need a paid model.
- **The cue route.** No cues were attached, so the results are not comparable with the 79.5% cue-attached baseline. Comparing them would need re-attaching the 2026-11-11 cues to these brains.
- **Held-out conversations.** They were not run, as instructed. LongMemEval was not run either.
- **`prompt_context` itself.** `recall_context` was measured at 9,000 characters, the recall-block measure. `prompt_context` would take a few characters off for its notices.

## Observations (judgement)

- **The penalty comes from the gap in ages between competing memories, not from age itself.** It decides among candidates that are already close: 15 lost against 4 gained of 383. The steep part of the curve (0.47 down to 0.18 within 90 days) is where it acts.
- **The deliberate-search path did not meet the owner's rule** that anything stays reachable when the host searches on purpose: only `my_replies` escaped the weight, and that option changes what is included. The change below follows from this.

## The change: a search made on purpose is ranked by relevance alone

Runtime commit `a9469f61`. The recall request has a new optional field, `ranking`: omitted or `recency`, of two equally relevant memories the one recorded or used more recently ranks higher, as before; `relevance` leaves age out of the ranking. It changes ranking only, not what is eligible. The search tool of every host (the MCP hosts, OpenClaw, AstrBot, Hermes) asks for `relevance`; the automatic block does not.

**A first variant was measured and dropped.** It made the search with the existing intent `cue_recovery`, which also escapes the weight. That intent is a check of earlier records as well, and leaves out messages that are the user's questions or requests. Asked with the question itself it showed all the evidence for 78.3% of questions: better on questions with several evidence turns (40.2%), worse on those with one (90.4% against 91.8%).

**The variant kept**, asked a day after the last session on the same stored brains ([script](locomo/time_depth_deliberate.py)):

| | n | Automatic, as shipped | Weight off | Search, ranked by relevance |
| --- | --- | --- | --- | --- |
| All evidence shown | 383 | 77.5% | 80.4% | 80.4% |
| Several evidence turns | 92 | 32.6% | 41.3% | 41.3% |

The search equals the weight-off result for all 383 questions. Replaying the 75 recorded host searches: 81.3% as before, 82.7% ranked by relevance; with the automatic block added, 81.3% and 84.0%.

**What this does not show.** The search is asked here with the question or with searches recorded from an earlier run. Whether a host AI searches when the user refers to something old depends on the host; the notice now tells it that a search reaches further back, and no host was run. A history a year long with newer memories on top, where the floor matters most, was not built.

Evidence: [results](locomo/results-2026-11-12-time-depth/) (per-question rows for both times, the dates check, the summary, and the rows of the search arm in `deliberate/`).
