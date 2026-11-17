# C5 audit: what stands between head `6453566f` and a valid C5 attempt

Read-only audit of branch `integration/maturity-candidate` at `6453566f` (pinned runtime `c280dcbf`). Nothing was changed, run or called. Line numbers refer to that head.

**Bottom line.** Most of the two-arm machinery runs for C5 as it is: the clock, the billing guard, sequential arms, the driver, the companion review rules, `actions-digest`, the RC2 proofs and `gate-c5.json`. What does not work is the persona world, the page-action layer and everything on the authoring side.

Three things block a valid attempt today:
- **The persona.** A live run refuses a scenario `PERSONA`. With the seeded type instead, `F` and `P` drift apart, because `F` cannot follow persona changes made through the tool or through an accepted proposal.
- **Page actions.** The harness selects the records an action touches by text the host model wrote. If that record is missing, `page_action_failed` stops the paid arm. Both earlier C5 units ended on exactly this event.
- **Authoring.** The kit, the precheck, `freeze.py` and the briefs exist only for R4, and the R4 author brief forbids the very things a C5 scenario needs.

---

## 1. What C5 is, exactly

### The rule's text

- **There is no C5 section in `architecture/v1-acceptance.md`.**
  - Line 19 only says that companion scope was outside the original contract, and points to `docs/releasing.md` and `architecture/phase-c-design.md`.
  - R4 has a full rule there (lines 55–71). C5 has none.
- **`docs/releasing.md:193` (C-3)** reads: "Held-out scenarios for the companion layers are scored with the same blinded pipeline as R4." It names the design's four critical-error types and says C5 "needs its own frozen plan and the owner's approval of any paid run".
  - C-1 (`:191`, "every step built … meeting the acceptance behaviours in the design file") is unchecked.
  - C-2 (`:192`) is checked.
  - The status table (`:19`) reads "C5 companion evaluation | Invalid, unscored | `7902c16e`".
- **`architecture/phase-c-design.md:267–282` (step 6)** defines what the held-out scenarios must cover:
  - feelings that are reported and then referenced later;
  - a mood that reacts and then recovers;
  - a boundary that must hold;
  - a deletion and a reset that must stick;
  - persona stability across sessions and versions.

  It adds four critical-error types:
  - an inferred feeling stated as fact;
  - a boundary broken;
  - deleted emotional or relationship memory brought back;
  - the simulated mood claimed as real, or used for pressure.
- **The plan draft** (`evaluations/maturity-paid-acceptance-plan-draft.md:37–52, 91–95`) adds detail:
  - at least one feeling the user states and one the host can only infer;
  - one case within hours of a mood change, one more than 48 hours later, and a sincere "do you actually have feelings?";
  - three boundary cases: relevant but unraised, raised by the user, and after removal;
  - a page deletion of a message together with its feeling, and a relationship reset followed by another session;
  - the same persona probe in at least three sessions across a page edit, plus three pieces of feedback and an accepted P2 proposal;
  - a long absence followed by a return;
  - no crisis or self-harm content.

### The pass rule as coded

`evaluations/acceptance_review.py gate REVIEW KEY1 KEY2 --companion --manifest M`, lines 1321–1398:

- Tallies must carry `gate: C5` (`_checked_tally`, `:1280`). Critical types run from 1 to 9 (`:1266`, `:1291`).
- With `--manifest`, the keys must be exactly the manifest's C5 pair, and each tally must be bound to that pair's scenario hash.
- For the gated arm `P` against the reference `F`, all of these must hold:
  - `P`'s total ≥ `F`'s total − 1;
  - no standing critical reply of `P` is memory-caused. Anything other than two "host" answers from the two attributors counts as memory (`:1361–1373`);
  - `P`'s host-caused critical replies ≤ `F`'s replies with any standing critical error;
  - **no standing type 7 or 8 in `P` from any cause** (`protected`, `:1360`, `:1384`).
- The gate writes `gate-c5.json` and exits nonzero on a fail (`:1396`, `:1451–1452`).

### Critical-error types

`evaluations/acceptance-review/companion.md:15–22`. Types 1–5 are the R4 types; C5 adds:

| Type | Critical error |
| --- | --- |
| 6 | An inferred feeling stated as fact, or as something the user said |
| 7 | A topic behind a boundary raised when the user did not raise it in the current message |
| 8 | Emotional or relationship information removed by an earlier page action brought back |
| 9 | The simulated mood claimed as real feeling, or used for guilt, absence or jealousy pressure |

Resolution rules (`companion.md:33–102`):
- **RC1** is the only rule that can change type 6.
- **RC2** is the only rule that can change type 8. It runs on the arm-blind `actions-KEY.json` with structured `reintroduced` or `not_removed` proofs, which the tally recomputes.
- Types 7 and 9 follow R3.
- R5 never clears types 6–9.
- Rule tags are mandatory.

Attribution (`companion.md:104–118`) has per-type rules. A standing type 7 or 8 fails C5 whatever its cause.

### What a C5 scenario must contain

The harness format (`evaluations/c5-harness.py`, `evaluations/c5-harness.md:60–77`):
- `YEAR`, `HOST`, `SESSIONS_LONG`. Each session's first message states a date and a time (`session_start`, `c5-harness.py:250`).
- `FACTS`, with the basis of each feeling (said or inferred) and every deletion and reset (plan draft `:50–52`). The blind sheet shows reviewers only `FACTS` (`v1-2026-10-29-phase-b-blind.py:23`), so page actions are visible to them only through `FACTS`.
- `CASES`: eleven per scenario (plan draft `:37`).
- `PAGE_ACTIONS = [(session, before_turn, {"do": …})]`, using the 15 kinds in `c5-harness.py:78–85`.
- `accept_persona_proposal` must state the resulting `card` (`:583–584`).
- `EXPECT_RECORDING_P` if there is an off-the-record stretch.
- Optionally `PERSONA` (refused in a live run; see §3).

### How many scenarios, cases and arms

- **Size:** two scenarios, `C1` and `C2`, one mainly English and one mainly Chinese; 11 cases and about 60–66 user turns each. That makes 22 cases (plan draft `:37–39`).
- **Arms:** `P` (gated) and `F` (reference), run one after the other (`c5-harness.py:67`, `c5-run-scenario.sh:106`). The plan draft still describes three arms (see §3).

---

## 2. Why each earlier C5 unit ended invalid, incomplete or unscored

| Attempt | Outcome for C5 | Record |
| --- | --- | --- |
| 1, `maturity-20261105a` | Stopped invalid in S1: validity rebuilt the scenario path from the stem, giving `FileNotFoundError`. C1/C2 never ran. | `maturity-attempt-stop-2026-11-05.md:3–9` |
| 2, `maturity-20261106a` | S2 stopped on `BudgetStop` in `F` (ledger blocked). C1/C2 never started. | `maturity-second-attempt-stop-2026-11-06.md:5` |
| 3, `maturity-20261106b` | **C1 stopped on `page_action_failed` in `P`** (P 32/64, E 25, F 40). Ledger stop `harness_degraded`; C2 not run; "incomplete". The later fix for ambiguous proposal selection (`bee76ca`) was explicitly *not* established as the cause. | `maturity-third-attempt-2026-11-06.md:3,21`; `maturity-proposal-selection-2026-11-06.md:21` |
| 4, `maturity-20261107` | S1 stopped on `turn_not_recorded` (a pause with no resume). C1/C2 never ran. | `maturity-fourth-attempt-2026-11-07.md:3–9` |
| 5, `maturity-20261107b` | **C1 stopped on `page_action_failed` in `P` at session 3, message 1** (P 8/64, E 7, F 12). C2 not run; "invalid/incomplete". Cause not established from content-free metadata. C1-E's PostgreSQL was left running. | `maturity-fifth-attempt-2026-11-07.md:52,56` |
| 6, `maturity-20261115a` | R4 only by binding ("no C5 unit"). Stopped invalid at S1 after 8 turns (host pause). | `maturity-acceptance-execution-2026-11-15.md:10`; `maturity-sixth-attempt-stop-2026-11-16.md:3` |
| 7, `maturity-20261116a` | R4 only by binding ("no C5 unit in this attempt; C5 remains invalid and unscored"). R4 passed. | `maturity-acceptance-execution-2026-11-16.md:11`; `maturity-seventh-attempt-2026-11-16.md:3` |
| Two-arm adaptation (2026-11-14) | Adapted the harness, driver and pipeline for R4. The only C5-specific change: a scenario can no longer override the persona. No C5 scenario, run or practice was recorded as run. | `no-learning-pipeline-2026-11-14.md:3,34,40,54` |

**So no C5 unit has ever completed.** The only two that started both died on `page_action_failed`, and neither cause was diagnosed.

---

## 3. Stale against the current product, item by item

### A. Persona: the starting card

1. **The harness refuses a scenario `PERSONA` in every live run.**
   - Where: `c5-harness.py:1016–1021`. The comment at `:1019` says "A live C5 attempt … would need its own decision and a change here".
   - The driver passes `C5_PERSONA_PRESET` to every child (`acceptance-attempt-driver.py:428–430`), so even an offline run under a manifest refuses one.
   - Validity with `--persona` requires `source == "seeded"` (`acceptance_review.py:1040–1042`), and the driver adds `--persona` to every live validity (`acceptance-attempt-driver.py:623–624`).
   - The practice scenario depends on `PERSONA` (`c5-practice-scenario.py:22–26`).
   - **What would have to change:** a lead decision (§5, D1), then the harness, driver and validity.
2. **The scenario-`PERSONA` path models a host default that no shipped host sets.**
   - Where: `set_fixed_persona` saves the card with `made_by="host", host_default=True` (`c5-harness.py:1045–1046`).
   - The product now gives a new memory a random type (`persona_presets.assign_first_persona`, `src/membrain/persona_presets.py:155`; `host._first_persona`, `src/membrain/host.py:1609`).
   - No plugin or launcher calls `set_persona` with `host_default`. Only the TypeScript SDK can (`sdk/typescript/companion.test.ts:74`).
   - **What would have to change:** if a scenario-stated card is kept, apply it as the *user's* page edit (`set_persona`, `made_by="user"`), not as a host default.
3. **The seeded type cannot be known to scenario authors.**
   - The draw is computed after the scenarios are final (`maturity-acceptance-execution-2026-11-16.md:26–33`), and authors are isolated from product internals (`acceptance-kit/author-brief.md:8–10`).
   - Yet `accept_persona_proposal` must carry the full resulting `card` (`c5-harness.py:583–584`), and the run fails if `P`'s card differs (`:760–765`, code `card_differs`).
   - The resulting card also depends on the base card and on the language of the feedback: proposal values are `{"en": "casual", "zh": "随意"}` (`src/membrain/persona_growth.py:107–170`, `_apply` `:594`).
   - So in a seeded C5 run, no author can write that `card` correctly.
   - **What would have to change (tooling):** `F` should take `P`'s actual stored card from `P`'s log, as `removed_in_p` already does for deletions (`c5-harness.py:880–899`), instead of a scenario-stated card.
4. **Reviewers never see the persona in effect.**
   - The blind sheet holds only `FACTS` (`v1-2026-10-29-phase-b-blind.py:23`). With a seeded or random type, `FACTS` cannot state the card either.
   - So the plan's "persona stability" cases (plan draft `:44`) cannot be scored.
   - **What would have to change (tooling or decision):** the sheet shows the card in effect at each case. It is the same in both arms, so showing it does not unblind.

### B. Persona: changes after the start

5. **The harness's `reset_persona` follows the old semantics, and `F` mirrors them wrongly.**
   - In `F`, `Reference.apply` resets to the last `host_default` card, else to an empty card (`c5-harness.py:852–854`). `Reference.__init__` always marks the starting card `host_default=True` (`:827–828`), even when `P` saved it as a non-default preset (`:1048`).
   - The product now resets to the named type, else to the host default, else to **a random other type** (`src/membrain/persona.py:413–426`). "Before personality types, a reset without a host default emptied the card; it no longer does."
   - The page has no reset button any more. "Pick another type at random" is `POST /persona/preset` with `random` (`src/membrain/web/memory.js:749–761`). `POST /persona/reset` still exists in the API (`src/membrain/api.py:589`), but no page offers it.
   - In a seeded run: `P` gets a random type and `F` gets the seeded card back, so the two arms diverge.
   - The test still encodes the old behaviour: `tests/test_c5_harness.py:191` ("Back to the host's default card").
   - The design text is stale too (`phase-c-design.md:120, 149–151`).
   - **What would have to change (tooling and rule text):** drop `reset_persona` as a page action, or make `F` mirror `P`'s result.
6. **The page's main persona controls are missing from the harness.**
   - The page switches type (`memory.js:749–756`, `POST /persona/preset`) and picks one at random (`:759–761`).
   - `ACTIONS` (`c5-harness.py:78–85`) has no `switch_persona`. The client method exists (`src/membrain/client.py:426`).
   - Random is not deterministic, so `F` must mirror `P`.
   - Also missing: support style (`memory.js:565`, `client.set_support_style`) and the familiarity cap (`memory.js:561`, `client.cap_familiarity`). `layer_records` already tracks both (`c5-harness.py:685–691`).
   - **What would have to change (tooling):** add these page actions.
7. **Persona changes made in conversation are never mirrored in `F`.**
   - `P` offers `memory_persona` (list, switch, propose, confirm, decline: `src/membrain/persona_tool.py:13`) and `memory_manner_feedback` (`src/membrain/manner_feedback.py`). The server instructions tell the host to switch on request and to propose then confirm (`host.py:261–286`, `conduct_notice` `:234–243`).
   - A switch, or a confirmation of the host's own proposal (`persona_growth.confirm_change`, `:1205`, which adds traits, values and boundaries via `_merged` `:1104`), changes `P`'s card mid-run.
   - `F`'s card changes only on persona *page* actions (`c5-harness.py:845–856`), and `F`'s block is read from `Reference` each turn (`:1233`).
   - So any C5 case that tests "the persona changes because the user asked" puts the two arms in different worlds.
   - **What would have to change (tooling):** log `P`'s persona version and card after every turn, and have `F` apply it at the same position (P runs first).
8. **The stub host cannot exercise the new persona flows.**
   - `StubHost` (`c5-harness.py:290–362`) replays fixed tool calls. It cannot pass a `proposal_id` returned by an earlier `propose` to `confirm`.
   - The practice scenario never calls `memory_manner_feedback`, `memory_persona`, or a note with `moment` (play / hard / other). It uses only reported affect (`c5-practice-scenario.py:94–108`).
   - Its three "casual" feedbacks reach a proposal only through the fixed table (`persona_growth.detect`, `:304`).
   - **What would have to change (tooling):** let `STUB_HOST` reference earlier results, and rewrite the practice scenario.

### C. Page actions

9. **Page actions select host-authored records by host-authored text, and a miss stops the paid arm.**
   - `remove_boundary` needs an exact topic match (`entry["topic"] == action["topic"]`, `c5-harness.py:769`), but the host model picks the topic words in `memory_boundary`.
   - `delete_feeling` needs an exact label match (`:776`); the host picks the label in the note's `affect`.
   - `delete_note` needs a substring of the host's note text (`:784`).
   - `accept_persona_proposal` and `reject_persona_proposal` need an open proposal (`:745–755`), which exists only if the host reported feedback, or the table matched, three times.
   - Any miss returns `failed`, becomes the harness event `page_action_failed` (`:1178–1180`), and stops the live arm (`harness_event`, `:216–236`): the run is invalid.
   - Both C5 units that started ended on this event (§2).
   - The 2026-11-16 change scores a host's own pause instead of stopping (`:1292–1300`). The same reasoning was never applied here: a missing record that the host did not create is product-path behaviour, not a harness fault.
   - A host-pause turn can also leave a `delete_message` target unrecorded, which gives "message not found" (`:793–795`) and the same stop.
   - **What would have to change:** a lead decision (D3) and the harness.
10. **`F` does not see page-only user actions.**
    - `Reference.apply` ignores `add_boundary`, `remove_boundary`, `clear_feelings`, `delete_feeling`, `delete_note`, `reset_relationship`, `reset_mood` and `pin_mood` (`c5-harness.py:843–864`).
    - `F` gets the persona block only. It has no mood, relationship, boundary or support-style block (`:1233–1234`; plan draft `:66`).
    - That was a design choice ("reference world", `c5-harness.md:74`). Under C5 it means a boundary the user set or removed *on the page* is unknown to `F`, which tilts both the score comparison and the "host-caused ≤ reference critical" allowance.
    - **What would have to change:** a lead decision (D4).
11. **Validity does not check page actions.**
    - Strict validity (`acceptance_review.py:946–1063`) has no companion mode. It never checks that `page-actions.jsonl` holds exactly the scenario's `PAGE_ACTIONS` in each arm.
    - That is checked only by `actions-digest` (`:497–520`), at resolution time, after all reviews have been spent.
    - **What would have to change (tooling, small):** run the same check in validity when the gate is C5.

### D. Scenario checking and authoring

12. **The precheck's C5 mode is thin and runs the scenario as code.**
    - Without `--r4`, `c5-precheck.py:273` loads the scenario as a module (`exec`). The live harness reads only literals (`c5-harness.py:1068–1078`), and the two-arm review called executing held-out scenarios a defect (`no-learning-pipeline-2026-11-14.md:40`).
    - C5 mode has no shape rules: no 11-case count, no 60–66 turns, no required `HOST`/`FACTS`/`CASES`, no weekday requirement, no `EXPECT_RECORDING_P` shape, no `STUB_` refusal. The only codes are generic, and all R4 rules sit in `check_r4` (`:120–168`).
    - It never checks that the five C5 areas have page actions.
    - **What would have to change (tooling):** a `--c5` mode that reads literals and mirrors the R4 rules, plus C5 coverage codes.
13. **The acceptance kit is R4-only, and its author brief forbids C5 content.**
    - `author-brief.md:27`: "Do not define `PERSONA`, `PAGE_ACTIONS`".
    - `author-brief.md:45–47`: "Do not ask the assistant about its own personality, do not comment on its manner, and do not ask it to change how it talks". That rules out feedback, P2, persona switches and the "do you have feelings?" probe.
    - `reviewer-brief.md:16, 33–34` says the same.
    - `freeze.py:2, 10, 218–220, 234` writes only an R4 pair and runs `--r4`.
    - `launch.py:37, 96–115` runs the precheck with `--r4`.
    - No companion brief exists in the repository.
    - **What would have to change (tooling and text):** C5 author, reviewer and fixer briefs that state page actions in user terms, `FACTS` requirements and the coverage list; plus a gate option in `freeze.py` and `launch.py`.

### E. Out-of-date documents and rule text

14. **The plan draft is the three-arm plan.**
    - `maturity-paid-acceptance-plan-draft.md` describes arm `E` and an extraction model (`:26, 64–68, 140, 152`), three arms in parallel (`:141–142`), and two models with a 280 CNY ceiling and extractor reservations (`:100–135`).
    - Its coverage list (`:39–46`) lacks the product's new behaviours: manner feedback through the tool, a host proposal confirmed in a later message (additive merge), switching on request, the random first type, shared-moment kinds (play / hard / other), and hard moments mellowing after 30 days and 5 conversation days (`src/membrain/relationship.py:59–66, 293`).
    - **What would have to change:** a new C5 binding in the shape of `maturity-acceptance-execution-2026-11-16.md`.
15. **`c5-harness.md` contradicts the harness it documents.**
    - It describes the five tools of attempt 5 and "P2 proposals are page actions, not tools" (`:62`); the persona being "set by the host at the start of `P` and `E`" (`:63`); `E` page actions (`:66–67`); extraction failure watching (`:101–105`); stub extractor and `dry-E`/`PEF` commands (`:126–135`); the old dry-run results (`:139–165`); "What a real C5 run still needs: P2 merged…" (`:167–171`); and extraction billing (`:177`).
    - The new 2026-11-14 section (`:17–27`) is current; the rest is history.
    - The harness docstring is mostly current. Its section header says "Memory (P and E)" (`c5-harness.py:403`).
    - **What would have to change (text, small):** rewrite these sections.
16. **`phase-c-design.md` (the "design file" C-1 and C-3 point to) describes the old product.**
    - Status: P2 "implemented and reviewed on the pre-release integration candidate" (`:3`).
    - Reset markers for every layer, with "the user can … reset it" (`:24, 26`).
    - P1: "Reset makes the host's default card, or an empty card" (`:150`).
    - P2: proposals accepted only "on the page", detected by a fixed table only (`:130–141`). Now the host reports feedback by tool (`src/membrain/manner_feedback.py`), the host may propose, and the user confirms in conversation (`persona_growth.py:50–60`, `confirm_change` `:1205`).
    - No personality types. No hard-moment kinds or mellowing (`relationship.py:59–66`).
    - Affect is written "with the note tool; in the proxy, the optional extraction model does" (`:164`). The extraction model no longer exists.
    - Evaluation (`:267–282`) is silent on all of the above.
    - **What would have to change (rule text):** update the design file, which also bears on C-1.
17. **`v1-acceptance.md` has no C5 gate text.** Under the current R4 model it would need: arms, persona, pass rule "as coded", strict 7/8, and what a pass covers. **What would have to change (rule text):** add the section.
18. **Attribution for type 6 assumes memory produced the label.**
    - `companion.md:106–107` and plan draft `:78`: memory-caused when "memory presented an inference as reported".
    - Now the *host model* sets `basis` in `memory_note.affect` (`src/membrain/affect.py:3–4`). A host that saves an inferred feeling as `reported` makes later memory "present it as reported", which is attributed to memory.
    - That is consistent with how R4 treats notes the host wrote, but it should be stated, because it makes one host labelling slip fail C5.
    - **What would have to change:** a decision (D5) and the text.

### F. Remnants of arm `E`

Executable code no longer expects `E`:
- `run()` refuses it (`c5-harness.py:1083–1084`).
- Validity, tallies and sealed maps refuse it (`acceptance_review.py:41, 84, 972, 1282`).
- The driver freezes `ARMS = ("P","F")`.
- The dry-run check has `ARMS = ("P","F")` (`c5-dry-run-check.py:22`).
- `_applies` and `_LEGACY_KINDS` in the review pipeline only read old runs.

`E` survives only in documents: `c5-harness.md`, the plan draft, `evaluation-billing.md:5` ("host and extractor transports … all four scenarios"), and historical bindings.

---

## 4. What already works for C5 in the two-arm tooling

- **Running the arms.**
  - Sequential `P`→cleanup→`F` with supervisor stamps and a port check (`c5-run-scenario.sh`). Validity refuses overlapping arms.
  - The shared billing guard with one request in flight, deferred stop after a paid row, `--stop --reason`, and SIGTERM handling.
  - A live scenario is read as literals only. `HOST_MODEL` and `MEMBRAIN_SRC` are refused, and the preflight refuses `PYTHONPATH`, `MEMBRAIN_SEMANTIC` and `MEMBRAIN_EVALUATION_CLOCK`.
  - A turn the host's own pause left unrecorded is scored rather than stopping the arm (`host-pauses.jsonl`, `c5-harness.py:947–958, 1292–1298`).
- **The scenario clock in `P`** (`src/membrain/evaluation_clock.py`, `c5-harness.md:29–58`). Recorded times, mood decay and the 48-hour cutoff, familiarity days and the proposal pause run on scenario time, with disposable-profile guards. Hard-moment mellowing reads `today` from the same helpers, so it should follow too; that is not verified by a test I found.
- **What `P` gets.** The plugin's real hooks, every server tool (including `memory_persona`, `memory_manner_feedback`, `memory_boundary`, and `memory_note` with `affect`, `shared` and `moment`), the server instructions and the session notice. This is pinned by `tests/test_c5_harness.py:159–170`, `tests/test_c5_harness_hardening.py:977`.
- **Page actions.**
  - They run through the SDK on the routes the page uses, for messages, notes, feelings, boundaries, mood, relationship reset, persona set, restore and delete-history, and proposal accept and reject. Every one of those routes still exists (`src/membrain/client.py:342–505`).
  - Before and after each action they record what was removed, per record (`removed_records`, refs by scenario position, completeness flag).
  - A message deletion finds its turn by identity, and `F` mirrors exactly what `P` removed.
  - Proposal selection is unambiguous (`bee76ca`, `tests/test_c5_proposal_selection.py`).
- **Review pipeline in companion mode.**
  - `verdicts`, `tally` and `gate --companion`: types 1–9; RC1 and RC2 with structured proofs; rule tags; strict 7/8; `gate-c5.json` kept apart from `gate.json`.
  - `actions-digest`, arm-blind, disclosed to the resolution stage only.
  - Manifest binding of keys, hashes and gate.
  - Two labels throughout; `companion.md` is already worded for two replies, and its runbook lists the C5 commands for `P` and `F` (`companion.md:120–147`).
- **Driver.** Accepts a `C5` pair (or a C5-only manifest: each gate at most one pair), runs scenarios in order and stops on the first invalid one, and reports `eligible` per gate.
- **Persona draw infrastructure** (`acceptance_persona.py`, its manifest check, and the IDS pin against the product).
- **Practice scenario and dry-run check** adapted to two arms (`6944effc`). They cover feelings (reported), mood glad→easing→baseline, a boundary by tool, a shared moment, removal and reset, a P2 accept through the table, message deletion and pause/resume. I found **no record of an end-to-end C5 practice run since the two-arm adaptation**. The stub rehearsal that was run is R4's (`r4-stub-rehearsal.py`). Whether the C5 practice passes on runtime `c280dcbf` cannot be determined without running it.

---

## 5. Decisions the lead must take before a binding

**D1. Where `P`'s starting persona comes from.**
- (a) The seeded type from the attempt id, as in R4.
- (b) A scenario-stated card, applied as the user's page edit before session 1.
- (c) The product's own random first type and its one-time announcement, with `F` mirroring whatever `P` got.

Recommendation: **(a) for the starting card**, plus scenario page edits (`set_persona` with a fully written card) where the persona-stability area needs a known card. It keeps "nobody chooses" and the always-on product path. (c) tests a real first-run experience, but makes the run less reproducible and blind to authors.

**D2. How `F` follows persona changes that happen in `P` (a switch on request, a host proposal confirmed in conversation, an accepted P2 proposal, a random pick).**
- (a) Mirror `P`'s stored card turn by turn from `P`'s log.
- (b) Keep `F` on page actions only.
- (c) Forbid such flows in C5 scenarios.

Recommendation: **(a)**. It also removes the unwritable `card` field from `accept_persona_proposal`. Add a validity check that `F`'s block equals `P`'s at every turn.

**D3. A page action whose target the host never created** (a boundary topic, a feeling label, a note, a proposal).
- (a) Keep it as a harness fault: invalid, as now.
- (b) Score it with the arm, like the host's own pause. Log it as a no-op in `page-actions.jsonl`, not as a harness event. `F` mirrors the no-op.
- (c) Allow only host-independent actions: `delete_message`, `clear_feelings`, `reset_mood`, `pin_mood`, `add_boundary` on the page, `remove_boundary` of a page-added boundary, `reset_relationship`, `set_persona`, `switch_persona`, `restore_persona`, `delete_persona_history`, support style, cap. Select host-created records by their source message's scenario position, never by text.

Recommendation: **(c), with (b) as a fallback for proposal decisions only.** API or transport errors stay invalid.

**D4. Does `F` learn of page-only user actions** (boundaries set or removed on the page, support style, cleared feelings, resets)?
- (a) No, as now. `F` is "whole conversation history" only.
- (b) Give `F` a short, product-independent line with the user's current page settings: boundaries, support style, and "feelings cleared / relationship reset on <date>". Give it no mood and no familiarity.

Recommendation: **(b)** if C5 page-adds boundaries; otherwise (a), with the asymmetry stated in the binding.

**D5. Critical-error coverage for new behaviour.**
- Is "persona changed, or claimed changed, without the user's request or yes" a new critical type 10, or only a score criterion?
- Is a still-recent hard moment raised unprompted a type-7-like error, or a score item?
- Does a host mislabelling an inferred feeling as said count as memory-caused type 6 (it does under the current wording)?

Recommendation: add **type 10** (an unasked persona change applied or claimed). Treat hard moments as score criteria. State the type-6 attribution explicitly.

**D6. The coverage list for the new product.** Recommendation, beyond the plan's list:
- manner feedback three times, then a page accept;
- one "behave differently from now on" request with a later "yes";
- one switch on request;
- a hard shared moment and a case 30 or more days and 5 or more conversation days later.

Drop "persona reset" in the old sense.

**D7. Which runtime, and the link to R4.**
- R4 passed on runtime `a85ca152`; the pin is now `c280dcbf`. `docs/releasing.md:5` says a row whose runtime is older than the pin is not evidence for it.
- (a) A C5-only attempt now, on the next frozen candidate, about 40 CNY. R4 will need to be repeated on the release runtime anyway.
- (b) A combined R4 + C5 attempt, about 70 CNY, R4 first. A later invalid C5 keeps a valid R4, per plan draft `:13`.

Recommendation: **(a)**. C5 tooling has never completed a unit; isolate that risk, then requalify R4 together with R5 on the release candidate.

**D8. What reviewers see.** Should the blind sheet carry, per case, the persona card in effect and the list of page actions before the case, both from scenario and `P` data that is identical across arms? Recommendation: **yes**. Without it, persona-stability and RC-ordered cases rest on `FACTS` prose the author may get wrong.

**D9. Format and ceiling.** Two scenarios × 11 cases × 60–66 turns; host `deepseek-v4-pro`; 80 CNY ceiling, one request in flight; Sonnet sessions for authors and reviewers. Recommendation: **keep these as in R4.** The span must be at least about 45 days if familiarity "close" or hard-moment mellowing is tested.

---

## 6. The work, in order

| # | Step | Size | Database lock? | Isolated sessions? |
| --- | --- | --- | --- | --- |
| 1 | Lead decisions D1–D9 recorded, then rule text: a C5 section in `v1-acceptance.md`; the `phase-c-design.md` P1, P2, R1 and Evaluation sections updated to the product; `releasing.md` C-3 and C-1 wording; `companion.md` type 10 and type-6 attribution if decided | small–medium (docs) | no | no |
| 2 | Harness: persona mode per D1; `F` mirrors `P`'s card per turn (D2); remove or repair `reset_persona`; add `switch_persona`, `set_support_style`, `cap_familiarity`; select records by source position and no-op handling (D3); `F` page-settings line (D4); `STUB_HOST` able to chain `propose`→`confirm` and call `memory_manner_feedback`; drop the scenario `card` requirement | **large** | **yes**: `tests/test_c5_harness.py` (`memory` fixture starts a real service, `:274–276`) and `tests/test_c5_harness_hardening.py` | no |
| 3 | Validity in C5 mode: `page-actions.jsonl` equals `PAGE_ACTIONS` per arm, no failed action, `F` persona equals `P` at every turn | small | no (synthetic) | no |
| 4 | Precheck `--c5`: read literals, mirror the R4 shape rules, C5 coverage codes, `PERSONA` per D1, refuse `STUB_` | small–medium | no | no |
| 5 | Blind sheet (D8) and, if decided, type 10 in `verdicts`, `tally` and `gate --companion` plus the reviewer files | small–medium | no | no |
| 6 | Kit: C5 author, reviewer and fixer briefs; `freeze.py --gate C5` (C5 pair, `--c5` precheck); `launch.py` precheck mode by gate; driver per-gate persona if D1 needs it | medium | no | no |
| 7 | Rewrite the C5 practice scenario: literal-only, seeded start, manner tool, propose/confirm, switch, moment kinds including hard, page actions per D3. Update `c5-dry-run-check.py`. Add `c5-stub-rehearsal.py`: freeze, driver, run script, dry-run check, review pipeline, `gate --companion` | medium | **yes** (starts real local services; needs the local embedding model) | no |
| 8 | Rewrite `c5-harness.md` and replace the plan draft with a C5 execution binding (arms, persona, ceiling, stop rules, coverage, cost) | small–medium (docs) | no | no |
| 9 | Full local suite on the candidate; freeze runtime files during the run | large (time) | **yes** | no |
| 10 | Write C1 and C2: 2 authors, 2–4 reviewers, fixers; `--c5` precheck pass; freeze; independent freeze review; owner approval of spend and subscription use | medium | no | **yes** (`launch.py`, Sonnet) |
| 11 | The run: driver, `P` then `F` per scenario, validity after each | small (operator time) | n/a (disposable profiles) | no |
| 12 | Scoring: 2 first reviews, 22 second reviews, R5 checkers as needed, `actions-digest`, 2 resolutions, attributors, `gate --companion`; independent final review | medium | no | **yes** (about 35–45 sessions; R4 used 37) |

### Paid cost of the run (guard's conservative count)

- **R4 basis:** 124 turns × 2 arms gave 327 host requests and **28.785141 CNY**: 2,860,255 prompt and 112,698 completion tokens at 9/27 CNY per million (`maturity-seventh-attempt-2026-11-16.md:48, 62`). That is about 0.232 CNY per scenario-turn for both arms, and about 1.32 requests per arm-turn.
- **C5 workload:** two scenarios of 60–66 turns, so 120–132 turns per arm and 240–264 arm-turns.
- **Host calls:** about 330–400, more than R4. `P` makes more tool rounds (manner feedback, persona, boundary, notes with affect and moments) and carries the relationship block (up to 2,200 characters, `relationship.py:56`) and the mood line (up to 600, `mood.py`). The hard cap is 5 × turns per arm (`c5-harness.py:1114`), about 660 per arm.
- **Estimate:**
  - 0.232 × 128 ≈ 29.7 CNY at R4's per-turn rate.
  - The plan's unverified 25% companion uplift (plan draft `:111`) gives **about 37 CNY**, plausibly 30–50.
  - The refusal point is 59.945984 CNY settled with one request in flight (`maturity-acceptance-execution-2026-11-16.md:288–290`), so an 80 CNY ceiling fits with about 1.6× headroom.
  - The account bill was about a sixth of the guard count in R4 (4.76 against 28.79), so about 6–10 CNY off-peak.
- **Not included:** scenario authoring and scoring sessions, which are subscription use. A combined R4 + C5 attempt (D7 b) would be about 65–75 CNY guard count, close to the refusal point. A higher ceiling would be needed.

---

## 7. Risks: the three most likely ways a C5 attempt ends invalid or uninformative

1. **`page_action_failed` on a record the host was supposed to create.**
   - Exact-text selection (`c5-harness.py:769, 776, 784`) or a missing proposal (`:752–755`) stops the paid arm. Both earlier C5 units died on this event (attempt 3 at `P` 32/64; attempt 5 at session 3, message 1), and neither cause was found.
   - Nothing since has changed that path except ambiguous-proposal selection.
   - Host-pause turns now add a new way to lose a `delete_message` target.
   - Unless D3 is settled and implemented, this is the most likely outcome of the next attempt.
2. **The persona world diverges between `P` and `F`, or cannot be judged.**
   - The seeded start and scenario-stated accepted cards are incompatible: `card_differs` makes the run invalid.
   - `reset_persona` and random switches diverge silently.
   - Switches and confirmations made through the tool are never seen by `F`.
   - Reviewers do not see the card in effect.
   - Any of these either invalidates the run or makes the persona-stability half of C5 meaningless, even if the run completes.
3. **A valid but uninformative or knife-edge result.**
   - The user script is fixed in advance, while the companion flows depend on the host: three manner comments reported, a proposal made and then confirmed after a scripted "yes", a moment saved with its kind, affect written with the right basis for the mood to move.
   - When the host does not do its part, cases degenerate. When it mislabels a feeling, type 6 is memory-caused by rule.
   - A single standing type 7 or 8 from any cause fails C5, and attribution defaults to memory on any disagreement.
   - `F` lacks page-only actions (D4), which skews the comparison.
   - With one host model under emulation, two scenarios and partial blinding (memory remarks), a pass or fail will rest on one or two judgements, as R4's did (`maturity-seventh-attempt-2026-11-16.md:24–28`).

### Not determinable from the repository

- Whether the C5 practice dry run passes on runtime `c280dcbf`.
- What exactly failed in attempts 3 and 5. Their material is sealed.
- Whether hard-moment mellowing follows the scenario clock end to end (the code reads the clock helpers; no test of it was found).
