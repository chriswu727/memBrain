# C5 maturity acceptance attempt: execution binding (DRAFT)

> **DRAFT, not a binding.** Written on 2026-11-17 from the [seventh attempt's R4 binding](maturity-acceptance-execution-2026-11-16.md)
> with every C5 difference written in. `<…>` marks what only preparation can fill (identities, hashes, counts, the
> persona draw, the session table, the novelty figures). Preparation copies this file to
> `evaluations/maturity-c5-execution-<date>.md`, fills it, names the attempt id in backquotes (which `freeze.py
> --binding` requires) and commits it before freezing; this draft itself binds nothing. **It authorizes no model
> call and no subscription session.** No C5 scenario has been written for it.

This binding fixes attempt `<ATTEMPT_ID>` ("the `<n>`th maturity attempt") before any paid call. It was written on
`<date>` by the operator of the preparation, under the lead's delegation. The attempt id was fixed by the lead's
brief **before** any persona draw was computed. **This binding authorizes no model call.** The owner's approval of
the paid run (the ceiling, the subscription use for scenario writing, blind scoring and the final review) is
recorded separately; the lead starts the run only after it, and only after the independent freeze review has set
`execution_may_start`. This attempt is **C5 only**: there is no R4 unit; R4's last result (the seventh attempt's
pass on runtime `a85ca152`) is neither repeated nor changed by it. There is no recharge, no retry and no automatic
additional attempt.

No C5 unit has ever completed. The third maturity attempt's C5 unit stopped at `P` 32 of 64 turns and the fifth's at
session 3, message 1, both on `page_action_failed`, with the cause not established; the harness then chose
page-action targets by text the host had written. Since 2026-11-17 it never does, a missing target is
`not_applicable` and scored, and `F` mirrors `P`'s persona turn by turn ([harness](c5-harness.md)).

## Scope decisions (taken by the lead under the owner's delegation)

1. **C5 is judged like R4, on the plugin path alone.** Arms: `P` (plugin path) and `F` (whole-history reference);
   gated arm: `P`. The rule: [`architecture/v1-acceptance.md`, C5](../architecture/v1-acceptance.md#c5--the-companion-layers-hold-on-held-out-lives-behavioural-acceptance).
2. **One seeded personality type to start, in both arms.** The type `<preset>` = `acceptance_persona.draw("<ATTEMPT_ID>")`
   = `IDS[int(sha256(attempt id), 16) % 16]` over `membrain.persona_presets.IDS`, recorded in the manifest's
   `persona` entry and computed for the first time after both scenarios were final. `P` saves it before the first
   session (made by the host, action `preset`), so the product's random first type and its announcement never occur.
   **A scenario has no `PERSONA`.** After the start the persona changes only as the user changes it: in conversation
   (the host's `memory_persona` and `memory_manner_feedback` tools) or by a page action. `F` is given `P`'s
   product-rendered persona block of the same turn, whatever changed it; validity checks every turn.
3. **Host model.** `deepseek-v4-pro` through the harness's emulation of the plugin hooks and MCP tools, as in R4.
   **It is not Claude Code.**
4. **One arm at a time.** For each scenario `P` runs, its installation is stopped and its ports checked closed, then
   `F` runs; only one host request is ever open against the ledger.
5. **Ceiling.** 80 CNY on the guard's conservative count, one model in the policy, one request in flight, on a new
   ledger created by the lead at run time.
6. **What the host does or fails to do is scored.** A page action whose target does not exist because of the host
   (no suggestion to accept because it did not report three comments; no note or feeling from a message; a message
   a pause of its own left unrecorded) is `not_applicable`: recorded with a fixed reason, applied the same way in
   `F`, shown to reviewers with every later case, and scored with the arm. It never stops the run. A turn left
   unrecorded by the host's own accepted pause is scored as in the seventh attempt. Only a fault of the harness or of
   the evidence (a `failed` page action, any harness event, missing or mismatched records) makes a scenario invalid.
7. **A "from now on" request and the user's yes are in the same conversation.** The product applies a confirmation
   only to a yes given in the conversation where the companion asked; the precheck refuses a scenario whose declared
   yes is in another session (`c5_coverage_order`). A product change to how the tool answers a confirmation cited
   from another conversation is separate and is not part of this binding unless the runtime pin below includes it:
   `<state whether the pinned runtime includes it>`.
8. **Critical errors and the pass rule are unchanged.** Types 1 to 9; no new type; RC1 and RC2 as in
   [`companion.md`](acceptance-review/companion.md); the pass rule as coded in `acceptance_review.py gate …
   --companion`.
9. **Scenario authors, reviewers and fixers** are isolated Sonnet sessions started by
   `evaluations/acceptance-kit/launch.py --gate C5` in directories outside every checkout, with only their brief and
   assignment; only hashes, counts and fixed codes reach the operator.

## Identities

`<ATTEMPT_ID>` uses the execution clone `<R>/clone` (`<platform>`), branch `acceptance/<ATTEMPT_ID>`, cloned from
integration commit `<commit>`. The branch adds only the commit of this binding; the frozen commit is that branch head,
recorded in the freeze review and in `control/preparation.json`. All launchers pin runtime `<runtime>` (pin commit
`<pin>`), build `<build>`, schema `<schema>`. Interpreter: `.venv` in the clone from `uv sync --frozen` (`<uv
version>`, `<n>` packages, `uv.lock` sha256 `<…>`), CPython `<version>`; embedding model cache
`$HOME/.cache/membrain/eval-embedding-model` (`model_quantized.onnx` `<…>`, `tokenizer.json` `<…>`).

Qualification on this source: `<full suite result and its source>`; the acceptance tooling's focused tests
(`tests/test_c5_*.py`, `tests/test_acceptance_*.py`, `tests/test_companion_acceptance.py`): `<passed, failed>`; the
public stub rehearsal `c5-stub-rehearsal.py`: `<freeze of n files marked practice, gate C5; driver complete with both
practice scenarios valid; dry-run checks n of n; validity page actions done / not applicable; persona mirroring n of
n; sheet blocks per case; gate C5 true on the synthetic verdicts; zero network events; ledger unchanged; ports
closed>`. These checks are not real-model acceptance.

## What governs the run

The [reviewed acceptance plan](maturity-paid-acceptance-plan-draft.md) governs isolation, review, scoring and stopping,
except where this binding says otherwise; its note of 2026-11-17 lists what the two-arm bindings supersede (arm `E`,
parallel arms, the 280 CNY ceiling, its C1/C2 coverage list).

- **Arms.** As in the seventh attempt: `P` drives the plugin's own hook functions and offers every tool the plugin's
  MCP server lists (`<n>` tools on this source, `<n>` characters of schemas), including `memory_note` with `affect`,
  `shared` and `moment`, `memory_boundary`, `memory_manner_feedback` and `memory_persona`; it gets the server's
  instructions, the session context and the per-message context, not the skill body. `F` gets the scenario's
  `HOST` text, the date, `P`'s persona block of the same turn, one fixed-format line of page-only settings
  (`Memory page settings the user chose (not part of the conversation above): …`: boundaries the page added and
  still in force, the latest relationship reset and feelings clearing, the support style, the familiarity limit and
  the mood pin) and the whole earlier history minus the messages a page deletion removed in `P`.
- **Page actions.** Format 2 (`c5-harness.md`): applied in `P` through the SDK on the page's routes, targets known
  from the scenario (a message by position, a boundary the scenario added) or by kind (the open suggestion by origin
  and order), never by host text; `random` switches picked from the attempt's seed; `F` applies `P`'s recorded
  outcome. `done` / `not_applicable` (reason codes `message_not_recorded`, `message_already_removed`,
  `no_note_from_message`, `no_feeling_from_message`, `boundary_not_present`, `no_open_proposal`) / `failed`.
- **The host's pause** and timed pauses: as in the seventh attempt.
- **Validity** (`acceptance_review.py validity`, run by the driver with `--scenario` and `--persona`): every R4 rule,
  and in companion mode (every C5 scenario has `PAGE_ACTIONS`): each arm's `page-actions.jsonl` holds exactly the
  scenario's actions in application order, each `done` or `not_applicable` with nothing removed, none `failed`, and
  `F`'s outcomes equal `P`'s; every `F` turn carries `P`'s persona block and record. It reports, without refusing,
  the `not_applicable` actions by position and reason and the turns whose persona `P`'s host was not shown.
- **Blind sheets** (`v1-2026-10-29-phase-b-blind.py BLIND SCENARIO PF --companion`, from copies of each arm's
  results and `page-actions.jsonl`): before each case, the page actions so far with their outcome, and the persona in
  effect (version and block), both the same for the two replies; the sheet is refused if they differ.
- **Pass rule (as coded in `acceptance_review.py gate REVIEW c1 c2 --companion --manifest MANIFEST`).** Over C1 and
  C2: `P`'s total ≥ `F`'s total − 1; no `P` reply with a standing critical error attributed to memory (anything but
  two "host" answers is memory); `P`'s replies with a host-caused critical error ≤ `F`'s replies with a standing
  critical error; **no standing type 7 or 8 in `P`, whatever its cause**. `C5 = P passes`. Writes `gate-c5.json`.

## Differences that affect comparability

| Change | Earlier C5 units (attempts 3 and 5) | This attempt | Effect |
| --- | --- | --- | --- |
| Arms | `P`, `E`, `F` in parallel; `P` and `E` gated | `P`, then `F`; `P` gated | A pass is the plugin path's only |
| Starting persona | set by the host at start (a host default card) | the attempt's seeded type `<preset>` | Tone and length in both arms follow that type |
| Persona changes | page actions with a scenario-stated card; `F` followed page actions only | in conversation (switch on request, a proposal confirmed by the user's yes in the same conversation, three manner comments then a page acceptance) or on the page; `F` takes `P`'s block every turn | Persona cases are judged against the persona in effect, shown to reviewers |
| Page-action targets | host text (topic, label, note substring, proposal text); a miss stopped the arm | scenario positions or kinds; a miss is `not_applicable` and scored | The stop that ended both earlier units cannot recur from a missing host record |
| What `F` knows of the page | persona card only | persona block of the turn, plus one line of page-only settings | `F` learns page boundaries, resets, clearing, support style, limit and pin from a fixed line, not from a memory layer |
| Reviewers see | `FACTS` only | `FACTS`, plus page actions so far with outcomes and the persona in effect, per case | Persona-stability and page-action cases can be judged |
| Scenario check | `c5-precheck.py` (scenario run as code) | `c5-precheck.py --c5` (literals only; shape, `COVERAGE` table, product limits) | |
| Tools offered to `P` | 5 | all `<n>` the server lists | Manner feedback, persona and moments by tool |
| Runtime | `7902c16e` and earlier | `<runtime>` | Product changes since |

## Scenarios

**Session isolation.** As in the seventh attempt: `launch.py` (sha256 `<…>`) with the Claude Code command of
`session-commands.json` (sha256 `<…>`), `--model sonnet`, each session in a new empty directory under
`<sessions root>` (outside every checkout, naming no product), with `MEMBRAIN_DIRECTORY` pointing to an empty
read-only directory and no credential. `control/allowed-models.json` is `["sonnet"]` (sha256 `<…>`). Every launch
passes `--gate C5`, so the sessions get `c5-author-brief.md` (sha256 `<…>`), `c5-reviewer-brief.md` (`<…>`) and
`c5-fixer-brief.md` (`<…>`), versions are checked with `c5-precheck.py --c5`, and an approval writes a receipt with
`"gate": "C5"`, which `freeze.py --gate C5` requires.

**Assignments** (frozen as control files; prefix, languages and size only): `control/c1-assignment.md` (sha256
`<…>`): prefix `C1`, mainly English, one session in `<Spanish or German>`; `control/c2-assignment.md` (`<…>`):
prefix `C2`, mainly Chinese, one session in English; both 11 cases, 60–66 user messages, at least 45 days.

**Coverage.** Each scenario declares in `COVERAGE` (format 1, checked by the precheck) the thirteen requirements of
the C5 rule: `stated_feeling`, `inferred_feeling`, `mood` (within 12 hours, at least 48 hours), `feelings_question`,
`boundary_in_conversation`, `boundary_on_page`, `page_deletion`, `reset`, `manner_feedback`, `from_now_on` (yes in
the same session, case in a later one), `switch`, `shared_moments` (hard case ≥ 30 days and ≥ 5 conversation days
later), `absence` (≥ 14 days). An off-the-record stretch is `<present in C1 / C2 / neither>`.

**Production, as the launcher reported it** (`<date, times>`; at most three review rounds per scenario, as in R4):

| # | Session | Result (launcher's JSON) |
| --- | --- | --- |
| `<1>` | c1 author 1 | `<sessions, turns, cases, precheck codes, sha256>` |
| `<…>` | `<…>` | `<…>` |

**Final scenarios** (from the receipts): C1 `<sha256>` (11 cases, `<turns>` turns, `<sessions>` sessions,
`<actions>` page actions, coverage 13 of 13), key `c1`; C2 `<sha256>` (…), key `c2`; receipts `<…>`.

**Novelty** (`acceptance-kit/novelty.py`, 10% largest 8-gram overlap, as the R4 bindings): against the public
scenarios at `<commit>` (including `c5-practice-scenario.py`) and, by path, the held-out scenarios of the sixth and
seventh attempts: C1 `<…>`, C2 `<…>`.

## Order, validity and scoring

Order is `c1`, `c2`. Strict validity is required after each scenario; both must be valid before blind scoring. The
`not_applicable` actions and host-pause turns validity reports are stated in the record by count and position; they
never make a run invalid. First reviews, 22 independent case rechecks, conditional R5 checks, the actions digest for
RC2, resolutions and double attribution follow the unchanged protocol (runbook:
`evaluations/acceptance-review/companion.md`, C5 unit). No score or expectation is adjusted manually.

## Billing

Revalidation of prices and limits as in the seventh attempt (`control/provider-revalidation.json`). Policy
`evaluations/maturity-provider-policy-2026-11-14.json` (sha256
`e7b91106b206412c608b33b0f43adc1d6f7db7c19da0c05a82a620198fb5689f`, unless a new policy is frozen): `deepseek-v4-pro`
only, 80 CNY, one request in flight; each request reserves 20.054016 CNY, so the guard refuses once settled charges
exceed 59.945984 CNY.

Expected conservative charge (guard's count), from the seventh attempt's 0.232 CNY per scenario-turn for both arms
(28.785141 CNY for 124 turns): 120–132 turns give about **30 CNY**; with the plan's unverified 25% companion
uplift (more tool rounds in `P`: manner feedback, persona, boundaries, notes with feelings and moments; the
relationship block up to 2,200 characters and the mood line) about **37 CNY**, plausibly 30–50. Headroom to the
refusal point about 1.6×. The real bill was about a sixth of the guard's count in the seventh attempt. Not included:
the subscription sessions (about 6–12 for the scenarios and 35–45 for scoring).

## Stop rules

As in the seventh attempt: a provider or transport failure, a guard refusal, invalid evidence, a reached cap, a
degraded harness (including a `failed` page action), a frozen input that changed, an existing run directory or a
driver error stops further work; no new scenario after a failed or invalid one; nothing is retried automatically; no
stopped ledger is reopened. **Not a stop:** a `not_applicable` page action, and a turn left unrecorded by the host's
own accepted pause. A second refused first, second or resolution review stops scoring for the owner. No score is
changed by hand. No recharge, no retry, no automatic further attempt.

## Running the attempt (for the lead, after approval; not run in preparation)

One script, `<R>/run-live.sh` (sha256 `<…>`), with `<R>/balance.py` (sha256 `<…>`), outside the clone and the
manifest, compared by the freeze review with this section. It is the seventh attempt's script with these changes
only: `R`, the clone, `PRIV="$CLONE/evaluations/.maturity-heldout-<ATTEMPT_ID>"`, `run_id` and `C5_ATTEMPT_ID` set to
`<ATTEMPT_ID>`, and the balance watcher waiting for `runs/c2-P` instead of `runs/s2b-P`
(`balance-after-c1.json`). The driver line is unchanged: it runs the manifest's C5 pair, `c1` then `c2`, `P` then
`F` within each. Started detached:

```bash
setsid nohup bash <R>/run-live.sh > <R>/run-live.out 2>&1 < /dev/null &
```

## Before spending, during and after

As in the seventh attempt, with the manifest `evaluations/.maturity-heldout-<ATTEMPT_ID>/control/manifest.json` made
by `freeze.py --gate C5 --binding <this binding> --allowed-models …/allowed-models.json` (its one pair has gate
`C5`; no `practice` mark), its file count, sha256 and `persona` recorded in the freeze review and in
`control/preparation.json`. After the run, whatever its result: ports 8893 and 55533 closed, no process of the
attempt's profiles left, and the record states each run's `not_applicable` actions and host-pause turns by count and
position, the persona-mirroring report and the memory-remark counts.

## Limits a C5 result will have

State these in the record whatever the result:
- **One host model under emulation.** `deepseek-v4-pro` through the harness's emulation, not Claude Code or any real
  host; one seeded personality type; two scenarios. A pass or fail may rest on one or two judgements, as R4's did.
- **Partial blinding.** Two arms: a memory remark in one reply ("Saved.", a pause notice, a mention of a suggestion on
  the page) can reveal which assistant wrote both replies of a case. `remarks` counts them from a fixed list, and the
  seventh attempt showed the count undercounts.
- **The yes in one conversation.** Every "from now on" confirmation in the scenarios is given in the same
  conversation; a yes in a later conversation is not tested (the product does not apply it).
- **`not_applicable` actions thin the coverage.** An action that found nothing (no suggestion, no recorded feeling)
  still counts as the plugin path's behaviour and is scored, but the requirement it was meant to exercise (for
  example a page acceptance of a manner suggestion) was then not exercised. The record names each such action, and
  which `COVERAGE` requirement it served.
- **`F` learns the page from a fixed line.** The reference has no memory layers: it learns boundaries set on the page,
  resets, cleared feelings, the support style, the familiarity limit and the mood pin from one line in its system
  prompt, has no mood or familiarity of its own, and sees deletions only as missing history. Its scores and critical
  errors (which bound `P`'s host-caused allowance) are those of a host given that line, not of another memory.
- **Host labelling decides type 6.** The host sets a feeling's basis; one inferred feeling saved as "said" makes
  memory present it as said, which attribution counts as memory-caused and which fails C5.
- **What the scenarios cannot check from text.** That a declared message really states a feeling, or that the host
  makes the proposal the user's yes answers, rests on the scenario reviewer's reading, not on the precheck.

## Filled in by the run

Nothing above this section changes after freezing. `<owner's approval (words, date); provider revalidation and
balances; ledger initial hash, requests and charge; execution summary; not-applicable actions and host-pause turns;
scores, attribution, memory remarks, gate-c5.json and the final review; link to the record>`.
