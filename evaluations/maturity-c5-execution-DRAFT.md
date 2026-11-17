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
   a pause left unrecorded), or that the page refuses with a validation error for a limit after the precheck
   validated the scenario's own words (`page_refused`: for example a page boundary past the page's limits because
   of boundaries the host saved), is `not_applicable`: recorded with a fixed reason, applied the same way in `F`,
   shown to reviewers with every later case, and scored with the arm; it does not stop the run. A timed pause the
   host asks for is answered to the host as a tool error and counted with the tool errors; it is not a harness
   event. A server error or an exception on a page action stays `failed`.
   **Changed from the R4 binding of 2026-11-16 (its decision 6), for R4 and C5 alike:** a turn of `P` left
   unrecorded while the product's pause state said recording was paused for that conversation as the turn began is
   the plugin path's behaviour, **whoever made the pause**: the host's tool, or the product's own prompt hook
   recognising a pause request in the user's words ("Off the record: …", "Don't remember this."). It is listed in
   `host-pauses.jsonl` and scored. That binding stated that a turn left unrecorded by a pause the product itself made
   on the user's words, with no accepted pause of the host, stopped the run (`turn_not_recorded`); that stop is
   removed, because the product's own pause on the user's words is the plugin path working as designed, and the
   rule now reads the product's state instead of counting the host's calls. `turn_not_recorded` remains for a turn
   left unrecorded with no pause in force. Both prechecks (`--r4`, `--c5`) refuse a scenario in which a message
   outside a declared off-the-record stretch would trigger the product's recogniser (`pause_outside_stretch`).
   **What can still end a run as invalid because of the host** (everything else the host does is scored): the host
   writing an extra message into the session's own conversation with a low-level tool such as `memory_observe`
   (`message_identity_unknown`, or `unexpected_recording` in a turn left unrecorded; read from the code, not run end
   to end); a session of `P` lasting longer in real time than the scenario gap to the next session
   (`clock_already_past`; the prechecks now require sessions at least three hours apart, so this takes hours of host
   calls); four empty replies in a row (the host client's retries end the arm with a traceback); and using up the
   host call cap (five calls per scenario turn over the arm). A fault of the harness, the local service or the
   evidence (any other harness event, a `failed` page action, missing or mismatched records) makes a scenario
   invalid.
7. **A "from now on" request and the user's yes are in the same conversation.** The product applies a confirmation
   only to a yes given in the conversation where the companion asked; the precheck refuses a scenario whose declared
   yes is in another session (`c5_coverage_order`). **The pinned runtime includes the confirmation fix:** `ef0e8727`
   ("Never report a persona confirmation as saved when it cannot be; report one that failed"), under which the
   tool refuses a yes cited from another conversation at once and tells the host, is an ancestor of the launcher pin
   `0b1c052d`. Note that the harness imports the product from the frozen clone's `src/`, so what the harness runs is
   the frozen commit's source, not the launchers' pin; the freeze review checks that both contain the fix. R4's pass
   (the seventh attempt) was measured on runtime `a85ca152`, older than this pin: that R4 result and a C5 result on
   this runtime do not together qualify one release runtime.
8. **Persona cases are judged against what the user asked for and agreed to** (`FACTS` and the case's criteria),
   not against the persona block that `F` takes from `P`. The sheet shows the persona in effect, and the persona
   versions so far with the position each took effect and its origin as far as records shared by both arms show it
   (a page action by number and kind, or "in the conversation" during a given message), as context. A requested and
   agreed change that was not made, or a change nobody asked for, is scored through the case's criteria. **No new
   critical type** (the review's question D5 is decided this way): types 1 to 9 stay as they are. The author brief
   requires every persona case's criteria to say what was asked for and agreed to and what a reply honouring it
   looks like.
9. **Critical errors and the pass rule are unchanged.** Types 1 to 9; no new type; RC1 and RC2 as in
   [`companion.md`](acceptance-review/companion.md) (RC2 since 2026-11-17 with its rule for actions that removed only
   derived records: type 8 does not stand when what the reply used is still in a user message the user did not
   delete, unless it uses what only the removed record held); the pass rule as coded in `acceptance_review.py gate …
   --companion`. **The host-diligence table is published with the result:** `acceptance_review.py coverage-report`
   (also `host_diligence` in validity's report) states, per `COVERAGE` item, whether `P`'s host made the tool call
   the product expects at the declared position, in tool names, argument codes and yes/no only, so that a failure
   can be read as the product's or the host's. A fail caused by a host step still counts as a fail: the result is
   one for memBrain together with this host model under emulation.
10. **Scenario authors, reviewers and fixers** are isolated Sonnet sessions started by
   `evaluations/acceptance-kit/launch.py --gate C5` in directories outside every checkout, with only their brief and
   assignment; only hashes, counts and fixed codes reach the operator. **Preparation allows up to four review rounds
   per scenario, plus precheck-only fix rounds:** when a version fails `c5-precheck.py --c5`, the launcher writes
   that version's failure lines (codes and positions only) as precheck findings, and a fixer session may be started
   on them without a reviewer round; a precheck-only fix round does not count as a review round.

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
  `no_note_from_message`, `no_feeling_from_message`, `boundary_not_present`, `no_open_proposal`, `page_refused`) /
  `failed`. A decision on a suggestion may name the manner `kind` it takes.
- **The host's pause** and timed pauses: as decision 6 states (changed from the seventh attempt: a pause the product
  made on the user's words counts too, and a timed pause is a tool error, not a harness event).
- **Validity** (`acceptance_review.py validity`, run by the driver with `--scenario` and `--persona`): every R4 rule,
  and in companion mode (every C5 scenario has `PAGE_ACTIONS`): each arm's `page-actions.jsonl` holds exactly the
  scenario's actions in application order, each `done` or `not_applicable` with nothing removed, none `failed`, and
  `F`'s outcomes equal `P`'s; every `F` turn carries `P`'s persona block and record. It reports, without refusing,
  the `not_applicable` actions by position and reason, the turns whose persona `P`'s host was not shown, and the
  host-diligence table (decision 9). It accepts one asymmetry: a deletion of a message `P` never recorded removes
  nothing in `P` and still removes that message from `F`'s history.
- **Blind sheets** (`v1-2026-10-29-phase-b-blind.py BLIND SCENARIO PF --companion`, from copies of each arm's
  results and `page-actions.jsonl`): before each case, the page actions so far with their outcome, the persona in
  effect (version and block) and the persona versions so far with position and origin, all the same for the two
  replies; the sheet is refused if they differ.
- **Pass rule (as coded in `acceptance_review.py gate REVIEW c1 c2 --companion --manifest MANIFEST`).** Over C1 and
  C2: `P`'s total ≥ `F`'s total − 1; no `P` reply with a standing critical error attributed to memory (anything but
  two "host" answers is memory); `P`'s replies with a host-caused critical error ≤ `F`'s replies with a standing
  critical error; **no standing type 7 or 8 in `P`, whatever its cause**. `C5 = P passes`. Writes `gate-c5.json`.

## Differences that affect comparability

| Change | Earlier C5 units (attempts 3 and 5) | This attempt | Effect |
| --- | --- | --- | --- |
| Arms | `P`, `E`, `F` in parallel; `P` and `E` gated | `P`, then `F`; `P` gated | A pass is the plugin path's only |
| Starting persona | set by the host at start (a host default card) | the attempt's seeded type `<preset>` | Tone and length in both arms follow that type |
| Persona changes | page actions with a scenario-stated card; `F` followed page actions only | in conversation (switch on request, a proposal confirmed by the user's yes in the same conversation, three manner comments then a page acceptance) or on the page; `F` takes `P`'s block every turn | Persona cases are judged against what the user asked for and agreed to; the persona in effect and its versions so far are shown to reviewers as context (decision 8) |
| Page-action targets | host text (topic, label, note substring, proposal text); a miss stopped the arm | scenario positions or kinds; a miss, or a page refusal for a limit the host's records reached, is `not_applicable` and scored | A page action no longer fails because the host did or did not save something; it still fails on a server error, an exception or a deletion the harness cannot mirror |
| Unrecorded turns | any unintended one stopped the arm | a pause in force (the host's or the product's own) is scored; only a turn unrecorded with no pause in force stops (decision 6) | The same rule now governs R4 runs |
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
the C5 rule: `stated_feeling`, `inferred_feeling`, `mood` (the first case's session within 6 hours of the news's
session, the second at least 49 hours after it, no declared feeling or shared moment in between), `feelings_question`,
`boundary_in_conversation`, `boundary_on_page`, `page_deletion` (a user message with emotional or relationship
content), `reset`, `manner_feedback` (accepted with its manner `kind`; no emoji kinds), `from_now_on` (about the
companion's manner of responding, never a task or anything tied to a time; yes in the same session, case in a later
one; no page decision on a suggestion in between), `switch` (never a named type), `shared_moments` (hard case ≥ 30
days and ≥ 5 conversation days later), `absence` (≥ 14 days). An off-the-record stretch is `<present in C1 / C2 /
neither>`; the precheck reports whether the product recognises its opening message by itself (`<n of n>`).

**Production, as the launcher reported it** (`<date, times>`; at most four review rounds per scenario, plus
precheck-only fix rounds, decision 10):

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
stopped ledger is reopened. **Not a stop:** a `not_applicable` page action (`page_refused` included), a turn left
unrecorded while a pause was in force (the host's or the product's own, decision 6), and a timed pause the host asks
for (a tool error). The host behaviours that still end a run as invalid are listed in decision 6. A second refused first, second or resolution review stops scoring for the owner. No score is
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

## What was measured beforehand

A host probe of 2026-11-17 (evidence to be published with the attempt's record) ran `deepseek-v4-pro` with the
plugin path's standing prompt on public situations, each twice. The host called the expected tool in 2 of 2 trials
each for: a boundary request (English and Chinese), a manner comment (English and Chinese), a request to switch
personality ("surprise me"), a stated feeling (affect basis reported), an inferred feeling (basis inferred), a hard
shared moment (kind hard, with the feeling) and a playful one; and it answered "do you have feelings?" without
claiming real feelings. The boundary tool was used from its own tool description, which the server's instructions do
not name: the review's finding m6 therefore needs no product change before this attempt. The same probe found that a
"from now on" request for a task tied to a time ("check in with me the evening before my exams", "quiz me on
vocabulary every morning") was saved as a commitment note in 4 of 4 trials and never proposed as a persona change,
while a request about the manner of responding ("when I say I'm tired, listen first before giving advice") was
proposed and, after the yes, confirmed in 2 of 2: the C5 briefs therefore require the second kind. The probe is not
part of the acceptance result.

## Limits a C5 result will have

State these in the record whatever the result:
- **Persona cases are judged against the user's request, not the block** (decision 8). The persona-version list
  says only "in the conversation" for a change made through the host's tool: the records both arms share do not
  show whether it was a switch or a confirmed change.
- **Coverage that depends on the seeded type is avoided, not removed.** Comments about emoji, and named types, are
  excluded because their effect depends on the type drawn; with one seeded type, some manner kinds may still change
  less in some types than in others.
- **`F` is told about resets; `P`'s host is not** (review finding m4). `F`'s page line says "relationship reset on
  DATE" and "feelings cleared on DATE"; `P`'s host only finds the layers gone (no product text tells it a reset
  happened). This tilts reset cases toward `F`.
- **Emulation limits on tool use** (finding m5). A turn has at most three tool rounds and six tool calls, and a
  consolidation batch, asked for before the reply to a session's first message, takes two of those rounds.
- **A month-only date delays mellowing** (finding m8). A hard moment the host dates only to a month counts from that
  month's last day, which can put the 30 days past the scenario's case; the case's score then reflects that.
- **Probes the plan named that are not in `COVERAGE`** (finding m10): the same persona probe in three or more
  sessions, and boundary cases after a boundary's removal or raised by the user. They stay dropped for this attempt;
  a scenario may still contain them, unscored as coverage.
- **RC2 cannot clear a mark caused by a record without sources** (finding m12). When a deletion did not reach a host
  note that cites no message, a `not_removed` claim would need a content ref the resolution reviewer does not have,
  so such a mark stands.
- **Type 8 after derived-record actions** (finding M4): judged by the RC2 rule of decision 9; only `delete_message`
  makes type 8 unambiguous in both arms, which is why item 5 deletes a user message.
- **A deletion of a message `P` never recorded** removes it from `F`'s history only (finding m3); validity accepts that
  one asymmetry, and neither arm can bring the message back from memory.
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
- **What the scenarios cannot check from text.** That a declared message really states a feeling, that a "from now
  on" request is about the manner of responding and not a task, that no message names a duration for the
  off-the-record stretch, or that the host makes the proposal the user's yes answers, rests on the scenario
  reviewer's reading, not on the precheck.

## Filled in by the run

Nothing above this section changes after freezing. `<owner's approval (words, date); provider revalidation and
balances; ledger initial hash, requests and charge; execution summary; not-applicable actions and host-pause turns;
scores, attribution, memory remarks, gate-c5.json and the final review; link to the record>`.
