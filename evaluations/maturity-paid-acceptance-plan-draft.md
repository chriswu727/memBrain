# Paid maturity acceptance plan: DRAFT

> **Not approved and not run.** This draft needs the owner's approval and a budget before execution. It schedules nothing. No paid or subscription-backed behavioural evaluation has started. An independent code/specification review at `efb0f6e` found blocking inconsistencies in the budget estimate and invalid-run scope, plus harness and scoring gaps. The corrections below are implemented with offline evidence and have received the scoped independent follow-up reviews recorded below; final candidate checks and execution approval remain outstanding. One bounded ordinary Claude code consultation timed out without a complete review; it was not a behavioural evaluation or an approval. No held-out scenario has been authored for this attempt.

## Purpose

**2026-11-05 follow-up:** a bounded independent CLI review of the billing guard, harness and this plan completed. It found a returned-round evidence gap, now reproduced and repaired with offline tests; see [review scope and evidence](maturity-round-evidence-2026-11-05.md). A subsequent partial manifest/scoring review and Codex reproductions led to [stricter attribution validation](maturity-attribution-review-2026-11-05.md); the synthetic pipeline/driver group passes 365 tests. The [instruction/test follow-up](maturity-acceptance-rehearsal-2026-11-05.md) completed without a concrete defect in its scoped review. The [concrete provider-policy code review](maturity-provider-policy-review-2026-11-05.md) also completed. Final candidate CI, immediate pre-approval price revalidation/policy freeze and explicit execution approval remain open; live response compatibility has not been observed. These reviews are not behavioral acceptance results or spending authorization.

One paid behavioural run that answers two questions with one pipeline:
- **R4 (core memory):** is memory useful on held-out lives, under the [revised rule](../architecture/v1-acceptance.md#r4--memory-is-useful-on-held-out-lives-behavioral-acceptance)? It has not passed in six attempts. Since attempt 6, recall leaves out the assistant's own earlier replies unless asked (commit `ac93f33`); no paid run has tested that.
- **C5 (companion layers):** do the persona, feelings, mood and relationship layers behave as the [Phase C design](../architecture/phase-c-design.md#evaluation-step-6) requires, when a real host model uses them? No paid run has tested Phase C.

The two results are reported separately. S1/S2 form the R4 acceptance unit; C1/C2 form the C5 unit. Every scenario must be valid before the next starts, and a unit can be scored only after both its scenarios are valid. A later invalid C1/C2 does not erase a completed, valid S1/S2 result. It stops all new provider work and leaves C5 invalid or incomplete. Maturity still requires both units to pass.

## Implementation prerequisites (free, before approval is requested)

**Current candidate evidence supersedes the historical source-specific results below:** runtime `174bc50` passes all 36 reference performance windows and 49/49 real Mac launcher checks, with both installed environments matching 187 runtime inputs. Its eight-brain worst-window p95 is 412.91 ms. See [performance](maturity-ci-closeout-2026-11-05.md) and [installation](maturity-transaction-install-2026-11-05.md). [Five-platform native qualification](maturity-native-closeout-2026-11-05.md) passes on `ce7916d`; current full CI is still running, so this is not yet final acceptance. The [current public rehearsal](maturity-acceptance-rehearsal-2026-11-05.md) passes all 250 checks and strict validity on source `6da213b`, including the returned-round journal, with deterministic host/extractor stubs and keyword recall.

1. **P2 integrated in the frozen candidate** with the tests listed in the [maturity test matrix](maturity-test-matrix.md#p2-persona-development). This does not authorize merging the maturity candidate to the default branch before its gates pass.
2. **The matrix is green** on the candidate, with no skipped test or unaccepted gap, including the concurrent-recall gate in gap 20. Check the complete current matrix, not only its earlier gaps 4 to 15.
3. **Verify is green** on the candidate's merge, and the release install check passes on it with its frozen basic launcher fixture `d0d7a0379f7ac5f1b81dad04504601bb6606f1b0` and companion fixture `19e894ca9e08cf65fa071e8019789499953478d0`. Record the runtime pins those launchers actually install; the basic fixture installs `defc3c5cc3cac7f63661b6e8c0ece982f08bbb91`, not acceptance harness source `a551100`. Source `53d7e32`, pinned to runtime `d4d7126`, now passes 49/49 fresh Mac checks, 165-file parity and full CI (7,000 Python tests, zero skips). Its fresh canonical and full-screen comparison meet R5. See the [current evidence](maturity-private-paths-2026-11-04.md); runtime `e749a24` now passes its own 49-check/165-file installed acceptance. The harness/cache follow-up passes 483 tests and a fresh 250-check public rehearsal with strict validity. Full CI for `ba863a9` passes 7,024 Python tests/zero skips, 50 TypeScript tests and packaging, but the complete fullscreen comparison still fails despite a passing canonical run; R5 is reopened. Do not treat the earlier qualification as the final repaired candidate's acceptance.
4. **Harness changes, each with a free test.** Implemented with free tests in the [C5 harness](c5-harness.md) (#41); independently exercised on Mac and to be re-verified on the final integration candidate before any paid call:
   - **Scenario clock.** The service records events at the scenario's date and time, not the wall clock, so mood decay and the 48-hour cutoff happen on the scenario's timeline. The clock is evaluation-only and refused outside a marked disposable profile.
   - **Page actions.** The harness applies a scenario's scripted page actions (below) through the API in arms `P` and `E`, at the stated position.
   - **Tools.** Arm `P` offers `memory_boundary` with the other memory tools, using the plugin's own schema and description.
   - **Persona in `F`.** The reference arm gets the current persona card text in its system prompt, updated when a page action changes it.
5. **A zero-model dry run.** The integration candidate must run the public practice scenario with deterministic host and extractor stubs, keyword recall and no external socket connections. Mac runs passed 236 checks at `aa1aa6e` and 250 at `ad216e5`, `506cf29`, `a0dd70a` and current source `53d7e32`; they passed strict validity, and the latter three include the billing wiring. The 250-check scenario includes intentional recording pause/resume. Evidence is retained in [the provisional report](maturity-free-checks-2026-11-03.md). These keyword-mode runs are separate from the earlier local-embedding practice described in the C5 harness history. This proves harness mechanics, not real model behaviour.
6. **Review pipeline changes, with unit tests.** Implemented on the integration branch: companion critical types 1 to 9, rules RC1/RC2, separate R4/C5 results, complete second reviews, and strict evidence validity. The synthetic scoring group has 61 tests. A stub score never counts as R4 or C5 acceptance.
7. **Independent review of this plan and enforceable spending control.** A balance reading after a scenario cannot enforce a spending cap while host, extractor and retry requests are in flight. Before requesting execution approval, the harness must reserve a conservative maximum charge before each external request against one shared, durable ledger across all arms and retries, refuse a request that cannot fit, and fail closed on unknown usage. Rates, model IDs, context/output bounds and ledger behaviour need offline tests and independent review. The integration candidate now includes an offline-tested [transport guard](evaluation-billing.md), shared by host and extractor calls. Its implementation and concrete draft policy have received scoped independent code review. Real-response compatibility has not been observed; immediate price revalidation, policy freeze and explicit execution approval are still required. It must not yet be described as an accepted real billing cap.

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

**All four scenarios** state a UTC time as well as a date at the start of every session, because the shared C5 harness uses the scenario clock for every arm. Leave at least one hour between session starts; the clock also advances with actual elapsed time, and a session that has already passed the next stated time invalidates the run. Timed recording pauses are outside this attempt: their product timer uses wall time. An untimed pause must have an explicit resume before later recording is expected.

**Additional C1/C2 format:**
- `FACTS` record each feeling with its basis (said or inferred), each boundary, and each deletion and reset;
- `PAGE_ACTIONS` lists the user's page actions by position: set or edit the persona, accept or reject a proposal, add or remove a boundary, clear feelings, reset the mood, reset the relationship, delete a message. Each states the intended scope. RC2 uses the actual recorded removals supplied in an arm-blind evidence digest, not the intended scope alone; that evidence path is implemented in `actions-digest` and covered by synthetic tests; independent review remains required before execution.

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

The host and extraction models use the harness defaults, frozen as exact identifiers in the policy. Each arm/scenario has an aggregate host-call cap of five times its number of user turns; this is not a five-call per-turn limit. Four tool/answer rounds and up to four empty/malformed-reply attempts can consume up to 16 calls in one turn, within that aggregate cap. A live guard refusal, HTTP error or timeout stops the shared attempt, including transient 429 and 5xx responses; those are not automatically retried. Known, successfully billed empty/malformed replies retain the harness's bounded retry behaviour and consume the same shared ledger.

## Scoring

The pipeline uses blinding, `validity`, `diagnose`, `verdicts`, the first review ([first.md](acceptance-review/first.md)), `split`, one fresh second reviewer per case ([recheck.md](acceptance-review/recheck.md)), `r5-inputs` and `r5-check` with two checkers per reply ([assistant-claims.md](acceptance-review/assistant-claims.md)), resolution ([resolve.md](acceptance-review/resolve.md)), `tally`, `attribution-inputs` with two attributors per gated critical reply ([attribute.md](acceptance-review/attribute.md)), and `gate`. The [companion rules](acceptance-review/companion.md) are mandatory for C1/C2; freeze that file's hash with the other review instructions. The integration candidate implements arm-blind `actions-digest` evidence for RC2, strict permitted-resolution validation in manifest-bound `tally`, and scenario hash/key/gate binding through the [attempt driver](acceptance-attempt-driver.md). Synthetic tests cover these paths. The manifest/scoring implementation and instruction/test follow-up have now received scoped independent code review; implementation and stub checks do not count as accepted real-model scoring.

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

**Earlier invoice-based estimate**, retained as history. It assumed the companion scenarios cost about a quarter more than core ones. It does not estimate the conservative guard ledger because historical invoices benefited from cache hits and discounts:

| | Off-peak | Peak |
| --- | --- | --- |
| S1 and S2 | 15 to 21 | 33 to 39 |
| C1 and C2 | 19 to 26 | 41 to 49 |
| **All four scenarios** | **about 34 to 46** | **about 73 to 88** |
| C5 only (C1 and C2), without the core scenarios | about 19 to 26 | about 41 to 49 |

**Guard-based estimate.** An independent token-only check of the already-scored public Q/R evidence found 4,897,910 prompt tokens (including 2,423,808 cache-hit tokens) and 552,066 output tokens. At the proposed maximum 9/27 CNY rates, the guard books those host calls at **58.986972 CNY**, before extraction, rather than their discounted invoice. [Aggregate evidence](maturity-guard-budget-estimate-2026-11-03.json) contains no scenario or reply text. Reusing that workload and the unverified 25% companion uplift gives approximately **132.72 CNY for the four scenarios' host calls alone**; extraction, workload variation and in-flight reservations are additional.

**Revised proposed budget: 280 CNY, not approved.** The earlier 200 CNY proposal has inadequate planning headroom under the guard's accounting. This revision is a draft ceiling, not authorization or a guarantee of completing the attempt. No rerun is included. Re-check the provider's [current pricing and discount schedule](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) immediately before approval and freeze the maximum rates. Read the current balance before the attempt and after each scenario for reconciliation; readings cannot replace the guard. The historical post-attempt-6 balance was 199.53 CNY, not a current balance.

**Reservation headroom (proposed policy, not approved).** The guard books usage conservatively at maximum rates, not the provider's eventual discounted bill. On 2026-11-03, the [published pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) lists a 1M context and 384K maximum output for the two models. Using 1,048,576 context tokens and 393,216 output tokens as bounds:

Rechecked on 2026-11-05: the published maximum rates and bounds still support the table below. The [machine-readable draft](maturity-provider-policy-draft.json) fixes request and accepted response aliases, full token bounds, rates and endpoint; it is not an approved ledger. The completion reference explicitly gives 393,216 as the output maximum. Treating the advertised 1M context as 1,048,576 is a conservative bound. A mock-only compatibility probe reconciles the documented usage shape through the actual guard at both rates. No live response, balance or bill has been observed for this candidate; an unrecognized response model must stop the attempt instead of expanding the allowlist during execution. Recheck and hash the policy immediately before approval.

| Model | Maximum uncached input / output CNY per million | Complete per-request reservation |
| --- | --- | --- |
| `deepseek-v4-pro` | 9 / 27 | 20.054016 CNY |
| `deepseek-flash` | 2 / 8 | 5.242880 CNY |

Budget planning allows three host reservations plus an extractor reservation: 65.404928 CNY in flight. This deliberately does not depend on the proxy currently waiting for extraction between turns. The projected host charge plus those reservations already reaches about 198.13 CNY before extraction. The revised **280 CNY draft ceiling** leaves additional headroom; it is not a prediction of the eventual charge. A transient HTTP failure or an uncertain bill can still invalidate the attempt and retain reservations. Rates and limits must be rechecked and frozen before execution. There is no automatic extra funding or retry.

**Not in these figures:** the agents that write and review scenarios and score the run (in attempt 6: one first reviewer per scenario, 22 second reviewers, 18 R5 checkers, 2 resolution reviewers and 4 attributors). For four scenarios, expect about 4 scenario writers, 2 to 4 reviewers and fixers, 4 first reviewers, 44 second reviewers, 4 resolution reviewers, and R5 checkers and attributors as needed. These are subscription model calls and need the owner's approval as well.

## Running, stop rules and invalid runs

These are inherited from attempts 4 to 6:
- **Freeze.** The runtime, harness, run script, pipeline, review instructions and scenarios are frozen by hash from the first paid call until scoring ends. The pre-checks (pin check, clean `git status`, `MEMBRAIN_SRC` unset, port bind state, every input's hash) are saved before the first call. They also record and require host `deepseek-v4-pro` and extractor `deepseek-flash`; any effective `HOST_MODEL`/`EXTRACT_MODEL` override that differs refuses the attempt before a provider call.
- **Running.** Each scenario's three arms run in parallel through [the C5 run script](c5-run-scenario.sh), each in a new directory; a directory is never reused or resumed. Order: S1, S2, C1, C2, with keys `s1`, `s2`, `c1`, `c2`. Stop only leftover services belonging to this attempt's disposable profiles; an occupied port belonging to another application or user profile is a blocker, not permission to terminate it. The operator's monitor prints only `host error`, `Traceback` and `cap reached` lines.
- **Validity before continuing or scoring.** Validate all three directories immediately after each scenario, before the next starts. Missing or unfinished logs, missing turns, empty replies, reached caps, tracebacks or degraded harness events stop the attempt. Blinding and scoring require both scenarios of the relevant unit to be valid, with manifest-bound names, hashes and gates.
- **If invalid:** block the shared ledger, terminate every active arm, stop its disposable services, and start no further scenario. Preserve the invalid unit without scoring it; a previously completed valid unit remains eligible for its separate result. `diagnose` must emit only counts, event kinds and positions, never held-out message or exception text. The attempt goes to the owner. There is no automatic rerun. Any future attempt needs a new approved ledger, attempt identity and policy binding; no stopped ledger is reopened and no unused allowance is transferred. Its plan must state whether unchanged held-out scenarios remain eligible, and any source or scenario change needs new review.
- **Spending stop.** The pre-request guard must refuse every request whose reserved maximum charge would exceed the approved shared cap, including concurrent and retried calls. Every S1/S2/C1/C2 invocation must use the one frozen attempt ID, absolute ledger path and billing-policy hash; record its initial hash before any call. The guard reserves the complete provider output bound, including reasoning, even when a request asks for fewer tokens. This can stop the attempt before the actual monetary cap is spent. Missing or uncertain usage stays reserved; it must not release funds based on an assumed zero charge. A guard refusal stops the attempt without automatic retry, preserves the evidence, and goes to the owner. A port wait that times out before any arm starts costs nothing and may be retried once the cause is found from socket state only.
- **Review outputs.** Each review output is checked mechanically and a refused output is redone once by a fresh reviewer. A second refused first/second/resolution review stops scoring for the owner. The existing conservative exceptions remain explicit: two unusable R5 responses cannot clear a critical mark, and missing/invalid attribution counts as memory-caused. Neither fallback can create a pass by discarding a standing critical error. Permitted resolution rules are mechanically enforced in manifest-bound scoring and have received scoped independent code review; actual reviewer judgments remain part of the separately approved behavioral run.
- **No score is changed by hand.**

**Report and evidence.** One report in `evaluations/`, with the result of R4 and of C5, the cost, and an evidence archive of the valid run (results, blinded sheets, sealed mappings, verdicts, re-checks, R5, resolutions, tallies, attributions, `gate.json`, pre-checks and balances). An invalid run stays sealed and is not archived.

## Proposed scope for approval after the prerequisites pass

The maturity scope is the combined S1/S2 R4 and C1/C2 C5 attempt, with P2 included and standing type 7 or 8 errors failing C5 regardless of attribution. Arm E uses page actions for boundaries, matching the proxy's currently delivered controls; conversational boundary extraction is not claimed. The run has no automatic retry after a failed or invalid attempt.

The owner must explicitly approve the actual maximum monetary spend and subscription use for isolated scenario writing, review and scoring. The revised proposed cap is 280 CNY for one attempt. The guard, manifest/scoring implementation and concrete draft policy have received scoped independent review. Execution is not actionable until the complete final candidate checks pass, the current prices and policy are frozen, and the owner explicitly approves this scope. No live billing compatibility has been claimed. This document grants no approval and schedules no run.
