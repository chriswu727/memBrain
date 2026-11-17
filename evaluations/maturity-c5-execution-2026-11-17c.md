# Second two-arm companion attempt (C5 only): execution binding

This binding fixes attempt `maturity-c5-20261117c` ("the second two-arm companion attempt") before any paid call.
The operator of the preparation wrote it on 2026-11-17, under the lead's delegation, from the
[draft C5 binding](maturity-c5-execution-DRAFT.md) (sha256
`47b58983d87072323f94942ce8b0d044e385b40c27324e04d19a7f6f04a7aabd` at the source commit). The draft was itself
written from the [seventh attempt's R4 binding](maturity-acceptance-execution-2026-11-16.md), and since then carries
the provider-retry stop rule. The [first two-arm attempt's binding](maturity-c5-execution-2026-11-17.md) served as
the model of a completed one. That file belongs to attempt `maturity-c5-20261117b` and is neither changed nor
superseded here.

Every section was revised for this attempt, and every number below was measured on this source. The lead's brief
fixed the attempt id **before** any persona draw was computed. **This binding authorizes no model call.** The
owner's approval of the paid run is recorded separately (`control/owner-approval.json`). It covers the ceiling and
the subscription use for blind scoring and the final review. The lead starts the run only after that approval, and
only after the independent freeze review has set `execution_may_start`.

Subscription use so far: four isolated Sonnet sessions for scenario writing and review (below). No session ran the
provider's largest model. This attempt is **C5 only**: there is no R4 unit. R4's last result (the seventh attempt's
pass on runtime `a85ca152`) is neither repeated nor changed by it. There is no recharge, no retry beyond the bounded
resend of an interrupted host request (Stop rules), and no automatic additional attempt.

## Earlier attempts under this kit

**`maturity-c5-20261117a`** was a preparation. It stopped on 2026-11-17 at scenario authoring and froze nothing:
its first scenario was not approved in four review rounds, and neither was its one restart, under the review
procedure then in force.

**`maturity-c5-20261117b`** ran on 2026-11-17, 06:08–06:51 UTC, under [its binding](maturity-c5-execution-2026-11-17.md)
(frozen commit `707edc57`, runtime `ef0e8727`). It **stopped as incomplete**:
- One request got no answer within 600 s (`ReadTimeout`) at turn 54 of 63 of the second scenario's `P`.
- The stop rule then in force retried nothing and kept that request's whole reservation.
- The second scenario's `F` never ran, and the gate was not computed ([record](maturity-c5-attempt-stop-2026-11-17.md)).
- Its first scenario was scored afterwards as a diagnostic only: `P` 8.5 of 11, `F` 8.5, no standing critical error.

Both of its scenarios are spent: the first was scored, the second was shown to the host for 53 turns. They are
published in that record's evidence archive. Nothing of either earlier attempt is reused here. This attempt has:
- a new id;
- a new clone, private root and sessions root;
- two new scenarios, written by new isolated sessions that saw neither earlier scenario nor that record.

The authors and reviewers of this attempt's scenarios see only their brief, the author brief and the assignment.
They never see the earlier scenarios, the diagnostic scores or the record.

No C5 unit has ever completed:
- The third maturity attempt's C5 unit stopped at `P` 32 of 64 turns, and the fifth's at session 3, message 1.
  Both stopped on `page_action_failed`, with the cause not established; the harness then chose page-action targets
  by text the host had written.
- Since 2026-11-17 the harness never chooses targets that way. A missing target is `not_applicable` and scored, and
  `F` mirrors `P`'s persona turn by turn ([harness](c5-harness.md)).
- The first two-arm attempt stopped on the provider timeout, as above.

## Scope decisions (taken by the lead under the owner's delegation)

1. **C5 is judged like R4, on the plugin path alone.**
   - Arms: `P` (plugin path) and `F` (whole-history reference); gated arm: `P`.
   - The rule: [`architecture/v1-acceptance.md`, C5](../architecture/v1-acceptance.md#c5--the-companion-layers-hold-on-held-out-lives-behavioural-acceptance).
2. **One seeded personality type to start, in both arms.**
   - The type is `intj` = `acceptance_persona.draw("maturity-c5-20261117c")` = `IDS[int(sha256(attempt id), 16) %
     16]` over `membrain.persona_presets.IDS` (seed `maturity-c5-20261117c`). It is recorded in the manifest's
     `persona` entry.
   - It was computed for the first time on 2026-11-17 at 09:49:43 UTC, after both scenarios were final (approved
     09:36 and 09:43 UTC) and while this binding was written. Nobody chose it.
   - `P` saves it before the first session (made by the host, action `preset`), so the product's random first type
     and its announcement never occur.
   - **A scenario has no `PERSONA`.** After the start the persona changes only as the user changes it: in
     conversation (the host's `memory_persona` and `memory_manner_feedback` tools) or by a page action.
   - `F` is given `P`'s product-rendered persona block of the same turn, whatever changed it; validity checks this
     every turn.
3. **Host model.** `deepseek-v4-pro` through the harness's emulation of the plugin hooks and MCP tools, as in R4.
   **It is not Claude Code.**
4. **One arm at a time.** For each scenario `P` runs, its installation is stopped and its ports are checked closed,
   then `F` runs. Only one host request is ever open against the ledger.
5. **Ceiling.** 80 CNY on the guard's conservative count, one model in the policy, one request in flight, on a new
   ledger. The lead's run script creates the ledger at run time, never in preparation.
6. **What the host does or fails to do is scored.**
   - **`not_applicable` page actions.** A page action is `not_applicable` when its target does not exist because of
     the host: no suggestion to accept because the host did not report three comments; no note or feeling from a
     message; a message a pause left unrecorded. It is also `not_applicable` when the page refuses it with a
     validation error for a limit after the precheck validated the scenario's own words (`page_refused`: for
     example a page boundary past the page's limits because of boundaries the host saved). Such an action is
     recorded with a fixed reason, applied the same way in `F`, shown to reviewers with every later case and scored
     with the arm. It does not stop the run.
   - **Timed pauses.** A timed pause the host asks for is answered to the host as a tool error and counted with the
     tool errors. It is not a harness event.
   - **Failures.** A server error or an exception on a page action stays `failed`.
   - **Unrecorded turns (changed from the R4 binding of 2026-11-16, its decision 6, for R4 and C5 alike).** A turn of
     `P` is the plugin path's behaviour, **whoever made the pause**, when it was left unrecorded while the product's
     pause state said recording was paused for that conversation as the turn began. The pause may come from the
     host's tool, or from the product's own prompt hook recognising a pause request in the user's words ("Off the
     record: …", "Don't remember this."). Such a turn is listed in `host-pauses.jsonl` and scored.
     - That binding stopped the run (`turn_not_recorded`) on a turn left unrecorded by a pause the product itself
       made on the user's words, with no accepted pause of the host. That stop is removed: the product's own pause
       on the user's words is the plugin path working as designed. The rule now reads the product's state instead
       of counting the host's calls.
     - `turn_not_recorded` remains for a turn left unrecorded with no pause in force.
     - Both prechecks (`--r4`, `--c5`) refuse a scenario in which a message outside a declared off-the-record stretch
       would trigger the product's recogniser (`pause_outside_stretch`). Neither scenario of this attempt declares
       an off-the-record stretch, and both pass.
   - **What can still end a run as invalid because of the host.** Everything else the host does is scored.
     - The host writing an extra message into the session's own conversation with a low-level tool such as
       `memory_observe` (`message_identity_unknown`, or `unexpected_recording` in a turn left unrecorded). This is
       read from the code, not run end to end.
     - A session of `P` lasting longer in real time than the scenario gap to the next session (`clock_already_past`).
       The prechecks require sessions at least three hours apart, so this takes hours of host calls, or several
       fully failed retried host calls in one session (Stop rules).
     - Four empty replies in a row: the host client's retries end the arm with a traceback.
     - Using up the host call cap: five calls per scenario turn over the arm, retries of interrupted sends included.
   - **Faults that are not the host's.** A fault of the harness, the local service or the evidence makes a scenario
     invalid: any other harness event, a `failed` page action, missing or mismatched records, or a mismatch between
     the ledger's interrupted requests and the interruption records.
7. **A "from now on" request and the user's yes are in the same conversation.**
   - The product applies a confirmation only to a yes given in the conversation where the companion asked. The
     precheck refuses a scenario whose declared yes is in another session (`c5_coverage_order`).
   - **The pinned runtime is `3afc0dda` (launcher pin `e82ad9d6`).** It includes the confirmation fix `ef0e8727`
     ("Never report a persona confirmation as saved when it cannot be; report one that failed"). Under that fix the
     tool refuses at once a yes cited from another conversation and tells the host. It also includes `55a88f1f`
     ("Ask the host AI to use memory tools before it writes its reply").
   - The harness imports the product from the frozen clone's `src/`, so the harness runs the frozen commit's source,
     not the launchers' pin. Measured in preparation:
     - `ef0e8727` and `55a88f1f` are ancestors of `3afc0dda`, of `e82ad9d6` and of the source commit;
     - `src/` and `migrations/` are identical across `3afc0dda`, `e82ad9d6` and the source commit;
     - `plugins/` is identical between `e82ad9d6` and the source commit.
     The freeze review checks this again.
   - R4's pass (the seventh attempt) was measured on runtime `a85ca152`, older than this pin. That R4 result and a C5
     result on this runtime do not together qualify one release runtime.
8. **Persona cases are judged against what the user asked for and agreed to** (`FACTS` and the case's criteria), not
   against the persona block that `F` takes from `P`.
   - The sheet shows, as context, the persona in effect and the persona versions so far. Each version is shown with
     the position it took effect and its origin, as far as records shared by both arms show it: a page action by
     number and kind, or "in the conversation" during a given message.
   - A requested and agreed change that was not made, or a change nobody asked for, is scored through the case's
     criteria.
   - **No new critical type** (the review's question D5 is decided this way): types 1 to 9 stay as they are.
   - Every persona case's criteria follow the author brief's template for its item (since 2026-11-17): what was
     asked for and agreed to, with dates, and a test a reader can see in the reply.
     - For a manner kind: a visible test such as "at most three sentences".
     - For a "from now on" change: the agreed behaviour in a situation that calls for it.
     - For a switch: that the reply neither refuses nor presents itself as unchanged, and nothing about the new
       manner, since nobody knew the type drawn when the scenarios were written.
9. **Critical errors and the pass rule are unchanged.**
   - Types 1 to 9; no new type.
   - RC1 and RC2 as in [`companion.md`](acceptance-review/companion.md). Since 2026-11-17 RC2 has its rule for actions
     that removed only derived records: type 8 does not stand when what the reply used is still in a user message
     the user did not delete, unless it uses what only the removed record held.
   - The pass rule as coded in `acceptance_review.py gate … --companion`.
   - **The host-diligence table is published with the result.** `acceptance_review.py coverage-report` (also
     `host_diligence` in validity's report) states, per `COVERAGE` item, whether `P`'s host made the tool call the
     product expects at the declared position. It uses tool names, argument codes and yes/no only, so that a failure
     can be read as the product's or the host's.
   - **Changed since the first two-arm attempt:** every entry has `reached`. A turn a stopped run never reached has
     `made` and `accepted` null and reads "not reached", never "not made". The first attempt's table had shown a
     switch request after its stop as not made.
   - A fail caused by a host step still counts as a fail: the result is one for memBrain together with this host
     model under emulation.
10. **Scenario authors, reviewers, fixers and verifiers** are isolated Sonnet sessions started by
    `evaluations/acceptance-kit/launch.py --gate C5`, in directories outside every checkout. Each gets only its
    brief, the author brief and the assignment (and, after the author, the scenario and the findings it acts on).
    Only hashes, counts and fixed codes reach the operator.
    - **The review procedure** (changed on 2026-11-17, after a public authoring diagnostic showed fresh reviewers each
      round re-judging what the round before had settled): per scenario key, **one full review** (round 1,
      `--role reviewer`; the launcher refuses a second), then **at most three verification rounds** (`--role
      verifier`, each after a fixer).
    - A verifier checks only two things: that every earlier blocking finding was resolved exactly as instructed,
      without reopening or rewording it; and the ten fatal classes of the C5 briefs over the whole file. Anything
      else it notes is advisory and never blocks.
    - Blocking means one of those fatal classes, for the reviewer too, and every blocking finding gives the exact
      change.
    - **Precheck-only fix rounds:** when a version fails `c5-precheck.py --c5`, the launcher writes that version's
      failure lines (codes and positions only) as precheck findings, and a fixer session is started on them (at
      most three such rounds per key). No review or verification runs on a failing version, and a precheck-only fix
      round does not count as a round.
    - **A restart under a new key, once per scenario:** a new author for the same assignment (`c1b`, `c2b`), whose
      version line gets its own one review and up to three verifications. If that is not approved either,
      preparation stops and reports.
    - In this attempt both scenarios were approved by their one full review, so no fixer, verifier or restart was
      used (below).

## Identities

`maturity-c5-20261117c` uses:
- **Clone:** the new execution clone `/home/yichen/.local/state/membrain-setup/runs/c5-attempt3/clone` (Linux
  x86_64, WSL2, kernel 6.18.58.1-microsoft-standard-WSL2).
- **Branch:** `acceptance/maturity-c5-20261117c`, cloned from integration commit
  `6ffcbbbe397463b67840e48d58cf5d7bac674982`. That was the head of `integration/maturity-candidate` locally and on
  GitHub when preparation started.
- **Frozen commit:** the branch adds only the commit of this binding, and the frozen commit is that branch head. It
  is recorded in the freeze review and in `control/preparation.json`. No tooling was changed in preparation.
- **Runtime:** all nine launchers pin runtime `3afc0dda274b21caff72fe5bcda97ec12298ce7e` (pin commit
  `e82ad9d633063b5df535bcf58a38c616874b4d72`). Build `3d3b119ae710eaf66455aa0245e36d4da36ecf891393b68fec5ddc1a8a942220`
  and schema `3a94d7b6ea6bfba8ff8a4d920aa83001123922f4f90b0a9d6430ef1997b6166d` (`membrain.build_identity` in the
  clone). The schema is the first two-arm attempt's; the build differs from it by the hard-moment change.
- **Interpreter:** `.venv` in the clone from `uv sync --frozen`:
  - uv 0.13.6, 79 packages, `include-system-site-packages = false`;
  - `uv.lock` sha256 `0bc566ca91736f5cb706fb200b84cdda8c36be62abbb91ec744f3ea1d54c7e92`;
  - CPython 3.12.16 managed by uv (binary sha256 `23bc148d2b48964b621c5561ff2b81c1d9c7b717967a7491efbf12f4304882b5`);
  - `membrain` imported from the clone's `src`; ONNX Runtime 1.31.1.
- **Embedding model cache:** `$HOME/.cache/membrain/eval-embedding-model`, with `model_quantized.onnx`
  `f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193` and `tokenizer.json`
  `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`, as in the first two-arm attempt.
- **Scenario sessions:** Claude Code 2.1.322.

**Full suite.** It passed on `3b3c32ef`: 4,576 passed, none failed, 3 skipped, as the
[hard-moment and provider-retry record](hard-moment-and-provider-retry-2026-11-17.md) reports. It was not rerun in
this preparation. The one commit between `3b3c32ef` and the source commit changes only documentation and evidence
(`README.md`, `README.zh-CN.md`, `docs/releasing.md`, `evaluations/*.md`, `evaluations/evidence/`).

**Focused tests in the clone.** At `6ffcbbbe`, with every `*_API_KEY` and `C5_*` variable unset, under the machine's
shared database-test lock (2026-11-17, 09:31:28–09:47:27 UTC), on a fresh task-owned database stopped afterwards
(702 s, 6 existing fork warnings).
- The acceptance tooling's focused tests: **1,011 passed, 0 failed, 0 skipped.** These are every
  `tests/test_c5_*.py`, `tests/test_acceptance_*.py`, `tests/test_companion_acceptance.py`,
  `tests/test_evaluation_billing_guard.py` and `tests/test_pause_request.py`. Per file: driver 155, kit 71, kit
  novelty 4, review hardening 157, review pipeline 128, scenario path 18, companion validity 20, converge 70, c5
  harness 56, harness hardening 80, c5 kit 77, proposal selection 7, review fixes 40, supervisor 7, companion
  acceptance 26, billing guard 57, pause request 38.
- In the same run, the provider retry's tests: `tests/test_provider_interruption_retry.py` 80 and
  `tests/test_billing_review_fixes.py` 33, all passed.
- In all, **1,124 passed**.

**Public stub rehearsal before freezing.** `c5-stub-rehearsal.py`, 244 s, stderr empty:
- freeze of 443 files marked practice, gate C5, persona `isfp` (the rehearsal's own id);
- driver complete with both practice scenarios valid, `eligible` `C5`;
- dry-run checks 606 of 606 for each;
- validity per scenario: 16 page actions, 14 done and 2 not applicable (action 11 `boundary_not_present`, action 13
  `message_not_recorded`), identical in `P` and `F`;
- persona mirroring 34 of 34 turns;
- host pauses: 1 in `P` (session 9, message 3), 0 in `F`;
- host-diligence 13 items, and coverage-report 13 of 13 made;
- sheets: 7 cases, each with page-action, persona and persona-version blocks;
- gate C5 true on the synthetic verdicts (`P` 13 against 13, one host-caused against one reference critical);
- zero network events; ledger unchanged with no request; ports closed; two stopped synthetic databases removed.

The rehearsal runs without the guard. The retry path is tested with a fake transport only. These checks are not
real-model acceptance.

## What governs the run

The [reviewed acceptance plan](maturity-paid-acceptance-plan-draft.md) governs isolation, review, scoring and stopping,
except where this binding says otherwise. Its note of 2026-11-17 lists what the two-arm bindings supersede: arm `E`,
parallel arms, the 280 CNY ceiling and its C1/C2 coverage list.

- **Arms.** As in the seventh attempt.
  - `P` drives the plugin's own hook functions and offers every tool the plugin's MCP server lists. On this source
    that is 14 tools: `memory_capabilities`, `memory_recall`, `memory_inspect`, `memory_observe`, `memory_note`,
    `memory_consolidate`, `memory_boundary`, `memory_pause`, `memory_resume`, `memory_manner_feedback`,
    `memory_persona`, `memory_prepare`, `memory_checkpoint`, `memory_forget`.
  - The schemas are 17,217 characters as the rehearsal's `tools.json` records them, or 16,425 bytes in their
    shortest JSON, the size the guard's interruption bound uses.
  - The tools include `memory_note` with `affect`, `shared` and `moment`, `memory_boundary`, `memory_manner_feedback`
    and `memory_persona`.
  - `P` gets the server's instructions, the session context and the per-message context, not the skill body. The
    instructions are 1,388 characters, sha256 `1067d3f96d1e55146eb3905089db4a52e14de8f0ce147df9fbef17e262f56a1d`,
    measured with `membrain.host.server_instructions()` and in the rehearsal. Since `3afc0dda` they define a hard
    shared moment as "a hard time you got through together (a bad night you sat with them through, or the user
    upset with you)".
  - `F` gets:
    - the scenario's `HOST` text and the date;
    - `P`'s persona block of the same turn;
    - one fixed-format line of page-only settings (`Memory page settings the user chose (not part of the
      conversation above): …`): boundaries the page added and still in force, the latest relationship reset and
      feelings clearing, the support style, the familiarity limit and the mood pin;
    - the whole earlier history minus the messages a page deletion removed in `P`.
- **Page actions.** Format 2 (`c5-harness.md`).
  - They are applied in `P` through the SDK on the page's routes. Targets are known from the scenario (a message by
    position, a boundary the scenario added) or by kind (the open suggestion by origin and order), never by host
    text.
  - `random` switches are picked from the attempt's seed. `F` applies `P`'s recorded outcome.
  - Outcomes are `done`, `not_applicable` or `failed`. The `not_applicable` reason codes are `message_not_recorded`,
    `message_already_removed`, `no_note_from_message`, `no_feeling_from_message`, `boundary_not_present`,
    `no_open_proposal` and `page_refused`.
  - A decision on a suggestion may name the manner `kind` it takes.
  - C1 has 1 page action and C2 has 3.
- **The host's pause and timed pauses:** as decision 6 states.
- **Validity** (`acceptance_review.py validity`, run by the driver with `--scenario` and `--persona`).
  - Every R4 rule applies.
  - In companion mode (every C5 scenario has `PAGE_ACTIONS`):
    - each arm's `page-actions.jsonl` holds exactly the scenario's actions in application order, each `done` or
      `not_applicable` with nothing removed, none `failed`;
    - `F`'s outcomes equal `P`'s;
    - every `F` turn carries `P`'s persona block and record.
  - It reports, without refusing: the `not_applicable` actions by position and reason; the turns whose persona `P`'s
    host was not shown; the host-diligence table (decision 9); and, per run, the interrupted provider sends and
    retried host calls with their positions and codes and the delay they added, in all and per session.
  - It refuses a malformed `provider-interruptions.jsonl` and an interruption that was not retried.
  - It accepts one asymmetry: a deletion of a message `P` never recorded removes nothing in `P` and still removes that
    message from `F`'s history.
  - After validity the driver runs `acceptance_review.py ledger-check` on the scenario: the ledger's interrupted
    requests must match the two directories' interruption records.
- **Blind sheets** (`v1-2026-10-29-phase-b-blind.py BLIND SCENARIO PF --companion`, from copies of each arm's results
  and `page-actions.jsonl`). Before each case the sheet shows the page actions so far with their outcome, the persona
  in effect (version and block) and the persona versions so far with position and origin, all the same for the two
  replies. The sheet is refused if they differ.
- **Pass rule (as coded in `acceptance_review.py gate REVIEW c1 c2 --companion --manifest MANIFEST`).** Over C1 and C2:
  - `P`'s total ≥ `F`'s total − 1;
  - no `P` reply with a standing critical error attributed to memory (anything but two "host" answers is memory);
  - `P`'s replies with a host-caused critical error ≤ `F`'s replies with a standing critical error;
  - **no standing type 7 or 8 in `P`, whatever its cause**.

  `C5 = P passes`. It writes `gate-c5.json`.

## Differences that affect comparability

Against the earlier three-arm C5 units (attempts 3 and 5):

| Change | Earlier C5 units (attempts 3 and 5) | This attempt | Effect |
| --- | --- | --- | --- |
| Arms | `P`, `E`, `F` in parallel; `P` and `E` gated | `P`, then `F`; `P` gated | A pass is the plugin path's only |
| Starting persona | set by the host at start (a host default card) | the attempt's seeded type `intj` | Tone and length in both arms follow that type |
| Persona changes | page actions with a scenario-stated card; `F` followed page actions only | in conversation (switch on request, a proposal confirmed by the user's yes in the same conversation, three manner comments then a page acceptance) or on the page; `F` takes `P`'s block every turn | Persona cases are judged against what the user asked for and agreed to; the persona in effect and its versions so far are shown to reviewers as context (decision 8) |
| Page-action targets | host text (topic, label, note substring, proposal text); a miss stopped the arm | scenario positions or kinds; a miss, or a page refusal for a limit the host's records reached, is `not_applicable` and scored | A page action no longer fails because the host did or did not save something; it still fails on a server error, an exception or a deletion the harness cannot mirror |
| Unrecorded turns | any unintended one stopped the arm | a pause in force (the host's or the product's own) is scored; only a turn unrecorded with no pause in force stops (decision 6) | The same rule now governs R4 runs |
| What `F` knows of the page | persona card only | persona block of the turn, plus one line of page-only settings | `F` learns page boundaries, resets, clearing, support style, limit and pin from a fixed line, not from a memory layer |
| Reviewers see | `FACTS` only | `FACTS`, plus page actions so far with outcomes and the persona in effect, per case | Persona-stability and page-action cases can be judged |
| Scenario check | `c5-precheck.py` (scenario run as code) | `c5-precheck.py --c5 --require` (literals only; shape, `COVERAGE` table of the scenario's items with one case each, product limits, short or reaction-opening messages) | |
| Coverage per scenario | each scenario all of its requirements | the thirteen items split across the pair (C1 seven, C2 six) | Each item is tested once in the attempt, not twice |
| Scenario review | a reviewer per round, up to three rounds | one full review, then at most three verification rounds (decision 10); both scenarios approved by the full review | Later rounds were not needed; no fixer touched either scenario |
| Tools offered to `P` | 5 | all 14 the server lists (17,217 characters of schemas) | Manner feedback, persona and moments by tool |
| Runtime | `7902c16e` and earlier | `3afc0dda` (pin `e82ad9d6`) | Product changes since |
| Transient provider failure (timeout, connection or protocol error, HTTP 429, 500, 502, 503 or 504, or a complete 2xx body without billing JSON) | stopped the arm and the attempt; the request kept its whole 20.054016 CNY reservation (attempt `maturity-c5-20261117b` stopped this way at turn 54 of 63 of its second scenario's `P`) | charged at a bound true for the request (Stop rules), the same request sent again after 30 and 120 s, three sends at most; a third interruption stops as before | A run can survive a provider hang; a retried reply is scored like any other (Limits) |

Against the [first two-arm attempt](maturity-c5-execution-2026-11-17.md) (`maturity-c5-20261117b`), with the same kit
(every kit file's sha256 unchanged), the same policy and the same arms:

| Change | First two-arm attempt | This attempt | Effect |
| --- | --- | --- | --- |
| Runtime | `ef0e8727` (pin `0b1c052d`, build `6200f1e1…`); the server's instructions (1,382 characters) define a hard shared moment only as "a difficult time between you (the user upset with you, a mistake of yours you sorted out together)" | `3afc0dda` (pin `e82ad9d6`, build `3d3b119a…`): "a hard time you got through together (a bad night you sat with them through, or the user upset with you)" (1,388 characters); nothing else in the product changed | The `shared_moments` hard case can now be saved for a hard time the two got through together. That attempt's host saved none for such a message. A public probe on this source saved one in 9 of 9 trials of a hard time (six bad nights, three reconciliations) and in 0 of 3 controls ([record](hard-moment-and-provider-retry-2026-11-17.md)). It may also save a bad day confided in earnest as a hard moment; that eagerness is not measured |
| Provider failures | any provider or transport failure stopped the attempt and kept the request's 20.054016 CNY reservation | the retry of Stop rules; `provider-interruptions.jsonl` per run; the driver's ledger check after validity | A hang costs a bound (typically 1.3–3.3 CNY) and up to about 33 minutes per host call instead of ending the attempt; see Billing for the headroom |
| Host-diligence table | a turn after a stop read as "not made" | `reached` per entry; an unreached turn reads "not reached" | A stopped run's table no longer blames the host for turns it never saw |
| Scenarios | `c1` 16 sessions, 61 turns, 91 days; `c2` 20 sessions, 63 turns, 70 days; persona `esfp` | two new scenarios (`c1` 17 sessions, 61 turns, 68 days; `c2` 20 sessions, 65 turns, 79 days); persona `intj` | Results of the two attempts are not of the same lives or the same type. The first attempt's `c1` was scored as a diagnostic only (8.5 against 8.5). Its record is public, and this attempt's authors and reviewers never saw it |
| Tooling tests | 1,004 focused tests on `4936e6bb` | 1,011 focused, plus 113 retry tests, on `6ffcbbbe`; full suite 4,576 on `3b3c32ef` | |

## Scenarios

**Session isolation.** As in the seventh attempt:
- **Launcher:** `launch.py` (sha256 `da046e8a727f642c50fb0ac8b35450df8496c0a43f43bebd0b3db8e72a56c68e`).
- **Command:** the Claude Code (2.1.322) command of `session-commands.json` (sha256
  `906a3964769b81c4bfa57196de08c4de9ad4c2f09c1ce2dd0ff939d2ea48edc4`, unchanged since the sixth attempt): `claude -p
  PROMPT --model sonnet --safe-mode --restricted --strict-mcp-config --no-session-persistence --tools Read,Write,Edit
  --disallowedTools Bash,WebFetch,WebSearch,Task --permission-mode acceptEdits`.
- **Directories and environment:** each session runs in a new empty directory under
  `/home/yichen/.local/state/acceptance-sessions/c5-20261117c` (outside every checkout, naming no product), with
  `MEMBRAIN_DIRECTORY` pointing to an empty read-only directory and no credential.
- **Allowed models:** `control/allowed-models.json` is `["sonnet"]` (sha256
  `1a1e8da4732b9a81a4de2356e7f114f5d51fe2e0c45e6297522b623c4337eaf4`).
- **Briefs:** every launch passed `--gate C5`, so the sessions got:
  - `c5-author-brief.md` (sha256 `d4ff72115180261fa18091adeed75086dc3cc2867425f1d22064ca79692cee3f`);
  - `c5-reviewer-brief.md` (`174e8ed2085e6f95b4b8170851446e904983ad23d2f00aa190703128fe4cb701`).

  `c5-verifier-brief.md` (`d6d42ac12815c22289471b1f6468b7a55f5dac72889aa44b261e76388af89ce1`) and `c5-fixer-brief.md`
  (`440ad821f649e747021f4cd1b8e21d6935d22f193c38d9e4c787699d9619066b`) are frozen but were given to no session,
  because no fixer or verifier was needed. Every session after the author also got the author brief and the key's
  stored assignment (`assignment.py` sha256 `529ce840a1ca8b1c5089813eb5876f6cf09e6c4d241f16b1c87820928d0d9193`).
- **Checks and receipts:**
  - Versions were checked with `c5-precheck.py --c5 --require`, given the assignment's items (`c5-precheck.py`
    sha256 `e77b6e509097d71eba92a63271a180061e85f509b3c869a04f5a1907e523b1f1`).
  - Each approval wrote a receipt with `"gate": "C5"` and the role and round that approved.
  - `freeze.py --gate C5` (sha256 `758481413e79373b17702887ec6a33cfd2cfaf84a57d8e88a045bd52c5e17ce2`) requires that
    receipt.
- **Unchanged since the first two-arm attempt:** every one of these kit files, `novelty.py`
  (`22e86044498cf4d310c065d33a099ecbb6a941df9752716623f63a19a53fb449`), `scenario_literals.py`
  (`82c44bce76ebb5ea43c8267740db12de5e900e69cf8feab8c4a09ff76504d7ea`) and `c5-stub-rehearsal.py`
  (`49fc53570d77d50e0ee76b989e56907783bed4ab846c160cd2bbe4e6070d2bd7`). The isolation probe of 2026-11-15 was not
  repeated: the Claude Code version and the session command are the same.

**Assignments.** They are frozen as control files and passed to `freeze.py --assignment`. They hold prefix,
languages, size and coverage items only, in the form of the public authoring diagnostic's assignment:
- `control/c1-assignment.md` (sha256 `e0e6ecfbed681ee8869d47e0b3254359288c6968993ed8a0ff7e0e1a5cafc81e`): prefix
  `C1`, mainly English, one session in German.
- `control/c2-assignment.md` (`dabfc500635278ec3babe4681cf1e52c1d06be1161c2d8725d7460eef3a0809f`): prefix `C2`,
  mainly Chinese, one session in English.
- Both: 11 cases, 60–66 user messages, at least 45 days. Both are byte-identical to the first two-arm attempt's
  (same sha256).
- Each has exactly one line `- Coverage items: item, item, ...`, which `acceptance-kit/assignment.py` parses strictly.
- `launch.py` kept the author's copy with the key (byte-identical to the control file for both keys) and gave it to
  the reviewer.

**Coverage, split across the pair** (changed on 2026-11-17: with eleven cases a scenario cannot give each of the
thirteen items its own case, and cases carrying two items were a recurring dispute in review).
- Each case serves one `COVERAGE` item at most (`mood` has two cases, both its own). The remaining cases of each
  scenario are ordinary memory cases its author designs.
- **C1 covers:**
  - `stated_feeling` and `inferred_feeling`;
  - `mood`: the first case's session within 6 hours of the news's session, the second at least 49 hours after it, no
    declared feeling in between;
  - `feelings_question` and `boundary_in_conversation`;
  - `page_deletion`: a user message with emotional or relationship content;
  - `absence`: at least 14 days.
- **C2 covers:**
  - `boundary_on_page` and `reset`;
  - `manner_feedback`: accepted with its manner `kind`; no emoji kinds;
  - `from_now_on`: about the companion's manner of responding, never a task or anything tied to a time; yes in the
    same session, case in a later one; no page decision on a suggestion in between;
  - `switch`: never a named type;
  - `shared_moments`: the hard case at least 30 days and at least 5 conversation days later.
- The precheck refuses a table with an item missing or not on the assignment's line, and a case named by two items.
  `freeze.py --gate C5` refuses a pair whose `COVERAGE` keys do not cover all thirteen together.
- Both scenarios span at least 45 days (C1 68, C2 79).
- Each coverage case's criteria follow its item's template in the author brief.
- **An off-the-record stretch is present in neither scenario.** Neither declares an `EXPECT_RECORDING_P` stretch,
  and for each the precheck reports 0 intended unrecorded turns and off-the-record openings recognised 0 of 0. So no
  turn is meant to be left unrecorded in this attempt.

**Production, as the launcher reported it** (2026-11-17, 09:31–09:43 UTC; per key one full review and at most three
verification rounds, plus precheck-only fix rounds; one restart under a new key per scenario, decision 10):

| # | Session | Result (launcher's JSON) |
| --- | --- | --- |
| 1 | c1 author 1 (09:31–09:35) | `{"cases": 11, "key": "c1", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 17, "sha256": "e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5", "turns": 61}` |
| 2 | c1 reviewer, round 1 (09:35–09:36) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "cbfe9be8b17a188ee3601f97a387824adb185d0b71d820db728197d244878d61", "key": "c1", "produced": true, "receipt_sha256": "97f52910c02b9386f95c798379a83ad2282ba493e1f20c67250d843449bd6a4c", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |
| 3 | c2 author 1 (09:36–09:41) | `{"cases": 11, "key": "c2", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 20, "sha256": "a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b", "turns": 65}` |
| 4 | c2 reviewer, round 1 (09:41–09:43) | `{"approved": true, "blocking": 0, "findings": 2, "findings_sha256": "9a192be4a5a298bcd97e0b106d4c575985a1a058840ca0a6c8cbec6b93324250", "key": "c2", "produced": true, "receipt_sha256": "07247a775e2f6a20e98d70da4aeaf7c41b7755fb4989af9d005d1ba8fbabfc9c", "review_sha256": "106cc330f2d21ad0c23935787339e0930a05b8715127fade092f3f9cc6a8b765", "reviewed_sha256": "a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b", "role": "reviewer", "round": 1, "session": 1, "session_exit": 0}` |

- Four Sonnet sessions. Every one exited 0 with an empty stderr and produced its outputs.
- Both author versions passed the precheck at once, so no precheck-only fixer ran.
- Both full reviews approved with 2 findings and 0 blocking (54 and 70 seconds of session time, as seen from outside),
  so no fixer, verifier or restart ran.
- The two `review_sha256` values are equal because both `review.json` files hold the same three values (approved, 2
  findings, 0 blocking). They equal the first two-arm attempt's for the same reason.
- The 2 non-blocking findings of each review were not applied: a fix would make a new version, which would need a
  verification round.
- The launcher does not report cost, and the operator did not open the session logs, so their subscription cost is
  not known.
- After each session its working directory (a redundant copy outside the private root) was emptied with `find DIR
  -mindepth 1 -delete` without being opened. The empty directories were kept, so the launcher's numbering continues.
- The private root keeps the scenarios, reviews, findings, `rounds.json` and the logs, which the operator never
  opened.

**Final scenarios** (from the receipts):
- **C1:** `e3406727949452279e33424c53b50970107da06d3e20138cc39d350d448f53b5`, key `c1`, `c1/scenario_c1.py`. 11 cases,
  61 turns, 17 sessions, 1 page action, span 68 days, coverage 7 of 7.
- **C2:** `a2a1b6bf9c1b7f522a1b55935c56fb48db2d38d307b3e1e9a2936213218b8f6b`, key `c2`, `c2/scenario_c2.py`. 11 cases,
  65 turns, 20 sessions, 3 page actions, span 79 days, coverage 6 of 6.
- Together they cover the thirteen items.
- **Receipts:** `control/c1-review-approved.json` `97f52910c02b9386f95c798379a83ad2282ba493e1f20c67250d843449bd6a4c`
  and `control/c2-review-approved.json` `07247a775e2f6a20e98d70da4aeaf7c41b7755fb4989af9d005d1ba8fbabfc9c`. Each was
  approved by the reviewer in round 1.
- Both pass `c5-precheck.py --c5 --require` with their assignment's items on this source, with no code.

**Novelty** (`acceptance-kit/novelty.py`, prints only numbers and booleans; stop threshold **10% largest 8-gram
overlap**, as in the R4 bindings).
- **Against the public set at `6ffcbbbe`:** 21 public scenarios (every top-level `evaluations/*scenario*.py` that
  assigns `SESSIONS_LONG`, `c5-practice-scenario.py` included, and the two scenario files of attempt 5's evidence),
  plus the 15,688 64-hex strings recorded under `evaluations/` there. Result: `ok` true.

  | Scenario | Hash new | Largest overlap | All together | Distinct 8-grams |
  | --- | --- | --- | --- | --- |
  | C1 | yes | 0.08% | 0.11% | 3,640 |
  | C2 | yes | 0.11% | 0.26% | 5,319 |

- **Why a wrapper.** `novelty.py` takes earlier files only from git, so earlier unpublished and diagnostic scenarios
  were added by path. The wrapper is the first two-arm attempt's, copied unchanged: it sits outside the repository,
  imports the kit's functions unchanged and prints numbers only
  (`/home/yichen/.local/state/membrain-setup/runs/c5-attempt3/novelty_with_extras.py`, sha256
  `1574aebd4715632ede032243085841150f3575ed81bc57452d8a3deb185b2856`).
- **The ten files added, in order:**
  - the sixth attempt's three held-out scenarios (`s1`, the unused first `s2`, `s2b`);
  - the seventh attempt's two (`s1b`, `s2b`);
  - the three public C5 authoring diagnostics of 2026-11-17 (`d2`, `d3` and the first, `d1`);
  - the first two-arm attempt's two spent scenarios (`c1`, `c2`).

  The C5 files were written with the same kit and criteria templates for the same items.
- **With all 31 together:** C1 largest 6.24%, together 6.59%; C2 largest 4.96%, together 6.81%. Both hashes are new
  and `ok` is true.
- **Each added file alone:**

  | Scenario | 6th `s1` | 6th `s2` | 6th `s2b` | 7th `s1b` | 7th `s2b` | `d2` | `d3` | `d1` | spent `c1` | spent `c2` |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | C1 | 0.03% | 0.16% | 0.00% | 0.00% | 0.00% | 5.74% | 0.69% | 0.93% | **6.24%** | 0.30% |
  | C2 | 0.00% | 0.15% | 0.04% | 0.00% | 0.04% | 0.11% | 4.47% | 0.19% | 0.36% | **4.96%** |

- Every figure is within the threshold. The largest overlaps are with the scenario of the same items written under
  the same templates (C1 with the spent `c1` and with `d2`; C2 with the spent `c2` and with `d3`). The criteria
  templates fix the wording of every coverage case's "must" and "must not", which explains them.
- The earlier preparation `maturity-c5-20261117a`'s unapproved versions were not compared, because its private root
  is not opened.

**Preparation notes, as they happened.**
- **The spent scenarios' paths.** To give them to the wrapper, the operator listed the file names in the first
  two-arm attempt's private root (`c1/scenario_c1.py`, `c2/scenario_c2.py`) and passed those two files by path. They
  were never displayed.
- **A comparison inside that private root.** The operator also ran `cmp` on that attempt's three control files
  (`allowed-models.json` and the two assignments) against this attempt's. That opened files in an earlier private
  root, which the brief said not to do. Nothing was printed beyond "identical", and the three files' hashes are
  already public in that attempt's `preparation.json`.
- **Extra tests.** The provider retry's two test files were added to the focused run beyond the brief's list.
  Their counts are given separately above.
- **The persona draw.** It was computed before the commit of this binding (at 09:49:43 UTC, after both scenarios
  were final), because the binding must name it. The first two-arm attempt did the same.
- **The binding's file name.** It is `maturity-c5-execution-2026-11-17c.md`, as the lead decided. The brief's name
  `maturity-c5-execution-2026-11-17.md` is the first two-arm attempt's binding, which is left unchanged.

## Order, validity and scoring

Order is `c1`, `c2`. Strict validity, and the driver's ledger check, are required after each scenario; both
scenarios must be valid before blind scoring. The record states by count and position the `not_applicable` actions,
the host-pause turns and the retried provider interruptions that validity reports. None of them ever makes a run
invalid. First reviews, 22 independent case rechecks, conditional R5 checks, the actions digest for RC2, resolutions
and double attribution follow the unchanged protocol (runbook: `evaluations/acceptance-review/companion.md`, C5
unit). No score or expectation is adjusted manually.

## Billing

**Revalidation.** As in the seventh attempt, the lead re-reads prices and limits and records them in
`control/provider-revalidation.json` before the run; the run script refuses without it. A mismatch stops the attempt
before any call. The script checks only that the record exists and is a JSON object, so the lead's procedure
enforces the match. The lead also checks that the account holds at least the 80 CNY ceiling. `balance.py` exits 0 on
any HTTP 200, whatever the balance, and an insufficient balance would consume the attempt at its first request.

**Policy.** `evaluations/maturity-provider-policy-2026-11-14.json` (sha256
`e7b91106b206412c608b33b0f43adc1d6f7db7c19da0c05a82a620198fb5689f`, unchanged; no new policy is frozen).
- `deepseek-v4-pro` only, 80 CNY, one request in flight.
- 9/27 CNY per million input/output tokens; conservative bounds of 1,048,576 context and 393,216 output tokens.
- Each request reserves 1,048,576 × 9 + 393,216 × 27 per million = 9.437184 + 10.616832 = 20.054016 CNY, so the guard
  refuses once settled charges exceed 80 − 20.054016 = 59.945984 CNY.
- The file still carries its labels `"status": "draft_not_approved"` and `"for": "sixth maturity attempt: R4 only"`.
  The approval lives in `control/owner-approval.json`, which names the 80 CNY ceiling and this policy's sha256.

**What an interrupted send costs.** An interrupted host send (Stop rules) counts at its bound in those settled
charges. For this harness (`max_tokens` 16,384; 9 and 27 CNY per million) that bound is about **0.59 CNY, plus 0.018
CNY per KB of request body, plus 0.5913 CNY when `P`'s tool schemas are sent**:
- 16,384 × 27 + 16,384 × 9 = 589,824 micro-CNY;
- plus 2 × 9 = 18 micro-CNY per body byte;
- plus 4 × 9 = 36 micro-CNY per byte of the schemas' shortest JSON (16,425 bytes on this source, measured: 591,300
  micro-CNY).

Examples: 1.31 CNY for a 40 KB request without tools, 1.90 CNY for a 40 KB `P` request with the schemas, 3.29 CNY for
a 150 KB request. The absolute maximum is **9.879552 CNY** (1,048,576 × 9 + 16,384 × 27 micro-CNY, from a body of
about 516 KB). A host call whose three sends all fail costs **three bounds** (9.87 CNY at 150 KB).

**Interruptions eat the headroom.** At the expected 30–50 CNY on the guard's count (below), the free headroom to the
refusal point is 59.945984 − 50 ≈ 10 CNY to 59.945984 − 30 ≈ 30 CNY:
- roughly **3 to 9 interruptions at 3.3 CNY** fit (9.95 / 3.3 ≈ 3.0; 29.95 / 3.3 ≈ 9.1);
- about 6 at the 37 CNY point estimate (22.95 / 3.3 ≈ 6.95);
- only **about 3 at the top of the range**.

Running out ends the attempt with `reservation_limit` at the next reservation: the guard refuses the request before
HTTP and blocks the ledger.

**Expected conservative charge** (guard's count), from the seventh attempt's 0.232 CNY per scenario-turn for both arms
(28.785141 CNY for 124 turns):
- This attempt's 126 turns (C1 61, C2 65) give about **29 CNY**.
- With the plan's unverified 25% companion uplift, about **37 CNY**, plausibly 30–50. The uplift covers more tool
  rounds in `P` (manner feedback, persona, boundaries, notes with feelings and moments), the relationship block of up
  to 2,200 characters and the mood line.
- The first two-arm attempt counted 24.473709 CNY for 265 settled requests over 61 + 53 turns of `P` and 61 of `F`,
  about 0.14 CNY per arm-turn. That is consistent with this estimate.
- Headroom to the refusal point is about 1.6× (59.945984 / 37) without interruptions; each interruption takes its
  bound from it.
- The real bill was about a sixth of the guard's count in the seventh attempt, and about a third in the first two-arm
  attempt (8.33 CNY, in peak hours).

**Not included:** the subscription sessions (four for the scenarios, already used; 35–45 for scoring).

## Stop rules

As in the seventh attempt, except for transient provider failures.

**What stops further work:** a provider failure other than a transient one, a guard refusal, invalid evidence, a
reached cap, a degraded harness (including a `failed` page action), a frozen input that changed, an existing run
directory, or a driver error. No new scenario starts after a failed or invalid one, and no stopped ledger is
reopened.

**A transient provider failure is retried (changed from the seventh and the first two-arm attempts).**
- **What counts as transient:** a host send that ends in a transport timeout or a connection or protocol error; one
  the provider answers with HTTP 429, 500, 502, 503 or 504; or one it answers with a 2xx whose complete body holds no
  billing JSON (only whitespace or empty lines, not JSON, or JSON without `usage`).
- **How it is charged:** at a bound true for that request, instead of the 20.054016 CNY reservation. The bound is
  `min(1,048,576, 2 × body bytes + 4 × tool-schema bytes + 16,384)` input tokens at 9 CNY per million plus the
  request's 16,384 output tokens at 27. That is about 0.59 CNY plus 0.018 CNY per KB of body plus about 0.59 CNY with
  `P`'s schemas, at most 9.879552 CNY (Billing above and [billing control](evaluation-billing.md)).
- **How it is retried:** the ledger stays open, and the harness sends the same request again after 30 and then 120
  seconds. A host call has three sends at most, each counted against the host call cap.
- **When it stops:** a host call that fails on all three sends costs three bounds, and the third interruption
  blocks the ledger and stops the arm as before.

**Still fatal at once:**
- any other HTTP status (501, 505 and the other 5xx included);
- a 2xx whose usage is present but cannot be settled (inconsistent or malformed usage, an unexpected response model,
  completion tokens above `max_tokens`);
- a guard refusal (`reservation_limit` included, when interruptions have used up the headroom);
- an unknown failure.

**A 400 is fatal too, and the harness is exposed to one.**
- The provider's thinking-mode guide says that with `tools` the `reasoning_content` must be passed back in all
  subsequent requests, or the API answers 400.
- `P` sends it back only within a turn's rounds, never for earlier turns of the session
  ([`c5-harness.md`](c5-harness.md#harness-events-stops-and-the-log)).
- Past runs got no 400, the first two-arm attempt's 265 requests included. If the rule is enforced, the first `P`
  request after a turn with a tool call (or already a session's second turn) stops the attempt early in its first
  scenario. That happens after a few turns' spend, with that request's reservation kept on the guard's count.
- The call shape is frozen and is not changed for this.

**The ledger check.** A mismatch between the ledger's interrupted requests and the interruption records (the
driver's ledger check after validity) is a harness defect and makes the scenario invalid.

Nothing else is retried automatically.

**Not a stop:**
- a retried provider interruption (listed by validity per run with its position, code and the delay it added, never
  a harness event);
- a `not_applicable` page action (`page_refused` included);
- a turn left unrecorded while a pause was in force (the host's or the product's own, decision 6);
- a timed pause the host asks for (a tool error).

The host behaviours that still end a run as invalid are listed in decision 6. A second refused first, second or
resolution review stops scoring for the owner. No score is changed by hand. No recharge, no retry beyond the bounded
resend of an interrupted host request, no R4 unit, no automatic further attempt.

**How to stop early.** If the lead must stop a running attempt (for example on a cost forecast or a hang), the only
way is SIGTERM to the driver's process alone (`acceptance-attempt-driver.py run`).
- The driver forwards it to the runner's supervisor, which blocks the ledger and stops its arms.
- `run-live.sh` then carries out its step 6: the final balance, the cleanup of each run directory, the port check and
  `execution-done`.
- Killing `run-live.sh` or the whole session or process group skips that step and is not allowed.

## Running the attempt (for the lead, after approval; not run in preparation)

One script, `/home/yichen/.local/state/membrain-setup/runs/c5-attempt3/run-live.sh` (sha256
`d09bd7371302e7076e691801df656c9bf2f9ae19106671fa61bfa770c96f1326`), runs the attempt with `/home/yichen/.local/state/membrain-setup/runs/c5-attempt3/balance.py` (sha256
`b34790e6e43f37d4050538e563f56acc83e6fb1114374fcda534be28e61ad7a1`).
- `balance.py` is a byte copy of the seventh and first two-arm attempts'. It was tested in preparation only without a
  key: it printed `{"error": "KeyError"}` and exited 1, with no request.
- Both files are outside the clone and the manifest. The freeze review compares them with this section.
- The script is the [first two-arm attempt's](maturity-c5-execution-2026-11-17.md) script with these changes only:
  `R`, the clone, `PRIV="$CLONE/evaluations/.maturity-heldout-c5-20261117c"`, the ledger's `run_id` and
  `C5_ATTEMPT_ID` set to `maturity-c5-20261117c`, and "first" changed to "second" in its header comment.

**What it keeps from the first two-arm attempt's script.** Those changes from the seventh attempt's script are all
kept:
- After the head, clean-tree, manifest and freeze-review checks, it refuses unless `control/owner-approval.json` and
  `control/provider-revalidation.json` exist and each holds a JSON object.
- The key is validated and the first balance read **before** the ledger is created, so a refused key or balance
  leaves no ledger.
- The key is unset on every refusal after it is exported.
- The ledger's policy hash is checked to be 64 hex characters before it is exported.
- The balance watcher waits for `runs/c2-P` (`balance-after-c1.json`).

**Unchanged from the seventh attempt:**
- the refusals before the ledger exists: the head and the manifest's sha256 as `control/preparation.json` records
  them, a clean tree, a freeze review with `execution_may_start` true, ports 8893 and 55533 free, at least 5 GiB free,
  no ledger, no `runs/`;
- the key read from the main checkout's `.env` into the environment only;
- balances read in-process;
- the driver line: it runs the manifest's C5 pair, `c1` then `c2`, `P` then `F` within each.

The new rules (the retry, the interruption records and the ledger check) live in the harness and the driver, not in
the script. Started detached:

```bash
setsid nohup bash /home/yichen/.local/state/membrain-setup/runs/c5-attempt3/run-live.sh \
  > /home/yichen/.local/state/membrain-setup/runs/c5-attempt3/run-live.out 2>&1 < /dev/null &
```

The script, verbatim:

```bash
#!/bin/bash
# The second two-arm companion attempt's live run (maturity-c5-20261117c, gate C5 only), as the binding's "Running the
# attempt" block prescribes. For the lead, after the owner's approval and the independent freeze review; not run in
# preparation. Start it detached (a background shell is killed after two hours):
#   setsid nohup bash /home/yichen/.local/state/membrain-setup/runs/c5-attempt3/run-live.sh \
#     > /home/yichen/.local/state/membrain-setup/runs/c5-attempt3/run-live.out 2>&1 < /dev/null &
# It writes progress to control files only and prints no key, no scenario text and no exception text.
set +x +v; set +H; HISTFILE=/dev/null; unset HISTFILE
R=/home/yichen/.local/state/membrain-setup/runs/c5-attempt3
CLONE=$R/clone
PRIV="$CLONE/evaluations/.maturity-heldout-c5-20261117c"
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
print(json.dumps(budget.create_ledger(sys.argv[1], run_id="maturity-c5-20261117c", limit_cny=policy["proposed_limit_cny"],
                                      endpoint=policy["endpoint"], models=models)))
PY
[ -s "$PRIV/control/ledger-initial.json" ] || { unset DEEPSEEK_API_KEY; echo "refused: ledger not created"; exit 96; }

# 4. The attempt's binding variables.
export C5_ATTEMPT_ID=maturity-c5-20261117c C5_BILLING_LEDGER="$PRIV/control/ledger.json"
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

The `.env` line must be the plain form `DEEPSEEK_API_KEY=value` (no quotes). The driver refuses to start unless:
- the manifest is the one below and every frozen hash matches;
- the ledger is unblocked and bound to this attempt and policy;
- the persona entry is the draw of the attempt id.

Its stderr holds only paths, keys and exit codes. The run directories hold scenario content and are never opened by
the operator.

## Before spending, during and after

As in the seventh attempt, with the manifest `evaluations/.maturity-heldout-c5-20261117c/control/manifest.json`, made
by `freeze.py --gate C5 --binding evaluations/maturity-c5-execution-2026-11-17c.md --allowed-models
evaluations/.maturity-heldout-c5-20261117c/control/allowed-models.json --assignment
c1=evaluations/.maturity-heldout-c5-20261117c/control/c1-assignment.md --assignment
c2=evaluations/.maturity-heldout-c5-20261117c/control/c2-assignment.md`.
- Its one pair has gate `C5`, and there is no `practice` mark.
- Each scenario is prechecked with its assignment's items, and the pair covers all thirteen.
- Its file count, sha256 and `persona` are recorded in the freeze review and in `control/preparation.json`.

**Before spending**, the lead records:
- the owner's approval (`control/owner-approval.json`, naming the 80 CNY ceiling and the policy's sha256);
- the provider revalidation (`control/provider-revalidation.json`);
- the initial balance (at least the ceiling).

The run script records the ledger's initial hash.

**After the run**, whatever its result:
- ports 8893 and 55533 are closed, and no process of the attempt's profiles is left;
- the record states, by count and position, each run's `not_applicable` actions, host-pause turns, and retried
  provider interruptions (with the delay per session);
- it states the ledger check, the persona-mirroring report, the host-diligence table and the memory-remark counts.

## What was measured beforehand

**The host probe of 2026-11-17** (published in the [first two-arm attempt's evidence](evidence/maturity-c5-attempt-stop-2026-11-17/))
ran `deepseek-v4-pro` with the plugin path's standing prompt on public situations, each twice. It is not part of the
acceptance result.
- The host called the expected tool in 2 of 2 trials each for:
  - a boundary request (English and Chinese);
  - a manner comment (English and Chinese);
  - a request to switch personality ("surprise me");
  - a stated feeling (affect basis reported) and an inferred feeling (basis inferred);
  - a hard shared moment (kind hard, with the feeling) and a playful one.
- It answered "do you have feelings?" without claiming real feelings.
- The boundary tool was used from its own tool description, which the server's instructions do not name. The
  review's finding m6 therefore needs no product change.
- A "from now on" request for a task tied to a time ("check in with me the evening before my exams", "quiz me on
  vocabulary every morning") was saved as a commitment note in 4 of 4 trials and never proposed as a persona change.
- A request about the manner of responding ("when I say I'm tired, listen first before giving advice") was proposed
  and, after the yes, confirmed in 2 of 2. The C5 briefs therefore require the second kind.

**The hard-moment probe on this runtime** ([record](hard-moment-and-provider-retry-2026-11-17.md)): three trials each
on public messages. It is not part of the acceptance result either.
- A bad night told in Chinese and then thanks for staying through it was saved as a hard shared moment in 3 of 3.
- The same in English: 3 of 3.
- A reconciliation after the user was upset with the agent: 3 of 3.
- A long day with a small consolation (control): 0 of 3.
- In all six "bad night" trials the moment was saved at the message that told of the night, before the thanks.

## Limits a C5 result will have

State these in the record whatever the result:
- **A reply produced on a retry is not distinguished in scoring.** When a host send was interrupted and the same
  request was sent again, the reply scored is the one the retry returned; reviewers are not told, and no score
  depends on it.
  - Validity lists every interrupted send and retried host call by position and code, and the record states them.
  - The retry repeats the request exactly, but the model's answer to it can differ from the answer the interrupted
    send would have produced.
  - In `P` the retry's waits run on the scenario clock, while `F` has no clock. Validity reports the delay the
    interruptions added per session (failed sends plus waits, up to about 33 minutes for one host call). The record
    names the sessions whose scenario clock moved this way, because companion items such as a mood "within hours"
    are time-sensitive.
- **The retry is untested against the real provider.** No interruption has occurred under the new rule. It is
  tested with a fake transport only, and the stub rehearsals run without the guard.
- **Two billing assumptions.** The interruption bound rests on two assumptions:
  - that a prompt never has more tokens than bytes, which the billing review checked against the provider's
    published tokenizer;
  - that `max_tokens` also caps reasoning tokens, which the provider's documentation implies without stating it. If
    it were false, up to 10.17 CNY per interrupted send would be uncounted ([billing review](evidence/hard-moment-and-provider-retry-2026-11-17/provider-retry-review.md)).
- **The host model's earlier reasoning is not passed back.** With `tools`, `P` sends `reasoning_content` back only
  within a turn's rounds. Earlier turns of a session are sent without it, and `F` is never offered tools
  ([`c5-harness.md`](c5-harness.md#harness-events-stops-and-the-log)). The provider's thinking-mode guide asks for it
  in all subsequent requests. A result is therefore of the host model as this emulation calls it, which may differ
  from a client that passes the reasoning back. If the service enforces the rule, the attempt stops with a 400
  instead (Stop rules).
- **A tool call in a turn's last round leaves the reply empty.** A turn's last round offers no tools (after three tool
  rounds or six calls). If the host answers that round with tool calls and no text, the reply is empty, it is not
  retried, and validity refuses the run. This is a theoretical gap named by the first two-arm attempt's freeze
  review; it did not occur there.
- **The hard-moment definition may be eager.** The wider definition may also make the host save as a hard moment a
  bad day confided in earnest. The probe did not measure how often, and no real plugin host was tried.
- **Persona cases are judged against the user's request, not the block** (decision 8). The persona-version list says
  only "in the conversation" for a change made through the host's tool: the records both arms share do not show
  whether it was a switch or a confirmed change.
- **Coverage that depends on the seeded type is avoided, not removed.** Comments about emoji, and named types, are
  excluded because their effect depends on the type drawn. With one seeded type (`intj`), some manner kinds may still
  change less in some types than in others.
- **`F` is told about resets; `P`'s host is not** (review finding m4). `F`'s page line says "relationship reset on
  DATE" and "feelings cleared on DATE". `P`'s host only finds the layers gone: no product text tells it a reset
  happened. This tilts reset cases toward `F`.
- **Emulation limits on tool use** (finding m5). A turn has at most three tool rounds and six tool calls. A
  consolidation batch, asked for before the reply to a session's first message, takes two of those rounds.
- **A month-only date delays mellowing** (finding m8). A hard moment the host dates only to a month counts from that
  month's last day, which can put the 30 days past the scenario's case; the case's score then reflects that.
- **Probes the plan named that are not in `COVERAGE`** (finding m10): the same persona probe in three or more
  sessions, and boundary cases after a boundary's removal or raised by the user. They stay dropped for this attempt;
  a scenario may still contain them, unscored as coverage.
- **RC2 cannot clear a mark caused by a record without sources** (finding m12). When a deletion did not reach a host
  note that cites no message, a `not_removed` claim would need a content ref the resolution reviewer does not have,
  so such a mark stands.
- **Type 8 after derived-record actions** (finding M4) is judged by the RC2 rule of decision 9. Only `delete_message`
  makes type 8 unambiguous in both arms, which is why item 5 deletes a user message.
- **A deletion of a message `P` never recorded** removes it from `F`'s history only (finding m3). Validity accepts
  that one asymmetry, and neither arm can bring the message back from memory.
- **One host model under emulation.** `deepseek-v4-pro` through the harness's emulation, not Claude Code or any real
  host; one seeded personality type; two scenarios. A pass or fail may rest on one or two judgements, as R4's did.
- **R4 and C5 are on different runtimes.** R4's pass was measured on runtime `a85ca152`, older than this attempt's
  `3afc0dda`. The two results do not together qualify one release runtime (decision 7).
- **Partial blinding.** With two arms, a memory remark in one reply ("Saved.", a pause notice, a mention of a
  suggestion on the page) can reveal which assistant wrote both replies of a case. `remarks` counts them from a
  fixed list, and the seventh attempt showed that the count undercounts.
- **The yes in one conversation.** Every "from now on" confirmation in the scenarios is given in the same
  conversation. A yes in a later conversation is not tested (the product does not apply it).
- **`not_applicable` actions thin the coverage.** An action that found nothing (no suggestion, no recorded feeling)
  still counts as the plugin path's behaviour and is scored. But the requirement it was meant to exercise (for
  example a page acceptance of a manner suggestion) was then not exercised. The record names each such action, and
  which `COVERAGE` requirement it served.
- **`F` learns the page from a fixed line.** The reference has no memory layers. It learns boundaries set on the page,
  resets, cleared feelings, the support style, the familiarity limit and the mood pin from one line in its system
  prompt. It has no mood or familiarity of its own, and sees deletions only as missing history. Its scores and
  critical errors (which bound `P`'s host-caused allowance) are those of a host given that line, not of another
  memory.
- **Host labelling decides type 6.** The host sets a feeling's basis. One inferred feeling saved as "said" makes
  memory present it as said, which attribution counts as memory-caused and which fails C5.
- **Later review rounds are not independent of the first review** (decision 10). A verifier must accept every change
  the round-1 reviewer instructed, and checks only the fixed fatal classes beyond that; what the one reviewer missed
  outside those classes, or decided wrongly, stays. The criteria templates fix the wording of every coverage case's
  "must" and "must not" in advance, so the scenarios' judgement of those items is the templates', not each author's.
  A template that tests the wrong thing would err the same way in every case of its item.
- **Each scenario had one reviewer.** Both scenarios were approved by their one full review (54 and 70 seconds of
  session time, as seen from outside), with no verification round. Each scenario's fitness beyond the precheck rests
  on that one Sonnet reading.
  - Its scan of every user message cannot be checked from outside without reading the review.
  - Each review's 2 non-blocking findings were not applied.
  - The kit offers no second reading of an approved version without a fixer making a new version, as the first
    two-arm attempt's freeze review found.
- **Each item is tested in one scenario only.** The thirteen items are split across C1 and C2 (seven and six), so
  each has one case (two for the mood) in the attempt, and an item is tested in one language mix only.
- **No off-the-record stretch.** Neither scenario declares one, so this attempt does not exercise a pause on the
  user's words, the recording of its resume, or honesty about an unrecorded stretch.
- **The automatic message checks are narrow.** The precheck refuses user messages under 16 characters (6 in CJK) and
  messages that open with a reaction from a fixed list. A reaction later in a message, one worded otherwise, and a
  message that assumes what the companion said are left to the reviewer and verifiers.
- **What the scenarios cannot check from text.** Several things rest on the scenario reviewer's reading, not on the
  precheck: that a declared message really states a feeling; that a "from now on" request is about the manner of
  responding and not a task; that no message names a duration for a pause; and that the host makes the proposal the
  user's yes answers.
- **The cost estimate is not bounded above.** Its basis (0.232 CNY per scenario-turn) comes from runtime `a85ca152`,
  and the uplift is unverified. The script runs `c2` after `c1` without a decision point. A run that reaches the
  refusal point stops with no C5 result.

## Filled in by the run

Nothing above this section changes after freezing. `<owner's approval (words, date, the ceiling and the policy hash
it names); provider revalidation and balances; ledger initial hash, requests and charge; retried interruptions and
the ledger check; execution summary; not-applicable actions and host-pause turns; scores, attribution, memory
remarks, host-diligence table, gate-c5.json and the final review; link to the record>`.
