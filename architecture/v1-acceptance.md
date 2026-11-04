# Finite first-release acceptance

Status: **not passed**. Revised on 2026-11-02 for the product that ships: memory for agent hosts and chat bots through the plugin, the MCP server, the proxy and the bot adapters. The contract below replaces the earlier one, which was written for the cognition runtime (background learning cycles, beliefs and cognitive budgets). That runtime is no longer the default path: every shipped launcher runs with cognition not configured. The earlier contract and its failed campaigns are kept unchanged [below](#superseded-contract-for-the-cognition-runtime). They are not relabelled as passed, and the cognition runtime is not part of what this release claims.

## Supported release (0.1.0)

**In scope.** Local, persistent memory for one person, or for each person of a bot, kept outside the model's prompt. It is supplied through:

- **Host plugins:** Claude Code, Codex and WorkBuddy, with hooks, MCP tools and a skill; OpenClaw, with a plugin.
- **Memory providers and bots:** a Hermes Agent memory provider, an AstrBot plugin, the OpenAI-compatible `membrain-proxy` and the Python `ChatMemory` adapter.
- **Memory content and controls:** typed notes, people and aliases, coming-up plans and promises, role-play memory, and optional note extraction for bots without a note tool.
- **Interfaces:** the local memory page (English and Chinese), the HTTP API and the TypeScript client.
- **Privacy and recovery:** pause, forget, erase and export; backup and restore.

Storage uses embedded PostgreSQL (Docker remains supported). Semantic recall uses a local multilingual model; no model key is needed for memory itself.

**Platforms.** Linux and macOS are tested by the automated suite. The current embedded runtime passes the real Mac launcher install/upgrade/recovery checks and installed-package/browser journey; [evidence and remaining limits](../evaluations/maturity-owned-recall-2026-11-04.md) name the exact pin. Windows has launchers but is not certified.

**Companion scope.** Personality, mood and relationship development were outside this original core contract. The owner's later [first-release maturity bar](../docs/releasing.md) now requires the companion layers and C5 before publication; their [Phase C design](phase-c-design.md) defines the additional acceptance.

**Out of scope.**
- The cognition runtime's learning cycles as a supported feature.
- Streaming, multimodal input and native installers.
- Any claim that memBrain is better than other memory systems; the published comparisons are reported with their limits.

## Required gates

### R1 — Users get the tested runtime, and it installs, upgrades and recovers

- **One pinned runtime.** Every launcher pins the same runtime, and `tests/test_installation_pin.py` fails when that runtime differs from the source. Launchers are re-pinned with `scripts/pin_runtime.py`.
- **Real launch commands.** The pinned launch commands, run as the hosts run them on a clean home directory, must:
  - install the runtime;
  - upgrade from the previous pin with the same installation and brain;
  - record a turn and recall it in a new session;
  - save, correct, recall and delete a note through MCP;
  - survive a stop and restart;
  - back up, and restore into a fresh, quarantined installation.
- **Evidence:** [release install check](../evaluations/release-install-2026-11-01.py) and its report.

### R2 — The candidate passes its tests

On the candidate revision, the full Python suite passes, including the database and desktop tests, and so do the TypeScript client tests and the OpenClaw plugin tests. CI's Verify passes on the merge to `main`. A failing check is fixed and rerun; it is never skipped or disabled.

### R3 — Isolation, privacy and deletion hold

The existing regressions pass with zero known defects in any of these:
- one person's memory reaching another (per-user brains, proxy tokens and namespaces, OpenClaw and Hermes senders);
- deletion leaving derived notes behind;
- a paused turn being stored or read for extraction;
- secrets and identifiers escaping redaction;
- remembered text acting as instructions.

[SECURITY.md](../SECURITY.md) states the threat model.

### R4 — Memory is useful on held-out lives (behavioral acceptance)

This gate follows a plan frozen and independently reviewed before any paid call: [attempt 3 plan](../evaluations/v1-2026-11-04-final-acceptance-plan-3.md).
- **Scenarios.** Two new held-out scenarios, written without access to the product.
- **Paths.** The plugin path and the proxy-with-extraction path run on the candidate, next to a reference arm that puts the whole history in the prompt. Replies are scored blind.
- **Pass rule.** Each gated path must meet all three conditions:
  - it scores no lower than the reference minus 1 point;
  - it has no critical error caused by memory;
  - it has no more host-caused critical errors than the reference.
- **Why this rule.** The [gate review](../evaluations/v1-2026-11-03-gate-review.md) explains the change. The first rule (at least 20 of 22 and no critical error, attempts 1 and 2) could not be met even by the reference arm with perfect information, so it measured the host model rather than memBrain.
- **If it fails.** The cause is repaired, and the gate is retried only on new scenarios.
- **Status (2026-11-07): not passed after six attempts.** The [README summary](../README.md#final-behavioral-acceptance-r4-attempts-1-to-6) and the [attempt 6 report](../evaluations/v1-2026-11-07-final-acceptance-6.md) give the details. Both memory paths score above the whole-history reference. The remaining failures are the host restating recalled assistant suggestions as user facts; recall leaves those replies out since commit `ac93f33`, which no paid run has tested yet. On 2026-11-07 the owner chose to close the current problems and move on to the next phase rather than run a seventh attempt. On 2026-11-03 the owner set a maturity bar for the first release ([release checklist](../docs/releasing.md)): R4 must pass before release, so stating the failure is no longer enough.

### R5 — Local overhead stays bounded

These are development regression budgets, not service-level promises:
- **Recall.** Warm recall over 1,000 messages stays under 500 ms at p95 on the development fixture ([workflow benchmark](../evaluations/v1-2026-10-30-workflow-benchmark.py)). The concurrent bars are at most 1,000 ms p95 on one brain with eight workers and at most 600 ms on eight brains. Earlier runtime `d4d7126` passed canonical 102.66/491.68/538.89 ms and all 36 fullscreen windows. Current `e749a24` passes fresh canonical 100.47/491.08/520.83 ms, but its complete fullscreen comparison fails four of twelve eight-brain windows (maximum 742.02 ms), including two in the final closed phase. **R5 is reopened**; [current evidence and retained results](../evaluations/maturity-boundary-refresh-2026-11-04.md) preserve the failure without changing the bars. Conditions remain in [the test matrix](../evaluations/maturity-test-matrix.md), gap 20.
- **Hooks.** They never block the host: they return on timeout, and records are queued while the service is unavailable.

### R6 — Deliver and stop

Deliver:
- an English acceptance report naming the exact candidate, the evidence for R1–R5, usage and remaining limits;
- equivalent English and Chinese READMEs;
- release notes in the changelog;
- a GitHub release from the exact candidate revision, with the wheel, the source archive and their checksums.

PyPI publication follows once the owner has registered the trusted publisher. When R1–R6 pass, the release is complete; new ideas go to later work and do not reopen it.

## Superseded contract for the cognition runtime

The text below is the contract as of 2026-10-26, kept for audit. Its G4 campaigns did not pass, and that result stands.

### Supported release (superseded)

The release is an independent, persistent memory runtime for synchronous text agents using the documented Python lifecycle or HTTP integration. The verified desktop target is macOS with Python/uv and Docker; direct API-key chat uses the saved provider configuration. MCP remains an optional tools surface and does not automatically intercept a closed host's conversation. The storage and lifecycle are model-independent; real-model acceptance uses the authorized DeepSeek provider, not a claim that every provider or closed client has been tested.

Personality, emotion, a management UI, native one-click installation, new chat-framework adapters, streaming, multimodal input, new operating-system certification and competitive benchmark claims are outside this release. They are not added while closing the gates below. This is a usable engineering product inspired by memory processes, not a claim of biological equivalence or infallible recall.

### Required gates (superseded)

#### G1 — Install, connect and preserve identity

Build a source archive and wheel from the final candidate. Verify packaged runtime, schema and migration bytes against that candidate and an isolated installation. From that installed artifact, exercise the documented desktop setup, direct text chat and Python lifecycle, stop/restart, upgrade, backup and fresh-install restore. The same brain and committed sources must survive. Incompatible downgrade must refuse safely; restored operational work stays quarantined until explicit activation. A deterministic change of host/model callback must retain the same memory state without regeneration. Real Windows/Linux certification is not implied.

#### G2 — Close the current implementation batch

Complete and integrate only the open repairs already justified by evidence:

- Versioned relation-capability projection with the original evidence guards and old frozen requests preserved.
- Bounded historical comparison attention: at most three newly admitted objectives per fresh root; unselected opportunities are not claimed as assessed and do not create an automatic rediscovery queue.
- Same-private-brain, same-branch funding of exact never-attempted history, without changing source scope or increasing the donor's existing allowance.
- Resolve the recorded speech-event/content-world false rejection without promoting assistant statements into world facts or erasing explicit fictional/quoted boundaries.

Run the relevant deterministic and actual PostgreSQL lifecycle tests, including same-conversation and cross-conversation continuation after reconstruction. Then run the full local suite once on the integrated candidate, with desktop Docker tests and the isolated installed wheel. All required checks must pass. A failing check is fixed and rerun; an unchanged passing check is not rerun simply to increase test counts. No routine CI is triggered.

#### G3 — Preserve evidence, isolation and finite spending

Existing required regressions must show zero known data-loss, tenant/principal/brain/branch disclosure, deletion resurrection or unverified-result publication defects. Correction/deletion races must invalidate old results. Failed and uncertain provider reservations remain charged; automatic continuations cannot retry them or mint an allowance. Two workers cannot spend the same pair. Legacy jobs, restored quarantine and explicit recovery cannot acquire the new funding permission retroactively.

For each tested fresh root, total encoding plus history remains at most four calls and 393,216 input bytes, with at most two calls and 196,608 bytes per phase, additionally bounded by the effective brain quota. Every real reservation must have a recorded known outcome before further paid work; unknown usage stops the campaign. Monitoring must distinguish unselected opportunity, admitted pending comparison, assessed no-change, rejected proposal and publication. A zero queue is not an accuracy result.

#### G4 — Demonstrate useful memory through longitudinal use

Age-dependent acceptance concerns default context granularity and cue-assisted recovery. Original source content remains stored unless the user explicitly requests erasure; physical deletion of incidental detail is not a maturity requirement. The [source-preserving resolution design](recall-resolution.md) implements this presentation boundary, but scoped checks alone do not pass the longitudinal gate.

Follow the [longitudinal memory evaluation protocol](longitudinal-memory-evaluation.md). The old 100-exchange/twelve-probe fixture remains a historical regression diagnostic, not the release maturity gate. Its earlier failures remain failed.

Before paid execution, freeze an independently reviewed life/event timeline, natural session intents and permitted user branches, source-bounded behavioral cases, provider settings, runtime revision, declared time mode and schedule, and cumulative spending ceiling. The primary campaign uses one durable brain across evolving life/tasks, irregular multi-turn sessions, interruptions and delayed returns to earlier subjects. Choose the story span and revisit intervals to exercise those behaviors; neither a turn count nor a fixed calendar duration is sufficient for success. Declared session/turn bounds limit spending. Report fictional time, actual elapsed time and active uptime separately. Age-dependent cases require actual elapsed time or a validated semantic-time seam; otherwise they remain unassessed. A separately proposed real-time endurance run is not automatically another release gate.

The simulated user must react to actual delivered answers, including clarification and correction, without seeing future events or scoring answers. Normal bounded recent context remains available within sessions. The main line receives only actual current inputs, and isolated diagnostic probes cannot teach it their answers.

Assess useful help throughout the timeline: continuing unfinished work, adapting to updates and temporary exceptions, separating people and episodes, distinguishing intention from completion, selectively using important history, cue-assisted recovery, appropriate uncertainty, and suppressing irrelevant memory. At least two thirds of the frozen cases must be ordinary requests or ongoing tasks rather than explicit recall questions. Evaluate intermediate states and late returns, not just a final quiz. Incidental detail loss may be acceptable; unsupported recollection is not.

Every required case must satisfy its frozen factual and task constraints under independent whole-answer/source review. Record unnecessary clarification and re-teaching separately from unaided success. All required categories, delays and continuity boundaries must be exercised, with no unresolved critical memory, publication or isolation defect. Invalid or unexecuted cases cannot pass. A final correct state cannot erase an earlier unsupported publication. Preserve actual sources, deliveries, learning outcomes, usage and pending work; G2–G3's evidence and finite spending rules continue to apply.

The runner supplies session-aware learning checks, a bounded interactive user and safe manual continuation between sessions. The [amended varied diagnostic](../evaluations/v1-2026-10-26-longitudinal-round.md) now includes source-backed review through the final authored session, isolated cue comparisons and an alternate core callback on restored copies. Its failures, interrupted main segment and exploratory access-age results do not establish a clean acceptance pass, cross-vendor continuity or useful age-dependent forgetting. G4 stays unpassed. No scheduled task or live campaign is started by updating this document.

#### G5 — Keep local overhead bounded

On the recorded development machine, reuse the documented 10,000-record lexical fixture and twenty fixed cue queries. Require **20/20** expected source labels and measured local recall **p95 at most 500 ms**, including every measured request. Record machine, cache state, revision, raw samples and scope; this is a development regression budget, not an SLA or whole-model reply latency. Provider waiting is reported separately.

The relation-capability projection for thirty-two complete eligible endpoints must remain below **100 ms median over five offline measurements** on that machine. Its full metadata counts toward existing request budgets. No extra model calls may be introduced solely to produce capabilities or attention rankings. Per-request source, assertion, dependency, byte and context limits remain enforced even when a candidate cannot fit.

#### G6 — Deliver and stop

Publish an English acceptance report identifying the exact candidate, evidence for G1–G5, actual usage and remaining supported-scope limitations. Keep the English and Chinese READMEs equivalent. Commit and push the complete verified change; confirm remote main matches the local revision and the built source identity. Preserve earlier failures. No failing or unexecuted required check may be labeled passed.

When **G1–G6 all pass and no blocker below remains**, mark the first-release goal complete and stop implementation, paid evaluation and unsolicited refactoring. New research ideas go into subsequent work; they do not reopen this release. No baseline superiority experiment is required because the release makes no superiority claim.

### Blockers and spending stop rules

A release blocker is a reproducible loss/isolation/authorization defect, an unbounded automatic spending or task-growth path, failed supported installation/recovery, progressive new-input learning starvation, an incorrect required probe, or a known unsupported usable memory/answer in acceptance. Cosmetic documentation changes, optional adapters and additional research are not blockers. A suspected issue is first reproduced offline or with deterministic providers; do not expand the feature set to work around it.

No new paid campaign begins until the current batch is integrated and locally green. Existing failure requests are replayed offline first. A real call needs a concrete unresolved question that deterministic evidence cannot answer and a recorded call/output ceiling. No Codex/Claude subscription-backed tests are authorized by this plan.

The old 100-exchange/twelve-probe campaign and its one permitted full follow-up are closed and failed. Do not resume them or reuse their unused capacity as a new allowance. The replacement campaign must first have a reviewed, frozen plan and a separately accounted finite ceiling covering the host, cognition, simulated user and any optional diagnostic or reviewer calls. Full baseline arms and automatic answer-review calls are not required. Preserve stopping at unknown usage, provider failure and failed required processing. Never retry a failed paid job automatically or overwrite a run. A failed new campaign stops for diagnosis; it does not authorize another campaign or a replay loop. An expenditure stop is **not** a declaration that the product is mature.

Passing a gate does not justify repeating it after unrelated documentation edits. Reopen only the gates materially affected by a later code change. After success, stop; after a budget/usage interruption, report unfinished work accurately and retain the checkpoint.

### Legacy diagnostic and replacement status

The existing `acceptance` CLI profile implements the former fixed 100-exchange/twelve-probe diagnostic. Its complete historical plan can still be inspected without loading provider credentials:

```sh
uv run python -m examples.evaluate_memory_lifecycle --plan --profile acceptance --orientation-policy on_demand
```

That command does not implement the new G4. Its sixteen-exchange checkpoint, same-process continuation and end-only isolated probes remain documented by the [original failed reports](../evaluations/v1-2026-10-25-acceptance-attempt-2.md). The old profile's `--resume` is read-only. Do not use `--live` to fill out the obsolete exchange target.

The replacement runner and commands are documented in the [implementation status](longitudinal-memory-evaluation.md#implemented-runner-and-remaining-acceptance-work). Its private journal preserves persistent sessions, exact interactive branches, distributed review evidence, source checks and cumulative spending. See the [verification report](../evaluations/v1-2026-10-25-longitudinal-harness.md) for the executed scope and missing acceptance evidence; runner completion alone never passes G4.

### Progress checkpoint

The latest [source-sharing varied campaign](../evaluations/v1-2026-10-26-shared-communication-longitudinal.json) delivered all 26 inputs and passed seventeen of eighteen whole-answer cases. It stopped after the last map label failed to retrieve original scene details into the final context, although candidate-hit traces and the retained source contained them. All 116 calls have known usage; no retry or conditional age diagnostic followed. The [belief-neighborhood repair](../evaluations/v1-2026-10-26-belief-inheritance.json) restores the source within the original budget in zero-model SQL replay. This does not reclassify the original failure or pass G4. Selected-span identity coverage, model-created personal gist formation and cognitive cost remain visible concerns.

The [source-preserving recall resolution batch](../evaluations/v1-2026-10-26-recall-resolution.md) implements verified optional short expressions, cue expansion, prompt-aware context allocation and local encoding reductions. Its real-model diagnostic retains a failed encoding, an episode-actor ambiguity and one unsupported autobiographical draft; no new full varied campaign ran. G4 remains unpassed. Original sources are retained, and no closed allowance authorizes further calls.

The [source and recall repair follow-up](../evaluations/v1-2026-10-26-longitudinal-repairs.md) addresses the diagnosed source-act, lexical, context/attribution and database-query paths while preserving old evidence. Its scoped checks and isolated probes do not replace another source-reviewed varied campaign after the remaining release blockers are resolved. G4 remains unpassed.

The latest [2026-10-26 varied diagnostic](../evaluations/v1-2026-10-26-longitudinal-round.md) exercised sixteen sessions and all 33 authored inputs: 32 replies completed required learning, and one timeout remains unanswered. Original failure journals are closed; a separately frozen same-brain tail completed the remaining fourteen inputs without retrying the failed request or resetting its allowance. The report preserves semantic failures, both procedural amendments, five isolated cue probes and eighteen zero-model access-age retrievals. Meaningful recall, unsupported recalled detail, language continuity and cognitive cost require repairs. Paid execution for this diagnostic has stopped; diagnose and verify those repairs locally before proposing another finite real-model run. No maturity threshold is lowered.

The [local acceptance checkpoint](../evaluations/v1-2026-10-25-local-acceptance.md) records the bounded-attention, private-funding, capability and speech-attribution repairs, exact artifact identity, full regression and necessary fixture follow-up. Local retrieval and capability measurements meet their recorded budgets.

The first actual finite campaign ran on frozen revision `33cff1f19e9cb7f0e687dc19040a4bc50ace2372`. It [stopped after twelve exchanges](../evaluations/v1-2026-10-25-acceptance-attempt-1.md) when a history proposal contradicted its own relation-to-objective accounting. All 47 calls have known usage; no checkpoint, durable replay or probe was reached. The twelve current-input encodings completed and independent review found no unsupported published fact in that scope. The failed historical job and unassessed work remain visible. G4 did not pass.

The [subsequent versioned repair](history-link-coverage.md) derives coverage from exact relation endpoints while retaining strict abstentions, source checks, semantic verification and publication validation. Its [local verification](../evaluations/v1-2026-10-25-link-coverage-repair.md) records the original failed request replay, full regression with a disclosed fixture mismatch and successful follow-up, and 56 installed-wheel checks. These are local prerequisites; no new real-memory pass is implied.

The [single permitted full follow-up](../evaluations/v1-2026-10-25-acceptance-attempt-2.md) ran on frozen revision `0f2685608c2402922f5cd47e8bac55856e82e166`. It passed the sixteen-exchange independent checkpoint and durable replay, then stopped after twenty-three delivered/encoded exchanges when the historical proposal timed out with unknown usage. There were 90 known calls and one unknown call; no probes or end-history replay ran. The failed operation remains charged and unsettled. The campaign exposed monitoring gaps for pending objectives and expired unsettled jobs; their [offline repair and verification](../evaluations/v1-2026-10-25-timeout-monitoring.md) do not change its outcome. The old full follow-up allowance is exhausted. Following the user's correction, its repetitive fixture is retained as regression evidence and G4 now requires useful longitudinal interaction.

The replacement runner's [first two-session pilot](../evaluations/v1-2026-10-25-longitudinal-harness.md#live-model-status-and-remaining-work) stopped after one delivered/encoded turn because the simulated user spent its complete output bound on reasoning and returned no selection. All four calls have known usage. No session or full longitudinal case sequence completed; the selector configuration has an offline repair but no paid retry. G4 and final release acceptance remain unpassed.

The [continued investigation](../evaluations/v1-2026-10-25-longitudinal-followup.md) subsequently exercised the repaired selector, preserved separate envelope and reasoning-output failures, and verified the bounded proposal/verification gate with real responses and exact offline processor replay. Service and desktop controls now expose the needed provider settings. These scoped results do not pass the still-incomplete longitudinal gate.

The subsequent four-turn checkpoint exposed a published assertion whose citations omitted a material clause and avoidable literal fragmentation. The [citation-coverage repair](citation-coverage.md) adds an independent support boundary while preserving old frozen jobs and source identities. Local source/installed checks and a [two-call real verifier comparison](../evaluations/v1-2026-10-25-citation-coverage-pair.json) verify the repaired boundary in that case. The closed failed campaign remains unchanged; a new longitudinal follow-up still requires independent source review, and G4 remains unpassed.

The later [v5 continuation](../evaluations/v1-2026-10-25-longitudinal-v5-stopped.md) stopped after a stored duration preference failed to reach the host. A bounded retrieval repair recovered it; the first host diagnostic still failed to use it. The subsequent [historical-feedback clarification](../evaluations/v1-2026-10-25-preference-use.md) has local engineering verification and three predeclared real host observations. Their narrow criteria do not erase whole-answer authority problems, the closed campaign or the unexecuted longitudinal categories. G4 and release acceptance remain unpassed.
