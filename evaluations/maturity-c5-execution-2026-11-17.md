# First two-arm companion attempt (C5 only): execution binding

This binding fixes attempt `maturity-c5-20261117b` ("the first two-arm companion attempt") before any paid call. It
was written on 2026-11-17 by the operator of the preparation, under the lead's delegation, from the
[draft C5 binding](maturity-c5-execution-DRAFT.md) (sha256
`66f5212854e577207cbb977bed2bcb92c93061036d9b901eda5a636c59d603ca` at the source commit), itself written from the
[seventh attempt's R4 binding](maturity-acceptance-execution-2026-11-16.md). Every section was revised for this
attempt, and every number below was measured on this source. The attempt id was fixed by the lead's brief **before**
any persona draw was computed. **This binding authorizes no model call.** The owner's approval of the paid run (the
ceiling, the subscription use for blind scoring and the final review) is recorded separately
(`control/owner-approval.json`); the lead starts the run only after it, and only after the independent freeze review
has set `execution_may_start`. Subscription use so far: four isolated Sonnet sessions for scenario writing and review
(below); no session ran the provider's largest model. This attempt is **C5 only**: there is no R4 unit; R4's last
result (the seventh attempt's pass on runtime `a85ca152`) is neither repeated nor changed by it. There is no recharge,
no retry and no automatic additional attempt.

An earlier preparation under the attempt id `maturity-c5-20261117a` stopped on 2026-11-17 at scenario authoring and
froze nothing: its first scenario was not approved in four review rounds, nor was its one restart, under the review
procedure then in force (a fresh full review every round). No persona was drawn for it, no binding was committed and
no model was called. Nothing of it is reused here: this attempt has a new id, a new clone, a new private root, a new
sessions root and new scenarios, written under the converging review procedure of decision 10.

No C5 unit has ever completed. The third maturity attempt's C5 unit stopped at `P` 32 of 64 turns and the fifth's at
session 3, message 1, both on `page_action_failed`, with the cause not established; the harness then chose
page-action targets by text the host had written. Since 2026-11-17 it never does, a missing target is
`not_applicable` and scored, and `F` mirrors `P`'s persona turn by turn ([harness](c5-harness.md)).

## Scope decisions (taken by the lead under the owner's delegation)

1. **C5 is judged like R4, on the plugin path alone.** Arms: `P` (plugin path) and `F` (whole-history reference);
   gated arm: `P`. The rule: [`architecture/v1-acceptance.md`, C5](../architecture/v1-acceptance.md#c5--the-companion-layers-hold-on-held-out-lives-behavioural-acceptance).
2. **One seeded personality type to start, in both arms.** The type `esfp` = `acceptance_persona.draw("maturity-c5-20261117b")`
   = `IDS[int(sha256(attempt id), 16) % 16]` over `membrain.persona_presets.IDS` (seed `maturity-c5-20261117b`),
   recorded in the manifest's `persona` entry. It was computed for the first time on 2026-11-17 at 05:12 UTC, after
   both scenarios were final (both approved, 05:04 and 05:12 UTC) and while this binding was written; nobody chose
   it. `P` saves it before the first session (made by the host, action `preset`), so the product's random first type
   and its announcement never occur. **A scenario has no `PERSONA`.** After the start the persona changes only as the
   user changes it: in conversation (the host's `memory_persona` and `memory_manner_feedback` tools) or by a page
   action. `F` is given `P`'s product-rendered persona block of the same turn, whatever changed it; validity checks
   every turn.
3. **Host model.** `deepseek-v4-pro` through the harness's emulation of the plugin hooks and MCP tools, as in R4.
   **It is not Claude Code.**
4. **One arm at a time.** For each scenario `P` runs, its installation is stopped and its ports checked closed, then
   `F` runs; only one host request is ever open against the ledger.
5. **Ceiling.** 80 CNY on the guard's conservative count, one model in the policy, one request in flight, on a new
   ledger created by the lead's run script at run time (never in preparation).
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
   outside a declared off-the-record stretch would trigger the product's recogniser (`pause_outside_stretch`);
   neither scenario of this attempt declares an off-the-record stretch, and both pass.
   **What can still end a run as invalid because of the host** (everything else the host does is scored): the host
   writing an extra message into the session's own conversation with a low-level tool such as `memory_observe`
   (`message_identity_unknown`, or `unexpected_recording` in a turn left unrecorded; read from the code, not run end
   to end); a session of `P` lasting longer in real time than the scenario gap to the next session
   (`clock_already_past`; the prechecks require sessions at least three hours apart, so this takes hours of host
   calls); four empty replies in a row (the host client's retries end the arm with a traceback); and using up the
   host call cap (five calls per scenario turn over the arm). A fault of the harness, the local service or the
   evidence (any other harness event, a `failed` page action, missing or mismatched records) makes a scenario
   invalid.
7. **A "from now on" request and the user's yes are in the same conversation.** The product applies a confirmation
   only to a yes given in the conversation where the companion asked; the precheck refuses a scenario whose declared
   yes is in another session (`c5_coverage_order`). **The pinned runtime includes the confirmation fix:** `ef0e8727`
   ("Never report a persona confirmation as saved when it cannot be; report one that failed"), under which the
   tool refuses a yes cited from another conversation at once and tells the host, is the runtime the launcher pin
   `0b1c052d` points at (and so an ancestor of it). The harness imports the product from the frozen clone's `src/`,
   so what the harness runs is the frozen commit's source, not the launchers' pin; measured in preparation, both
   contain the fix (and `55a88f1f`, "Ask the host AI to use memory tools before it writes its reply"), and `src/`,
   `migrations/` and `plugins/` are identical between `0b1c052d` and the source commit; the freeze review checks this
   again. R4's pass (the seventh attempt) was measured on runtime `a85ca152`, older than this pin: that R4 result and
   a C5 result on this runtime do not together qualify one release runtime.
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
   nobody knew the type drawn when the scenarios were written).
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
   (codes and positions only) as precheck findings, and a fixer session is started on them (at most three such
   rounds per key); no review or verification runs on a failing version, and a precheck-only fix round does not count
   as a round. **A restart under a new key, once per scenario:** a new author for the same assignment (`c1b`,
   `c2b`), whose version line gets its own one review and up to three verifications. If that is not approved either,
   preparation stops and reports. In this attempt both scenarios were approved by their one full review, so no
   fixer, verifier or restart was used (below).

## Identities

`maturity-c5-20261117b` uses the new execution clone `/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/clone`
(Linux x86_64, WSL2, kernel 6.18.58.1-microsoft-standard-WSL2), branch `acceptance/maturity-c5-20261117b`, cloned from
integration commit `4936e6bb29a7c993d756628eaebf8f59628833f7` (head of `integration/maturity-candidate` locally and
on GitHub when preparation started). The branch adds only the commit of this binding; the frozen commit is that
branch head, recorded in the freeze review and in `control/preparation.json`. No tooling was changed in preparation.
All nine launchers pin runtime `ef0e87276242595672c73a8558a0d905d50b712d` (pin commit
`0b1c052d1af3652eac1fe84e8b342b9b5deb6bec`; `src/`, `migrations/` and `plugins/` are identical between `0b1c052d` and
`4936e6bb`, and `src/` and `migrations/` also between `ef0e8727` and `4936e6bb`), build
`6200f1e1452f6dc3080b4194f593492bff2a4fb7ebc17a11bf7c6b37c0d2ae8a`, schema
`3a94d7b6ea6bfba8ff8a4d920aa83001123922f4f90b0a9d6430ef1997b6166d` (`membrain.build_identity` in the clone; the
schema is the seventh attempt's). Interpreter: `.venv` in the clone from `uv sync --frozen` (uv 0.13.6, 79 packages,
`include-system-site-packages = false`, `uv.lock` sha256
`0bc566ca91736f5cb706fb200b84cdda8c36be62abbb91ec744f3ea1d54c7e92`), CPython 3.12.16 managed by uv (binary sha256
`23bc148d2b48964b621c5561ff2b81c1d9c7b717967a7491efbf12f4304882b5`), `membrain` imported from the clone's `src`;
ONNX Runtime 1.31.1; embedding model cache `$HOME/.cache/membrain/eval-embedding-model` (`model_quantized.onnx`
`f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193`, `tokenizer.json`
`0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`, as in the seventh attempt). Claude Code 2.1.322
for the scenario sessions.

Qualification on this source: the full local suite passed on the pinned source `0b1c052d` (4,271 passed, none failed,
3 skipped, reported in the [persona-confirmation record](persona-confirmation-2026-11-17.md)); it was not rerun in
this preparation, and the commits after the pin changed no file under `src/`, `migrations/` or `plugins/`. In the
clone at `4936e6bb`, with every `*_API_KEY` and `C5_*` variable unset and under the machine's shared database-test
lock (2026-11-17, 04:59:52–05:15:33 UTC): the acceptance tooling's focused tests (every `tests/test_c5_*.py`,
`tests/test_acceptance_*.py`, `tests/test_companion_acceptance.py`, `tests/test_evaluation_billing_guard.py`,
`tests/test_pause_request.py`) **1,004 passed, 0 failed, 0 skipped** (driver 152, kit 71, kit novelty 4, review
hardening 157, review pipeline 128, scenario path 18, companion validity 20, converge 70, c5 harness 56, harness
hardening 79, c5 kit 77, proposal selection 7, review fixes 39, supervisor 7, companion acceptance 26, billing guard
55, pause request 38; 2 existing fork warnings; 688 s on a fresh task-owned database, stopped afterwards). The public
stub rehearsal `c5-stub-rehearsal.py` before freezing (234 s, stderr empty): freeze of 441 files marked practice, gate
C5, persona `esfp` (the rehearsal's own id); driver complete with both practice scenarios valid, `eligible` `C5`;
dry-run checks 606 of 606 for each; validity per scenario 16 page actions, 14 done and 2 not applicable (action 11
`boundary_not_present`, action 13 `message_not_recorded`), identical in `P` and `F`; persona mirroring 34 of 34 turns;
host pauses 1 in `P` (session 9, message 3), 0 in `F`; host-diligence 13 items and coverage-report 13 of 13 made;
sheets 7 cases each with page-action, persona and persona-version blocks; gate C5 true on the synthetic verdicts
(`P` 13 against 13, one host-caused against one reference critical); zero network events; ledger unchanged with no
request; ports closed; two stopped synthetic databases removed. These checks are not real-model acceptance.

## What governs the run

The [reviewed acceptance plan](maturity-paid-acceptance-plan-draft.md) governs isolation, review, scoring and stopping,
except where this binding says otherwise; its note of 2026-11-17 lists what the two-arm bindings supersede (arm `E`,
parallel arms, the 280 CNY ceiling, its C1/C2 coverage list).

- **Arms.** As in the seventh attempt: `P` drives the plugin's own hook functions and offers every tool the plugin's
  MCP server lists (14 tools on this source: `memory_capabilities`, `memory_recall`, `memory_inspect`,
  `memory_observe`, `memory_note`, `memory_consolidate`, `memory_boundary`, `memory_pause`, `memory_resume`,
  `memory_manner_feedback`, `memory_persona`, `memory_prepare`, `memory_checkpoint`, `memory_forget`; 17,217
  characters of schemas, as the rehearsal's `tools.json` records them), including `memory_note` with `affect`,
  `shared` and `moment`, `memory_boundary`, `memory_manner_feedback` and `memory_persona`; it gets the server's
  instructions (1,382 characters, sha256 `fc7492b4032558baf9b37ba778e08637a1bb40014114fbd9640f1f578ab8dc63`, measured
  with `membrain.host.server_instructions()` and in the rehearsal), the session context and the per-message context,
  not the skill body. `F` gets the scenario's `HOST` text, the date, `P`'s persona block of the same turn, one
  fixed-format line of page-only settings (`Memory page settings the user chose (not part of the conversation
  above): …`: boundaries the page added and still in force, the latest relationship reset and feelings clearing, the
  support style, the familiarity limit and the mood pin) and the whole earlier history minus the messages a page
  deletion removed in `P`.
- **Page actions.** Format 2 (`c5-harness.md`): applied in `P` through the SDK on the page's routes, targets known
  from the scenario (a message by position, a boundary the scenario added) or by kind (the open suggestion by origin
  and order), never by host text; `random` switches picked from the attempt's seed; `F` applies `P`'s recorded
  outcome. `done` / `not_applicable` (reason codes `message_not_recorded`, `message_already_removed`,
  `no_note_from_message`, `no_feeling_from_message`, `boundary_not_present`, `no_open_proposal`, `page_refused`) /
  `failed`. A decision on a suggestion may name the manner `kind` it takes. C1 has 1 page action and C2 has 3.
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
| Starting persona | set by the host at start (a host default card) | the attempt's seeded type `esfp` | Tone and length in both arms follow that type |
| Persona changes | page actions with a scenario-stated card; `F` followed page actions only | in conversation (switch on request, a proposal confirmed by the user's yes in the same conversation, three manner comments then a page acceptance) or on the page; `F` takes `P`'s block every turn | Persona cases are judged against what the user asked for and agreed to; the persona in effect and its versions so far are shown to reviewers as context (decision 8) |
| Page-action targets | host text (topic, label, note substring, proposal text); a miss stopped the arm | scenario positions or kinds; a miss, or a page refusal for a limit the host's records reached, is `not_applicable` and scored | A page action no longer fails because the host did or did not save something; it still fails on a server error, an exception or a deletion the harness cannot mirror |
| Unrecorded turns | any unintended one stopped the arm | a pause in force (the host's or the product's own) is scored; only a turn unrecorded with no pause in force stops (decision 6) | The same rule now governs R4 runs |
| What `F` knows of the page | persona card only | persona block of the turn, plus one line of page-only settings | `F` learns page boundaries, resets, clearing, support style, limit and pin from a fixed line, not from a memory layer |
| Reviewers see | `FACTS` only | `FACTS`, plus page actions so far with outcomes and the persona in effect, per case | Persona-stability and page-action cases can be judged |
| Scenario check | `c5-precheck.py` (scenario run as code) | `c5-precheck.py --c5 --require` (literals only; shape, `COVERAGE` table of the scenario's items with one case each, product limits, short or reaction-opening messages) | |
| Coverage per scenario | each scenario all of its requirements | the thirteen items split across the pair (C1 seven, C2 six) | Each item is tested once in the attempt, not twice |
| Scenario review | a reviewer per round, up to three rounds | one full review, then at most three verification rounds (decision 10); both scenarios approved by the full review | Later rounds were not needed; no fixer touched either scenario |
| Tools offered to `P` | 5 | all 14 the server lists (17,217 characters of schemas) | Manner feedback, persona and moments by tool |
| Runtime | `7902c16e` and earlier | `ef0e8727` (pin `0b1c052d`) | Product changes since |

## Scenarios

**Session isolation.** As in the seventh attempt: `launch.py` (sha256
`da046e8a727f642c50fb0ac8b35450df8496c0a43f43bebd0b3db8e72a56c68e`) with the Claude Code (2.1.322) command of
`session-commands.json` (sha256 `906a3964769b81c4bfa57196de08c4de9ad4c2f09c1ce2dd0ff939d2ea48edc4`, unchanged since
the sixth attempt): `claude -p PROMPT --model sonnet --safe-mode --restricted --strict-mcp-config
--no-session-persistence --tools Read,Write,Edit --disallowedTools Bash,WebFetch,WebSearch,Task --permission-mode
acceptEdits`, each session in a new empty directory under `/home/yichen/.local/state/acceptance-sessions/c5-20261117b`
(outside every checkout, naming no product), with `MEMBRAIN_DIRECTORY` pointing to an empty read-only directory and
no credential. `control/allowed-models.json` is `["sonnet"]` (sha256
`1a1e8da4732b9a81a4de2356e7f114f5d51fe2e0c45e6297522b623c4337eaf4`, byte-identical to the seventh attempt's). Every
launch passed `--gate C5`, so the sessions got `c5-author-brief.md` (sha256
`d4ff72115180261fa18091adeed75086dc3cc2867425f1d22064ca79692cee3f`), `c5-reviewer-brief.md`
(`174e8ed2085e6f95b4b8170851446e904983ad23d2f00aa190703128fe4cb701`); `c5-verifier-brief.md`
(`d6d42ac12815c22289471b1f6468b7a55f5dac72889aa44b261e76388af89ce1`) and `c5-fixer-brief.md`
(`440ad821f649e747021f4cd1b8e21d6935d22f193c38d9e4c787699d9619066b`) are frozen but were not given to any session,
because no fixer or verifier was needed; every session after the author also got the author brief and the key's
stored assignment (`assignment.py` sha256 `529ce840a1ca8b1c5089813eb5876f6cf09e6c4d241f16b1c87820928d0d9193`).
Versions were checked with `c5-precheck.py --c5 --require`, given the assignment's items (`c5-precheck.py` sha256
`e77b6e509097d71eba92a63271a180061e85f509b3c869a04f5a1907e523b1f1`), and each approval wrote a receipt with
`"gate": "C5"` and the role and round that approved, which `freeze.py --gate C5` (sha256
`758481413e79373b17702887ec6a33cfd2cfaf84a57d8e88a045bd52c5e17ce2`) requires. The isolation probe of 2026-11-15 was
not repeated: the Claude Code version and the session command are the same.

**Assignments** (frozen as control files and passed to `freeze.py --assignment`; prefix, languages, size and
coverage items only, in the form of the public authoring diagnostic's assignment): `control/c1-assignment.md` (sha256
`e0e6ecfbed681ee8869d47e0b3254359288c6968993ed8a0ff7e0e1a5cafc81e`): prefix `C1`, mainly English, one session in
German; `control/c2-assignment.md` (`dabfc500635278ec3babe4681cf1e52c1d06be1161c2d8725d7460eef3a0809f`): prefix `C2`,
mainly Chinese, one session in English; both 11 cases, 60–66 user messages, at least 45 days. Each has exactly one
line `- Coverage items: item, item, ...` (`acceptance-kit/assignment.py` parses it strictly); `launch.py` kept the
author's copy with the key (byte-identical to the control file for both keys) and gave it to the reviewer.

**Coverage, split across the pair** (changed on 2026-11-17: with eleven cases a scenario cannot give each of the
thirteen items its own case, and cases carrying two items were a recurring dispute in review). Each case serves one
`COVERAGE` item at most (`mood` has two cases, both its own); the remaining cases of each scenario are ordinary
memory cases its author designs. **C1 covers** `stated_feeling`, `inferred_feeling`, `mood` (the first case's
session within 6 hours of the news's session, the second at least 49 hours after it, no declared feeling in
between), `feelings_question`, `boundary_in_conversation`, `page_deletion` (a user message with emotional or
relationship content) and `absence` (≥ 14 days); **C2 covers** `boundary_on_page`, `reset`, `manner_feedback`
(accepted with its manner `kind`; no emoji kinds), `from_now_on` (about the companion's manner of responding, never
a task or anything tied to a time; yes in the same session, case in a later one; no page decision on a suggestion in
between), `switch` (never a named type) and `shared_moments` (hard case ≥ 30 days and ≥ 5 conversation days later).
The precheck refuses a table with an item missing or not on the assignment's line and a case named by two items;
`freeze.py --gate C5` refuses a pair whose `COVERAGE` keys do not cover all thirteen together. Both scenarios span at
least 45 days (C1 91, C2 70). Each coverage case's criteria follow its item's template in the author brief. **An
off-the-record stretch is present in neither scenario** (both declare no `EXPECT_RECORDING_P` stretch; the precheck
reports 0 intended unrecorded turns and off-the-record openings recognised 0 of 0 for each), so no turn is meant to
be left unrecorded in this attempt.

**Production, as the launcher reported it** (2026-11-17, 05:00–05:12 UTC; per key one full review and at most three
verification rounds, plus precheck-only fix rounds; one restart under a new key per scenario, decision 10):

| # | Session | Result (launcher's JSON) |
| --- | --- | --- |
| 1 | c1 author 1 (05:00–05:03) | `{"cases": 11, "key": "c1", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 16, "sha256": "09522225bd1f86cba30334a7adacd5a1866e1a3ebd0598af4ee5e50ffd2ce181", "turns": 61}` |
| 2 | c1 reviewer, round 1 (05:03–05:04) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "d1654b205bf6f0b8dc503a6a2eb25c74ddfeedff3d77c020010f40dce4d4305a", "key": "c1", "produced": true, "receipt_sha256": "7ca18117f6be22955bcafbb3ad80c5418faa75601987f23167338e45867898ac", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "09522225bd1f86cba30334a7adacd5a1866e1a3ebd0598af4ee5e50ffd2ce181", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |
| 3 | c2 author 1 (05:04–05:10) | `{"cases": 11, "key": "c2", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 20, "sha256": "ec1de6c4a95c076534cd29571bb5980612d0939786afb184744a3d71df9a2b19", "turns": 63}` |
| 4 | c2 reviewer, round 1 (05:10–05:12) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "bf8bbbb23bf82d7814c2b774b36da21c430d179ac0a930656e9bd469c9d9b536", "key": "c2", "produced": true, "receipt_sha256": "5a170f3b2f044f39d5450c888270516d09ddbf2f19578e3284763e118d5fba7e", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "ec1de6c4a95c076534cd29571bb5980612d0939786afb184744a3d71df9a2b19", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |

Four Sonnet sessions, every one exited 0 with an empty stderr and produced its outputs; both author versions passed
the precheck at once, so no precheck-only fixer ran; both full reviews approved with 2 findings and 0 blocking, so no
fixer, verifier or restart ran. The two `review_sha256` values are equal because both `review.json` files hold the
same three values (approved, 2 findings, 0 blocking). The 2 non-blocking findings of each review were not applied: a
fix would make a new version, which would need a verification round. The launcher does not report cost, and the
operator did not open the session logs (35–45 bytes each by size), so their subscription cost is not known. After
each session its working directory (a redundant copy outside the private root) was emptied with `find DIR -mindepth
1 -delete` without being opened; the empty directories were kept so that the launcher's numbering continues. The
private root keeps the scenarios, reviews, findings, `rounds.json` and the logs, which the operator never opened.

**Final scenarios** (from the receipts): C1 `09522225bd1f86cba30334a7adacd5a1866e1a3ebd0598af4ee5e50ffd2ce181` (11
cases, 61 turns, 16 sessions, 1 page action, span 91 days, coverage 7 of 7), key `c1`, `c1/scenario_c1.py`; C2
`ec1de6c4a95c076534cd29571bb5980612d0939786afb184744a3d71df9a2b19` (11 cases, 63 turns, 20 sessions, 3 page
actions, span 70 days, coverage 6 of 6), key `c2`, `c2/scenario_c2.py`; together the thirteen items; receipts
`control/c1-review-approved.json` `7ca18117f6be22955bcafbb3ad80c5418faa75601987f23167338e45867898ac` and
`control/c2-review-approved.json` `5a170f3b2f044f39d5450c888270516d09ddbf2f19578e3284763e118d5fba7e` (each approved
by the reviewer in round 1). Both pass `c5-precheck.py --c5 --require` with their assignment's items on this source
with no code.

**Novelty** (`acceptance-kit/novelty.py`, prints only numbers and booleans; stop threshold **10% largest 8-gram
overlap**, as in the R4 bindings). Against the 21 public scenarios at `4936e6bb` (every top-level
`evaluations/*scenario*.py` that assigns `SESSIONS_LONG`, `c5-practice-scenario.py` included, and the two scenario
files of attempt 5's evidence) and the 15,646 64-hex strings recorded under `evaluations/` there: C1 hash new,
largest overlap 0.08%, all together 0.11% (3,536 distinct 8-grams); C2 hash new, largest 0.14%, together 0.28%
(5,676 8-grams); `ok` true. `novelty.py` takes earlier files only from git, so the files of earlier held-out and
diagnostic scenarios were added by path with a wrapper outside the repository that imports the kit's functions
unchanged and prints numbers only (`/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/novelty_with_extras.py`):
the sixth attempt's three held-out scenarios (`s1`, the unused first `s2`, `s2b`), the seventh attempt's two (`s1b`,
`s2b`) and the three public C5 authoring diagnostics of 2026-11-17 (`d2`, `d3`, and the first, `d1`), which were
written with the same kit and criteria templates for the same items. With all 29 together: C1 largest 6.36%, together
7.10%; C2 largest 3.12%, together 3.42%; both hashes new, `ok` true. Alone: C1 0.03% (sixth `s1`), 0.14% (sixth `s2`),
0.00% (`s2b`), 0.00% (seventh `s1b`), 0.00% (`s2b`), **6.36% (`d2`)**, 0.82% (`d3`), 0.96% (`d1`); C2 0.00%, 0.12%,
0.00%, 0.00%, 0.00%, 0.11% (`d2`), **3.12% (`d3`)**, 0.19% (`d1`). Every figure is within the threshold. The largest
overlaps are with the diagnostic of the same items (C1 with `d2`, C2 with `d3`), as the criteria templates fix the
wording of every coverage case's "must" and "must not"; the earlier attempt `maturity-c5-20261117a`'s unapproved
versions were not compared, because its private root is not opened.

## Order, validity and scoring

Order is `c1`, `c2`. Strict validity is required after each scenario; both must be valid before blind scoring. The
`not_applicable` actions and host-pause turns validity reports are stated in the record by count and position; they
never make a run invalid. First reviews, 22 independent case rechecks, conditional R5 checks, the actions digest for
RC2, resolutions and double attribution follow the unchanged protocol (runbook:
`evaluations/acceptance-review/companion.md`, C5 unit). No score or expectation is adjusted manually.

## Billing

Revalidation of prices and limits as in the seventh attempt, recorded by the lead in
`control/provider-revalidation.json` before the run (the run script refuses without it); a mismatch stops the
attempt before any call. Policy `evaluations/maturity-provider-policy-2026-11-14.json` (sha256
`e7b91106b206412c608b33b0f43adc1d6f7db7c19da0c05a82a620198fb5689f`, unchanged; no new policy is frozen):
`deepseek-v4-pro` only, 80 CNY, one request in flight, 9/27 CNY per million input/output tokens, conservative bounds
1,048,576 context and 393,216 output tokens; each request reserves 1,048,576 × 9 + 393,216 × 27 per million =
9.437184 + 10.616832 = 20.054016 CNY, so the guard refuses once settled charges exceed 80 − 20.054016 = 59.945984 CNY.

Expected conservative charge (guard's count), from the seventh attempt's 0.232 CNY per scenario-turn for both arms
(28.785141 CNY for 124 turns): this attempt's 124 turns (C1 61, C2 63) give about **29 CNY**; with the plan's
unverified 25% companion uplift (more tool rounds in `P`: manner feedback, persona, boundaries, notes with feelings
and moments; the relationship block up to 2,200 characters and the mood line) about **36 CNY**, plausibly 30–50.
Headroom to the refusal point about 1.7×. The real bill was about a sixth of the guard's count in the seventh
attempt. Not included: the subscription sessions (four for the scenarios, already used; 35–45 for scoring).

## Stop rules

As in the seventh attempt: a provider or transport failure, a guard refusal, invalid evidence, a reached cap, a
degraded harness (including a `failed` page action), a frozen input that changed, an existing run directory or a
driver error stops further work; no new scenario after a failed or invalid one; nothing is retried automatically; no
stopped ledger is reopened. **Not a stop:** a `not_applicable` page action (`page_refused` included), a turn left
unrecorded while a pause was in force (the host's or the product's own, decision 6), and a timed pause the host asks
for (a tool error). The host behaviours that still end a run as invalid are listed in decision 6. A second refused
first, second or resolution review stops scoring for the owner. No score is changed by hand. No recharge, no retry,
no R4 unit, no automatic further attempt.

## Running the attempt (for the lead, after approval; not run in preparation)

One script, `/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/run-live.sh` (sha256
`d0655f20f2028245e508f76e6dc20b7e8f800e0d290edab6ddd1b0214448c251`), with
`/home/yichen/.local/state/membrain-setup/runs/c5-attempt2/balance.py` (sha256
`b34790e6e43f37d4050538e563f56acc83e6fb1114374fcda534be28e61ad7a1`, a byte copy of the seventh attempt's; tested in
preparation only without a key: it printed `{"error": "KeyError"}` and exited 1, no request), outside the clone and
the manifest, compared by the freeze review with this section. It is the seventh attempt's script with these changes
only:
- `R`, the clone, `PRIV="$CLONE/evaluations/.maturity-heldout-c5-20261117b"`, the ledger's `run_id` and
  `C5_ATTEMPT_ID` set to `maturity-c5-20261117b`, and the balance watcher waiting for `runs/c2-P` instead of
  `runs/s2b-P` (`balance-after-c1.json`);
- two more refusals before anything else: `control/owner-approval.json` and `control/provider-revalidation.json` must
  exist and hold a JSON object;
- the key is validated and the first balance read **before** the ledger is created, so that a refused key or balance
  leaves no ledger (the seventh attempt created the ledger first); the key is unset on every refusal after it is
  exported, and the ledger's policy hash is checked to be 64 hex characters before it is exported.

Unchanged: the refusals before the ledger exists (the head and the manifest's sha256 as `control/preparation.json`
records them, a clean tree, a freeze review with `execution_may_start` true, ports 8893 and 55533 free, at least 5
GiB free, no ledger, no `runs/`), the key read from the main checkout's `.env` into the environment only, balances
read in-process, and the driver line: it runs the manifest's C5 pair, `c1` then `c2`, `P` then `F` within each.
Started detached:

```bash
setsid nohup bash /home/yichen/.local/state/membrain-setup/runs/c5-attempt2/run-live.sh \
  > /home/yichen/.local/state/membrain-setup/runs/c5-attempt2/run-live.out 2>&1 < /dev/null &
```

The script, verbatim:

```bash
#!/bin/bash
# The first two-arm companion attempt's live run (maturity-c5-20261117b, gate C5 only), as the binding's "Running the
# attempt" block prescribes. For the lead, after the owner's approval and the independent freeze review; not run in
# preparation. Start it detached (a background shell is killed after two hours):
#   setsid nohup bash /home/yichen/.local/state/membrain-setup/runs/c5-attempt2/run-live.sh \
#     > /home/yichen/.local/state/membrain-setup/runs/c5-attempt2/run-live.out 2>&1 < /dev/null &
# It writes progress to control files only and prints no key, no scenario text and no exception text.
set +x +v; set +H; HISTFILE=/dev/null; unset HISTFILE
R=/home/yichen/.local/state/membrain-setup/runs/c5-attempt2
CLONE=$R/clone
PRIV="$CLONE/evaluations/.maturity-heldout-c5-20261117b"
cd "$CLONE" || exit 90
unset HOST_MODEL MEMBRAIN_SRC PYTHONPATH MEMBRAIN_SEMANTIC MEMBRAIN_EVALUATION_CLOCK C5_STUB
export C5_PYTHON="$CLONE/.venv/bin/python" MEMBRAIN_MODEL_CACHE="$HOME/.cache/membrain/eval-embedding-model" PYTHON_DOTENV_DISABLED=1
leftover=$(env | grep -E '_API_KEY=|^C5_(BILLING|ATTEMPT)|^MEMORY_' | sed 's/=.*//')
[ -z "$leftover" ] || { echo "refused: variables set: $leftover"; exit 91; }

# Frozen state, before the ledger exists: the head and the manifest as control/preparation.json records them (the
# freeze review confirms both), a clean tree, the owner's approval and the provider revalidation recorded, free ports
# and disk.
want_head=$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["head"])' "$PRIV/control/preparation.json") || exit 92
want_manifest=$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["manifest_sha256"])' "$PRIV/control/preparation.json") || exit 92
[[ $want_head =~ ^[0-9a-f]{40}$ && $want_manifest =~ ^[0-9a-f]{64}$ ]] || { echo "refused: preparation record"; exit 92; }
[ "$(git rev-parse HEAD)" = "$want_head" ] || { echo "refused: head"; exit 92; }
[ -z "$(git status --porcelain --untracked-files=all)" ] || { echo "refused: tree not clean"; exit 93; }
[ "$(sha256sum "$PRIV/control/manifest.json" | cut -c1-64)" = "$want_manifest" ] || { echo "refused: manifest"; exit 94; }
[ -e "$PRIV/control/freeze-review.json" ] || { echo "refused: no freeze review"; exit 94; }
"$C5_PYTHON" -I -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("execution_may_start") is True else 1)' \
    "$PRIV/control/freeze-review.json" || { echo "refused: freeze review does not allow execution"; exit 94; }
for record in owner-approval provider-revalidation; do
  "$C5_PYTHON" -I -c 'import json,sys; sys.exit(0 if isinstance(json.load(open(sys.argv[1])), dict) else 1)' \
      "$PRIV/control/$record.json" 2>/dev/null || { echo "refused: no $record record"; exit 94; }
done
! ss -ltn | grep -qE ':(8893|55533)\b' || { echo "refused: an owned port is in use"; exit 94; }
[ "$(df --output=avail -B1 "$CLONE" | tail -n 1)" -ge 5368709120 ] || { echo "refused: less than 5 GiB free"; exit 94; }
[ ! -e "$PRIV/control/ledger.json" ] || { echo "refused: ledger exists"; exit 95; }
[ ! -e "$PRIV/runs" ] || { echo "refused: runs exist"; exit 95; }

# 1. The provider key, into the environment only: a trailing carriage return is stripped and the characters are
#    checked before it is exported; it is never printed, never on a command line, never written to a file.
IFS= read -r DEEPSEEK_API_KEY < <(sed -n 's/^DEEPSEEK_API_KEY=//p' /home/yichen/src/memBrain/.env | head -n 1)
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY%$'\r'}
if [[ $DEEPSEEK_API_KEY =~ ^[A-Za-z0-9_-]+$ ]]; then export DEEPSEEK_API_KEY; echo "key ok"; else unset DEEPSEEK_API_KEY; echo "key refused"; exit 97; fi

# 2. Balance before the first scenario (in-process; status and amounts only). A refused key or balance stops here,
#    before any ledger exists.
"$C5_PYTHON" -I "$R/balance.py" > "$PRIV/control/balance-initial.json" || { unset DEEPSEEK_API_KEY; echo "refused: balance"; exit 98; }

# 3. The ledger, from the policy exactly as c5-stub-rehearsal.py creates its own (once; it is never replaced).
"$C5_PYTHON" -I - "$PRIV/control/ledger.json" > "$PRIV/control/ledger-initial.json" <<'PY'
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("evaluation_budget", Path("evaluations/evaluation_budget.py"))
budget = importlib.util.module_from_spec(spec); spec.loader.exec_module(budget)
policy = json.loads(Path("evaluations/maturity-provider-policy-2026-11-14.json").read_text())
models = {name: {key: value for key, value in rate.items()} for name, rate in policy["models"].items()}
print(json.dumps(budget.create_ledger(sys.argv[1], run_id="maturity-c5-20261117b", limit_cny=policy["proposed_limit_cny"],
                                      endpoint=policy["endpoint"], models=models)))
PY
[ -s "$PRIV/control/ledger-initial.json" ] || { unset DEEPSEEK_API_KEY; echo "refused: ledger not created"; exit 96; }

# 4. The attempt's binding variables.
export C5_ATTEMPT_ID=maturity-c5-20261117b C5_BILLING_LEDGER="$PRIV/control/ledger.json"
export C5_BILLING_POLICY_SHA256="$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["policy_sha256"])' "$PRIV/control/ledger-initial.json")"
[[ $C5_BILLING_POLICY_SHA256 =~ ^[0-9a-f]{64}$ ]] || { unset DEEPSEEK_API_KEY; echo "refused: ledger policy hash"; exit 96; }

# Balance after the first scenario: once the second scenario's P run directory exists (its name only is checked).
( while [ ! -e "$PRIV/control/execution-done" ]; do
    if [ -d "$PRIV/runs/c2-P" ]; then "$C5_PYTHON" -I "$R/balance.py" > "$PRIV/control/balance-after-c1.json"; break; fi
    sleep 10
  done ) &
watcher=$!

# 5. The live driver: c1, then c2; P then F within each.
date -u +%FT%TZ > "$PRIV/control/execution-started"
"$C5_PYTHON" evaluations/acceptance-attempt-driver.py run --manifest "$PRIV/control/manifest.json" \
    --out "$PRIV/runs" --live > "$PRIV/control/execution-summary.out" 2> "$PRIV/control/execution-progress.err"
code=$?
echo "driver exit $code" > "$PRIV/control/execution-done"

# 6. Afterwards, whatever the result: the balance after the run, then close everything and check.
"$C5_PYTHON" -I "$R/balance.py" > "$PRIV/control/balance-final.json"
unset DEEPSEEK_API_KEY
kill "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null
for run in "$PRIV"/runs/*-P "$PRIV"/runs/*-F; do [ -d "$run" ] && "$C5_PYTHON" evaluations/c5-harness.py --cleanup "$run" >> "$PRIV/control/cleanup.out" 2>&1; done
(ss -ltn | grep -E ':(8893|55533)\b' || echo "ports closed") >> "$PRIV/control/execution-done"
date -u +%FT%TZ >> "$PRIV/control/execution-done"
```

The `.env` line must be the plain form `DEEPSEEK_API_KEY=value` (no quotes). The driver refuses to start unless the
manifest is the one below, every frozen hash matches, the ledger is unblocked and bound to this attempt and policy,
and the persona entry is the draw of the attempt id. Its stderr holds only paths, keys and exit codes; the run
directories hold scenario content and are never opened by the operator.

## Before spending, during and after

As in the seventh attempt, with the manifest `evaluations/.maturity-heldout-c5-20261117b/control/manifest.json` made
by `freeze.py --gate C5 --binding evaluations/maturity-c5-execution-2026-11-17.md --allowed-models
evaluations/.maturity-heldout-c5-20261117b/control/allowed-models.json --assignment
c1=evaluations/.maturity-heldout-c5-20261117b/control/c1-assignment.md --assignment
c2=evaluations/.maturity-heldout-c5-20261117b/control/c2-assignment.md` (its one pair has gate `C5`; no `practice`
mark; each scenario prechecked with its assignment's items and the pair covering all thirteen), its file count,
sha256 and `persona` recorded in the freeze review and in `control/preparation.json`. Before spending, the lead
records the owner's approval (`control/owner-approval.json`), the provider revalidation
(`control/provider-revalidation.json`) and the initial balance; the run script records the ledger's initial hash.
After the run, whatever its result: ports 8893 and 55533 closed, no process of the attempt's profiles left, and the
record states each run's `not_applicable` actions and host-pause turns by count and position, the persona-mirroring
report and the memory-remark counts.

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
  excluded because their effect depends on the type drawn; with one seeded type (`esfp`), some manner kinds may still
  change less in some types than in others.
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
- **Later review rounds are not independent of the first review** (decision 10). A verifier must accept every
  change the round-1 reviewer instructed and checks only the fixed fatal classes beyond that; what the one reviewer
  missed outside those classes, or decided wrongly, stays. The criteria templates fix the wording of every coverage
  case's "must" and "must not" in advance, so the scenarios' judgement of those items is the templates', not each
  author's; a template that tests the wrong thing would err the same way in every case of its item.
- **Each scenario had one reviewer.** Both scenarios were approved by their one full review (about 70 seconds of
  session time each, as seen from outside), with no verification round; each scenario's fitness beyond the precheck
  rests on that one Sonnet reading. Each review's 2 non-blocking findings were not applied.
- **Each item is tested in one scenario only.** The thirteen items are split across C1 and C2 (seven and six), so
  each has one case (two for the mood) in the attempt, and an item is tested in one language mix only.
- **No off-the-record stretch.** Neither scenario declares one, so this attempt does not exercise a pause on the
  user's words, the recording of its resume, or honesty about an unrecorded stretch.
- **The automatic message checks are narrow.** The precheck refuses user messages under 16 characters (6 in CJK)
  and messages that open with a reaction from a fixed list; a reaction later in a message, one worded otherwise, and
  a message that assumes what the companion said are left to the reviewer and verifiers.
- **What the scenarios cannot check from text.** That a declared message really states a feeling, that a "from now
  on" request is about the manner of responding and not a task, that no message names a duration for a pause, or
  that the host makes the proposal the user's yes answers, rests on the scenario reviewer's reading, not on the
  precheck.

## Filled in by the run

Nothing above this section changed after freezing. The frozen copy in the execution clone keeps its placeholder;
this copy was filled in on 2026-11-17 after the attempt had stopped.

- Owner's approval (words, date): "可以" (translation: "Yes, go ahead"), 2026-11-17, to the lead's question whether
  the companion evaluation may start under a ceiling of 80 CNY, C5 only, with about forty isolated sessions for
  scoring and one final review.
- Provider revalidation and balances: prices re-read on 2026-11-17 before the start, matching the policy; 117.80 CNY
  before the first scenario, 113.79 after it, 109.47 after the stop.
- Ledger: 265 requests settled, 24.473709 CNY on the guard's count, one reservation kept for an interrupted request;
  blocked with `provider_transport` (`ReadTimeout`).
- Execution summary: `c1` valid; `c2` stopped at turn 54 of 63 of arm `P` (`runner_failed`); arm `F` of `c2` not
  run. No not-applicable action and no host-pause turn in `c1`.
- Scores: the gate was not computed. `c1` was scored afterwards as a diagnostic (`P` 8.5, `F` 8.5, no standing
  critical error). No `gate-c5.json`, no final review. [Record](maturity-c5-attempt-stop-2026-11-17.md).
