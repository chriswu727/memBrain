"""Count-only C5 scenario precheck: is a scenario file fit for the C5 harness, before any service or model starts?

Usage: python c5-precheck.py SCENARIO.py

Checks, with the harness's own parsers:
- every session's first message states a date and a time (`session_start`);
- session starts are strictly increasing, and at least one hour apart;
- every PAGE_ACTIONS entry passes `check_actions` (a known kind at a real position; an accepted proposal states its
  card);
- no timed pause is scripted (a `memory_pause` with `hours` in STUB_HOST, or a page action with `hours`): the pause
  would run on the wall clock while the scenario clock moves by days.

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
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace

MIN_GAP = datetime.timedelta(hours=1)


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


def check(module, harness) -> dict:
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

    intended = len(harness.intended_unrecorded(module)) if not failures else None
    return {"ok": not failures, "sessions": len(sessions), "turns": turns, "actions": len(actions),
            "intended_unrecorded": intended, "failures": failures}


def main(argv: list) -> int:
    if len(argv) != 1:
        print(json.dumps({"ok": False, "error": "usage"}))
        return 2
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            harness = _load("c5_harness_for_precheck", Path(__file__).with_name("c5-harness.py"))
            try:
                module = _load("c5_scenario_for_precheck", Path(argv[0]))
            except BaseException as error:  # noqa: BLE001 - never shown: it may quote the scenario.
                if isinstance(error, KeyboardInterrupt):
                    raise
                module = None
            result = check(module, harness) if module is not None else {
                "ok": False, "sessions": 0, "turns": 0, "actions": 0, "intended_unrecorded": None,
                "failures": [{"code": "load_failed"}]}
    except Exception:  # noqa: BLE001 - an internal error is reported by code only.
        print(json.dumps({"ok": False, "error": "internal_error"}))
        return 2
    print(f"sessions {result['sessions']}")
    print(f"turns {result['turns']}")
    print(f"actions {result['actions']}")
    if result["intended_unrecorded"] is not None:
        print(f"intended unrecorded turns {result['intended_unrecorded']}")
    for failure in result["failures"]:
        print("FAIL " + " ".join(f"{key}={value}" if not isinstance(value, list) else f"{key}={value[0]}:{value[1]}"
                                 for key, value in failure.items()))
    summary = {"ok": result["ok"], "sessions": result["sessions"], "turns": result["turns"],
               "actions": result["actions"], "failures": len(result["failures"]),
               "codes": sorted({failure["code"] for failure in result["failures"]})}
    print(json.dumps(summary, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
