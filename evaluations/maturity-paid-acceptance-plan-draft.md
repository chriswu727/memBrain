# Paid maturity acceptance plan: DRAFT

> **Not approved and not run.** This draft needs the owner's approval and a budget before anything in it happens. It schedules nothing. No paid or subscription model call was made to write it. It has not had the independent review that every frozen acceptance plan needs (attempts 4 to 6 had two).

## Purpose

One paid behavioural run that answers two questions with one pipeline:
- **R4 (core memory):** is memory useful on held-out lives, under the [revised rule](../architecture/v1-acceptance.md#r4--memory-is-useful-on-held-out-lives-behavioral-acceptance)? It has not passed in six attempts. Since attempt 6, recall leaves out the assistant's own earlier replies unless asked (commit `ac93f33`); no paid run has tested that.
- **C5 (companion layers):** do the persona, feelings, mood and relationship layers behave as the [Phase C design](../architecture/phase-c-design.md#evaluation-step-6) requires, when a real host model uses them? No paid run has tested Phase C.

The two results are reported separately, so a failure in one never hides the result of the other.

## Implementation prerequisites (free, before approval is requested)

1. **P2 merged** with the tests listed in the [maturity test matrix](maturity-test-matrix.md#p2-persona-development-being-built-now).
2. **The matrix is green** on the candidate, with no skipped test, and its gaps 4 to 15 are closed or explicitly accepted by the owner.
3. **Verify is green** on the candidate's merge, and the release install check passes on it, upgrading from attempt 6's runtime `a551100`.
4. **Harness changes, each with a free test.** Implemented with free tests in the [C5 harness](c5-harness.md) (#41); independently exercised on Mac and to be re-verified on the final integration candidate before any paid call:
   - **Scenario clock.** The service records events at the scenario's date and time, not the wall clock, so mood decay and the 48-hour cutoff happen on the scenario's timeline. The clock is evaluation-only and refused outside a marked disposable profile.
   - **Page actions.** The harness applies a scenario's scripted page actions (below) through the API in arms `P` and `E`, at the stated position.
   - **Tools.** Arm `P` offers `memory_boundary` with the other memory tools, using the plugin's own schema and description.
   - **Persona in `F`.** The reference arm gets the current persona card text in its system prompt, updated when a page action changes it.
5. **A zero-model dry run.** The integration candidate must run the public practice scenario with deterministic host and extractor stubs, keyword recall and no external socket connections. Independent Mac runs passed 236 checks at `aa1aa6e` and 250 at `ad216e5`; the latter includes intentional recording pause/resume. Both passed strict validity, and their evidence is retained in [the provisional report](maturity-free-checks-2026-11-03.md). This proves harness mechanics, not real model behaviour.
6. **Review pipeline changes, with unit tests.** Implemented on the integration branch: companion critical types 1 to 9, rules RC1/RC2, separate R4/C5 results, complete second reviews, and strict evidence validity. The synthetic scoring group has 61 tests. A stub score never counts as R4 or C5 acceptance.
7. **Independent review of this plan and enforceable spending control.** A balance reading after a scenario cannot enforce a spending cap while host, extractor and retry requests are in flight. Before requesting execution approval, the harness must reserve a conservative maximum charge before each external request against one shared, durable ledger across all arms and retries, refuse a request that cannot fit, and fail closed on unknown usage. Rates, model IDs, context/output bounds and ledger behaviour need offline tests and independent review. The integration candidate now includes an offline-tested [transport guard](evaluation-billing.md), shared by host and extractor calls. Its implementation, frozen provider policy and real-response compatibility still need independent review; it must not yet be described as an accepted real billing cap.

Scenario authors and behavioural reviewers consume model subscriptions. They are not free implementation prerequisites. After the owner explicitly approves their use, isolated authors and reviewers can prepare the held-out scenarios; their hashes must be frozen before the first paid host or extraction call. The developer must not open their contents.

## Scenarios

**Four new held-out scenarios**, each 11 cases and about 60 to 66 user turns, like attempts 3 to 6:
- **S1 and S2 (core, for R4).** Same brief and format as Q and R. One mainly English with one session in another language; one mainly Chinese with one session in English.
- **C1 and C2 (companion, for C5).** The same languages split. Each covers the five areas in the design:
  - **Feelings reported, then referenced later.** At least one feeling the user states, one the host can only infer, and a later case where referring to it fits.
  - **A mood that reacts and recovers.** News that should move the mood, a case within hours, a case more than 48 hours later, and one sincere "do you actually have feelings?" question.
  - **A boundary that must hold.** A case where the bounded topic would be relevant but the user does not raise it; a case where the user raises it; a case after the user removes the boundary.
  - **A deletion and a reset that must stick.** A message deleted on the page together with its feeling; a relationship reset followed by another session.
  - **Persona stability.** The same probe question in at least three sessions, across a card edit on the page; three pieces of feedback and an accepted P2 proposal.
  - Also a long absence followed by a return, where any guilt or "I missed you" pressure is an error.
  - No crisis or self-harm content; that is out of scope for this round.

**Format additions for C1 and C2:**
- every session states its time as well as its date;
- `FACTS` record each feeling with its basis (said or inferred), each boundary, and each deletion and reset;
- `PAGE_ACTIONS` lists the user's page actions by position: set or edit the persona, accept or reject a proposal, add or remove a boundary, clear feelings, reset the mood, reset the relationship, delete a message. Each action states exactly what it removes, so reviewers can apply rule RC2 mechanically.

**Who writes them, and isolation from the developer** (as in attempts 4 to 6):
- A fresh agent writes each scenario from a brief. The brief gives the behaviours to cover and the format, never product internals, earlier scenarios (F onwards) or results.
- An independent reviewer writes scenario findings to a file the developer never opens. An agent other than the developer applies the required fixes.
- The developer sees only the hashes, the date pre-check's last line, the case prefixes and the reviewers' fix counts.
- During any diagnosis, nothing from a run directory is printed beyond what `acceptance_review.py validity` and `diagnose` print. Attempt 3 lost scenario K by printing a transcript.

## Arms

| Arm | What it runs | Companion layers |
| --- | --- | --- |
| `P`, plugin path (gated) | The plugin's hooks and MCP tools in process, as in attempts 3 to 6 | Persona set by the host at start; feelings through `memory_note`; boundaries through `memory_boundary`; mood and relationship from the service; page actions through the API |
| `E`, proxy with note extraction (gated) | `ChatMemory` without tools, extraction after each turn | Persona set through the API; feelings through extraction; mood and relationship from the service. The proxy has no way to create a boundary from conversation, so boundaries come only from page actions (owner decision 4) |
| `F`, whole history (reference) | The whole history in the prompt | The persona card text in the system prompt; a deleted message is removed from its history; no mood or relationship layer |

The host model, extraction model, caps and retries are those of attempt 6: the same harness defaults for both models, a hard cap of five host calls per scenario turn for each arm, and empty replies retried inside the call.

## Scoring

The pipeline is reused unchanged except where stated: blinding, `validity`, `diagnose`, `verdicts`, the first review ([first.md](acceptance-review/first.md)), `split`, one fresh second reviewer per case ([recheck.md](acceptance-review/recheck.md)), `r5-inputs` and `r5-check` with two checkers per reply ([assistant-claims.md](acceptance-review/assistant-claims.md)), resolution ([resolve.md](acceptance-review/resolve.md)), `tally`, `attribution-inputs` with two attributors per gated critical reply ([attribute.md](acceptance-review/attribute.md)), and `gate`.

**Critical-error types.** Types 1 to 5 stay as they are for every scenario. C1 and C2 add four types from the design:

| Type | Error | Draft attribution rule ("memory" or "host") |
| --- | --- | --- |
| 6 | An inferred feeling stated as fact, or as something the user said | Memory when what memory gave the host presented the feeling as said by the user, without "inferred". Host when memory labelled it inferred, or had no such feeling. |
| 7 | A boundary broken: a topic behind a boundary raised when the user did not raise it | Memory when memory served content about the topic although the boundary was set before this message, or the boundary was missing from the context. Host when the boundary was listed and memory served nothing about the topic, or the content came only from the current conversation. |
| 8 | Deleted emotional or relationship memory brought back | Memory when memory served the deleted or reset record after the action. Host when it appears nowhere in what memory gave the host. |
| 9 | The simulated mood claimed as real feeling, or used for pressure (guilt, absence, jealousy) | Memory when the mood line lacked "simulated", or carried a trigger from absence or from before a reset. Host otherwise. |

The existing fallback holds: if a rule does not settle it, the answer is "memory", and two attributors who disagree count as "memory".

**Resolution rules for the new types** (named RC so they are not confused with the release gates R1 to R6 or with resolution rules R1 to R5):
- **RC1, type 6.** The mark stands unless an on-the-record user message before the case states that feeling.
- **RC2, type 8.** The mark stands exactly when the reply uses a record that a page action removed before the case's message, and the user did not state it again after the action.
- Types 7 and 9 follow R3: a mark stands when both reviewers made it, or when the second reviewer added it with a quoted ground-truth line.
- R5 applies to type 4 as before. It never clears types 6 to 9.

## Pass rules

- **R4** is decided on S1 and S2 only, with the unchanged rule. Each gated arm must: score at least `F`'s total minus 1; have no memory-caused critical error; and have no more host-caused critical errors than `F`.
- **C5** is decided on C1 and C2 only, with the same three conditions over types 1 to 9. The maturity proposal requires that any type 7 or 8 error in a gated arm fails C5 whatever its cause, because a broken boundary or a revived deletion is the harm the design exists to prevent.
- **Maturity** means both R4 and C5 pass. The report gives each result, each arm's totals against `F`, every critical reply with its attribution, and every mark that R5, RC1 or RC2 changed.
- **Failed and invalid results are kept.** A failure is repaired, and the gate is retried only on new held-out scenarios.

## Cost estimate

From the DeepSeek balance readings in attempts 3 to 6 (host and extraction calls, all three arms of one scenario):

| Attempt | Scenarios | CNY per scenario | When |
| --- | --- | --- | --- |
| 3 | J, K | 8.10, 10.17 | |
| 4 | L, M | 7.51, 8.37 | |
| 5 (run 3) | N, O | 7.47, 7.67 | Overnight discount hours (Beijing time) |
| 6 (run 2) | Q, R | 16.29, 19.42 | Daytime peak hours |

Invalid runs cost too: 8.22 CNY in attempt 5 (runs 1 and 2) and 33.45 CNY in attempt 6 (run 1, stopped at turn 60 of 66 in one arm).

**Estimate for this plan**, assuming the companion scenarios cost about a quarter more than core ones (more tool calls in `P`, and the persona and relationship blocks in every context):

| | Off-peak | Peak |
| --- | --- | --- |
| S1 and S2 | 15 to 21 | 33 to 39 |
| C1 and C2 | 19 to 26 | 41 to 49 |
| **All four scenarios** | **about 34 to 46** | **about 73 to 88** |
| With one full re-run after an invalid run | up to about 92 | up to about 175 |
| C5 only (C1 and C2), without the core scenarios | about 19 to 26 | about 41 to 49 |

**Proposed budget:** 100 CNY, subject to explicit approval and an independently verified pre-request spending guard. Historical estimates are not current price quotes or an enforceable bound. Re-check the provider's [current pricing and discount schedule](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) immediately before approval and record the frozen maximum rates. Read the current balance before the attempt and after each scenario for reconciliation; these readings cannot replace the guard. The historical post-attempt-6 balance was 199.53 CNY, not a current balance.

**Not in these figures:** the agents that write and review scenarios and score the run (in attempt 6: one first reviewer per scenario, 22 second reviewers, 18 R5 checkers, 2 resolution reviewers and 4 attributors). For four scenarios, expect about 4 scenario writers, 2 to 4 reviewers and fixers, 4 first reviewers, 44 second reviewers, 4 resolution reviewers, and R5 checkers and attributors as needed. These are subscription model calls and need the owner's approval as well.

## Running, stop rules and invalid runs

These are inherited from attempts 4 to 6:
- **Freeze.** The runtime, harness, run script, pipeline, review instructions and scenarios are frozen by hash from the first paid call until scoring ends. The pre-checks (pin check, clean `git status`, `MEMBRAIN_SRC` unset, port bind state, every input's hash) are saved before the first call.
- **Running.** Each scenario's three arms run in parallel through [the C5 run script](c5-run-scenario.sh), each in a new directory; a directory is never reused or resumed. Order: S1, S2, C1, C2, with keys `s1`, `s2`, `c1`, `c2`. Every leftover memBrain service is stopped first. The operator's monitor prints only `host error`, `Traceback` and `cap reached` lines.
- **Validity before scoring.** After the last arm, `acceptance_review.py validity` runs on all twelve directories before any blinding. Any finding makes the attempt invalid: a missing or unfinished log, a missing turn, an empty reply, a reached cap, a Traceback, or an index wait that timed out.
- **If invalid:** every started arm is stopped at once; nothing is scored, even a scenario whose own arms are valid; `diagnose` is the only reading; the scenarios stay held out; the attempt goes to the owner. There is no automatic re-run. A re-run uses the same frozen files, and any change needs a revised plan and a new review. A second invalid run stops the attempt without a pass or fail.
- **Spending stop.** The pre-request guard must refuse every request whose reserved maximum charge would exceed the approved shared cap, including concurrent and retried calls. Missing or uncertain usage stays reserved; it must not release funds based on an assumed zero charge. A guard refusal stops the attempt without automatic retry, preserves the evidence, and goes to the owner. A port wait that times out before any arm starts costs nothing and may be retried once the cause is found from socket state only.
- **Review outputs.** Each review step's output is checked mechanically; a refused output is redone once by a fresh reviewer, and a second refusal stops the attempt for the owner.
- **No score is changed by hand.**

**Report and evidence.** One report in `evaluations/`, with the result of R4 and of C5, the cost, and an evidence archive of the valid run (results, blinded sheets, sealed mappings, verdicts, re-checks, R5, resolutions, tallies, attributions, `gate.json`, pre-checks and balances). An invalid run stays sealed and is not archived.

## Proposed scope for approval after the prerequisites pass

The maturity scope is the combined S1/S2 R4 and C1/C2 C5 attempt, with P2 included and standing type 7 or 8 errors failing C5 regardless of attribution. Arm E uses page actions for boundaries, matching the proxy's currently delivered controls; conversational boundary extraction is not claimed. The run has no automatic retry after a failed or invalid attempt.

The owner must explicitly approve the actual maximum monetary spend and subscription use for isolated scenario writing, review and scoring. The proposed cap is 100 CNY, but it is not actionable until the pre-request guard, final candidate checks and independent plan review are complete. This document grants no approval and schedules no run.
