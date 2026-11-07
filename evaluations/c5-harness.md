# C5 harness: scenario clock, page actions and the zero-network dry run

Free prerequisites 4 and 5 of the [paid acceptance plan draft](maturity-paid-acceptance-plan-draft.md). Nothing here makes a model call; no held-out scenario has been run with it.

| File | What it is |
| --- | --- |
| [`c5-harness.py`](c5-harness.py) | Arms `P` (plugin path), `E` (proxy with extraction) and `F` (whole history), built on the Phase B harness |
| [`c5-run-scenario.sh`](c5-run-scenario.sh) | Runs the three arms in parallel, as `v1-2026-11-05-run-scenario.sh` does |
| [`c5-practice-scenario.py`](c5-practice-scenario.py) | A **public practice** scenario with stub scripts. Never a held-out scenario |
| [`c5-dry-run-check.py`](c5-dry-run-check.py) | Checks a dry run, layer by layer |
| [`c5-precheck.py`](c5-precheck.py) | Checks a scenario file before a run, printing counts and positions only |
| [`../src/membrain/evaluation_clock.py`](../src/membrain/evaluation_clock.py) | The evaluation-only scenario clock |

## Scenario clock

**Problem.** The Phase B harness only patched the date seen by the harness's own process. The local service is a separate process, so it recorded events on the wall clock: the mood never decayed on the scenario's timeline, familiarity counted one real day, and a 30-day proposal pause could never pass.

**Design.** `helpers.now()` and `helpers.today()` read an optional scenario clock. Every Phase C time read goes through them: event `recorded_at` (stamped by the service), mood decay and the 48-hour cutoff, familiarity days (from `recorded_at`), proposal pauses (P2 uses `helpers.now`), the default `felt_at` of a feeling, plan dates in the coming-up block, and extraction's "today".
- The clock is a JSON file, `evaluation-clock.json` in the profile directory: `{"time": T, "set_at": wall seconds}`. A reading is `T` plus the wall seconds since `set_at`, so events within a turn keep their real spacing. Both processes compute the same value.
- The harness sets `T` to each session's stated date and time before the session starts. Sessions must state a time ("Today is Tuesday, March 3, 21:00"). The clock runs in UTC: the harness sets `TZ=UTC` for itself and the service.

**Safety guards.**
1. **Off unless asked.** Only `MEMBRAIN_EVALUATION_CLOCK` turns it on. No launcher, plugin, adapter or SDK sets it; a test fails if any file under `integrations/`, `plugins/`, `sdk/`, `scripts/` or `src/` names it (besides the clock module). The run script refuses to start if it is already set.
2. **Disposable profiles only.** With the variable set, the service starts only if all of these hold:
   - the profile has the harness's marker file, written for that installation's id;
   - the variable names the clock file inside that profile;
   - the profile is not the default installation directory.
   Otherwise the service refuses to start, before it opens the database. The refusal goes to `service.log` (`evaluation_clock_refused`), and `desktop start` fails.
3. **Loud.** A service on the clock logs `evaluation_clock_enabled_time_is_simulated` in `service.log` and prints a warning on standard error. The harness stops if the service log lacks that line.
4. **Never backwards.**
   - The writer refuses a time earlier than the last one set.
   - A time the running clock has already passed leaves the clock as it is; the harness records this as `clock_already_past`.
   - Each reading process holds its last time if the file is ever moved back. Recorded times therefore follow the order of sequence numbers.

**Not on the clock.** These stay on the wall clock or the database clock, because they are not scenario time: job leases and retries; plugin session markers; `memory_pause` durations; the orientation expiry in `learning.py`, which needs a cognition model that the harness does not configure.

**Tests** (`tests/test_evaluation_clock.py`):
- A real local service in a temporary directory records `recorded_at` at the scenario time.
- On that service, a glad mood eases the next morning and is exactly the baseline once the clock passes 48 hours.
- Familiarity counts two scenario days.
- After a restart without the variable, the same installation records on the wall clock again.
- Each refusal case is covered.
- Time never goes backwards.

## Harness changes

- **Tools.** Arm `P` offers `memory_recall`, `memory_note`, `memory_boundary`, `memory_pause` and `memory_resume`. Each uses the plugin's own MCP schema, so `memory_note` carries `affect` and `shared`. `P` also passes `include_source=True` to the prompt hook, as the plugin does; this gives the note tool its source hint. The proxy (`E`) has no tools. P2 proposals are page actions, not tools.
- **Persona.** The scenario's `PERSONA` is set by the host at the start of `P` and `E`, as the host default. `F` gets the same card as the product-rendered `<membrain-persona>` block in its system prompt. Each persona page action changes `F`'s card the same way, with the same version numbers. An accepted proposal must state its resulting card in the scenario, because `F` has no feedback layer. The dry-run check compares `F`'s block with `P`'s at every turn.
- **Page actions.** `PAGE_ACTIONS = [(session, before_turn, action)]`. Each action runs before that turn through the `MemoryClient` SDK, on the routes and with the arguments the memory page uses.
  - Actions: `set_persona`, `restore_persona`, `reset_persona`, `delete_persona_history`, `accept_persona_proposal`, `reject_persona_proposal`, `add_boundary`, `remove_boundary`, `clear_feelings`, `delete_feeling`, `delete_note`, `delete_message`, `reset_relationship`, `reset_mood`, `pin_mood`.
  - `"arms": "E"` limits an action to some arms. For example, the proxy user sets a boundary on the page while `P` sets it by tool. `F` follows `P`.
  - In `E`, page actions apply to the proxy user's own brain (`api:person`), and the proxy's block cache is cleared so the next message sees the change.
  - Each action is logged in `run.log`. It is also logged in `page-actions.jsonl` with page counts before and after: messages, notes, feelings, boundaries, shared moments, familiarity, mood and persona version.
  - A failed action is recorded as `page_action_failed`.
  - Proposal actions match an exact proposal ID or kind first, otherwise a case-insensitive substring of the kind or displayed label. Inherited persona fields and quoted feedback are not selectors. A selector matching more than one open proposal fails before any decision, with diagnostic code `ambiguous_proposal`; it never chooses by list order.
  - After `accept_persona_proposal`, the harness reads `P`'s current card and compares it, in the stored form (`persona.normalize_card`), with the card the scenario gives `F`. If they differ, the action fails with the differing fields, and `page_action_failed` makes the run invalid instead of letting `F` silently follow a different card. The dry-run check's block comparison remains as a second check.
  - A live run refuses a scenario with proposal actions on a runtime without P2.
- **Message identity.** After each turn the harness records which new user message and reply that turn wrote, by event id, under its scenario position. `delete_message` deletes the message recorded at the named position, never by matching text, so two turns that say the same thing ("Thanks.") are told apart. A turn that did not write exactly one of each is recorded as `message_identity_unknown`; deleting it, or a deletion that removes a message with no recorded position, fails the action.
- **Reference world.** `F`'s earlier history drops a message only when `delete_message` deletes it. The product erases a deleted message; resets, cleared feelings, deleted feelings and notes, and mood and persona actions keep the conversation. So those never change `F`'s history, and the dry run checks this for every action. Within the session in progress, every arm keeps its own transcript, as a host app does. A message deleted during the session in progress stays in that session's running transcript, but it is left out when the session is added to `F`'s history, so later sessions never see it.
- **Index wait.** The harness waits on the dashboard's `status.pending_jobs` and `index_lag`. `pending_jobs` must count every job of the brain that can still run (queued, running or failed) and no superseded or cancelled job, which never finish. Older runtimes counted only the latest 100 listed jobs and included superseded ones, so after a page deletion the wait timed out; the dashboard fix that the integration candidate carries corrects this, and the harness relies on it rather than counting the listed jobs itself.
- **No resume.** An existing results file or installation is refused.
- **Returned host rounds.** `host-rounds.jsonl` durably records each returned host round's position, message and usage before tool execution, omitting `reasoning_content`. If another arm stops the shared ledger between tool rounds, these partial replies remain available without inventing a completed results row. The ledger is checked before tool execution. An existing round journal also prevents resuming a partial run. The journal contains scenario/reply content and stays sealed with the run; it is not diagnostic console output or a scored answer.

## Hardening after the independent plan review

- **A degraded live arm stops (U2).** `harness_event` is the single choke point. Every recorded event makes the run invalid (`acceptance_review.py validity`), so in a live run it records the event, blocks the shared billing ledger (`harness_degraded`, as an interrupted arm does), and raises `DegradedRun`. `DegradedRun` is a `SystemExit` with exit code 3: no `except Exception` swallows it, and the main block's cleanup (`stop_started`) still runs. The run script then sees a failed arm and stops the others. A dry run (`C5_STUB=1`) records the event and goes on, so its checks still see every event.
  - **The paid turn's row is kept.** An event raised while a turn's paid reply is being recorded (`record_turn`, the extraction checks, `turn_not_recorded`) blocks the ledger at once. The stop itself waits until that turn's results row is written, in the usual format, with `"stopped_after": "<event kind>"`. The run stays invalid: the event is in `harness-events.jsonl`, the later turns are missing, and `run.log` has no finished line.
  - **The same holds when another arm stopped the shared ledger during this turn's host call.** The billing checks in a turn's bookkeeping run first, before recording, and again after the extraction wait. A stop found there writes the turn's row with `"stopped_after": "billing_stop"`, then raises the billing stop. Once stopped, the turn is not recorded in memory and nothing is extracted, so no further billed request is made.
- **The dry-run check fails on any harness event.** Its "run" verdict used to fail only on `page_action_failed`, `index_wait_timed_out` and `extraction_unfinished`. It now fails on every event kind, as `acceptance_review.py validity` does, and still reads kinds only. This includes `page_action_unsupported`, so a dry run on a runtime without P2 no longer passes the check.
- **Event payloads hold only kinds, positions and counts.**
  - `page_action_failed` now has `reason` as a code (`not_found`, `card_differs`, `unknown_removed`). Before, it held the result's message, which named the topic, label, note text or proposal match.
  - `clock_already_past` now has `behind_seconds` instead of the requested and current times.
  - `network_refused` no longer names the host.
  - `index_wait_timed_out` no longer names the brain.
  - The full detail of a page action is still in `page-actions.jsonl`.
- **Which records a page action removed.** Each action's `result` in `page-actions.jsonl` now has `removed_records` and `removed_records_complete`. Kinds and counts alone cannot tell two feelings with the same label apart.
  - **How they are found.** The harness lists every layer's records by their own ids before and after the action, through the same SDK calls `world()` uses: messages, `list_notes`, `affect_records`, `relationship()` and `persona_versions`. A record is removed when its id is present before and gone after.
  - **Entry format.** Each removed record is `{"kind", "ref", "sources", "established": true}`.
    - `kind` is one of `message`, `note`, `shared_moment`, `commitment`, `feeling`, `boundary`, `support_style`, `familiarity_cap` or `persona_version`.
    - `sources` are the record's source messages as `[session_id, turn_index, role]` triples, mapped through the positions `record_turn` recorded.
  - **`ref`** is computed by `record_ref`, the formula the review side recomputes. It never contains a database id or content.
    - With sources: `"src:" + sha256(json.dumps([kind, sorted(sources)], separators=(",", ":"), ensure_ascii=False))`.
    - Without sources: `"content:" + sha256(json.dumps([kind, content], separators=(",", ":"), ensure_ascii=False, sort_keys=True))`, over the record's normalized content fields.
  - **Unestablished drops.** A drop in a `world()` count that no id diff explains is written as `{"kind", "established": false}`, with no ref. `removed_records_complete` is true only when there is no such entry.
  - **Arm `F`** lists only the messages a deletion removed. It uses the same refs as `P`, and its `removed_records_complete` is always true. The `removed` field is unchanged.
- **Failed extraction is reported (B3).** The extractor's worker catches every error and only logs it. Arm `E` therefore watches two signals from the extractor itself, without changing `src/`:
  - the extraction status in the installation's state, `extraction.json` (`turns_failed` and `turns_skipped`);
  - the extractor's own failure warnings (`note extraction failed`, `queue full`, `note not saved`), counted by message template and never by text.

  After each turn's extraction wait, any new failure records `extraction_failed` with the session and turn only.
- **Timed pauses are refused (I3).** `memory_pause(hours=...)` ends on the wall clock (`host.pause`), so on the scenario clock it would span scenario days, or nothing.
  - When the host model passes `hours`, the harness does not call the tool. It returns a tool error ("Timed pauses are unavailable in this evaluation...") and records `timed_pause_refused`. A live arm stops on that event.
  - An untimed pause, with or without `until_resumed`, reaches the plugin's tool as before.
- **Unintended unrecorded turns are flagged.** A turn that ends unrecorded records `turn_not_recorded` (session and turn), unless the scenario intended it. In arm `P`, intended turns are:
  - the turns that `EXPECT_RECORDING_P` marks `False`;
  - the turns from an untimed `memory_pause` scripted in `STUB_HOST` up to, but not including, a `memory_resume` in the same session.

  A live run has no stub script, so a scenario that asks for a pause must declare those turns in `EXPECT_RECORDING_P`. Otherwise the pause stops the arm.
- **Count-only precheck (I2).** `python evaluations/c5-precheck.py SCENARIO.py` checks a scenario with the harness's own parsers before any service or model starts. It checks that:
  - each session's first message states a date and a time;
  - session starts strictly increase and are at least one hour apart (I4);
  - every page action passes `check_actions`;
  - no timed pause is scripted, either in `STUB_HOST` or as a page action with `hours`.

  It prints only counts (sessions, turns, actions, intended unrecorded turns) and, for each failure, a code with a session index, an action index or a `session:turn` position. It never prints a message, a session id, a topic, a label or an exception's text. Output from loading the scenario is discarded. The last line is a JSON summary. It exits 0 when the scenario is fit and 1 when it is not.

## Zero-network dry run

`C5_STUB=1` swaps in deterministic stubs for the host model and the extraction model. Both are `httpx.MockTransport` handlers that answer from the scenario's `STUB_HOST` and `STUB_EXTRACT` scripts. `STUB_HOST` can make scripted tool calls, with the current message's source when asked. The harness also refuses every non-loopback socket connection and records it as `network_refused`. The run script accepts `C5_STUB=1` only with a scenario whose file name contains "practice".

```sh
C5_STUB=1 C5_PYTHON=/path/to/python MEMBRAIN_MODEL_CACHE=/path/with/the/embedding/model \
  evaluations/c5-run-scenario.sh evaluations/c5-practice-scenario.py OUT_ROOT dry
python evaluations/c5-dry-run-check.py evaluations/c5-practice-scenario.py OUT_ROOT dry
python evaluations/acceptance_review.py validity OUT_ROOT/dry-P OUT_ROOT/dry-E OUT_ROOT/dry-F
```

The run produces the artifacts a real run produces: per-arm results, `run.log`, `harness-events.jsonl` and `page-actions.jsonl`. Blinded sheets come from `v1-2026-10-29-phase-b-blind.py OUT practice PEF` over a directory holding the three results files.

## Dry run results

**Runs.** Two dry runs on 2026-11-03, with the local embedding model, the stub host and the stub extractor, and no network: `main` + this harness (`b9c5ce9`), and a temporary merge of that commit with `origin/claude/p2-persona-growth` (not kept). Each arm took one to two minutes. Both runs were `valid` under `acceptance_review.py validity`. For the run on `main`, blinded sheets and sealed mappings were produced with `v1-2026-10-29-phase-b-blind.py` (four practice cases, labels A to C). The outputs were deleted after this summary.

**Every check in `c5-dry-run-check.py` passed in both runs:**
- **Persona.**
  - `<membrain-persona version="1">` with the host card reached `P`, `E` and `F`.
  - On the P2 merge, three feedback messages in two sessions produced a "casual" proposal. Accepting it on the page gave version 2 with `register casual` in all three arms, and `F`'s block was identical to `P`'s at every turn.
  - On `main` the proposal action was skipped in every arm alike, and reported.
- **Feelings.**
  - The next session's plan note carried "(the user said they felt nervous, 2 Mar)".
  - Deleting that message on the page removed the note and its feeling in `P` and `E`. Neither came back.
  - "Clear feelings" removed the promotion feeling and kept the note.
- **Mood.**
  - "I got promoted, I'm so happy" (21:00) gave the glad mood line on the next message.
  - The next morning at 09:00 it read "glad, easing".
  - Sixty-nine scenario hours later there was no mood line.
- **Relationship.**
  - The boundary (by tool in `P`, on the page in `E`) was listed, and the message about the bounded topic stayed out of later context.
  - The shared moment (`P` only; the proxy has no note tool) appeared in the relationship block.
  - Removing the boundary, then resetting, left no boundary and no shared moment, and familiarity went from "getting to know" to "new".
- **Page action scope.**
  - Each action changed only what it names. For example, a mood reset changed no message, note, feeling or boundary count, and a relationship reset removed only the shared-moment note.
  - In `F`, only the message deletion changed the history.
- **Message deletion.** In this runtime, deleting the user message removed that message only. The assistant reply recorded with it stayed, in `P` and in `E`, so `F` dropped that one message too. `F` mirrors whatever `P`'s deletion removes, so a runtime that also erased the reply would be mirrored as well.
- **Clock, tools and network.**
  - Every turn's scenario time was its session's stated time plus the run's minutes.
  - `P` called `memory_boundary` and `memory_note` with `affect` and with `shared`, with no tool error.
  - No connection left the machine.

## What a real C5 run still needs

- P2 merged. Without it, proposal actions are skipped in every arm in a dry run and refused in a live run.
- Companion scoring (critical types 6 to 9, rules RC1 and RC2) in the review pipeline. This is being added separately. It will need, per case, the page actions before the case's message, with what each removed: `page-actions.jsonl` has this. It will also need whether a feeling was said or inferred, which comes from the scenario's `FACTS`.
- The owner's decisions in the plan draft, held-out scenarios written to this format (each session with a time, `PAGE_ACTIONS` by position), and the independent reviews.

## Prospective live billing guard

`c5-harness.py --stop` blocks the shared ledger. It takes an optional `--reason CODE`, where CODE matches `[a-z][a-z0-9_]{0,39}`, and the ledger keeps the first reason it is given. Without `--reason` the reason is `arm_failed`, as before. A malformed reason is refused before the ledger is opened.

Live runs require the approved attempt's shared `C5_BILLING_LEDGER`; host, extraction and retries all reserve against it before HTTP. See [billing control](evaluation-billing.md) for conservative rates, crash reservations and stop rules. The guard is offline-tested and awaiting independent review. It grants no model-use approval. Stub practice still requires no ledger and makes no external request.
