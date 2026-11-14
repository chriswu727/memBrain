"""Count-only C5 scenario precheck: is a scenario file fit for the C5 harness, before any service or model starts?

Usage: python c5-precheck.py [--r4] SCENARIO.py

Checks, with the harness's own parsers:
- every session's first message states a date and a time (`session_start`);
- session starts are strictly increasing, and at least one hour apart;
- every PAGE_ACTIONS entry passes `check_actions` (a known kind at a real position; an accepted proposal states its
  card);
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
# Every failure code this precheck prints; tools that relay its result print only these.
CODES = ("no_sessions", "malformed_session", "duplicate_session", "no_date", "no_time", "bad_date", "not_increasing",
         "too_close", "weekday_mismatch", "bad_action", "proposal_without_card", "proposals_unsupported",
         "malformed_action", "timed_pause", "load_failed", "r4_not_literal", "r4_page_actions", "r4_persona",
         "r4_missing", "r4_stub_script", "r4_case_count", "r4_turn_count", "r4_case_position", "r4_case_id",
         "r4_recording_position", "r4_recording_missing", "r4_recording_shape", "r4_no_weekday")


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


def check(module, harness, *, r4: bool = False) -> dict:
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
    previous = None
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
        if previous is not None:
            if start <= previous:
                failures.append({"code": "not_increasing", "session": number})
            elif start - previous < MIN_GAP:
                failures.append({"code": "too_close", "session": number})
        previous = start
        weekday = stated_weekday(entry[1][0])
        if weekday is not None and weekday != start.date().weekday():
            failures.append({"code": "weekday_mismatch", "session": number})

    # Page actions, one at a time so that each failure has its own position.
    actions = list(getattr(module, "PAGE_ACTIONS", None) or [])
    for number, entry in enumerate(actions):
        single = SimpleNamespace(SESSIONS_LONG=sessions, PAGE_ACTIONS=[entry])
        try:
            harness.check_actions(single)
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
    intended = len(harness.intended_unrecorded(module)) if not failures else None
    return {"ok": not failures, "sessions": len(sessions), "turns": turns, "actions": len(actions),
            "intended_unrecorded": intended, "cases": len(list(getattr(module, "CASES", None) or [])),
            "failures": failures}


def main(argv: list) -> int:
    r4 = bool(argv) and argv[0] == "--r4"
    if r4:
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
                if r4:  # Read without running it: an R4 scenario holds only literal assignments.
                    code = "r4_not_literal"
                    module = _load("scenario_literals_for_precheck",
                                   Path(__file__).with_name("scenario_literals.py")).read(Path(argv[0]))
                else:
                    module = _load("c5_scenario_for_precheck", Path(argv[0]))
            except BaseException as error:  # noqa: BLE001 - never shown: it may quote the scenario.
                if isinstance(error, KeyboardInterrupt):
                    raise
                module = None
            result = check(module, harness, r4=r4) if module is not None else {
                "ok": False, "sessions": 0, "turns": 0, "actions": 0, "intended_unrecorded": None, "cases": 0,
                "failures": [{"code": code}]}
    except Exception:  # noqa: BLE001 - an internal error is reported by code only.
        print(json.dumps({"ok": False, "error": "internal_error"}))
        return 2
    print(f"sessions {result['sessions']}")
    print(f"turns {result['turns']}")
    print(f"actions {result['actions']}")
    if r4:
        print(f"cases {result['cases']}")
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
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
