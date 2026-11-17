# C5 harness: two arms, scenario clock, persona mirroring, page actions and the zero-network dry run

The behavioural acceptance harness for R4 and for the C5 companion scenarios. Nothing here makes a model call; no held-out C5 scenario has been run with the harness as described here.

| File | What it is |
| --- | --- |
| [`c5-harness.py`](c5-harness.py) | Arms `P` (plugin path) and `F` (whole history), built on the Phase B harness |
| [`c5-run-scenario.sh`](c5-run-scenario.sh) | Runs `P`, cleans it up, then runs `F`: one arm at a time |
| [`c5-practice-scenario.py`](c5-practice-scenario.py) | A **public practice** C5 scenario (literal assignments only) with stub scripts. Never a held-out scenario |
| [`r4-practice-scenario.py`](r4-practice-scenario.py) | A **public practice** R4 scenario (no page actions) with stub scripts |
| [`c5-stub-rehearsal.py`](c5-stub-rehearsal.py) | The free two-arm C5 rehearsal: freeze, driver with the C5 pair, run script, validity, dry-run check, companion review pipeline and gate |
| [`r4-stub-rehearsal.py`](r4-stub-rehearsal.py) | The same for R4 |
| [`acceptance_persona.py`](acceptance_persona.py) | The seeded draw of the attempt's starting personality type |
| [`c5-dry-run-check.py`](c5-dry-run-check.py) | Checks a dry run, layer by layer |
| [`c5-precheck.py`](c5-precheck.py) | Checks a scenario file before a run, printing counts and positions only (`--r4` for R4 scenarios, `--c5` for held-out C5 scenarios) |
| [`../src/membrain/evaluation_clock.py`](../src/membrain/evaluation_clock.py) | The evaluation-only scenario clock |

## Arms

- **`P`, the plugin path.** A disposable evaluation installation on the scenario clock. `P` calls the plugin's own hook functions (`membrain.plugin.session_start`, `user_prompt`, `stop`, with Claude Code's tool names), offers every tool the plugin's MCP server lists with its own schemas and descriptions, keeps one server per session (as a host keeps one MCP connection), and puts the server's instructions and the session context into the system prompt. It does not get the skill body: a host loads it only when its model opens the skill, which the 2026-11-13 trial never saw in 86 turns. Two differences from a real host remain: Claude Code may defer tool descriptions, while `P` gets them all up front; and the host model runs through this emulation, not inside Claude Code.
- **`F`, the whole-history reference.** No memory service. Its host gets the scenario's `HOST` text, the date, `P`'s persona block for the same turn (below), one line of page-only settings (below), and the whole earlier conversation of the scenario, minus the messages a page action deleted.
- **One arm at a time.** The run script runs `P` to the end, stops its installation (`c5-harness.py --cleanup RUN_DIR`, which stops only profiles carrying the harness's disposable marker and checks their ports), checks the ports free, then runs `F`. Each run directory gets `supervisor.log` (started, finished, cleaned) and `cleanup.log`; validity refuses arms that overlapped. `F` reads `P`'s finished run (results, `persona.json`, `page-actions.jsonl`).
- `run` refuses any other arm. The proxy-with-extraction arm of attempts 1 to 5 and its note-extraction model are gone from the product and from this harness.

## Persona

- **The start: the seeded type, in every run.** Both arms start from one personality type drawn from a recorded seed (`acceptance_persona.py`: the attempt id in a live run; `C5_PERSONA_SEED`, the attempt id or the fixed practice seed in a dry run). `P` saves it before the first session as the product saves a type (made by the host, action `preset`), so the product's random first type and its one-time announcement never happen. A scenario `PERSONA` card is refused in every run, dry runs included. Each arm writes `persona.json` (seed, type, card hash, starting version); `F` refuses to start unless `P`'s matches its own draw, and validity compares them.
- **Changes: as a user makes them.** In conversation, through the host's `memory_persona` tool (a switch on request; a proposal the user confirms in a later message; a decline) and `memory_manner_feedback` (three comments of one kind make a suggestion), or on the page (`switch_persona`, `set_persona`, `accept_proposal`, `reject_proposal`, `delete_persona_history`).
- **`F` mirrors `P` turn by turn.** After the prompt hook of each turn, `P` reads the persona in effect from the product (`client.persona()`, the block the hook renders) and records it in the turn's row:
  - `persona_block`: the product-rendered `<membrain-persona>` block, `""` for none;
  - `persona_turn`: `{"format": 1, "version": V, "sha256": H}`, the version (0 for none) and the sha256 of the block's UTF-8 (`null` for none);
  - `persona_shown_to_host`: whether that block was anywhere in what `P`'s host was sent this turn (`null` for none).

  `F` gives its host exactly `P`'s block for the same turn and records `reference_persona` (the block) and the same `persona_turn`. So a change made by the host's tool, by an accepted suggestion or by a random pick reaches `F` at the turn it reaches `P`, and no scenario has to state the card a change leads to. `F` refuses a `P` row whose block does not match its identity.

## Page actions

`PAGE_ACTIONS = [(session, before_turn, action), ...]` are the user's actions on the memory page. Each runs before that turn of that session through the public `MemoryClient` SDK, on the routes the page uses, in `P`; `F` applies `P`'s outcome. Actions are applied by position (session order, then `before_turn`, then their order in the list), which is also the order validity and `actions-digest` read them in.

**A target is never chosen by text the host wrote.** It is known from the scenario itself (a message by its scenario position; a boundary topic the scenario added on the page) or from the product's state by kind (the open suggestion, by origin and order). `check_actions` refuses anything else before any model call.

| `do` | Arguments | Target, and when it is not applicable |
| --- | --- | --- |
| `delete_message` | `session`, `turn`, optional `role` (`user`, default, or `assistant`) | The message recorded at that scenario position, by event identity; the product's cascade (notes and feelings drawn from it) follows. `message_not_recorded` when that turn ended unrecorded (the host's own pause, or a turn the scenario leaves unrecorded); `message_already_removed` when an earlier deletion's cascade removed it |
| `delete_note_from` | `session`, `turn`, optional `role` | Every note whose source messages include that message. `message_not_recorded`; `no_note_from_message` |
| `delete_feeling_from` | `session`, `turn`, optional `role` | Every feeling whose source messages include that message. `message_not_recorded`; `no_feeling_from_message` |
| `clear_feelings` | none | Every feeling (notes and messages stay) |
| `reset_relationship` | none | Shared moments, support style, boundaries, cap, acknowledgements |
| `reset_mood` | none | The mood, back at baseline |
| `pin_mood` | optional `pinned` (default `true`) | The mood pin |
| `add_boundary` | `topic`, optional `aliases` (list of strings) | A boundary in the scenario's own words |
| `remove_boundary` | `topic` | The boundary with that topic (compared as the product compares topics, case and spacing ignored); the topic must be one an earlier `add_boundary` page action added. `boundary_not_present` when it is gone (a relationship reset erased it) |
| `set_support_style` | `text` (empty removes it) | The support style |
| `cap_familiarity` | `level`: `new`, `getting_to_know`, `familiar` or `null` (no cap) | The familiarity cap |
| `switch_persona` | `preset`: a type id (`persona_presets.IDS`) or `random` | A new persona version of that type. `random` is picked by the harness: see below |
| `set_persona` | `card` (a card object) | The user's own card, saved as a new version made by the user |
| `delete_persona_history` | none | Every persona version |
| `accept_proposal`, `reject_proposal` | optional `origin` (`any`, default; `feedback`; `host`) and `position` (from 1, default 1) | The `position`-th open suggestion of that origin in the page's order (open first, newest first). `no_open_proposal` when there are fewer |

Every action may also carry `"arms": ["P"]` (only `P` may be named; `F` follows `P`). Any other argument, or a message position at or after the action's own, is refused.

**The random pick.** The page's "pick another type at random" asks the product for `random`, which picks uniformly among the types other than the current one. The harness makes the same kind of pick reproducible without changing the product: `others = [type for type in persona_presets.IDS if type != current]` (the product's order; `current` is `None` for a card that is not a type), and the chosen type is `others[int(sha256(json.dumps(["switch_persona", seed, index], separators=(",", ":"))), 16) % len(others)]`, where `seed` is the attempt's persona seed and `index` the action's index in `PAGE_ACTIONS`. It then asks the product for that type by name. A rerun with the same attempt id makes the same pick; `F` mirrors `P` anyway. A random switch the **host** makes with its tool is the product's own pick and is not reproducible; `F` mirrors it all the same.

**Outcomes.** Each action is `done`, `not_applicable` (its target did not exist because of what the host did or did not do: no open suggestion, no note from that message, a turn its pause left unrecorded) or `failed`.
- `not_applicable` is the plugin path's behaviour and is scored with the arm. The run goes on; no harness event is recorded; validity reports the count and positions.
- `failed` is a real fault: the service refusing a well-formed action on an existing target (`service_refused`), an exception (`exception`), a deletion that removed messages the harness cannot mirror (`unknown_removed`), a recorded turn whose message was never identified (`not_found`). It records the harness event `page_action_failed` with that reason code, which makes the run invalid and stops a live arm.
- A dry run on a runtime without persona suggestions skips proposal actions in both arms and records `page_action_unsupported`; a live run refuses such a scenario.

### `page-actions.jsonl` (format 2)

One JSON object per action applied, in application order, in each arm:

```json
{"format": 2, "index": 3, "session": "<session id>", "before_turn": 0, "action": "add_boundary",
 "detail": {"topic": "...", "aliases": ["..."]},
 "status": "done" | "not_applicable" | "failed", "reason": "<code, absent when done>",
 "before": {...}, "after": {...}, "time": "<scenario time, P only>",
 "result": {"...": "...", "removed_records": [...], "removed_records_complete": true}}
```

- `index` is the action's index in `PAGE_ACTIONS`; `detail` is the action's arguments without `do` (a `set_persona` card is replaced by its `card_sha256`).
- `reason` is one of `NOT_APPLICABLE` (`message_not_recorded`, `message_already_removed`, `no_note_from_message`, `no_feeling_from_message`, `boundary_not_present`, `no_open_proposal`) for `not_applicable`, one of `FAILURE_CODES` (`not_found`, `unknown_removed`, `service_refused`, `exception`; `card_differs` and `ambiguous_proposal` only in older runs) for `failed`.
- `before` and `after` are, in `P`, the page counts (`world()`): messages, notes, feelings, boundaries (topics), shared moments, familiarity level, days and cap, support style (set or not), mood (label or `baseline`), mood pinned, persona version; in `F`, `{"history_items"}`, plus `removed_still_in_history` after a deletion.
- `result` holds what the action did (`deleted` and `removed` positions for a deletion; `preset`, `seeded_random`, `version`, `unchanged` for a switch; `proposal`, `kind`, `version` for a decision; `not_applicable` with its code; `failed` with `code`), and the records it removed:
  - **`removed_records`** lists every record present before and gone after, by its own id, through the same SDK calls `world()` uses: `{"kind", "ref", "sources", "established": true}`, or `{"kind", "established": false}` for a drop in a count that no id diff explains. `kind` is `message`, `note`, `shared_moment`, `commitment`, `feeling`, `boundary`, `support_style`, `familiarity_cap` or `persona_version`; `sources` are `[session_id, turn_index, role]` triples.
  - **`ref`** is `record_ref`, the formula the review side recomputes: with sources `"src:" + sha256(json.dumps([kind, sorted(sources)], separators=(",", ":"), ensure_ascii=False))`; without, `"content:" + sha256(json.dumps([kind, content], separators=(",", ":"), ensure_ascii=False, sort_keys=True))` over the record's normalized content. It never contains a database id or content.
  - `removed_records_complete` is true only when every entry is established. A `not_applicable` action removes nothing: its list is empty and complete, and validity and `actions-digest` refuse one that is not.
  - In `F` the list holds only the messages a deletion removed, with `P`'s refs, and is always complete.

### The line `F` is given (format 1)

Before each turn `F`'s system prompt gets, after the persona block, one line of what the page has done so far that the conversation does not show, from `P`'s outcomes and the scenario's own words, or nothing when there is none:

```
Memory page settings the user chose (not part of the conversation above): <item>; <item>; ....
```

Items, in this order, each only when present:
1. `topics not to bring up: "<topic>" (also "<alias>", ...), ...`: boundaries the page added and still in force (a relationship reset removes them; boundaries the host set by tool are in the conversation and are not listed);
2. `relationship reset on YYYY-MM-DD` (the latest);
3. `feelings cleared on YYYY-MM-DD` (the latest);
4. `support style: "<text>"`;
5. `familiarity limited to <new | getting to know | familiar>`;
6. `simulated mood held at its baseline` (the mood pin).

Dates are the scenario date of the session the action came before. Topics, aliases and the support style are the scenario's literals, JSON-quoted; nothing else is free text. Each `F` row records it as `reference_page_line` (`""` for none). Message deletions are not listed: they change `F`'s history instead.

## Reference world

`F`'s earlier history drops a message only when `delete_message` deletes it in `P` (the product erases it), exactly the positions `P`'s deletion removed, cascades included. Resets, cleared feelings, deleted notes and feelings, and mood and persona actions keep the conversation. Within the session in progress every arm keeps its own transcript, as a host app does; a message deleted during that session stays in its running transcript but is left out when the session is added to `F`'s history.

## Recording

- **Message identity.** After each turn `P` records which new user message and reply the turn wrote, by event id, under its scenario position, and which turns ended unrecorded. A recorded turn that did not write exactly one of each is the harness event `message_identity_unknown`.
- **Timed pauses are refused.** `memory_pause(hours=...)` ends on the wall clock, so on the scenario clock it would span scenario days or nothing. The harness answers it with a tool error and records `timed_pause_refused`.
- **Unrecorded turns.** A turn that ends unrecorded records `turn_not_recorded` unless the scenario intended it (`EXPECT_RECORDING_P` marks it `False`, or `STUB_HOST` scripts an untimed pause up to a resume in the same session) or the host's own accepted pause explains it. Such a turn is the plugin path's behaviour: it appends `{"time", "session", "turn", "kind": "unrecorded_by_host_pause"}` to `host-pauses.jsonl`, records no harness event, and the arm goes on. The pause tool requires `request`, the user's own words.
- **Index wait.** The harness waits on the dashboard's `status.pending_jobs` and `index_lag` before each session.

## Scenario clock

`P` runs on a disposable profile whose service reads the scenario clock (`helpers.now()`, `helpers.today()`). Every session's first message states its date and time ("Today is Tuesday, March 3, 21:00"; Spanish, German and Chinese forms too), and the clock is set to it before the session starts, in UTC. Recorded times, mood decay and the 48-hour cutoff, familiarity days and the proposal pause follow it.

**Safety guards.**
1. **Off unless asked.** Only `MEMBRAIN_EVALUATION_CLOCK` turns it on. No launcher, plugin, adapter or SDK sets it; a test fails if any file under `integrations/`, `plugins/`, `sdk/`, `scripts/` or `src/` names it (besides the clock module). The run script refuses to start if it is already set.
2. **Disposable profiles only.** With the variable set, the service starts only on a profile with the harness's marker for that installation's id, with the clock file inside it, and not the default installation directory; otherwise it refuses before opening the database (`evaluation_clock_refused` in `service.log`).
3. **Loud.** A service on the clock logs `evaluation_clock_enabled_time_is_simulated`; the harness stops if that line is missing.
4. **Never backwards.** The writer refuses an earlier time; a time the clock has already passed leaves it as it is (`clock_already_past`); each reading process holds its last time.

**Not on the clock:** job leases and retries, plugin session markers, `memory_pause` durations, and the orientation expiry in `learning.py`. Whether hard-moment mellowing follows the clock end to end is not covered by a test.

Tests: `tests/test_evaluation_clock.py`.

## Harness events, stops and the log

- **Every harness event makes the run invalid** (`acceptance_review.py validity`). In a live run `harness_event` records the event, blocks the shared billing ledger (`harness_degraded`) and raises `DegradedRun` (a `SystemExit`, exit 3). An event raised while a paid turn is being recorded waits until that turn's row is written (`"stopped_after": "<kind>"`). A dry run records every event and goes on.
- **Event payloads hold only kinds, positions and counts** (`session`, `turn`, `role`, `action`, `reason` as a fixed code, `new_messages`, `behind_seconds`).
- **The harness's own log** (`run.log`) names positions by index ("session 2 of 8, message 1"), page actions by number, kind, status and reason code, and tool calls by the names the server offered ("other" for anything else); never a session id, scenario words, tool arguments or replies.
- **Host rounds.** `host-rounds.jsonl` records each returned host round (without `reasoning_content`) before tool execution, so a stopped turn keeps its paid rounds. It holds content and stays sealed with the run.
- **Tool errors** the host was shown are counted by tool name in `tool-errors.json`; validity reports them without refusing.
- **No resume.** An existing results file, round journal, `persona.json` or installation is refused.

## Validity in companion mode

`acceptance_review.py validity RUN_P RUN_F [--scenario PATH] [--persona PRESET] [--companion]` keeps every R4 rule and adds, for a scenario with `PAGE_ACTIONS` (every C5 scenario) or with `--companion`:
- every arm's `page-actions.jsonl` holds exactly the scenario's `PAGE_ACTIONS` in application order (format 2, `index`, session, `before_turn`, kind); each is `done`, or `not_applicable` with an allowed reason and no removal; none `failed`; `F`'s outcome of each is `P`'s;
- every `P` row records a valid `persona_turn` for its `persona_block`, and every `F` row the same `persona_turn` with that block as `reference_persona`.

New report fields:
- `page_actions`: per run directory, `{"count", "done", "not_applicable": {"count", "at": [{"action": n (from 1), "session": i, "before_message": m, "kind", "reason"}]}}`;
- `persona_mirroring`: `{"checked_turns", "not_shown_to_p_host": {"count", "positions": [[session, message], ...]}}` (reported, never refused), or `null` when no run was read.

The persona check also runs on any run whose `P` rows carry the records (every run of this harness, R4 included); an older run without them is checked as before. Page actions recorded for a scenario without `PAGE_ACTIONS` are refused. The driver passes `--scenario` and `--persona`; companion mode follows from the scenario.

## Zero-network dry run

`C5_STUB=1` swaps the host model for a deterministic stub, an `httpx.MockTransport` that answers from the scenario's `STUB_HOST` script:
- In each round of a turn it makes the steps scripted for that round (`"round": N`, default 0), then a fixed reply naming the memory blocks it was given and whether the server's instructions were in the system prompt.
- `"source": "current"` passes the current message's `source_messages`; a recording capture is passed where the tool takes one; a pause without `request` quotes the user's words.
- `{"$result": [session, turn, index, field]}` as an argument passes on a field of an earlier scripted call's result (the stub keeps every result it is shown), so a proposal made in one turn can be confirmed in a later one; with no such result the argument is left out and the tool answers with an error.
- It answers a consolidation batch with a cue.

The harness also refuses every non-loopback socket connection and records it as `network_refused`. The run script accepts `C5_STUB=1` only with a scenario whose file name contains "practice".

```sh
C5_STUB=1 C5_PYTHON=/path/to/python MEMBRAIN_MODEL_CACHE=/path/with/the/embedding/model \
  evaluations/c5-run-scenario.sh evaluations/c5-practice-scenario.py OUT_ROOT dry
python evaluations/c5-dry-run-check.py evaluations/c5-practice-scenario.py OUT_ROOT dry
python evaluations/acceptance_review.py validity --scenario evaluations/c5-practice-scenario.py OUT_ROOT/dry-P OUT_ROOT/dry-F
python evaluations/c5-stub-rehearsal.py NEW_OUT_ROOT_OUTSIDE_THE_REPOSITORY
```

**The practice scenario** (`c5-practice-scenario.py`, eight sessions, 22 turns, 14 page actions) covers: three "too formal" comments reported by tool and the suggestion accepted on the page; a host proposal confirmed after the user's yes in a later turn of the same conversation (the product applies a confirmation only to an answer given in the conversation where the companion asked; a yes in a later conversation is answered "Confirmed" by the tool but never saved, which the first rehearsal of this practice showed); a second proposal declined after a no; a host switch on request (random) and a page random switch; a note with a shared moment of kind `play` and one of kind `hard`; a feeling said and one inferred; a boundary by tool and one on the page; a message deleted on the page with its note and feeling, a feeling and a note deleted by their source message; clear feelings, mood reset and pin, support style, familiarity cap, relationship reset; an off-the-record stretch; and two actions meant to find no target (`EXPECT_NOT_APPLICABLE`: a removed page boundary after the reset, and a deletion of an off-the-record message). `c5-dry-run-check.py` checks every layer in both arms' contexts, the persona version at chosen turns, the `memory_persona` actions in order, each page action's outcome and scope, `F`'s persona and page line, and the sequence, cleanup and network.

## History

The three-arm harness of maturity attempts 1 to 5 (2026-11-03 dry runs on `b9c5ce9`; C5 units of attempts 3 and 5, both stopped on `page_action_failed`) is described in this file's git history and in the attempt records. Those runs are not evidence for this harness. The two-arm form came on 2026-11-14 (`no-learning-pipeline-2026-11-14.md`); the host's own pause is scored since 2026-11-16 (`maturity-sixth-attempt-stop-2026-11-16.md`); persona mirroring, the format-2 page actions, `not_applicable` outcomes and `F`'s page line since 2026-11-17 (this change). Since the sixth attempt every prompt of both arms carries a persona, which can change tone and length of replies in both arms alike.

## What a live C5 attempt still needs

- Since 2026-11-17 the kit for C5 exists: `c5-precheck.py --c5` (literal reading, the R4 shape rules, the `COVERAGE` table and its codes), `acceptance-kit/freeze.py --gate C5`, `acceptance-kit/launch.py --gate C5` with the C5 author, reviewer and fixer briefs, and the blind sheet's display of the page actions so far and the persona in effect before each case (`v1-2026-10-29-phase-b-blind.py`, companion mode); `c5-stub-rehearsal.py` uses them. The rule text is in `architecture/v1-acceptance.md` (C5) and `acceptance-review/companion.md`, and a draft binding in `maturity-c5-execution-DRAFT.md`.
- Still needed: the binding completed by preparation and committed, the owner's approval of the spend and of the subscription sessions, two held-out scenarios written, reviewed and frozen with the kit, the independent freeze review, and the run.

## Prospective live billing guard

`c5-harness.py --stop` blocks the shared ledger. It takes an optional `--reason CODE`, where CODE matches `[a-z][a-z0-9_]{0,39}`, and the ledger keeps the first reason it is given; without `--reason` the reason is `arm_failed`. Live runs require the approved attempt's shared `C5_BILLING_LEDGER`; every host call and retry reserves against it before HTTP. See [billing control](evaluation-billing.md). The guard grants no model-use approval. Stub practice needs no ledger and makes no external request.
