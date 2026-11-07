# Proposed fourth maturity acceptance attempt

**Subsequently approved:** the owner authorized this one round on November 7, 2026. See the [execution binding](maturity-acceptance-execution-2026-11-07.md). The proposal as submitted is retained below; its pending-approval statements are historical.

**Awaiting explicit execution approval.** This proposal requests one new R4/C5 attempt with new hidden scenarios, a shared **280 CNY DeepSeek ceiling**, and Codex subscription use for isolated authorship, independent scenario review, blind scoring and one final independent release/source review. No scenarios, live ledger or provider calls have been created for this proposal. It does not authorize a repeat, account top-up, main merge, tag or release.

The [reviewed acceptance plan](maturity-paid-acceptance-plan-draft.md) supplies the unchanged protocol, instructions, scoring rules, isolation and stop conditions. This document replaces its historical candidate and approval-status statements for this proposed attempt only. Earlier attempts remain closed; their approval cannot fund or authorize this one.

## Frozen candidate and free prerequisites

| Input | Identity |
| --- | --- |
| Proposed attempt | `maturity-20261107` |
| Fully qualified integration source | `ee564c5d75fcee5db0f8d6eee73e0e41a49e0ff1` |
| Preparation source | `25cfbcce0256fc8520c6d6186be119e52517a9de` (only documentation/evidence changes after qualified source) |
| All nine launcher runtime pins | `4115e90c24eb1eb09857624a01db8bd3b22bfe50` |
| Build | `09051895b947ff192b1c277af3ca5fc2f5ac7f3d3021be66cb751201cf8f57b8` |
| Schema | `478061ac77337fd25d87174df1185ab1d40ad4d4216290078fb26fd2f519fe39` |
| Reviewed provider policy SHA-256 | `23030242604ab3e3bfbf234b4e434fe13b76d6612de61f36d460ba3305afffe2` |

[Integrated qualification](maturity-ui-code-atomicity-2026-11-07.md) is complete: Verify run `42380382170` passed 7,838 Python and 53 TypeScript tests, zero skips, Ruff, strict types and both builds. Native run `42380381989` passed all five platforms, with 47 unique stage summaries audited. Three Python fork warnings remain recorded. The source branch's earlier 45-minute Verify cancellation and two deliberately cancelled redundant documentation-triggered runs remain in the evidence; they are not passes. New documentation-only commits do not claim fresh head CI.

Current-runtime fresh installation and public rehearsal results are recorded in [free preparation](maturity-acceptance-preparation-2026-11-07.md). That report must be complete before requesting approval. Historical performance and installed results keep their original source/workload scope; they are not renamed as new measurements. The UI-code-only runtime change leaves recall, schema, native and visualization runtime inputs unchanged from the preceding qualification.

Before the first paid completion, save the exact execution commit and clean working-tree state; freeze runtime, launchers, harness, supervisor, scoring pipeline, review instructions, policy, this proposal, the approved execution binding and all final scenario hashes. Verify the execution tree differs from the qualified tree only in documentation/evidence. A changed runtime, provider policy, scoring rule or missing prerequisite stops execution for review before spending; it cannot be silently substituted into this proposal.

## Work requested

1. Prepare four entirely new, isolated scenarios: S1/S2 for core memory and C1/C2 for companion behavior. Each has eleven cases and approximately 60–66 user turns. Each pair includes a mainly English life with another-language session and a mainly Chinese life with an English session. Authors receive the existing behavioral brief and format, without implementation details, prior hidden content or results. Independent reviewers and separate fixers complete the established structural/date checks before hashes are frozen. The developer sees only permitted counts, prefixes, hashes and content-free status.
2. Execute S1, S2, C1, C2 in that order, each with plugin (`P`), extraction (`E`) and full-history reference (`F`) arms in fresh directories. C1/C2 cover stated versus inferred feelings, simulated mood changes/recovery, boundaries, deletion/reset persistence, persona stability and accepted growth proposals, and return after an absence without emotional pressure. E's boundaries come from page actions; conversational boundary extraction is not claimed. The unchanged scenario-clock and pause/resume restrictions apply.
3. Run strict validity after each scenario. S1/S2 must both be valid before R4 scoring; C1/C2 must both be valid before C5 scoring. Use the existing blind pipeline: first reviews, 44 independent case rechecks, conditional R5 checks, resolutions and critical-error attribution. Refused review outputs follow the existing single replacement-review limit and conservative fallbacks; no score is edited by hand. A valid R4 result survives a later invalid C5 unit, but maturity requires both to pass.
4. Complete one independent source/release review against the frozen candidate and gate evidence. Report its findings and unresolved release blockers. Fixes discovered after evaluation require their own appropriate validation and assessment of whether a new behavioral attempt is necessary; this proposal does not authorize another paid attempt.

Passing means each gated arm scores at least the reference total minus one, has no memory-caused critical error and no more host-caused critical errors than the reference. For C5, any standing type 7 boundary violation or type 8 revived deletion/reset fails regardless of attribution. Public stubs and unit tests cannot establish these outcomes or human-like emotional capability.

## Spending and stop conditions

DeepSeek's [pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) and [completion limits](https://api-docs.deepseek.com/api/create-chat-completion/) were rechecked on November 7, 2026. Maximum uncached input/output rates remain 9/27 CNY per million for `deepseek-v4-pro` and 2/8 for `deepseek-flash`. Published context is 1M and output is 384K; the completion reference explicitly permits 393,216 output tokens. The unchanged policy conservatively reserves 1,048,576 context and 393,216 output tokens. Full request reservations are 20.054016 CNY for Pro and 5.242880 for Flash; three host reservations plus one extractor need 65.404928 CNY of headroom. These are guard reservations, not predicted invoices.

Revalidate prices immediately before execution. The exact endpoint and request/response alias allowlists remain unchanged. This proposal covers chat completions only, not Search, Fetch or additional provider services. No live response compatibility, current account balance or eventual invoice is asserted by this preparation.

After approval only, create a fresh private root and ledger under `/Users/yichen/tmp/membrain-acceptance-20261107/`, with attempt ID `maturity-20261107`, absolute ledger path and frozen policy binding. Every request, including permitted malformed-reply retries, reserves its conservative maximum against the same 280 CNY ledger before transmission. There is no top-up or automatic repeat. Account balance observations are reconciliation evidence, not spending authority or a guarantee that all scenarios will finish.

A guard refusal, unknown usage, provider/transport error, invalid evidence or degraded harness stops all new work, blocks the ledger, terminates this attempt's arms and stops only its disposable services. Preserve all evidence. Known, successfully billed malformed responses retain only the existing bounded retries; HTTP 429/5xx/timeouts are not automatically retried. An unknown charge remains reserved. Old ledgers stay blocked and unchanged: the previous attempt's 20.054016 CNY unknown reservation is neither released nor transferred by a new approval.

The [previous attempt](maturity-third-attempt-2026-11-06.md) remains R4 failed (plugin 17.5 against required 18, two memory-critical and one host-critical errors), with C5 incomplete. Its 48.080210 CNY settled usage and 20.054016 CNY held reservation remain historical figures, not this attempt's budget or current balance. New source fixes and public checks do not erase that result.

## Decision requested after free preparation

Authorize exactly this one complete attempt, including new isolated scenario authors/reviewers and blind scoring through the Codex subscription, the shared DeepSeek ceiling of 280 CNY, and one independent final release/source review. No automatic extra attempt or account recharge is included. Both behavioral gates and final release review remain required before any main merge, tag or publication.
