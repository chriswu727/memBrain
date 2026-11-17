"""Count-only C5 scenario precheck: is a scenario file fit for the C5 harness, before any service or model starts?

Usage: python c5-precheck.py [--r4 | --c5] SCENARIO.py

Checks, with the harness's own parsers:
- every session's first message states a date and a time (`session_start`);
- session starts are strictly increasing, and at least one hour apart;
- every PAGE_ACTIONS entry passes `check_actions` (a known kind of the harness's vocabulary at a real position, with
  exactly its kind's arguments; a message named by position comes before the action; a removed boundary is a topic
  an earlier page action added), checked one at a time with the others as context;
- no timed pause is scripted (a `memory_pause` with `hours` in STUB_HOST, or a page action with `hours`): the pause
  would run on the wall clock while the scenario clock moves by days.

With --r4 (an R4 behavioural-acceptance scenario) it also refuses PAGE_ACTIONS (`r4_page_actions`) and PERSONA
(`r4_persona`): both arms carry the attempt's seeded personality type, which the harness sets, and scenario authors
never need to know product internals. It refuses stub scripts (`r4_stub_script`), and checks the R4 shape: eleven
cases (`r4_case_count`), 60 to 66 user messages (`r4_turn_count`), HOST, FACTS and CASES present (`r4_missing`),
every case names a real (session, turn) position (`r4_case_position`) with a unique id (`r4_case_id`), and every
EXPECT_RECORDING_P entry names a real position (`r4_recording_position`). In --r4 mode the file is read without
running it (scenario_literals.py: top-level literal assignments only, `r4_not_literal`), every session states a
weekday (`r4_no_weekday`), and EXPECT_RECORDING_P is present (`r4_recording_missing`) with the one shape the harness
can run without stopping a live arm (`r4_recording_shape`): all entries in one session, at consecutive turns, every
one False except the last, which is True (the request to resume). The harness treats a False entry as "may stay
unrecorded" and stops a live arm on any unrecorded turn the scenario did not declare, so a stretch declared one turn
short, split across sessions, or without the resume turn would end a paid attempt.

With --c5 (a held-out C5 companion scenario) the file is read the same way, without running it (`c5_not_literal`),
and the R4 shape rules apply with C5 codes: eleven cases (`c5_case_count`), 60 to 66 user messages
(`c5_turn_count`), HOST, FACTS, CASES, PAGE_ACTIONS and COVERAGE present (`c5_missing`), real case positions
(`c5_case_position`), unique case ids of the form <PREFIX>NN-<slug> (`c5_case_id`) sharing one prefix and numbered 01
to 11 in order (`c5_case_prefix`), a weekday in every session (`c5_no_weekday`), and, when the scenario has an
off-the-record stretch, EXPECT_RECORDING_P at real positions (`c5_recording_position`) in the one shape the harness
runs (`c5_recording_shape`); the stretch is allowed, not required. It refuses PERSONA (`c5_persona`: both arms start
from the attempt's seeded type and the persona changes only as the user changes it), any STUB_* script
(`c5_stub_script`), any other name outside the format (`c5_unknown_name`), a page action naming "arms"
(`c5_action_arms`), a deletion aimed at a declared off-the-record message (`c5_action_off_record`: it could only
find nothing), and a boundary, support style or card the product's own validators refuse (`c5_action_limit`: the
service would refuse it in the run, which makes the run invalid). The story spans at least 45 scenario days (`c5_span`). Then it checks the scenario's COVERAGE table
(the author's declaration of where each companion requirement happens; `c5_coverage_*`, see check_c5): every
requirement present, of its shape, at real positions, cases and page actions, in the required order and timing, not
undone by a page action before its case, and not off the record. What cannot be read from text (that a message
really states a feeling, that the host makes a proposal the user's yes answers) is the reviewers' to check.

In every mode a stated weekday must be that date's weekday in the scenario's YEAR (`weekday_mismatch`): English
"Today is Tuesday, March 3", Spanish "Hoy es martes, 3 de marzo", German "Heute ist Dienstag, der 3. März", Chinese
"今天是3月3日，星期二" or "周二". Both arms are told "Today's date: … (weekday)" from the parsed date, so a wrong weekday
would contradict the user's own words.

It prints only counts and positions (session index, turn index, action index) with short failure codes. It never
prints a message, a session id, a topic, a label or an exception's text: held-out scenarios can be prechecked
without being read. Output from loading the scenario is discarded. Exit 0 when the scenario is fit, 1 when it is not,
2 on a usage error. The last line is a one-line JSON summary.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import re
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

MIN_GAP = datetime.timedelta(hours=1)
R4_CASES, R4_TURNS = 11, (60, 66)  # An R4 scenario: eleven cases, 60 to 66 user messages.
# Weekday names by Python weekday (Monday = 0), as scenarios state them.
WEEKDAYS = [("monday", "lunes", "montag", "一"), ("tuesday", "martes", "dienstag", "二"),
            ("wednesday", "miércoles", "mittwoch", "三"), ("thursday", "jueves", "donnerstag", "四"),
            ("friday", "viernes", "freitag", "五"), ("saturday", "sábado", "samstag", "六"),
            ("sunday", "domingo", "sonntag", "日", "天")]
STATED = re.compile(r"(?:Today is|Hoy es|Heute ist) (\w+),|今天是\d+月\d+日[，,、\s]*(?:星期|周)([一二三四五六日天])",
                    re.IGNORECASE)
# A held-out C5 scenario: the R4 size, the names it may define, the names it must define, and its time rules.
C5_CASES, C5_TURNS = 11, (60, 66)
C5_SPAN_DAYS = 45
C5_NAMES = ("YEAR", "HOST", "SESSIONS_LONG", "FACTS", "CASES", "PAGE_ACTIONS", "COVERAGE", "EXPECT_RECORDING_P")
C5_REQUIRED = ("HOST", "FACTS", "CASES", "PAGE_ACTIONS", "COVERAGE")
MOOD_WITHIN = datetime.timedelta(hours=12)  # A mood case "within hours": its session starts at most 12 hours later.
MOOD_AFTER = datetime.timedelta(hours=48)  # The product's cutoff: the mood is exactly the baseline 48 hours after.
HARD_DAYS, HARD_CONVERSATION_DAYS = 30, 5  # The product's relationship.HARD_MELLOW_DAYS / _CONVERSATION_DAYS.
ABSENCE_DAYS = 14  # A long absence: the return session's date at least 14 days after the session before it.
CASE_ID = re.compile(r"([A-Z][A-Z0-9]*?)(\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*")
# The COVERAGE table (format 1): requirement -> {key: kind of value}. "position" is (session_id, turn_index) of a
# user message; "positions" a list of at least three of them; "case" a case id of CASES; "action" a
# (session_id, before_turn, kind) triple naming exactly one PAGE_ACTIONS entry. "switch" takes either "request" or
# "action", not both.
COVERAGE_FIELDS = {
    "stated_feeling": {"message": "position", "case": "case"},
    "inferred_feeling": {"message": "position", "case": "case"},
    "mood": {"event": "position", "within_hours": "case", "after_48_hours": "case"},
    "feelings_question": {"case": "case"},
    "boundary_in_conversation": {"asked": "position", "case": "case"},
    "boundary_on_page": {"action": "action", "case": "case"},
    "page_deletion": {"action": "action", "case": "case"},
    "reset": {"action": "action", "case": "case"},
    "manner_feedback": {"comments": "positions", "accept": "action", "case": "case"},
    "from_now_on": {"request": "position", "yes": "position", "case": "case"},
    "switch": {"request": "position", "action": "action", "case": "case"},
    "shared_moments": {"play": "position", "hard": "position", "case": "case"},
    "absence": {"case": "case"},
}
OPTIONAL_KEYS = {"switch": ({"request", "action"}, 1)}  # Exactly one of these keys.
ACTION_KINDS = {("boundary_on_page", "action"): ("add_boundary",), ("page_deletion", "action"): ("delete_message",),
                ("reset", "action"): ("reset_relationship", "clear_feelings"),
                ("manner_feedback", "accept"): ("accept_proposal",), ("switch", "action"): ("switch_persona",)}
PERSONA_CHANGES = ("switch_persona", "set_persona", "delete_persona_history")
C5_CODES = ("c5_not_literal", "c5_persona", "c5_stub_script", "c5_unknown_name", "c5_missing", "c5_case_count",
            "c5_turn_count", "c5_case_position", "c5_case_id", "c5_case_prefix", "c5_recording_position",
            "c5_recording_shape", "c5_no_weekday", "c5_action_arms", "c5_action_off_record", "c5_action_limit",
            "c5_span",
            "c5_coverage_shape", "c5_coverage_unknown", "c5_coverage_missing", "c5_coverage_position",
            "c5_coverage_case", "c5_coverage_action", "c5_coverage_distinct", "c5_coverage_order",
            "c5_coverage_timing", "c5_coverage_undone", "c5_coverage_off_record")
# Every failure code this precheck prints; tools that relay its result print only these.
CODES = ("no_sessions", "malformed_session", "duplicate_session", "no_date", "no_time", "bad_date", "not_increasing",
         "too_close", "weekday_mismatch", "bad_action", "proposal_without_card", "proposals_unsupported",
         "malformed_action", "timed_pause", "load_failed", "r4_not_literal", "r4_page_actions", "r4_persona",
         "r4_missing", "r4_stub_script", "r4_case_count", "r4_turn_count", "r4_case_position", "r4_case_id",
         "r4_recording_position", "r4_recording_missing", "r4_recording_shape", "r4_no_weekday",
         *C5_CODES)


def stated_weekday(text: str):
    """The weekday a session's first message states, as an index (Monday = 0), None when it states none, or -1 for
    a word that is no weekday."""
    match = STATED.search(text)
    if not match:
        return None
    word = (match[1] or match[2] or "").lower()
    return next((index for index, names in enumerate(WEEKDAYS) if word in names), -1)


def recording_shape_ok(entries) -> bool:
    """EXPECT_RECORDING_P as the harness can run it: one session, consecutive turns, False ... False, then True."""
    try:
        entries = [(session, turn, expected) for session, turn, expected in entries]
    except (TypeError, ValueError):
        return False
    if len(entries) < 2 or len({session for session, _, _ in entries}) != 1:
        return False
    turns = [turn for _, turn, _ in entries]
    if any(type(turn) is not int for turn in turns) or turns != list(range(turns[0], turns[0] + len(turns))):
        return False
    return all(expected is False for _, _, expected in entries[:-1]) and entries[-1][2] is True


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _start_code(error: BaseException) -> str:
    """A session_start failure as a code. Its message quotes the session's first message, so it is never shown."""
    if isinstance(error, ValueError) and str(error).startswith("no scenario date"):
        return "no_date"
    if isinstance(error, ValueError) and str(error).startswith("no scenario time"):
        return "no_time"
    return "bad_date"


def _action_code(error: BaseException) -> str:
    """A check_actions failure as a code. Its message names the action's session id."""
    text = str(getattr(error, "code", "") or "")
    if text.startswith("bad page action"):
        return "bad_action"
    if text.startswith("an accepted proposal"):
        return "proposal_without_card"
    if text.startswith("this runtime has no persona proposals"):
        return "proposals_unsupported"
    return "malformed_action"


def _timed(arguments) -> bool:
    return isinstance(arguments, dict) and arguments.get("hours") is not None


def check_r4(module, positions: dict) -> list[dict]:
    """The R4-only rules, as codes and positions only."""
    failures = []
    if list(getattr(module, "PAGE_ACTIONS", None) or []):
        failures.append({"code": "r4_page_actions"})
    if getattr(module, "PERSONA", None):
        failures.append({"code": "r4_persona"})
    for name in ("HOST", "FACTS", "CASES"):
        if not getattr(module, name, None):
            failures.append({"code": "r4_missing", "field": name})
    if [name for name in vars(module) if name.startswith("STUB_")]:
        failures.append({"code": "r4_stub_script"})
    if len(list(getattr(module, "CASES", None) or [])) != R4_CASES:
        failures.append({"code": "r4_case_count"})
    if not R4_TURNS[0] <= len(positions) <= R4_TURNS[1]:
        failures.append({"code": "r4_turn_count"})
    seen = set()
    for number, entry in enumerate(list(getattr(module, "CASES", None) or [])):
        try:
            session, turn, case, _criteria = entry
        except (TypeError, ValueError):
            failures.append({"code": "r4_case_position", "case": number})
            continue
        if (session, turn) not in positions:
            failures.append({"code": "r4_case_position", "case": number})
        if not isinstance(case, str) or case in seen:
            failures.append({"code": "r4_case_id", "case": number})
        seen.add(case)
    for number, entry in enumerate(list(getattr(module, "EXPECT_RECORDING_P", None) or [])):
        try:
            session, turn, _expected = entry
            known = (session, turn) in positions
        except (TypeError, ValueError):
            known = False
        if not known:
            failures.append({"code": "r4_recording_position", "entry": number})
    recording = list(getattr(module, "EXPECT_RECORDING_P", None) or [])
    if not recording:
        failures.append({"code": "r4_recording_missing"})
    elif not recording_shape_ok(recording):
        failures.append({"code": "r4_recording_shape"})
    for number, entry in enumerate(list(getattr(module, "SESSIONS_LONG", None) or [])):
        try:
            first = entry[1][0]
        except (TypeError, IndexError, KeyError):
            continue
        if isinstance(first, str) and stated_weekday(first) is None:
            failures.append({"code": "r4_no_weekday", "session": number})
    return failures


def _pos_shape(value) -> bool:
    return isinstance(value, tuple | list) and len(value) == 2 and isinstance(value[0], str) \
        and type(value[1]) is int


def _topic(text) -> str:
    """A boundary topic as the harness and the product compare it: whitespace collapsed, case ignored."""
    return " ".join(str(text or "").split()).casefold()


def _within_product_limits(action: dict) -> bool:
    """Whether the product would take this page action's own words: a boundary topic and its other words, a support
    style and a card are checked with the product's validators (pure functions, no service). The service refusing a
    well-formed action is a harness fault (failed: service_refused) that makes the run invalid, so it is caught
    here, before any model call."""
    from membrain import persona, relationship
    from membrain.helpers import DomainError

    try:
        if action.get("do") == "add_boundary":
            relationship._boundary(action.get("topic"), action.get("aliases", []))
        elif action.get("do") == "set_support_style":
            relationship._support(action.get("text"))
        elif action.get("do") == "set_persona":
            persona.normalize_card(action.get("card"))
    except (DomainError, TypeError, ValueError):
        return False
    return True


def check_c5(module, positions: dict, starts: dict) -> tuple[list[dict], int]:
    """The C5-only rules (see the module docstring), as codes, positions and fixed field names only: never a name,
    topic, case id or message from the scenario.

    COVERAGE (format 1) maps each requirement of COVERAGE_FIELDS to a dict of its keys. Order is the scenario's: a
    user message at (session, turn) comes after every page action applied before that turn (before_turn == turn), so
    "after an action" includes the case whose message the action comes just before. Session times are the session
    starts the harness parses; a date is a session's date."""
    failures = []
    names = set(vars(module))
    sessions = list(getattr(module, "SESSIONS_LONG", None) or [])
    if "PERSONA" in names:
        failures.append({"code": "c5_persona"})
    stubs = {name for name in names if name.startswith("STUB_")}
    if stubs:
        failures.append({"code": "c5_stub_script"})
    unknown = names - set(C5_NAMES) - {"PERSONA"} - stubs
    if unknown:
        failures.append({"code": "c5_unknown_name", "count": len(unknown)})
    for name in C5_REQUIRED:
        if not getattr(module, name, None):
            failures.append({"code": "c5_missing", "field": name})
    if len(list(getattr(module, "CASES", None) or [])) != C5_CASES:
        failures.append({"code": "c5_case_count"})
    if not C5_TURNS[0] <= len(positions) <= C5_TURNS[1]:
        failures.append({"code": "c5_turn_count"})

    # Cases: real positions, unique ids <PREFIX>NN-<slug> with one prefix, numbered 01 to 11 in order.
    cases, seen, prefixes, numbers = {}, set(), set(), []
    for number, entry in enumerate(list(getattr(module, "CASES", None) or [])):
        try:
            session, turn, case, _criteria = entry
            known = (session, turn) in positions
        except (TypeError, ValueError):
            failures.append({"code": "c5_case_position", "case": number})
            continue
        if not known:
            failures.append({"code": "c5_case_position", "case": number})
        match = CASE_ID.fullmatch(case) if isinstance(case, str) else None
        if match is None or case in seen:
            failures.append({"code": "c5_case_id", "case": number})
        else:
            prefixes.add(match[1])
            numbers.append(int(match[2]))
            if known:
                cases[case] = (session, turn)
        seen.add(case if isinstance(case, str) else number)
    if len(prefixes) > 1 or (numbers and numbers != list(range(1, len(numbers) + 1))):
        failures.append({"code": "c5_case_prefix"})

    # The optional off-the-record stretch, in the harness's one shape.
    recording = list(getattr(module, "EXPECT_RECORDING_P", None) or [])
    off_record = set()
    for number, entry in enumerate(recording):
        try:
            session, turn, expected = entry
            known = (session, turn) in positions
        except (TypeError, ValueError):
            known = False
        if not known:
            failures.append({"code": "c5_recording_position", "entry": number})
        elif expected is False:
            off_record.add((session, turn))
    if recording and not recording_shape_ok(recording):
        failures.append({"code": "c5_recording_shape"})
    for number, entry in enumerate(sessions):
        try:
            first = entry[1][0]
        except (TypeError, IndexError, KeyError):
            continue
        if isinstance(first, str) and stated_weekday(first) is None:
            failures.append({"code": "c5_no_weekday", "session": number})
    if 0 in starts and len(sessions) - 1 in starts and \
            (starts[len(sessions) - 1].date() - starts[0].date()).days < C5_SPAN_DAYS:
        failures.append({"code": "c5_span"})

    # Page actions: the harness's check_actions ran already; here what is C5-only.
    actions = list(getattr(module, "PAGE_ACTIONS", None) or [])
    formed = {}
    for number, entry in enumerate(actions):
        try:
            session, before, action = entry
            formed[number] = (positions[(session, before)][0], before, action) if isinstance(action, dict) else None
        except (TypeError, ValueError, KeyError):
            formed[number] = None
        action = formed[number][2] if formed[number] else None
        if action is None:
            continue
        if "arms" in action:
            failures.append({"code": "c5_action_arms", "action": number})
        target = (action.get("session"), action.get("turn"))
        if action.get("do") in ("delete_message", "delete_note_from", "delete_feeling_from") and \
                all(isinstance(part, str | int) for part in target) and target in off_record:
            failures.append({"code": "c5_action_off_record", "action": number})
        if not _within_product_limits(action):
            failures.append({"code": "c5_action_limit", "action": number})
    coverage, covered = _coverage(module, positions, starts, sessions, cases, formed, off_record)
    return failures + coverage, covered


def _coverage(module, positions, starts, sessions, cases, formed, off_record) -> tuple[list[dict], int]:
    """The COVERAGE table's checks (see check_c5), and how many requirements passed them all."""
    failures = []
    if "COVERAGE" not in vars(module):
        return failures, 0  # c5_missing already says so.
    table = module.COVERAGE
    if not isinstance(table, dict):
        return [{"code": "c5_coverage_shape", "field": "COVERAGE"}], 0
    unknown = [key for key in table if key not in COVERAGE_FIELDS]
    if unknown:
        failures.append({"code": "c5_coverage_unknown", "count": len(unknown)})

    def message(key):
        return (positions[key][0], key[1], 1)

    def applied(index):
        return (formed[index][0], formed[index][1], 0)

    def between(start, end, test, skip=None) -> bool:
        return any(item is not None and index != skip and start < applied(index) < end and test(item[2])
                   for index, item in formed.items())

    def date(point):
        return starts[point[0]].date() if point[0] in starts else None

    resolved = {}
    for field, spec in COVERAGE_FIELDS.items():
        if field not in table:
            failures.append({"code": "c5_coverage_missing", "field": field})
            continue
        entry = table[field]
        choice = OPTIONAL_KEYS.get(field)
        required = set(spec) - (choice[0] if choice else set())
        if not isinstance(entry, dict) or required - set(entry) or set(entry) - set(spec) or (
                choice and len(choice[0] & set(entry)) != choice[1]):
            failures.append({"code": "c5_coverage_shape", "field": field})
            continue
        values, problems = {}, []
        for key, value in entry.items():
            kind = spec[key]
            if kind == "case":
                if not isinstance(value, str):
                    problems.append(("c5_coverage_shape", key))
                elif value not in cases:
                    problems.append(("c5_coverage_case", key))
                else:
                    values[key] = message(cases[value])
            elif kind in ("position", "positions"):
                items = list(value) if kind == "positions" and isinstance(value, list | tuple) else [value]
                if kind == "positions" and len(items) < 3 or not all(_pos_shape(item) for item in items):
                    problems.append(("c5_coverage_shape", key))
                    continue
                keys = [(item[0], item[1]) for item in items]
                if any(item not in positions for item in keys):
                    problems.append(("c5_coverage_position", key))
                elif any(item in off_record for item in keys):
                    problems.append(("c5_coverage_off_record", key))
                else:
                    values[key] = keys if kind == "positions" else keys[0]
            else:  # An action: (session_id, before_turn, kind), exactly one matching PAGE_ACTIONS entry.
                if not (isinstance(value, tuple | list) and len(value) == 3 and isinstance(value[0], str)
                        and type(value[1]) is int and isinstance(value[2], str)):
                    problems.append(("c5_coverage_shape", key))
                    continue
                matches = [index for index, item in formed.items() if item is not None
                           and module.PAGE_ACTIONS[index][0] == value[0] and item[1] == value[1]
                           and item[2].get("do") == value[2]]
                kinds = ACTION_KINDS.get((field, key), ())
                if len(matches) != 1 or value[2] not in kinds or (
                        field == "manner_feedback" and formed[matches[0]][2].get("origin") != "feedback"):
                    problems.append(("c5_coverage_action", key))
                else:
                    values[key] = matches[0]
        for code, key in problems:
            failures.append({"code": code, "field": field, "part": key})
        if not problems:
            resolved[field] = values

    def fail(code, field, part):
        failures.append({"code": code, "field": field, "part": part})

    switch = resolved.get("switch", {})
    switch_point = message(switch["request"]) if "request" in switch else None

    def persona_change(action) -> bool:
        return action.get("do") in PERSONA_CHANGES

    def persona_changed(start, end) -> bool:
        return between(start, end, persona_change) or (switch_point is not None and start < switch_point < end)

    for field in ("stated_feeling", "inferred_feeling"):
        if field not in resolved:
            continue
        said, case = resolved[field]["message"], resolved[field]["case"]
        if not message(said) < case:
            fail("c5_coverage_order", field, "case")
        elif between(message(said), case, lambda action, said=said: action.get("do") == "clear_feelings" or (
                action.get("do") in ("delete_message", "delete_feeling_from")
                and (action.get("session"), action.get("turn")) == said and action.get("role", "user") == "user")):
            fail("c5_coverage_undone", field, "case")
    if {"stated_feeling", "inferred_feeling"} <= set(resolved) and \
            resolved["stated_feeling"]["message"] == resolved["inferred_feeling"]["message"]:
        fail("c5_coverage_distinct", "inferred_feeling", "message")

    if "mood" in resolved:
        event = message(resolved["mood"]["event"])
        soon, later = resolved["mood"]["within_hours"], resolved["mood"]["after_48_hours"]
        if not event < soon:
            fail("c5_coverage_order", "mood", "within_hours")
        else:
            if event[0] in starts and soon[0] in starts and starts[soon[0]] - starts[event[0]] > MOOD_WITHIN:
                fail("c5_coverage_timing", "mood", "within_hours")
            if between(event, soon, lambda action: action.get("do") in ("reset_mood", "clear_feelings") or (
                    action.get("do") == "pin_mood" and action.get("pinned", True) is True)):
                fail("c5_coverage_undone", "mood", "within_hours")
        if not event < later:
            fail("c5_coverage_order", "mood", "after_48_hours")
        elif event[0] in starts and later[0] in starts and starts[later[0]] - starts[event[0]] < MOOD_AFTER:
            fail("c5_coverage_timing", "mood", "after_48_hours")

    if "boundary_in_conversation" in resolved:
        asked, case = message(resolved["boundary_in_conversation"]["asked"]), resolved["boundary_in_conversation"][
            "case"]
        if not asked < case:
            fail("c5_coverage_order", "boundary_in_conversation", "case")
        elif between(asked, case, lambda action: action.get("do") == "reset_relationship"):
            fail("c5_coverage_undone", "boundary_in_conversation", "case")

    if "boundary_on_page" in resolved:
        index, case = resolved["boundary_on_page"]["action"], resolved["boundary_on_page"]["case"]
        topic = _topic(formed[index][2].get("topic"))
        if not applied(index) < case:
            fail("c5_coverage_order", "boundary_on_page", "case")
        elif between(applied(index), case, lambda action: action.get("do") == "reset_relationship" or (
                action.get("do") == "remove_boundary" and _topic(action.get("topic")) == topic)):
            fail("c5_coverage_undone", "boundary_on_page", "case")

    for field in ("page_deletion", "reset"):
        if field in resolved and not applied(resolved[field]["action"]) < resolved[field]["case"]:
            fail("c5_coverage_order", field, "case")
    if "page_deletion" in resolved:
        target = formed[resolved["page_deletion"]["action"]][2]
        if any((target.get("session"), target.get("turn")) == item for item in off_record):
            fail("c5_coverage_off_record", "page_deletion", "action")

    if "manner_feedback" in resolved:
        comments = resolved["manner_feedback"]["comments"]
        accept, case = applied(resolved["manner_feedback"]["accept"]), resolved["manner_feedback"]["case"]
        points = [message(item) for item in comments]
        if len(set(comments)) != len(comments):
            fail("c5_coverage_distinct", "manner_feedback", "comments")
        elif points != sorted(points) or not points[-1] < accept:
            fail("c5_coverage_order", "manner_feedback", "accept")
        elif between(points[0], accept, lambda action: action.get("do") in ("delete_persona_history",
                                                                            "reject_proposal") or (
                action.get("do") == "delete_message" and action.get("role", "user") == "user"
                and (action.get("session"), action.get("turn")) in comments)):
            fail("c5_coverage_undone", "manner_feedback", "accept")
        if not accept < case:
            fail("c5_coverage_order", "manner_feedback", "case")
        elif persona_changed(accept, case):
            fail("c5_coverage_undone", "manner_feedback", "case")

    if "from_now_on" in resolved:
        request, yes = resolved["from_now_on"]["request"], resolved["from_now_on"]["yes"]
        case = resolved["from_now_on"]["case"]
        if request[0] != yes[0] or not request[1] < yes[1]:
            fail("c5_coverage_order", "from_now_on", "yes")
        elif persona_changed(message(request), message(yes)):
            fail("c5_coverage_undone", "from_now_on", "yes")
        if not message(yes)[0] < case[0]:
            fail("c5_coverage_order", "from_now_on", "case")
        elif persona_changed(message(yes), case):
            fail("c5_coverage_undone", "from_now_on", "case")

    if "switch" in resolved:
        point = switch_point if switch_point is not None else applied(switch["action"])
        case = switch["case"]
        if not point < case:
            fail("c5_coverage_order", "switch", "case")
        elif between(point, case, persona_change, skip=switch.get("action")):
            fail("c5_coverage_undone", "switch", "case")

    if "shared_moments" in resolved:
        play, hard, case = (resolved["shared_moments"][key] for key in ("play", "hard", "case"))
        if play == hard:
            fail("c5_coverage_distinct", "shared_moments", "hard")
        if not message(hard) < case:
            fail("c5_coverage_order", "shared_moments", "case")
        else:
            day, today = date(message(hard)), date(case)
            if day is not None and today is not None:
                # Conversation days the product counts by the case: distinct later dates with a recorded message,
                # strictly before the case's own date (that day may not be recorded yet when the case is asked).
                talked = {starts[number].date() for number, (_, turns) in enumerate(sessions) if number in starts
                          and day < starts[number].date() < today
                          and any((sessions[number][0], turn) not in off_record for turn in range(len(turns)))}
                if (today - day).days < HARD_DAYS or len(talked) < HARD_CONVERSATION_DAYS:
                    fail("c5_coverage_timing", "shared_moments", "case")
            if between(message(hard), case, lambda action: action.get("do") == "reset_relationship"):
                fail("c5_coverage_undone", "shared_moments", "case")

    if "absence" in resolved:
        number = resolved["absence"]["case"][0]
        if number < 1 or number not in starts or number - 1 not in starts or \
                (starts[number].date() - starts[number - 1].date()).days < ABSENCE_DAYS:
            fail("c5_coverage_timing", "absence", "case")
    covered = sum(1 for field in resolved if not any(item.get("field") == field for item in failures))
    return failures, covered


def check(module, harness, *, r4: bool = False, c5: bool = False) -> dict:
    failures: list[dict] = []
    sessions = list(getattr(module, "SESSIONS_LONG", None) or [])
    if not sessions:
        failures.append({"code": "no_sessions"})
    turns, positions, malformed = 0, {}, set()
    for number, entry in enumerate(sessions):
        try:
            session, messages = entry
            messages = list(messages)
            if not messages or not all(isinstance(text, str) for text in messages):
                raise TypeError
        except (TypeError, ValueError):
            failures.append({"code": "malformed_session", "session": number})
            malformed.add(number)
            continue
        if any(key[0] == session for key in positions):
            failures.append({"code": "duplicate_session", "session": number})
        turns += len(messages)
        positions.update({(session, turn): (number, turn) for turn in range(len(messages))})

    # Session starts: parsed with the harness's own parser, strictly increasing and at least an hour apart.
    year = getattr(module, "YEAR", harness.YEAR)
    previous, starts = None, {}
    for number, entry in enumerate(sessions):
        if number in malformed:
            previous = None
            continue
        try:
            start = harness.session_start(entry[1][0], year)
        except Exception as error:  # noqa: BLE001 - every failure becomes a code, never its message.
            failures.append({"code": _start_code(error), "session": number})
            previous = None
            continue
        starts[number] = start
        if previous is not None:
            if start <= previous:
                failures.append({"code": "not_increasing", "session": number})
            elif start - previous < MIN_GAP:
                failures.append({"code": "too_close", "session": number})
        previous = start
        weekday = stated_weekday(entry[1][0])
        if weekday is not None and weekday != start.date().weekday():
            failures.append({"code": "weekday_mismatch", "session": number})

    # Page actions, one at a time so that each failure has its own position; the earlier ones are read as context
    # (a removed boundary must be one an earlier action added).
    actions = list(getattr(module, "PAGE_ACTIONS", None) or [])
    for number, entry in enumerate(actions):
        single = SimpleNamespace(SESSIONS_LONG=sessions, PAGE_ACTIONS=actions)
        try:
            harness.check_actions(single, only=number)
        except BaseException as error:  # noqa: BLE001 - SystemExit included: it carries the session id.
            if isinstance(error, KeyboardInterrupt):
                raise
            failure = {"code": _action_code(error), "action": number}
            try:
                failure["at"] = list(positions[(entry[0], entry[1])])
            except (TypeError, KeyError, IndexError):
                pass
            failures.append(failure)
        try:
            if _timed(entry[2]):
                failures.append({"code": "timed_pause", "action": number})
        except (TypeError, IndexError, KeyError):
            pass

    # Scripted timed pauses (stub host scripts).
    script = getattr(module, "STUB_HOST", None) or {}
    for key, steps in (script.items() if isinstance(script, dict) else ()):
        for step in steps or ():
            if isinstance(step, dict) and step.get("tool") == "memory_pause" and _timed(step.get("arguments")):
                failure = {"code": "timed_pause"}
                if key in positions:
                    failure["at"] = list(positions[key])
                failures.append(failure)

    if r4:
        failures += check_r4(module, positions)
    covered = None
    if c5:
        found, covered = check_c5(module, positions, starts)
        failures += found
    intended = len(harness.intended_unrecorded(module)) if not failures else None
    result = {"ok": not failures, "sessions": len(sessions), "turns": turns, "actions": len(actions),
              "intended_unrecorded": intended, "cases": len(list(getattr(module, "CASES", None) or [])),
              "failures": failures}
    if c5:
        span = (starts[len(sessions) - 1].date() - starts[0].date()).days \
            if sessions and 0 in starts and len(sessions) - 1 in starts else None
        result.update(span_days=span, coverage=covered)
    return result


def main(argv: list) -> int:
    r4 = bool(argv) and argv[0] == "--r4"
    c5 = bool(argv) and argv[0] == "--c5"
    if r4 or c5:
        argv = argv[1:]
    if len(argv) != 1:
        print(json.dumps({"ok": False, "error": "usage"}))
        return 2
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            harness = _load("c5_harness_for_precheck", Path(__file__).with_name("c5-harness.py"))
            code = "load_failed"
            try:
                if r4 or c5:  # Read without running it: a held-out scenario holds only literal assignments.
                    code = "r4_not_literal" if r4 else "c5_not_literal"
                    module = _load("scenario_literals_for_precheck",
                                   Path(__file__).with_name("scenario_literals.py")).read(Path(argv[0]))
                else:
                    module = _load("c5_scenario_for_precheck", Path(argv[0]))
            except BaseException as error:  # noqa: BLE001 - never shown: it may quote the scenario.
                if isinstance(error, KeyboardInterrupt):
                    raise
                module = None
            result = check(module, harness, r4=r4, c5=c5) if module is not None else {
                "ok": False, "sessions": 0, "turns": 0, "actions": 0, "intended_unrecorded": None, "cases": 0,
                "failures": [{"code": code}]}
    except Exception:  # noqa: BLE001 - an internal error is reported by code only.
        print(json.dumps({"ok": False, "error": "internal_error"}))
        return 2
    print(f"sessions {result['sessions']}")
    print(f"turns {result['turns']}")
    print(f"actions {result['actions']}")
    if r4 or c5:
        print(f"cases {result['cases']}")
    if c5 and "coverage" in result:
        print(f"span days {result['span_days']}")
        print(f"coverage {result['coverage']} of {len(COVERAGE_FIELDS)}")
    if result["intended_unrecorded"] is not None:
        print(f"intended unrecorded turns {result['intended_unrecorded']}")
    for failure in result["failures"]:
        print("FAIL " + " ".join(f"{key}={value}" if not isinstance(value, list) else f"{key}={value[0]}:{value[1]}"
                                 for key, value in failure.items()))
    summary = {"ok": result["ok"], "sessions": result["sessions"], "turns": result["turns"],
               "actions": result["actions"], "failures": len(result["failures"]),
               "codes": sorted({failure["code"] for failure in result["failures"]})}
    if r4:
        summary.update(mode="r4", cases=result["cases"])
    if c5:
        summary.update(mode="c5", cases=result["cases"], span_days=result.get("span_days"),
                       coverage=result.get("coverage"), requirements=len(COVERAGE_FIELDS))
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
