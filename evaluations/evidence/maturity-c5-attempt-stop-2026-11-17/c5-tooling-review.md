# C5 tooling review (independent), 2026-11-17

Branch `integration/maturity-candidate` at `0856594f`. I changed no repository file, made no model call, used no key and pushed nothing. I ran the C5 stub rehearsal once, under the shared lock, from the repository root with no `*_API_KEY` or `C5_*` set: `/home/yichen/.local/state/membrain-setup/runs/c5-review-rehearsal-20261117`, `--keep`. Result `ok: true`: driver complete, C5 eligible, c1 and c2 valid; dry-run checks 444 of 444 in each; 14 page actions in each, 12 done and 2 not applicable (`boundary_not_present`, `message_not_recorded`), the same in `P` and `F`; persona mirrored on 22 of 22 turns; 6 cases with page-action and persona blocks on each sheet; `gate-c5.json` true; zero network events; ledger unchanged; ports closed; seeded type `estj`; **0 consolidation batches answered**. Afterwards I removed the two stopped databases (`runs/c1-P/brain-*` and `runs/c2-P/brain-*`, 223 MB each, paths checked to be under the run root, no process using them) and released the lock. Logs and results are kept. I ran no pytest.

## Verdict

**Yes, after the fixes listed below.** The machinery works. Page actions no longer depend on text the host wrote, the persona and page-action mirroring is consistent, and the review pipeline and gate run end to end. Before any money is spent, five things must be fixed:

- one rule decision that changes what a pass means: B1, how persona cases are judged;
- four host-reachable stops that the binding says cannot happen: M1, M2, M3 and M8;
- the authoring loop: M5;
- the COVERAGE gaps: M6, M7 and M9.

All of them are small.

## Findings

### Blocking

**B1. Persona cases are judged against the persona block that `F` copies from `P`. This hides a requested change that the plugin path never made, and any change nobody asked for.**
- **Where.**
  - `evaluations/acceptance-review/companion.md:42–44`: "Judge persona cases … against this persona, not against what `FACTS` says the user intended."
  - `evaluations/acceptance-kit/c5-author-brief.md`, "What makes a case fair": criteria "are judged against the personality in effect".
  - `evaluations/maturity-c5-execution-DRAFT.md`, comparability table.
  - The mirroring itself: `c5-harness.py:1575–1580`, `p_persona` at `:1211`.
- **Why it matters.** Suppose `P`'s host never calls `switch`, never proposes, or does not confirm after the user's yes.
  - `P`'s block stays as it was, and `F` is shown the same unchanged block.
  - `F` can still read the request in its history and go along with it.
  - The reviewer sees the old block, criteria that ask for the new behaviour, and an instruction to judge against the block. So `P`, which follows the old persona, counts as correct, and `F`, which honours the request, counts as off-persona.

  The reverse case is just as invisible. If `P`'s host switches type or changes the card without being asked (`switch` needs only *a* cited message), the new block reaches `F` as well and becomes the yardstick. Items 7–9 of the coverage, which C5 claims to test, therefore cannot fail. In practice the score comparison is the only place persona failures could show up, and this rule removes them from it. A product that ignores persona requests could pass.
- **Smallest acceptable fix.**
  1. Judge persona cases against what the user asked for and agreed to (`FACTS`). Show the block as "the persona the product had in effect", for information.
  2. On the sheet, list the persona versions since the start, each with the position it took effect and its origin (`made_by`/`action`: preset, user switch, feedback accept, host proposal confirmed). This list is identical across arms, so a reviewer can see that a requested change never happened, or that an unasked one did.
  3. Record a decision on D5 (an unasked persona change: a critical type or a score item) and state it in the binding.

### Major

**M1. A host-chosen `hours` on `memory_pause` stops the paid arm.**
- **Where.** `c5-harness.py:1269–1271` records `timed_pause_refused` as a harness event. During the tool loop `_DEFERRED` is None, so the stop is immediate and the run is invalid.
- **Why it matters.** The tool's own description invites the argument: "pass hours when they name a duration" (`src/membrain/host.py:729`). The author brief does not forbid naming a duration ("for a bit", "for the next hour"), and the precheck checks only `STUB_HOST`. The host sees the refusal either way, so nothing about the run is degraded.
- **Fix.** Return the refusal to the host and count it (`tool-errors.json`, or a `timed-pauses.jsonl` that validity reports), with no harness event. Add one line to the brief: "never name a duration".

**M2. A pause that the product's own prompt hook makes on the user's words is not treated as plugin-path behaviour.**
- **Where.**
  - `held_by_host_pause` (`c5-harness.py:1565`) requires `host_pause`, which only an accepted `memory_pause` call sets (`:1615–1618`). `:1641–1645` then raises `turn_not_recorded`.
  - `host.py:1767–1769` pauses the conversation itself when a message opens with a clause `recording_policy.requests_pause` recognises: "Off the record: …", "Don't remember this.", "不要记录…".
- **Why it matters.** Natural off-the-record wording triggers the hook. If the host then does not also call `memory_pause`, any later turn of that session left unrecorded becomes a harness event and the run is invalid. That happens when the host does not resume, or resumes without `session_id`. The same wording outside a declared stretch has the same effect, and the precheck never tests for it.

  Neither the practice nor R4 exercised this path. The practice's request ("Please stop recording for the rest of this conversation.") does not fullmatch the regex. In R4's seventh attempt the host happened to call both tools (2 of 2).
- **Fix.**
  - In the harness, count a pause the product holds at the start of the turn (`memory.paused(session)`), whoever made it.
  - In the precheck (`--c5` and `--r4`), run `requests_pause` on every user message and require each match to be a declared `False` turn (a new code).

**M3. `add_boundary` on the page can still invalidate the run because of boundaries the host added.**
- **Where.** `relationship.py:54–55` and `:600–605` (at most 12 boundaries, a 900-character line) lead to `service_refused`, then `failed`, then `page_action_failed` (`c5-harness.py:1046–1048`, `:1518–1520`). The precheck checks only the scenario's own words. (A topic the host already added under the same name is merged, `done`, with the page's aliases replacing the host's.)
- **Why it matters.** The cause is what the host did, but the outcome is an invalid paid run.
- **Fix.** Map a 4xx `validation_failed` on an action whose words the precheck already validated (`add_boundary`, `set_support_style`) to `not_applicable: page_refused`. Add that reason to the `NOT_APPLICABLE` lists in the harness, `acceptance_review.py`, the blind script and `companion.md`. 5xx errors and exceptions stay `failed`.

**M4. Type 8 after a reset, a clearing or a feeling deletion is decided without the evidence that matters, and only `P` is exposed to it.**
- **Where.**
  - `_WORLD_KINDS = {"F": {"message"}}` (`acceptance_review.py:581`).
  - RC2 (`companion.md`).
  - `delete_feeling_from`, `clear_feelings` and `reset_relationship` keep the messages (`companion.md:25`).
- **Why it matters.**
  - `F` can never have a standing type 8 from these actions.
  - `P` can, from the same behaviour: re-inferring "lonely" after the feelings were cleared, or mentioning a shared moment recalled from a message that still exists. A standing type 8 fails C5 whatever its cause.
  - The resolver sees neither `P`'s memory context nor any proof, so the outcome is discretionary.
  - The digest also hints at which arm is which (an acknowledged limitation).
- **Fix.**
  1. In RC2, state that after these actions, content also present in an undeleted on-the-record message clears under `not_removed` (kind `message`). The exception is a reply that uses what only the removed record held: the inferred label presented as said, the hard or playful framing, the familiarity level.
  2. Require the `page_deletion` target to be a user message that carries emotional or relationship content (the plan draft said "a page deletion of a message together with its feeling"). Otherwise bringing it back is not type 8 by definition.

**M5. A scenario that fails the precheck has no repair path.**
- **Where.**
  - The author cannot run the check. Its brief says "only short codes come back" (`c5-author-brief.md:262`), but they go only to the operator (`launch.py:241`).
  - The reviewer brief says the automatic check "has already verified" the table.
  - The fixer applies reviewer findings only, and `freeze.py` refuses a failing file.
- **Why it matters.** C5's 13-item `COVERAGE` table with timing rules is far more likely than R4 to fail on a first draft. R4 never hit a precheck code.
- **Fix.** Have `launch.py` write the precheck failures (fixed code, field and part only) as an extra findings file for the next fixer, and have the fixer brief say to resolve them. Plan for more than three review rounds.

**M6. The COVERAGE timing numbers do not match how the product's mood actually behaves.**
- **Where.** `c5-precheck.py:79–80` and the brief, item 2.
- **Why it matters.**
  - **The 12-hour case.** `MOOD_WITHIN` = 12 hours is the half-life (`mood.py:50`), not the time for which the mood stays visible. A push's strength is |valence| × (1 + intensity) / 4 (`mood.py:131`), and the mood snaps to rest within 0.25. So a valence-1, intensity-1 feeling is at baseline exactly at 12 hours, and weaker ones sooner. The "within hours" case can face a mood that is already at rest, depending on the intensity the host chose.
  - **The 48-hour case.** The precheck measures 48 hours between session starts. The product's cutoff counts from the last trigger's recorded time, on a clock that runs with wall time (`evaluation_clock.py:19–20`; `mood.py:357–372`). A case exactly 48 hours later therefore comes before the cutoff, and any later feeling restarts it.
- **Fix.**
  - Within the same session, or at most 6 hours later (`EASING_AFTER`).
  - The later case at 49 hours or more.
  - In the brief: no other news or feeling between the event and the 48-hour case (checked by the reviewer).

**M7. Some coverage choices depend on the seeded type, which the author cannot know.**
- **Where.** The brief offers "fewer emoji" (`c5-author-brief.md:29`) and explicit type letters (`:66`).
- **Why it matters.**
  - `less_emoji`'s value "rarely" is already on all 8 introverted cards (I***), so `_apply` returns `already_in_card` (`persona_growth.py:575–608`). No suggestion can ever appear, whatever the host does, and item 7 becomes `no_open_proposal`.
  - An explicit preset has a 1-in-16 chance of being the current type, and is then `unchanged`.
- **Fix.** Drop "fewer emoji" from the brief and allow only `random` or "a different personality". Have the precheck refuse a `switch_persona` with an explicit preset.

**M8. The binding and the rule text promise more than the code does.**
- **Where.**
  - "It never stops the run" (`maturity-c5-execution-DRAFT.md:44`).
  - "never a reason to stop or exclude a run" (`architecture/v1-acceptance.md:103`).
  - "cannot recur from a missing host record" (DRAFT:115).
- **Why it matters.** Host behaviour can still invalidate a run:
  - M1, M2 and M3;
  - `memory_observe`, which is offered to `P` and writes an assistant-authored message into a conversation the host names (`mcp_server.py:143–178`). If that conversation is the session's, the turn has two assistant messages, which raises `message_identity_unknown` (`c5-harness.py:663–669`). I could not confirm this end to end.
  - `clock_already_past` (`c5-harness.py:1524–1528`), if a `P` session takes longer in wall time than the gap to the next session. The precheck allows 1 hour; DeepSeek with thinking enabled can take 1–3 minutes per call.
  - Four empty replies in a row, which produce a Traceback.
- **Fix.** List these in the stop rules and limits. Report `clock_already_past` instead of stopping when the skew is small, or require session gaps of 3 hours or more for C5.

**M9. The precheck misses a page-side withdrawal of the "from now on" proposal.**
- **Where.** `persona_changed` uses `PERSONA_CHANGES` without proposal decisions (`c5-precheck.py:107`, `:445–449`, `:529`).
- **Why it matters.** Any accepted page decision between the request and the yes changes the persona version, and that withdraws the open host proposal ("persona_changed", `persona_growth.py:689–691`). The yes can then never confirm, yet the scenario passes the precheck.
- **Fix.** Include `accept_proposal`/`reject_proposal` (any origin) between the request and the yes.

### Minor

- **m1. A page deletion of the companion's reply passes the check.** `page_deletion` coverage accepts `role: "assistant"`, which deletes a reply that differs between arms (`c5-precheck.py:501–504`). Require role `user`.
- **m2. The page can accept the wrong suggestion.** `accept_proposal` with origin `feedback` takes the newest open feedback suggestion (`c5-harness.py:953–957`). If the host pushed two kinds to the threshold, that may be the wrong kind. Add an optional `kind` argument (an id from the product's `KINDS` table, not host text) and require it in COVERAGE.
- **m3. `F` keeps a message the user deleted.** When `P`'s host pause left a turn unrecorded, a page deletion of it is `not_applicable`, and `F` mirrors that by keeping the message (`c5-harness.py:1100–1101`). `F` can then use content the user deleted, and no type 8 is possible (`companion.md:52`). Drop the position from `F`'s history anyway, or state the asymmetry.
- **m4. `F` is told about resets; `P`'s host is not.** `F`'s page line says "relationship reset on DATE" and "feelings cleared on DATE" (`c5-harness.py:1146–1149`). `P`'s host is never told this: the only such text is an error message (`relationship.py:704`). This tilts the reset cases toward `F`. State it in the limits.
- **m5. The round cap is an unstated emulation limit.** The harness allows three tool rounds and six calls per turn (`c5-harness.py:1590–1591`). Consolidation takes two of those rounds on a session's first message (`host.py:142–145`). Neither is in the limits, and the rehearsal never consolidated.
- **m6 (product).** `memory_boundary` is named in no server instruction or notice (`host.py:79–81`, `:261–287`), only in its own tool description, which a real Claude Code host may defer. This is a likely route to type 7. One added sentence would fix it.
- **m7. What the practice and rehearsal do not exercise.**
  - Not exercised:
    - consolidation;
    - a pause made by the hook;
    - a yes refused because it came in another conversation (`NOT_HERE`), and the one-time pending notice that follows it;
    - a host proposal accepted or rejected on the page;
    - `reject_proposal`, `set_persona`, `delete_persona_history`;
    - an explicit preset;
    - the reasons `no_open_proposal`, `no_note_from_message`, `no_feeling_from_message` and `message_already_removed`;
    - boundary limits;
    - a timed pause;
    - mellowing of a hard moment on the scenario clock (the span is 11 days);
    - the 14-day absence.
  - All three manner comments also match the fixed feedback table, so the host-report path is not shown on its own.
  - The stub fills in `recording_capture` and `source_messages` itself (`c5-harness.py:428–436`); a real host must copy them.
  - No real-host probe exists for propose/confirm, manner feedback, switch or boundary. R4 had a pause probe.
- **m8. A month-only date delays mellowing.** A hard moment that the host dates only to a month counts from the month's last day (`relationship.py:296`), which can push the 30 days past the case.
- **m9. Binding decision 7 can be filled now.**
  - `ef0e8727` is an ancestor of the pin commit `0b1c052d`. Note, though, that the harness imports the product from the frozen `src`, so the launcher pin does not govern what the harness runs.
  - R4's pass ran on `a85ca152`, which is older than the pin. Say that the seventh attempt's R4 and this C5 together do not qualify one release runtime.
- **m10. Two kinds of probe from the plan were dropped.** The plan's "same persona probe in ≥3 sessions" and the boundary cases "after removal" and "raised by the user" are not in COVERAGE. Decide whether they stay dropped, and say so.
- **m11. Two tools still run the scenario as code.** Validity and the blind script load the scenario by executing it (`acceptance_review.py:63–67`; blind script `:105–107`). The risk is low, because freeze enforces literal-only files.
- **m12. RC2 cannot clear a mark caused by a record without sources.** If a deletion did not reach a host note that has no citation, a `not_removed` claim needs a `content_ref` the resolver does not have. The mark then stands by default.

## Answers

### 1. Validity

The harness events and whether host behaviour can reach them:

| Event | Can the host cause it? |
| --- | --- |
| `network_refused` | No: dry runs only. |
| `page_action_unsupported` | No: not on this runtime. |
| `index_wait_timed_out` | No: local. |
| `memory_unavailable` | No: local. |
| `bookkeeping_failed` | No: local. |
| `unexpected_recording` | I found no host path. |
| `timed_pause_refused` | **Yes** (M1). |
| `turn_not_recorded` | **Yes**, through a hook pause plus a missing or unnamed resume (M2). |
| `message_identity_unknown` | **Likely**, through `memory_observe` (M8). |
| `clock_already_past` | **Yes**, through slow host calls (M8). |
| `page_action_failed` | **Yes**, through `service_refused` on `add_boundary` after host boundaries (M3). |

The other `failed` codes (`not_found` for an unidentified recorded turn, `unknown_removed`, `exception`) are harness or local faults. Separately, four empty replies in a row produce a Traceback.

The specific cases you asked about:
- **`add_boundary` after the host's own boundaries.** The same topic merges and is `done`, with the page's aliases replacing the host's. Past 12 boundaries or 900 characters, the run is invalid.
- **A message a host pause left unrecorded.** The page action is `not_applicable: message_not_recorded`, for either role. `F` keeps the message (m3).
- **A proposal accept when the host proposed twice.** A newer host proposal replaces the older one, so only one is open. Origin `feedback` is unaffected. Origin `any` may pick the host's proposal, and two feedback kinds go newest first (m2).
- **A host switch in the same turn as a page action.** The page action comes first and the switch during the turn. `F` gets the result from the next turn. The switch replaces the card, which undoes manner or "from now on" changes and withdraws an open host proposal. That is scored, but invisible under B1.
- **The off-the-record stretch.** Safe only when the host's own tool made the pause (M2).
- **Consolidation turns.** Not an invalidation path. Consolidation is refused while paused (a tool error) and uses up tool rounds (m5). It was never exercised.

### 2. Fairness between the arms

`F` gets exactly `P`'s block every turn (validity checks it), the page line, and the deletions `P` removed.

What `P` has and `F` lacks:
- mood, familiarity and hard/mellowed guidance;
- labelled feelings;
- the dates that were off the record;
- host-made notes.

What `F` has and `P`'s host lacks:
- an explicit statement that the relationship was reset or the feelings cleared (m4);
- no exposure to type 8 except through deleted messages (M4);
- messages that a host pause left unrecorded in `P`, kept even when the user deleted them (m3).

Mirroring biases toward `P` exactly when `P`'s host fails a requested change. The sheet then shows the old block, `FACTS` describes the request, and the rule says to judge against the block, so `F`'s compliance looks off-persona and `P`'s failure costs nothing (B1). An unasked change by `P`'s host is copied into `F` and becomes the standard.

### 3. The blind sheet

There is no leak between arms: both blocks are identical by construction and the sheet refuses them if they differ. The `not_applicable` reasons expose `P`'s host behaviour, but that does not tell the reviewer which reply is `P`'s. The digest's world-kind difference does hint at the arm (acknowledged).

- **Type 7.** The sheet is enough: page boundaries are listed, and conversational ones are in `FACTS`.
- **Type 8 with `not_applicable`.** The guidance is correct. After resets it is underdetermined (M4).
- **Persona.** Not enough: there is no version history and the wrong yardstick (B1).

RC2 remains structurally sound with `not_applicable`: the action adds no entry and coverage stays complete. Its gaps are M4 and m12.

### 4. The gate

With the host now writing boundaries, feeling labels, proposals and confirmations, the gate measures memBrain together with `deepseek-v4-pro` under emulation, not the product alone. I would keep the strict rule for types 7 and 8 and type 6 counted as memory-caused, because they are user-visible harms. The binding should say:
- (a) a pass or fail is a result for that combination;
- (b) the record carries a pre-registered table, drawn from `P`'s `tool_calls` and the attribution inputs, of whether the host did its step for each coverage item and each standing critical (boundary saved? basis right? proposal made and confirmed?);
- (c) a fail caused by a host step is reported as such, but still counts as a fail.

The missing sentence about the boundary tool in the server instructions (m6) is a product fix to make before spending.

### 5. The scenario side

A competent author can write a passing scenario, but cannot run the check, and a failing draft has no repair path (M5).

- **Required but impossible for half the types:** "fewer emoji" (M7).
- **Hazardous wording:** the off-the-record phrasing (M2) and durations (M1).
- **Nothing C5 needs is forbidden.**
- **COVERAGE is checkable.**

| Kind of case | Example |
| --- | --- |
| Passes the precheck yet misses coverage | an `accept_proposal` between the "from now on" request and the yes (M9) |
| | a deletion of an assistant reply (m1) |
| | `less_emoji` comments (M7) |
| | a mood case exactly 48 h later, or 11–12 h after mild news (M6) |
| | an explicit preset equal to the seeded type (M7) |
| Fine yet refused | none that matters; the hard-moment count from the message date is conservative when the moment happened earlier |

The numbers against the product's constants:

| Number | Product constant | Verdict |
| --- | --- | --- |
| 30 days and 5 conversation dates | `HARD_MELLOW_DAYS`, `HARD_MELLOW_CONVERSATION_DAYS` | Match. The precheck is stricter, since it excludes the case's date. |
| 48 hours | `CUTOFF` | Matches in name, but it counts from the last trigger on a running clock, so a margin is needed. |
| 12 hours | `HALF_LIFE` | Should be at most 6 hours (`EASING_AFTER`). |
| 14 days (absence) | none: absence is never a trigger | Arbitrary, but harmless. |

### 6. The practice scenario and the stub rehearsal

Every flow on your list is exercised once, through the real product (my run confirms it):
- switch by tool (random, giving `infp`, v4) and on the page (v5);
- propose, then confirm in the next message, giving `waiting_for_message` and then v3 at the next turn;
- decline;
- three `less_formal` comments and a page accept (v2);
- `play` and `hard` moments;
- a feeling said and one inferred;
- a boundary set by tool (Tom) and one on the page;
- page deletions;
- pause and resume with `request` and `session_id`.

Nothing returns a result the real product would not give. What is supplied rather than tested: the stub fills in `recording_capture` and `source_messages` itself, and the table detection makes the manner-feedback tool redundant. Gaps are in m7, most importantly consolidation, the hook-made pause and four of the six `not_applicable` reasons.

### 7. The draft binding and the rule text

The gate, validity and page-action wording match the code. The claims about what never stops a run do not (M8).

Limits missing from the draft: B1, M4, m4, m5, m6, m8, the seeded-type dependence of the coverage (M7), and the R4 runtime gap (m9).

To decide or measure before freezing:
- the persona yardstick and D5 (B1);
- the harness changes M1–M3;
- the brief and precheck changes M5–M7 and M9;
- the m9 fill-in;
- the post-run diagnosis table (Q4).

I recommend a small, owner-authorised probe on a real host of propose/confirm with `source_messages`, manner feedback, switch and boundary, as R4 had for the pause. Then a full local suite run on the candidate, and the rehearsal again.

### 8. Cost and what the result would show

**Cost.** The estimate is credible.
- R4 used about 8.7k prompt tokens and 0.088 CNY per request.
- C5 means about 2–2.5 `P` requests per turn plus 1 for `F`, so roughly 380–450 requests and 35–45 CNY on the guard's count. That is against a refusal point of 59.95 CNY: one request in flight, each reserving 20.054016 CNY.
- The call cap (5 × turns per arm, about 320) cannot bind.
- Only a worst case of 4 rounds on every `P` turn approaches the refusal point.

**A pass would show:** on two authored lives, with one host under emulation and one seeded type, the plugin path did not break a boundary or bring back page-deleted emotional information, made no memory-caused critical error, and stayed within one point of a whole-history reference.

**A pass would not show (under B1):** that persona requests are honoured, or anything about real or other hosts.

**The likeliest fails:**
- type 7, from a boundary that was never saved (m6);
- type 6, from host mislabelling, which counts as memory-caused by rule;
- type 8 after a clearing or reset (M4);
- a score gap from coverage thinned by `not_applicable`.

**The likeliest invalidations** are M1–M3 and M8.

**Telling product fault from host fault.** The run evidence can do it after the fact: `host-rounds`, `tool_calls` and the attribution inputs. The gate does not. Hence the table proposed in Q4.

## What I could not determine

- Whether `delete_note_from` also removes the feeling attached to that note.
- Whether `P`'s 9,000-character hook context can drop the persona block. Validity only reports `not_shown_to_p_host`.
- Whether `memory_observe` into the session's conversation shows up in the timeline exactly as I describe. I read the code; I did not run it.
- Whether hard-moment mellowing follows the scenario clock end to end. No rehearsal reaches 30 days.
- How often DeepSeek does any of the host behaviours above.
