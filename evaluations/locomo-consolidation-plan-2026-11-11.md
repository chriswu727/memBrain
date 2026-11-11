# Plan: does consolidation into notes close the multi-evidence gap? (paid, approved 2026-11-11)

Status: **run on 2026-11-11; [result](locomo-consolidation-2026-11-11.md).** The text below is the plan as written before any call. The owner approved a bounded DeepSeek run on 2026-11-11, including the Pro model where it does the work better. This file is written before any call and is not edited afterwards except to add a pointer to the result. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## Question

[Recall cannot reach](locomo-multi-evidence-2026-11-11.md) what a conversation never states in one place: a list of what a person does, a status implied by a remark. That is consolidation's job. In the default plugin path nothing consolidates unless the host model saves notes; an optional extraction model writes notes after every turn. This run measures, on answers:

1. how much note extraction after every turn adds over messages alone;
2. whether one consolidation call per finished session, which sees the notes so far and merges into them, does as well or better;
3. what each costs.

## Arms

Harness: [consolidation_experiment.py](locomo/consolidation_experiment.py), SHA-256 `bdff4e7a149bc8ed460ae580390de930ccc18b3937b9d0a8c69215f37897bec2` at the time of this plan. Runtime under test: the integration head at the time of the run, recorded with the result.

| Arm | Memory | Model calls while storing |
| --- | --- | --- |
| `plain` | The plugin path as shipped: messages, no notes | None |
| `turn` | Plus the shipped note extraction after every stored turn | One `deepseek-flash` call per turn, thinking off, 1,200 output tokens |
| `session` | Plus one consolidation call after each finished session: the notes so far and the session go in, added and replaced notes come out, each bound to the turns it rests on | One `deepseek-v4-pro` call per session, thinking on, 8,000 output tokens including reasoning |

The `session` arm exists only in the harness. Its instructions are in the script (`CONSOLIDATION_RULES`). Notes are saved through the product's own note writer, so its limits apply: 300 characters a note, sources that must resolve, replacement of current notes only. A note the writer refuses is counted and dropped.

Each arm stores every turn of a conversation in its own installation exactly as [run_locomo.py](locomo/run_locomo.py) does, embeds everything, and pauses recording before questions. Every question starts a new session; the host gets `session_context` and `prompt_context` and may call the recall tool twice. Answers and judging use `deepseek-flash` with thinking off and Mem0's judge prompt, as in the [2026-10-29 run](locomo-2026-10-29.md), so the three arms differ only in what was stored.

## Data and order

LoCoMo development conversations only (`conv-26`, `conv-30`, `conv-41`; 385 questions in categories 1 to 4). The seven held-out conversations are not touched by this plan.

1. **Pilot**: `conv-30` (369 turns, 19 sessions, 81 questions), all three arms. Ceiling **15 CNY**.
2. **Rest of the development split**: `conv-26` and `conv-41`, same arms, only if the pilot completes without a stop and its cost per conversation projects under the remaining ceiling. Ceiling for the whole plan **60 CNY**.

## Spending control

- One ledger file per run directory. Every request is priced at the provider's peak rates without cache discount (Flash 2 and 8 CNY, Pro 9 and 27 CNY per million input and output tokens, read from the provider's pricing page on 2026-11-11).
- Before a request, its worst case (the request body's size in bytes as input tokens, the full output limit) must fit under the ceiling, or it is refused and the run stops.
- A response without integer usage stops the run and is charged at its worst case. A transport failure is charged at its worst case. An HTTP error is counted and not charged.
- Only `api.deepseek.com/chat/completions`, the two named models, non-streaming, at most 16,000 output tokens. Anything else is refused before sending.
- Results append per question and per stored session, so a stopped run resumes without repeating paid work. No automatic repeat of a failed run.

## What is reported

Per arm: accuracy on all questions, by category, and for questions with one and with several evidence turns; paired gains and losses between arms; context size; how many questions used the recall tool; notes written and their total size; calls, tokens and cost by phase; refused or unreadable consolidation outputs. Every result is kept, including a stopped or failed run.

## How the result will be read

- The comparison that matters is `session` against `plain` on **questions with several evidence turns** (92 of the 385), and all questions as the guard against harm.
- With 92 such questions, a difference under about ten points is within what one run can produce by chance. The pilot's 81 questions decide nothing; they show cost and whether the notes are usable.
- If `session` does not beat `plain` on several-evidence questions, or loses on the rest, consolidation in this form is not built into the product.
- If it does, the next step is a design for the plugin path and a separate, separately approved run on the held-out conversations. Nothing is claimed from the development split alone.

## What this cannot show

One benchmark of two people chatting, stored as one user's messages; one host model; one judge of the same family; no real elapsed time. The session-start block shows at most 4,000 characters of notes, so a conversation with more notes than that depends on which notes the product chooses to show. Consolidation by the host's own model, which is how a plugin without an extra key would do it, is not what is run here.
