# Mem0 comparison and note extraction, 2026-11-01

Two questions. How does memBrain compare with Mem0 on LoCoMo when both use the same answering model, judge and embedding model? And does the new optional note extraction (`MEMBRAIN_EXTRACT_MODEL`), meant for bots whose model cannot save notes itself, close the gap? The second question was also checked on the two held-out Phase B scenarios through the proxy path.

## Result

LoCoMo, all 10 conversations, categories 1 to 4 (1,540 questions). The answering model and the judge are `deepseek-flash` (DeepSeek-V4.1-Flash, thinking disabled, temperature 0), with Mem0's published judge prompt, as in the [2026-10-29 report](locomo-2026-10-29.md). The full-context and memBrain rows are that report's runs, unchanged.

| Arm | Multi-hop (282) | Temporal (321) | Open-domain (96) | Single-hop (841) | Overall |
| --- | --- | --- | --- | --- | --- |
| Full context | 72.0% | 70.7% | 58.3% | 91.2% | **81.4%** |
| Mem0 open source (2.2.1) | 67.0% | 83.5% | 65.6% | 87.0% | **81.3%** |
| memBrain with note extraction | 64.5% | 80.1% | 56.2% | 84.9% | **78.4%** |
| memBrain without extraction | 58.9% | 75.7% | 58.3% | 84.7% | **76.4%** |

On the seven conversations not used to tune recall (1,155 questions):

| Arm | Multi-hop (208) | Temporal (231) | Open-domain (75) | Single-hop (641) | Overall |
| --- | --- | --- | --- | --- | --- |
| Full context | 74.5% | 67.5% | 60.0% | 90.8% | 81.2% |
| Mem0 | 67.8% | 79.2% | 60.0% | 87.2% | 80.3% |
| memBrain with extraction | 67.3% | 76.6% | 57.3% | 85.3% | **78.5%** |
| memBrain without extraction | 62.5% | 71.4% | 57.3% | 84.6% | 76.2% |

Paired per question (exact two-sided sign test on the questions where the two arms disagree):

| Comparison | All 1,540 | Held out 1,155 |
| --- | --- | --- |
| Extraction vs none | 110 fixed, 80 broken, p = 0.035 | 77 fixed, 50 broken, p = 0.021 |
| Mem0 vs memBrain without extraction | Mem0 alone right on 196, memBrain alone on 121, p < 0.001 | 143 vs 95, p = 0.002 |
| Mem0 vs memBrain with extraction | 180 vs 135, p = 0.013 | 133 vs 112, p = 0.20 |
| Full context vs memBrain with extraction | 169 vs 123, p = 0.008 | 121 vs 90, p = 0.039 |

- **Mem0 is ahead.** Under the same model, judge and embeddings, Mem0 open source matched full context (81.3% against 81.4%) and was 4.9 points above memBrain without extraction. Its advantage is in temporal (+7.8) and open-domain (+7.3) questions. It also gave the answering model less text: about 6,300 characters of prompt per question, against about 13,700 characters of memory context for memBrain.
- **Extraction closes about 40% of the gap.** Reading every stored message once with the same cheap model raised memBrain by 2.0 points (2.3 on held-out conversations). The gains are in multi-hop (+5.6) and temporal (+4.4) questions, the ones that need a fact assembled from several sessions or a date resolved once. Single-hop did not change, and open-domain fell 2.1 points (two questions).
- **On held-out conversations, memBrain with extraction and Mem0 are not clearly apart** (78.5% against 80.3%, p = 0.20). Over all ten conversations the difference is significant (p = 0.013).
- **Without an extraction model, memBrain makes no model calls at ingestion.** It records and recalls locally and scores 76.4%. Mem0 needs an LLM for every message it stores: 6,022 extraction and update calls, 53.5 million prompt tokens, here.

## Phase B scenarios through the proxy path

The [Phase B](v1-2026-10-29-phase-b.md) held-out scenarios D and E (22 cases about remembering a person's life) were run through the memory proxy's path: no tools and no skill, with memory placed at the start of the person's message, as a bot behind the proxy gets it. The host is DeepSeek-V4-Pro with thinking enabled, as before. Arm `X` has no extraction. Arm `E` reads each finished turn with `deepseek-flash` and saves notes. The plugin arm `P` is the same set of replies as in the Phase B report, scored again. A fresh reviewer scored all three arms blind per scenario.

| Arm | Scenario D (11) | Scenario E (11) | Total (22) |
| --- | --- | --- | --- |
| Proxy with extraction (`E`) | 9 | 11 | **20** |
| Proxy without extraction (`X`) | 10 | 9 | **19** |
| Plugin, agent writes notes (`P`) | 8 | 9.5 | **17.5** |

- **The scores are within reviewer noise.** The plugin's replies were identical to the Phase B run, where the first reviewer gave them 18.5. The fresh reviewer gave them 17.5. A difference of one or two points between these arms is not evidence.
- **Where extraction helped:** in scenario E, the proxy without extraction twice said the daughter's passport "was lodged in June" (E08, E10). The person had only planned it. With extraction, the plan was saved as an `intended` note and both replies were right.
- **Where it did not:** in D09, the extraction arm said the Canadian eTA had been applied for, which was only planned. The extracted `intended` plan existed, but the coming-up block filled its 1,500-character budget with the week ahead and cut the overdue plan. Coming-up now lists overdue and open items first ([d5864a1](https://github.com/chriswu727/memBrain/commit/d5864a1)). That change was made after reading scenario D, and the scenario E run had already started, so it is covered by unit tests only, not by held-out data.
- Both proxy arms passed D01 (follow up on the boiler), which every arm failed in the Phase B run. One possible reason is that the proxy puts memory in the person's message, where the plugin puts it in the system prompt. This was not tested.

## Method

- **Harnesses:** [`locomo/run_mem0.py`](locomo/run_mem0.py), [`locomo/run_locomo.py`](locomo/run_locomo.py) with `--extract-model`, and the [Phase B harness](v1-2026-10-29-phase-b-harness.py) arms `X` and `E`. Raw per-question LoCoMo results are in [`locomo/results-2026-11-01/`](locomo/results-2026-11-01/). The Phase B evidence (per-turn results, blinded sheets, sealed label mappings, verdicts) is in [`v1-2026-11-01-phase-b-proxy.evidence.tar.gz`](v1-2026-11-01-phase-b-proxy.evidence.tar.gz).
- **Mem0 arm:** follows Mem0's own LoCoMo evaluation (v0.1.100, `evaluation/src/memzero`).
  - Each speaker has a separate memory. Every session is added in pairs of messages: the speaker's own messages as `user`, the other speaker's as `assistant`, with the session date as a timestamp.
  - Each question searches the top 10 memories of both speakers, and Mem0's `ANSWER_PROMPT` answers from them.
  - Mem0 2.2.1 open source was used, with its default extraction and update prompts and its optional `nlp` and `extras` packages (spaCy lemmas, BM25 keyword search). Telemetry was off.
  - Mem0's own LLM calls were `deepseek-flash` with thinking disabled. Embeddings came from the local `multilingual-e5-small` model that memBrain uses, and vectors were stored in Qdrant on disk.
  - The open-source library does not pass the timestamp into extraction, so each message carries its session date in the text, exactly as memBrain stores it. Without that, "yesterday" would be resolved against the day of the run.
- **Differences from Mem0's published run:**
  - Mem0 published with its hosted platform, which uses custom instructions not available in the library.
  - Their answering model was GPT-4o-mini.
  - Their paper reports Mem0 6.0 points below full context. Here it matched full context, so this setup is not unfavourable to Mem0.
- **memBrain arms:** the plugin path, as in the 2026-10-29 report (session context plus recall, and the host may call `memory_recall` up to twice).
  - The extraction arm also ran `extract_turn` on every stored message right after it was stored. Extraction got the message as the person's turn, an empty reply, and the person's current notes.
  - Both LoCoMo speakers are stored as one person, so their notes share one memory.
  - At question time, notes appear in the session context.
  - Everything else is unchanged: the answering prompt, recall and the context budget.
- **Phase B proxy arms:** `ChatMemory` with `tools=None`, as `membrain-proxy` runs it. Arm `E` waited for each turn's extraction before the next message, as a live bot usually would.

## Cost

| Run | Model calls | Prompt tokens | Completion tokens | Balance change |
| --- | --- | --- | --- | --- |
| Mem0: extraction and update | 6,022 | 53.5 M | 0.79 M | 17.90 CNY in total (403.65 → 385.75) |
| Mem0: answering and judging | 3,080 | 3.0 M | 0.05 M | (included above) |
| memBrain with extraction: answering and judging | 3,498 | 10.5 M (66% cached) | 0.06 M | 10.84 CNY in total (385.75 → 374.91) |
| memBrain: extraction | about 5,900 (one per message) | not metered | not metered | (included above) |

The memBrain window also covered part of the Phase B proxy runs, so the whole memBrain run, extraction included, cost at most about 60% of the whole Mem0 run. The LoCoMo harness did not meter extraction calls separately. The product does not meter them either; a bot owner sees them on their model provider's bill.

## Incidents

- The LoCoMo extraction run was split into five shards. One shard failed when a stopped database was still holding its port. Another failed when a dropped connection ended an extraction call, which the harness then ran in line without a retry. Both partly ingested conversations were deleted and ingested again from the start, so no note came from a turn read twice.
- The harness now retries extraction three times and records which turns it has read, so a resumed run never reads a turn twice. In the product, extraction runs on a background worker that logs and drops a failed turn.

## Limits

- One run per arm, one model, and a judge from the same model family. No variance estimate on LoCoMo. Phase B has one reviewer per scenario, and the plugin arm's two scores (18.5 and 17.5 for the same replies) show about a point of reviewer noise.
- Mem0 was run with defaults. Tuning its prompts or `top_k`, or using its graph memory, might change its score. memBrain's recall was tuned on LoCoMo conversations 1 to 3, which is why the held-out rows are reported.
- LoCoMo is a conversation between two people, both stored as one user. memBrain's notes are built for one person talking to an assistant.
- The coming-up ordering fix has not been checked on held-out data.
