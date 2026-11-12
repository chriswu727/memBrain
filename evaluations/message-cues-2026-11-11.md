# Cues attached to messages: the recall block holds all the evidence for 78.5% of held-out LoCoMo questions, up from 72.2%

Base: pin `4af71af6` (runtime `933f4d8`). Runtime commit `6a136d6c`; pin commit `7f27eb6d` points all nine launchers at it. Migration `035_message_cues.sql`. Follows the [cue simulation of 2026-11-11](locomo-controls-and-cues-2026-11-11.md), which said the direction was worth building. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

Everything ran on WSL2 Linux with task-owned embedded PostgreSQL 16.15 and pgvector 0.8.6. **No model was called in this batch**: the cues are the ones `deepseek-flash` generated for the simulation (0.89 CNY, already recorded). GitHub Verify, native Windows and macOS, five-platform qualification, the R5 overhead protocol and an independent review were not run.

## What was built

A cue is a short phrase that names whom a message is about and what kind of fact it holds ("Melanie hobbies and activities"), in the words a later question would use. It is attached to the stored message and used only to find it.

- **Storage.** `memory_message_cues`: one row per message with its cue text, the rule and model that produced it, and, when a local embedding model is installed, one vector for the cue text. Row security by tenant and owner, as every other table.
- **Writing.** `POST /v1/brains/{brain_id}/message-cues` (Python `write_message_cues`, TypeScript `writeMessageCues`) takes up to 200 messages, each named by event id or by producer and source key, with at most six phrases. Phrases are scrubbed of secrets and cut to 80 characters. Only a current message that is not hidden or erased gets cues; writing again replaces them; writing is refused while server recording is paused. A metered embedding provider is never called for a cue.
- **Recall.** Cue matches enter ranking as the `entity` route, beside the keyword and meaning routes over the messages themselves. A match by the cue's words counts like a keyword match, scaled by the square of the share of the query the cue covers, so a cue that shares only a person's name with the question is found and counts for little. A match by meaning counts half, as a message matched by meaning does. One statement stands for each cued message: the one the other routes already found, otherwise the first.
- **What a host sees.** The original message, as before. The cue is not in the recall response, the recall block, the timeline, the memory page or an export.
- **Erasure.** Hiding, erasing or correcting a message deletes its cues in the same transaction; a cue of an earlier revision cannot lead to the corrected message.
- **Nothing generates cues yet.** This batch builds storage, recall and the write path, and measures them with cues made by a model beforehand. The owner has since fixed the direction for the missing half: the host's own AI writes the cues through memBrain's tools; memBrain ships no model of its own and asks the user to configure none. That is the next piece of work and is not in this batch.

## Result

Model-free [evidence-recall harness](locomo/retrieval_recall.py) through the plugin path as shipped (`--cues` attaches the earlier cues to the stored turns first): 2,198 of 5,882 turns have cues. Share of questions whose evidence turns are all present.

| Recall block (about 8,900 characters) | Questions | No cues (measured on `02a1aec`) | Runtime `6a136d6`, with cues |
| --- | --- | --- | --- |
| **Held-out conversations** | 1,152 | 72.2% | **78.5%** |
| Held out, one evidence turn | 831 | 86.6% | 91.2% |
| Held out, several evidence turns | 321 | 34.9% | **45.5%** |
| Held out, multi-hop | 208 | 30.3% | 41.8% |
| Held out, temporal | 230 | 74.3% | 83.0% |
| Held out, open-domain | 73 | 41.1% | 49.3% |
| Held out, single-hop | 641 | 88.6% | 92.0% |
| Development conversations | 383 | 79.9% | 82.5% |
| All ten conversations | 1,535 | 74.1% | 79.5% |

The no-cues column is the [message-context run](message-context-embeddings-2026-11-10.md) on the same stored brains; the two runtime commits between it and this batch (replies erased with their message, database authentication) do not touch recall, and it was not repeated.

- **Held out, paired: 86 questions gained all their evidence and 14 lost it** (exact two-sided binomial p < 10⁻¹²). The weights were chosen on the development conversations; the held-out conversations gain more.
- **For questions with several evidence turns, the mean share of evidence found rises from 58.3% to 71.5%** on the held-out conversations.
- **Whole context** (session opening plus recall block, about 18,200 characters): 73.7% to 79.4% held out, 75.5% to 80.5% on all ten. Plain retrieval (BM25 plus embeddings, no cues) filling the same number of characters has 79.3% and 80.1%; at the recall block's size it had 73.6% on all ten.
- **Smaller than the simulation.** At message level with a plain index the simulation put 50% to 54.5% of held-out several-evidence questions within the first 40 messages. Through the product, with the 9,000-character block, it is 45.5%.
- The recall block grows from about 8,600 to 8,930 characters on average.

### Choosing the weights

On the three development conversations, with the service running inside the measuring process so that the weights could be changed between requests ([cue_sweep.py](locomo/results-2026-11-11/cue_sweep.py)); 383 questions, recall block only:

| Cue route | All | One evidence turn | Several | Several, mean share |
| --- | --- | --- | --- | --- |
| No cues | 79.9% | 92.1% | 41.3% | 63.2% |
| Words, scaled by coverage | 80.7% | 93.1% | 41.3% | 64.6% |
| Words, scaled by coverage squared | 80.4% | 92.8% | 41.3% | 65.0% |
| Meaning, full weight | 80.7% | 90.0% | 51.1% | 75.1% |
| Meaning, half weight | 82.8% | 93.8% | 47.8% | 72.8% |
| Words (squared) and meaning at full weight | 80.9% | 90.4% | 51.1% | 75.2% |
| **Words (squared) and meaning at half weight** | **83.0%** | 93.5% | 50.0% | 74.1% |
| Words at half weight and meaning at half weight | 83.0% | 93.5% | 50.0% | 74.1% |
| Words (linear) and meaning at full weight | 80.4% | 90.4% | 48.9% | 74.4% |

- **The gain comes from meaning.** Matching cue words alone finds a little more evidence and completes no further several-evidence question.
- **Meaning at full weight displaces single-evidence answers** (92.1% to 90.0%); at half weight it does not.
- Reading at most as many cued messages as there are candidate slots, instead of twice as many, changed one question and saved 5 ms ([cue_sweep_limit.py](locomo/results-2026-11-11/cue_sweep_limit.py)); the smaller number was kept.

### A first variant that made recall worse

The first version fused cue matches by rank only, at the weight of a full keyword match, and by an error of mine sent all of a batch's cues to the embedding model in one request, which the local model refuses above 64 texts; the cues were stored without vectors and matched by their words only. On the development conversations the recall block fell from 79.9% to 76.8% (14 questions gained, 26 lost): every cue that named the person in the question was ranked as a strong match. The coverage scaling and the batching of embedding requests come from this.

### Latency

Paired in one process, same questions, alternating settings ([cue_profile.py](locomo/results-2026-11-11/cue_profile.py), [cue_sweep_limit.py](locomo/results-2026-11-11/cue_sweep_limit.py)): the median recall-block call went from 133 ms to 142 ms with cues. Finding the cued messages takes about 1.6 ms; the rest is reading the statements that stand for them.

The harness's own timings are not used for this. Its session-opening call, which this change does not touch, had a median of 242 ms in the earlier run and of 252 and 332 ms in two runs of this batch on the same machine.

## Verification

- **Full local source suite on the pin commit `7f27eb6d`**, with the local embedding model: 8,528 passed, 4 skipped (the Docker journeys), none failed, in 53 minutes. Source and migrations were unchanged during the run, and the pin test passes.
- Before the commit, the nine new cue tests and the test files that touch ranking, hosts, the API and the schema (373 tests) passed on a fresh database.
- The cue tests cover: a message recalled through a cue whose words it does not contain, with the cue absent from the response and the host shown the original message; replacement and removal of cues; bounds, scrubbing and refusal of unknown, hidden and erased messages; deletion of cues when a message is hidden, erased or corrected; refusal while recording is paused and for another owner; matching by meaning with a local model; and row security.
- TypeScript client: 57 tests and the strict type check pass. Ruff is clean on `src`, `tests` and `examples`.

## Limits

- **Retrieval only.** No answer was generated; the last answer run (82.5% on all ten conversations, 80.7% held out) was without cues. Whether more evidence in the block becomes more correct answers has not been measured.
- **The cues came from a paid model**, with instructions written after reading the development conversations. The product does not generate cues; an installation gains nothing from this batch until its host AI writes them, and cues written by a host AI in the course of a conversation may be better or worse than these.
- **One benchmark**: two people chatting, stored as one user's messages, English, no real elapsed time.
- **Cue words are matched as whole words and stem prefixes.** A question in Chinese, Japanese or Korean reaches a cue by meaning only.
- **Cue vectors are compared one by one**, without an approximate index. Brains here have 127 to 272 cued messages; the cost at tens of thousands was not measured. R5 was not repeated.
- Cues are not exported, so a restored archive has none until they are written again.

Files are in [results-2026-11-11](locomo/results-2026-11-11/): `recall-cues-6a136d6.jsonl.gz` and its summary, `recall-cues-keyword-only.jsonl.gz` (the first variant, development conversations), the rows and tables of the two sweeps (`cue-sweep-*`), `cue-profile.txt` and the three scripts. The baseline rows are `recall-02a1aec.jsonl.gz` in [results-2026-11-10](locomo/results-2026-11-10/).
