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
   a pause left unrecorded; no boundary saved by the words a page removal names), or that the page refuses with a
   validation error for a limit the host's records reached (`page_refused`: a type switch whose card and the
   agreements the user made with the host no longer fit together), is `not_applicable`: recorded with a fixed
   reason, applied the same way in `F`, shown to reviewers with every later case, and scored with the arm; it does not stop the run. A timed pause the
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
   critical type** (the review's question D5 is decided this way): types 1 to 9 stay as they are. Every persona
   case's criteria follow the author brief's template for its item (since 2026-11-17): what was asked for and
   agreed to, with dates, and a test a reader can see in the reply (for a manner kind, a visible test such as "at
   most three sentences"; for a "from now on" change, the agreed behaviour in a situation that calls for it; for a
   switch, that the reply neither refuses nor presents itself as unchanged, and nothing about the new manner, since
   nobody knows the type drawn).
9. **Critical errors and the pass rule are unchanged.** Types 1 to 9; no new type; RC1 and RC2 as in
   [`companion.md`](acceptance-review/companion.md) (RC2 since 2026-11-17 with its rule for actions that removed only
   derived records: type 8 does not stand when what the reply used is still in a user message the user did not
   delete, unless it uses what only the removed record held); the pass rule as coded in `acceptance_review.py gate …
   --companion`. **The host-diligence table is published with the result:** `acceptance_review.py coverage-report`
   (also `host_diligence` in validity's report) states, per `COVERAGE` item, whether `P`'s host made the tool call
   the product expects at the declared position, in tool names, argument codes and yes/no only, so that a failure
   can be read as the product's or the host's. A fail caused by a host step still counts as a fail: the result is
   one for memBrain together with this host model under emulation.
10. **Scenario authors, reviewers, fixers and verifiers** are isolated Sonnet sessions started by
   `evaluations/acceptance-kit/launch.py --gate C5` in directories outside every checkout, with only their brief,
   the author brief and the assignment (and, after the author, the scenario and the findings they act on); only
   hashes, counts and fixed codes reach the operator. **The review procedure (changed on 2026-11-17, after a public
   authoring diagnostic showed fresh reviewers each round re-judging what the round before had settled):** per
   scenario key, **one full review** (round 1, `--role reviewer`; the launcher refuses a second), then **at most
   three verification rounds** (`--role verifier`, each after a fixer). A verifier checks only that every earlier
   blocking finding was resolved exactly as instructed, without reopening or rewording it, and the ten fatal classes
   of the C5 briefs over the whole file; anything else it notes is advisory and never blocks. Blocking means one of
   those fatal classes, for the reviewer too, and every blocking finding gives the exact change. **Precheck-only fix
   rounds as before:** when a version fails `c5-precheck.py --c5`, the launcher writes that version's failure lines
   (codes and positions only) as precheck findings, and a fixer session is started on them; no review or
   verification runs on a failing version, and a precheck-only fix round does not count as a round. **A restart
   under a new key, once per scenario:** a new author for the same assignment, whose version line gets its own one
   review and up to three verifications. If that is not approved either, preparation stops and reports.

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
  `HOST` text, the date, `P`'s persona block of the same turn, one fixed-format line of page-only changes (format 2,
  `Memory page changes the user made (not part of the conversation above): …`: boundaries removed on the page, the
  latest relationship reset and feelings clearing, and the mood pin) and the whole earlier history minus the
  messages a page deletion removed in `P`.
- **Page actions.** Vocabulary format 3 (`c5-harness.md`, since the page simplification of 2026-11-18: only what the
  page still offers; no boundary, support style, familiarity limit or card is set on the page, and a boundary or a
  card change is something the user says to the agent; the precheck refuses a scenario that still uses one of
  those kinds with the code `removed_action`, and the harness refuses it before any model call): applied in `P`
  through the SDK on the page's routes, targets known from the scenario (a message by position, a boundary by the
  scenario's words for it) or by kind (the open suggestion by origin and order), never by host text; `random`
  switches picked from the attempt's seed; `F` applies `P`'s recorded outcome. `done` / `not_applicable` (reason codes `message_not_recorded`, `message_already_removed`,
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
| What `F` knows of the page | persona card only | persona block of the turn, plus one line of page-only changes | `F` learns boundary removals, resets, clearing and the pin from a fixed line, not from a memory layer |
| Reviewers see | `FACTS` only | `FACTS`, plus page actions so far with outcomes and the persona in effect, per case | Persona-stability and page-action cases can be judged |
| Scenario check | `c5-precheck.py` (scenario run as code) | `c5-precheck.py --c5 --require` (literals only; shape, `COVERAGE` table of the scenario's items with one case each, short or reaction-opening messages) | |
| Coverage per scenario | each scenario all of its requirements | the thirteen items split across the pair (C1 seven, C2 six) | Each item is tested once in the attempt, not twice |
| Tools offered to `P` | 5 | all `<n>` the server lists | Manner feedback, persona and moments by tool |
| Runtime | `7902c16e` and earlier | `<runtime>` | Product changes since |
| Transient provider failure (timeout, connection or protocol error, HTTP 429, 500, 502, 503 or 504, or a complete 2xx body without billing JSON) | stopped the arm and the attempt; the request kept its whole 20.054016 CNY reservation (attempt `maturity-c5-20261117b` stopped this way at turn 54 of 63 of its second scenario's `P`) | charged at a bound true for the request (Stop rules), the same request sent again after 30 and 120 s, three sends at most; a third interruption stops as before | A run can survive a provider hang; a retried reply is scored like any other (Limits) |

## Scenarios

**Session isolation.** As in the seventh attempt: `launch.py` (sha256 `<…>`) with the Claude Code command of
`session-commands.json` (sha256 `<…>`), `--model sonnet`, each session in a new empty directory under
`<sessions root>` (outside every checkout, naming no product), with `MEMBRAIN_DIRECTORY` pointing to an empty
read-only directory and no credential. `control/allowed-models.json` is `["sonnet"]` (sha256 `<…>`). Every launch
passes `--gate C5`, so the sessions get `c5-author-brief.md` (sha256 `<…>`), `c5-reviewer-brief.md` (`<…>`),
`c5-verifier-brief.md` (`<…>`) and `c5-fixer-brief.md` (`<…>`); every session after the author also gets the author
brief and the key's stored assignment. Versions are checked with `c5-precheck.py --c5 --require <the assignment's
items>`, and an approval (the reviewer's or a verifier's) writes a receipt with `"gate": "C5"` and the role and
round that approved, which `freeze.py --gate C5` requires.

**Assignments** (frozen as control files and passed to `freeze.py --assignment`; prefix, languages, size and
coverage items only): `control/c1-assignment.md` (sha256 `<…>`): prefix `C1`, mainly English, one session in
`<Spanish or German>`; `control/c2-assignment.md` (`<…>`): prefix `C2`, mainly Chinese, one session in English;
both 11 cases, 60–66 user messages, at least 45 days. Each has exactly one line `- Coverage items: item, item, ...`
(`acceptance-kit/assignment.py` parses it strictly); `launch.py` keeps the author's copy with the key and gives it to
every later session of that key.

**Coverage, split across the pair** (changed on 2026-11-17: with eleven cases a scenario cannot give each of the
thirteen items its own case, and cases carrying two items were a recurring dispute in review). Each case serves one
`COVERAGE` item at most (`mood` has two cases, both its own); the remaining cases of each scenario are ordinary
memory cases its author designs. **C1 covers** `stated_feeling`, `inferred_feeling`, `mood` (the first case's
session within 6 hours of the news's session, the second at least 49 hours after it, no declared feeling in
between), `feelings_question`, `boundary_in_conversation`, `page_deletion` (a user message with emotional or
relationship content) and `absence` (≥ 14 days); **C2 covers** `second_boundary` (a second boundary, on another
topic, asked for in conversation; until the page simplification of 2026-11-18 this item was `boundary_on_page`, a
boundary added on the page, which the page no longer offers; the C5 rule in `architecture/v1-acceptance.md` still
reads "one set on the page" until its owner rewords it, and this binding is not final before then), `reset`,
`manner_feedback` (accepted with its manner `kind`; no emoji kinds), `from_now_on` (about the companion's manner of responding, never
a task or anything tied to a time; yes in the same session, case in a later one; no page decision on a suggestion in
between), `switch` (never a named type) and `shared_moments` (hard case ≥ 30 days and ≥ 5 conversation days later).
The precheck refuses a table with an item missing or not on the assignment's line and a case named by two items;
`freeze.py --gate C5` refuses a pair whose `COVERAGE` keys do not cover all thirteen together. Both scenarios still
span at least 45 days. Each coverage case's criteria follow its item's template in the author brief. An
off-the-record stretch is `<present in C1 / C2 / neither>`; the precheck reports whether the product recognises its
opening message by itself (`<n of n>`).

**Production, as the launcher reported it** (`<date, times>`; per key one full review and at most three
verification rounds, plus precheck-only fix rounds; one restart under a new key per scenario, decision 10):

| # | Session | Result (launcher's JSON) |
| --- | --- | --- |
| `<1>` | c1 author 1 | `<sessions, turns, cases, precheck codes, sha256>` |
| `<…>` | `<…>` | `<…>` |

**Final scenarios** (from the receipts): C1 `<sha256>` (11 cases, `<turns>` turns, `<sessions>` sessions,
`<actions>` page actions, coverage 7 of 7), key `c1`; C2 `<sha256>` (…, coverage 6 of 6), key `c2`; together the
thirteen items; receipts `<…>` (approved by `<the reviewer in round 1 / a verifier in round n>`).

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
exceed 59.945984 CNY (80 − 20.054016). An interrupted host send (Stop rules) counts at its bound in those settled
charges. For this harness (`max_tokens` 16,384; 9 and 27 CNY per million) that bound is about **0.59 CNY plus
0.018 CNY per KB of request body, plus about 0.59–0.62 CNY when `P`'s tool schemas are sent**: 16,384 × 27 + 16,384 × 9
= 589,824 micro-CNY, plus 2 × 9 = 18 micro-CNY per body byte, plus 4 × 9 = 36 micro-CNY per byte of the schemas'
shortest JSON (16,425 bytes at `e82ad9d6`: 0.5913 CNY; the review's 0.62 used their 17,217 characters). Examples:
1.31 CNY for a 40 KB request without tools, 1.90 CNY for a 40 KB `P` request with the schemas, 3.29 CNY for a 150 KB
request. The absolute maximum is **9.879552 CNY** (1,048,576 × 9 + 16,384 × 27 micro-CNY, from a body of about
516 KB). A host call whose three sends all fail costs **three bounds** (9.87 CNY at 150 KB). Interruptions eat the
headroom: at the expected 30–50 CNY on the guard's count (below), the free headroom to the refusal point is
59.945984 − 50 ≈ 10 to 59.945984 − 30 ≈ 30 CNY, so roughly **3 to 9 interruptions at 3.3 CNY** fit (9.95 / 3.3 ≈ 3.0;
29.95 / 3.3 ≈ 9.1), about 6 at the 37 CNY point estimate (22.95 / 3.3 ≈ 6.95) and only **about 3 at the top of the
range**. Running out ends the attempt with `reservation_limit` at
the next reservation: the guard refuses the request before HTTP and blocks the ledger.

Expected conservative charge (guard's count), from the seventh attempt's 0.232 CNY per scenario-turn for both arms
(28.785141 CNY for 124 turns): 120–132 turns give about **30 CNY**; with the plan's unverified 25% companion
uplift (more tool rounds in `P`: manner feedback, persona, boundaries, notes with feelings and moments; the
relationship block up to 2,200 characters and the mood line) about **37 CNY**, plausibly 30–50. Headroom to the
refusal point about 1.6× (59.945984 / 37) without interruptions; each interruption takes its bound from it (above). The real bill was about a sixth of the guard's count in the seventh attempt. Not included:
the subscription sessions (for the scenarios, per key at least an author and a reviewer and at most an author, a
reviewer, three fixer and verifier pairs and the precheck-only fixers it needs, so about 4–20 for the pair without a
restart; 35–45 for scoring).

## Stop rules

As in the seventh attempt, except for transient provider failures: a provider failure other than a transient one, a
guard refusal, invalid evidence, a reached cap, a degraded harness (including a `failed` page action), a frozen input
that changed, an existing run directory or a driver error stops further work; no new scenario after a failed or
invalid one; no stopped ledger is reopened. **A transient provider failure is retried (changed from the seventh
attempt):** a host send that ends in a transport timeout or a connection or protocol error, that the provider
answers with HTTP 429, 500, 502, 503 or 504, or that it answers with a 2xx whose complete body holds no billing JSON
(only whitespace or empty lines, not JSON, or JSON without `usage`), is charged by the guard at a bound true for
that request (`min(1,048,576, 2 × body bytes + 4 × tool-schema bytes + 16,384)` input tokens at 9 CNY per million
plus the request's 16,384 output tokens at 27: about 0.59 CNY plus 0.018 CNY per KB of body plus about 0.59–0.62 CNY
with `P`'s schemas, at most 9.879552 CNY, instead of the 20.054016 CNY reservation; Billing above and
[billing control](evaluation-billing.md)), the ledger stays open, and the harness sends the same request again
after 30 and then 120 seconds, three sends at most for one host call, each counted against the host call cap. A
host call that fails on all three sends costs three bounds; the third interruption blocks the ledger and stops the
arm as before. Any other HTTP status (501, 505 and the other 5xx included), a 2xx whose usage is present but cannot
be settled (inconsistent or malformed usage, an unexpected response model, completion tokens above `max_tokens`), a
guard refusal (`reservation_limit` included, when interruptions have used up the headroom) and an unknown failure
stop at once. **A 400 is fatal too, and the harness is exposed to one:** the provider's thinking-mode guide says
that with `tools` the `reasoning_content` must be passed back in all subsequent requests or the API answers 400;
`P` sends it back only within a turn's rounds, never for earlier turns of the session ([`c5-harness.md`](c5-harness.md#harness-events-stops-and-the-log)).
Past runs got no 400; if the rule is enforced, the first `P` request after a turn with a tool call (or already a
session's second turn) stops the attempt early in its first scenario, after a few turns' spend, with that request's
reservation kept on the guard's count. The call shape is frozen and is not changed for this. A mismatch between the
ledger's interrupted requests and the interruption records (the driver's ledger check after validity) is a harness
defect and makes the scenario invalid. Nothing else is retried automatically. **Not a stop:** a retried provider
interruption (listed by validity per run with its position, code and the delay it added, never a harness event), a `not_applicable` page action (`page_refused`
included), a turn left unrecorded while a pause was in force (the host's or the product's own, decision 6), and a
timed pause the host asks for (a tool error). The host behaviours that still end a run as invalid are listed in decision 6. A second refused first, second or resolution review stops scoring for the owner. No score is
changed by hand. No recharge, no retry beyond the bounded resend of an interrupted host request, no automatic
further attempt.

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
by `freeze.py --gate C5 --binding <this binding> --allowed-models …/allowed-models.json --assignment
c1=…/control/c1-assignment.md --assignment c2=…/control/c2-assignment.md` (its one pair has gate `C5`; no
`practice` mark; each scenario prechecked with its assignment's items and the pair covering all thirteen), its file
count, sha256 and `persona` recorded in the freeze review and in
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
- **A reply produced on a retry is not distinguished in scoring.** When a host send was interrupted and the same
  request was sent again, the reply scored is the one the retry returned; reviewers are not told, and no score
  depends on it. Validity lists every interrupted send and retried host call by position and code, and the record
  states them. The retry repeats the request exactly, but the model's answer to it can differ from the answer the
  interrupted send would have produced, and in `P` the retry's waits run on the scenario clock. Validity reports the
  delay the interruptions added per session (failed sends plus waits, up to about 33 minutes for one host call);
  the record names the sessions whose scenario clock moved this way, because companion items such as a mood
  "within hours" are time-sensitive, while `F` has no clock.
- **The host model's earlier reasoning is not passed back.** With `tools`, `P` sends `reasoning_content` back
  only within a turn's rounds; earlier turns of a session are sent without it, and `F` is never offered tools
  ([`c5-harness.md`](c5-harness.md#harness-events-stops-and-the-log)). The provider's thinking-mode guide asks for
  it in all subsequent requests. A result is therefore of the host model as this emulation calls it, which may
  differ from a client that passes the reasoning back; if the service enforces the rule, the attempt stops with a
  400 instead (Stop rules).
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
- **`F` learns the page from a fixed line.** The reference has no memory layers: it learns boundaries removed on the
  page, resets, cleared feelings and the mood pin from one line in its system prompt, has no mood or familiarity of
  its own, and sees deletions only as missing history. Its scores and critical errors (which bound `P`'s
  host-caused allowance) are those of a host given that line, not of another memory.
- **Every boundary depends on the host** (since the page simplification of 2026-11-18). The page adds none, so both
  boundary items hold in `P` only if the host saved the boundary with `memory_boundary` when the user asked; the
  coverage report says per item whether it did. A page removal names the boundary by the scenario's words and finds
  it only if the host's topic or one of its other words is those words; otherwise it is `not_applicable`
  (`boundary_not_present`), and `F` is told of no removal.
- **Host labelling decides type 6.** The host sets a feeling's basis; one inferred feeling saved as "said" makes
  memory present it as said, which attribution counts as memory-caused and which fails C5.
- **Later review rounds are not independent of the first review** (decision 10). A verifier must accept every
  change the round-1 reviewer instructed and checks only the fixed fatal classes beyond that; what the one reviewer
  missed outside those classes, or decided wrongly, stays. The criteria templates fix the wording of every coverage
  case's "must" and "must not" in advance, so the scenarios' judgement of those items is the templates', not each
  author's; a template that tests the wrong thing would err the same way in every case of its item.
- **Each item is tested in one scenario only.** The thirteen items are split across C1 and C2 (seven and six), so
  each has one case (two for the mood) in the attempt, and an item is tested in one language mix only.
- **The automatic message checks are narrow.** The precheck refuses user messages under 16 characters (6 in CJK)
  and messages that open with a reaction from a fixed list; a reaction later in a message, one worded otherwise, and
  a message that assumes what the companion said are left to the reviewer and verifiers.
- **What the scenarios cannot check from text.** That a declared message really states a feeling, that a "from now
  on" request is about the manner of responding and not a task, that no message names a duration for the
  off-the-record stretch, or that the host makes the proposal the user's yes answers, rests on the scenario
  reviewer's reading, not on the precheck.

## Filled in by the run

Nothing above this section changes after freezing. `<owner's approval (words, date); provider revalidation and
balances; ledger initial hash, requests and charge; execution summary; not-applicable actions and host-pause turns;
scores, attribution, memory remarks, gate-c5.json and the final review; link to the record>`.
