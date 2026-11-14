# DRAFT — Approved sixth maturity acceptance attempt (R4 only)

> **DRAFT. Not an approval and not a binding.** Every `<…>` is a placeholder to fill before freezing. The final
> binding is committed as `evaluations/maturity-acceptance-execution-<date>.md` with every placeholder filled and
> every hash real, **before** `freeze.py` runs (the manifest freezes it). After freezing, any change is
> documentation only and must not alter scope, rules, arms, ceiling or inputs. Nothing in this draft authorizes a
> model call; the owner's approval of the paid run is recorded separately.

On <date> (America/Vancouver), the owner approved one new R4 attempt with the plugin path and the full-history
reference only: “<owner's words, original language>” (“<English translation>”). This authorizes exactly one attempt, an
**80 CNY DeepSeek ceiling on the guard's conservative count**, and subscription use for isolated scenario authorship,
independent scenario review, blind scoring and one independent source/freeze/final review, by sessions that are
never the provider's largest model (`<author/reviewer tool>`, models `<listed in control/allowed-models.json>`). There
is no recharge, no automatic additional attempt and no C5 unit in this attempt; C5 remains invalid and unscored.

## Scope decisions (taken by the lead under the owner's delegation)

1. **R4 is judged on the plugin path alone.** Arms: `P` (plugin path) and `F` (full-history reference); gated arm:
   `P`. The proxy path is not part of acceptance. Hosts whose model cannot call tools get recording and recall but
   no notes and are not covered by the gate. The rule text: `architecture/v1-acceptance.md`, R4 "Paths", amended at
   `<commit>` before this attempt; the R4 item of `docs/releasing.md` says the same.
2. **One fixed persona in both arms.** The companion layer is always on, so the run carries a persona: the
   personality type `<TYPE>` = `acceptance_persona.draw("<attempt id>")` = `IDS[int(sha256(attempt id), 16) % 16]`
   over `membrain.persona_presets.IDS`, recorded in the manifest's `persona` entry. The harness saves it in `P`
   before the first session (made by the host, action "preset"), so the product's random first type and its
   one-time announcement never occur; `F` receives the same product-rendered `<membrain-persona>` block. Nobody
   chose the type.
3. **Host model.** `deepseek-v4-pro` through the harness's emulation of the plugin hooks and MCP tools, as in
   attempts 1–5. **It is not Claude Code**: no hook subprocess, no stdio MCP, no Claude Code system prompt; the
   result says how memBrain's plugin path works with this model under this emulation, not how Claude Code behaves.
4. **One arm at a time.** For each scenario `P` runs, its installation is stopped and its ports checked closed,
   then `F` runs; only one host request is ever open against the ledger.
5. **Ceiling.** 80 CNY on the guard's conservative count, one model in the policy.
6. **A turn left unrecorded because the host did not resume recording stops the attempt as invalid**, as before.
   No resume call is inserted on the host's behalf.
7. **Scenario authors and reviewers** are isolated sessions started by `evaluations/acceptance-kit/launch.py` in
   directories outside every checkout, with only their brief; only hashes and counts reach the lead.

## Identities

Attempt `<id>` (named "the sixth maturity attempt", never "attempt 6", which names
`v1-2026-11-07-final-acceptance-6.md`) uses the new execution clone `<X>` (Linux x86_64, WSL2) at commit
`<frozen commit>`, from integration commit `<integration commit>`. All nine launchers pin runtime `<runtime>` (pin
`<pin commit>`), build `<build>`, schema `<schema>`. Qualification on this commit: <full local suite: N passed, M
skipped>, <installed-package check>, <public stub rehearsal `r4-stub-rehearsal.py`: dry-run checks N/N, strict
validity, gate computed, zero network events, ledger unchanged, ports closed>. These checks are not real-model
acceptance.

## What governs the run

The [reviewed acceptance plan](maturity-paid-acceptance-plan-draft.md) governs isolation, review, scoring and stopping,
except where this binding says otherwise. Where that plan names arm `E`, its extraction model, three
parallel host reservations plus an extractor reservation, or "each gated arm" including `E`, this binding supersedes
it: two arms, no extractor, one model, sequential arms, gated arm `P`.

- **Arms.** `P` and `F`, each in a fresh directory, run one after the other per scenario (`c5-run-scenario.sh`).
  `P` drives the plugin's own hook functions (`membrain.plugin.session_start`, `user_prompt`, `stop`, Claude Code's
  tool names), offers every tool the plugin's MCP server lists with its own schemas (`<tool list from tools.json>`),
  keeps one tool server per session, and receives what an MCP host gives its model without the model choosing to
  open anything: the server's instructions, the session context and the per-message context. It does **not**
  receive the skill body, which a host loads only when its model opens the skill (never in the 86 turns of the
  2026-11-13 trial). One difference from Claude Code remains: Claude Code can defer tool descriptions until the
  model looks a tool up, while `P` gets every description up front. `F` receives the whole earlier history and the
  same persona block. Blinding uses labels A and B (`v1-2026-10-29-phase-b-blind.py … PF`).
- **Scenario persona.** A scenario `PERSONA` card is refused by the harness in a live run and whenever the driver
  passes the manifest's draw; validity (given the draw by the driver) requires every arm's `persona.json` to record
  `source: "seeded"` and the manifest's type.
- **Changed evaluation code** (reviewed in `<review record>`, frozen below): two-arm harness, run script, driver and
  validity; review pipeline with frozen `ARMS = ("P", "F")` and `GATED = ("P",)`; `first.md`, `recheck.md` and
  `companion.md` worded for two replies; the persona draw; post-arm cleanup; R4 precheck mode; the stub host's
  consolidation; the rehearsal; the scenario kit. Criteria, rubric, critical types 1–5, resolution rules R1–R5,
  attribution rules and the pass rule are unchanged.
- **Pass rule (unchanged, as coded in `acceptance_review.py gate`).** Over S1 and S2: `P`'s total ≥ `F`'s total − 1;
  no `P` reply with a standing critical error attributed to memory (anything but two "host" answers is memory); the
  number of `P` replies with a host-caused critical error ≤ the number of `F` replies with a standing critical error.
  `R4 = P passes`. A tally or sealed mapping that does not hold exactly `P` and `F` is refused.

## Differences from attempt 5 that affect comparability

| Change | Attempt 5 | This attempt | Effect on comparison |
| --- | --- | --- | --- |
| Arms | `P`, `E`, `F` in parallel | `P`, then `F` | `E` results have no successor; parallel versus sequential does not change any arm's inputs |
| Gate | `P` and `E` both had to pass | `P` alone | An R4 pass here is a pass of the plugin path only |
| Persona | none in either arm | type `<TYPE>` in both | Every prompt ≈ 250 tokens longer; tone and length of replies may change in both arms alike |
| Tools offered to `P` | 5 (recall, note, boundary, pause, resume; ≈ 7.7k characters of schemas at today's sizes) | all 14 the server lists (16,989 characters of schemas) | New behaviours (consolidation, manner feedback, persona, forget, the low-level tools) can occur |
| Skill text in `P`'s prompt | the whole skill body (≈ 10.4k characters at runtime `7902c16e`) in every call | none (the skill is 16,593 characters now and a host loads it only on demand) | Guidance attempts 1–5 gave the host in every call is gone; what remains is the server's instructions and the notices |
| Server instructions | not given | in `P`'s system prompt (1,332 characters) | Instructions the shipped product relies on now reach the host |
| Net standing prompt of `P` | skill + 5 schemas | instructions + 14 schemas + persona block | About +0.5k characters per call besides the persona block |
| Hook path | `membrain.host.*` with default tool names | `membrain.plugin.*` with Claude Code's names | Notice wording as Claude Code's plugin gets it |
| MCP server | new per turn | one per session | A consolidation batch survives between its two calls |
| Consolidation | never requested (tool not offered) | requested when ≥ 5 messages wait; up to two tool calls in a turn | Cue writing now affects recall in `P`; more `P` host rounds |
| Runtime | `7902c16e` | `<runtime>` (no extraction model, host consolidation, first-persona logic, local dates) | Product changes since attempt 5 |
| Scenarios | S1/S2 of attempt 5 (now public) | new held-out S1/S2 from a rewritten brief | Briefs rewritten from the public plans; their text differs from attempt 5's (hashes `7b8d8ee1…`, `0e847ff0…`), which was never recovered |
| Review instructions | three replies | two replies; same criteria and rubric; `recheck.md` now also says to ignore wording about tools or memory, as `first.md` always did | A reviewer compares two replies instead of three |
| Blinding | three replies per case | two replies per case | **Partial blinding (limitation).** Any visible sign of memory use in one reply ("Saved.", "Memory's updated.", a repeated answer after consolidation) identifies both replies of that case. Reviewers are told to ignore such wording; `acceptance_review.py remarks` counts, per arm, the case replies and all replies containing a phrase from a fixed list (`MEMORY_REMARKS`), and the record states those counts and shares |
| Ceiling | 280 CNY, two models | 80 CNY, one model | Reservation headroom: refusal once settled charges exceed 59.95 CNY |

Unchanged: host model and call shape (`thinking` enabled, `max_tokens` 16,384, at most 4 rounds, tools in the first
3, at most 6 tool calls, up to 4 attempts for an empty reply, cap 5 × user turns), the billing guard, validity's
rules (plus: arms, persona agreement and no overlap), the scoring pipeline's rules, and the scenario format.

## Scenarios

**Session isolation.** Authors, reviewers and fixers run through `evaluations/acceptance-kit/launch.py` with the
Claude Code command `claude -p PROMPT --model MODEL --safe-mode --restricted --strict-mcp-config
--no-session-persistence --tools Read,Write,Edit --disallowedTools Bash,WebFetch,WebSearch,Task --permission-mode
acceptEdits`, in an empty directory outside every checkout, with `MEMBRAIN_DIRECTORY` pointing to an empty read-only
directory and no credential in the environment; the Codex command is marked non-isolating and is not used. What this
does not guarantee is stated in the kit (`launch.py`) and in the record: the flags were read from `claude --help`
(2.1.322), not observed in a launched session; `--restricted` confines the file tools but the model's provider
still receives everything the session reads; admin-managed policy settings still apply; and from outside the
launcher can show what a session wrote, never prove what it did not read.

Two new isolated authors receive the neutral brief (`evaluations/acceptance-kit/author-brief.md`, sha256 `<…>`) and an
assignment file each, without source, history, previous scenarios or outcomes. Each scenario has eleven cases and
60–66 user turns; S1 is mainly English with one session in <Spanish|German>, S2 mainly Chinese with one session in
English; neither has page actions or a persona, both hold only literal assignments, state every weekday correctly
and declare one off-the-record stretch in the shape the harness runs (`c5-precheck.py --r4`, which `freeze.py`
runs with the clone's interpreter and requires to pass). Independent reviewers keep findings private
(`reviewer-brief.md`, sha256 `<…>`); independent fixers apply corrections (`fixer-brief.md`, sha256 `<…>`). Only
hashes, counts, precheck codes and fix counts reach the developer. Final scenario hashes: S1 `<sha256>` (<cases>
cases, <turns> turns), S2 `<sha256>` (<cases>, <turns>); receipts `control/s1-review-approved.json` `<sha256>`,
`control/s2-review-approved.json` `<sha256>`; both differ from every earlier scenario hash, and their largest 8-gram
overlap with a public earlier scenario is <x>% and <y>% (stop above <threshold fixed in advance>).

## Order, validity and scoring

Order is S1, S2. Strict validity is required after each scenario; both must be valid before blind scoring. First
reviews, 22 independent case rechecks, conditional R5 checks, resolutions and double attribution follow the unchanged
protocol (runbook: `evaluations/acceptance-review/companion.md`, R4 unit). No score or recording expectation is
adjusted manually.

## Billing

After approval, [official prices](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) and
[completion limits](https://api-docs.deepseek.com/api/create-chat-completion/) are revalidated on <date> and recorded
in `control/provider-revalidation.json`; a mismatch stops preparation. Maximum input/output rates are <9/27> CNY per
million for `deepseek-v4-pro`; conservative context/output bounds <1,048,576/393,216> tokens. The policy file
`evaluations/maturity-provider-policy-2026-11-14.json` (sha256 `<…>`) admits only `deepseek-v4-pro` with a proposed
limit of 80 CNY. Search/Fetch and other provider services are excluded.

Private evidence is Git-excluded under `<X>/evaluations/.maturity-heldout-<id>/`. Its absolute `control/ledger.json`
binds this attempt, the 80 CNY ceiling and the policy: initial SHA-256 `<…>`, bound policy hash `<…>`, recorded
before any completion. Every host call and permitted malformed-response retry uses it. Each request reserves
20.054016 CNY; with one request open the guard refuses once settled charges exceed 59.945984 CNY (with two open it
would refuse above 39.891968 CNY, which is why the arms run one after the other).

Expected conservative charge (guard's count; characters at about 3.7 per token, as `budget.md`):

| Item | CNY |
| --- | --- |
| `P`, attempt-5 workload (S1 + S2, 173 host rounds) | 15.63 |
| `P` standing prompt: − skill 10.4k, + 9.3k more schema characters (all 14 tools, low-level ones included), + 1.33k instructions, + 0.3k notice ≈ +0.5k characters × ≈ 210 calls | +0.3 |
| Consolidation: ≈ 9 batches per scenario, 2 calls each | +5.4 |
| Persona block, both arms (≈ 250 tokens a call) | +0.8 |
| `F`, attempt-5 workload | 11.52 |
| Billed empty-reply retries | +0.4 |
| **Expected total** | **≈ 34** (plausible 26–45) |

Headroom: about 26 CNY between the expected settled total and the 59.945984 CNY refusal point (≈ 1.76 ×). For
comparison, the same count with the skill body kept in `P`'s prompt would be ≈ 42 CNY (the preparation's 40 left out
≈ 1.9 CNY of low-level tool schemas). The real bill is expected at about a fifth of the guard's count, ≈ 7–15 CNY
depending on the time of day. Unknown usage stays
reserved. Provider/transport failure, guard refusal, invalid evidence or a degraded harness stops further work and
closes the attempt's disposable services. No stopped ledger is reopened. Earlier ledgers, reservations and sealed
evidence are preserved separately.

## Before spending, during and after

Before spending, record the exact execution commit, clean status, pins, runtime/interpreter identity (dedicated venv
from `uv.lock`), the running service's build identity, owned-port availability (8893, 55533), free disk (≥ 5 GiB),
provider model settings and the initial balance. Freeze runtime, launchers, harness, supervisor, driver, scoring
pipeline, review instructions, persona draw, policy, this binding, briefs, receipts, control files and scenarios
through scoring (manifest `<path>`, <N> files, sha256 `<…>`, `persona` `<TYPE>`, no `practice` mark; made by
`freeze.py --binding <this file> --allowed-models <P>/control/allowed-models.json`, which refuses an attempt id this
binding does not name). Observe balances before S1, after S1
and after S2, separately from conservative ledger charges. Credentials are never printed or placed on a command line.
After the run, whatever its result, verify that ports 8893 and 55533 are closed and no process of the attempt's
profiles remains (`c5-harness.py --cleanup` on each run directory, then a process listing). The final independent
review examines the frozen source and the gate evidence. An R4 pass does not by itself allow merge, tag or
publication: C5, the repeated R5 protocol and the final release review remain open. Any source change requires review
and qualification; this approval includes no extra attempt.
