# Companion scenario fixer brief

You apply findings to one test scenario for an evaluation of AI companions. `scenario.py` is the scenario,
`findings.md` the findings, `author-brief.md` the brief the scenario was written to (its rules and its criteria
templates), `assignment.md` the scenario's assignment (its coverage items), and `brief.md` this file. The findings
are of one of three kinds:
- **A reviewer's findings** (headed "Findings"): blocking findings B1, B2, ... and minor ones M1, M2, .... Apply
  every one.
- **A verifier's findings** (headed "Verification"): blocking findings B1, B2, ... and advisory notes A1, A2, ....
  Apply every blocking finding; **do not apply the advisory notes** (they are not changes to make).
- **Findings of the automatic check** (the file is headed "Findings of the automatic check (not of a reviewer)"):
  one line per failure, a fixed code and where it is (`session=N`, `turn=N`, `case=N`, `action=N`, `entry=N` count
  from 0 in `SESSIONS_LONG`, `CASES`, `PAGE_ACTIONS` and `EXPECT_RECORDING_P`; `at=S:T` is a session index and
  turn index; `field=` and `part=` name a `COVERAGE` requirement and its key). What each code means is below.
  Change the smallest thing that removes each failure while keeping every rule below and the story as it is.

Work only in this directory. Read only these files. Do not open, list or search anything else on this machine, do
not use the web, and do not run the scenario file.

**Apply a blocking finding word for word**: put in exactly the new text it gives, at the places it names, and make
the other changes it lists. A verifier will check that the text it gave is in the file. Apply a minor finding as it
asks, but never by changing a coverage case's "must" or "must not" away from its template in `author-brief.md`.
Change nothing else: keep every other message, fact, case, criterion, page action and `COVERAGE` entry word for
word. When a finding asks for a change that would break another rule it quotes, apply the change in the way that
keeps that rule. Keep the file a Python module that only defines `YEAR`, `HOST`, `SESSIONS_LONG`, `FACTS`, `CASES`,
`PAGE_ACTIONS`, `COVERAGE` and, if present, `EXPECT_RECORDING_P`, with plain literal values; keep the 11 cases, the
60 to 66 user messages and the case ids' prefix and numbering.

Positions refer to messages: a page action is `(session_id, before_turn, {...})` and acts before that user message; a
deletion names its message by `"session"` and `"turn"`; `COVERAGE` names messages as `(session_id, turn_index)`,
cases by id, and page actions as `(session_id, before_turn, kind)`. When you add, remove or move a message, update
every case, page action, `COVERAGE` entry and `EXPECT_RECORDING_P` entry whose turn index it shifts, and keep
`FACTS` in agreement. Keep a "from now on" request and the user's yes in the same session, and keep each session's
first message stating its weekday, date and time in the form it already uses.

Rules a change must keep. Every user message reads naturally whatever the reply before it was: it never reacts to,
thanks for, agrees with or answers something the companion said, and never assumes what it said (`author-brief.md`,
"Every user message stands on its own"); it has at least 16 characters (6 when mostly Chinese) besides a session's
opening date and time, and does not open with a reaction ("Ha", "Cool", "Thanks", "Fair enough", "Klingt gut",
"好的", ...). Sessions start at least three hours apart, in time order, and the story spans at least 45 days. A
"from now on" request asks the companion to behave or respond differently in general, in its manner of responding
("From now on, when I'm upset, could you just listen first instead of jumping to advice?"); it is never a task, a
reminder, a check-in or anything tied to a time or an event, and never one of the manner-comment kinds (length,
formality, jokes). Manner comments are about formality, jokes or length, never emoji; the page acceptance of their
suggestion is `{"do": "accept_proposal", "origin": "feedback", "kind": ...}` with their kind (`"less_formal"`,
`"more_formal"`, `"more_playful"`, `"shorter"` or `"longer"`). The user never names a personality type, and a page
switch is `{"do": "switch_persona", "preset": "random"}`. No page decision on a suggestion and no switch comes
between the "from now on" request and its yes, or between an item and its case. `COVERAGE` holds exactly the items
of the assignment's coverage line, and no case serves two items. The deleted message of `"page_deletion"` is a user
message carrying emotional or relationship content. The two mood cases' sessions start at most 6 hours, and at least
49 hours, after the news's session, with no other declared feeling or shared moment in between. Outside the
off-the-record stretch no message begins with a request not to be remembered or recorded, and the stretch names no
duration.

The codes of the automatic check: `c5_not_literal` (only literal assignments), `c5_persona`, `c5_stub_script`,
`c5_unknown_name` (a name outside the format), `c5_missing` (`field=` names it), `c5_case_count` (11),
`c5_turn_count` (60 to 66), `c5_case_position`, `c5_case_id`, `c5_case_prefix`, `c5_recording_position`,
`c5_recording_shape`, `c5_no_weekday`, `c5_action_arms`, `c5_action_off_record`, `c5_action_limit` (a boundary
topic up to 60 characters with at most 6 other words of up to 40, a support style up to 200), `c5_named_preset`,
`c5_span`, `c5_short_message` (the message at `at=` is too short: make it a complete message that does not react to
a reply), `c5_reaction_opening` (the message at `at=` opens with a reaction to a reply: remove the reaction, keep the
rest), and for `COVERAGE` (`field=`, `part=`): `c5_coverage_shape`, `c5_coverage_unknown`, `c5_coverage_missing` (an
item of the coverage line is missing), `c5_coverage_not_required` (an item not on the coverage line: remove it from
`COVERAGE`), `c5_coverage_shared_case` (the item at `field=` names a case another item already names: give it its own
case), `c5_coverage_position`, `c5_coverage_case`, `c5_coverage_action` (no or several matching page actions, or the
wrong kind, origin, manner kind or role), `c5_coverage_distinct`, `c5_coverage_order`, `c5_coverage_timing`,
`c5_coverage_undone` (something in between undoes the item), `c5_coverage_off_record`; and `no_date`, `no_time`,
`bad_date`, `not_increasing`, `too_close`, `gap_under_3h`, `weekday_mismatch`, `malformed_session`,
`duplicate_session`, `bad_action`, `malformed_action`, `pause_outside_stretch` (a message outside the stretch would
pause recording by itself), `timed_pause`.

Write the corrected file as `scenario.py` in this directory (replacing it), and `fixes.json` as
`{"applied": <number of findings applied>, "fixes": [{"finding": "<B1, M2 or the code and position>", "change":
"<what you changed, in one line>"}, ...]}`, one entry per finding applied. Your final message should say only that
both are written. Do not repeat the scenario's content anywhere else.
