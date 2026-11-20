"""The host-trial scenario format: loading, validation, the wording lint, the hash, and the checks.

A scenario is one JSON file, plain public synthetic data. Its SHA-256 over the file's bytes is what an approval names
(``python trial.py hash FILE``).

    {
      "name": "resume-after-correction",            letters, digits and dashes
      "description": "what the trial asks, in one or two sentences",
      "questions": ["the questions the trial answers", ...],          optional, copied into the record draft
      "memory": {"new": true}  |  {"continues": "<earlier scenario name>"},
      "project": {"files": {"README.md": "...", ...}}  |  {"continues": true}  |  omitted (an empty directory),
      "stop_on_failure": false,
      "refs": {"corrected": {"note_matching": "SQLite"}},             optional: ids read from the memory before turn 1
      "page_capture": {"note": "corrected"},                          optional: the lead's own look at the page
      "sessions": [                                                   each session is a new host session
        {"name": "day1", "turns": [
          {"name": "t01-decision", "message": "exactly what the user types",
           "lint_override": {"words": ["forget"], "reason": "this turn asks to forget"},      optional
           "checks": [ ... ]}
        ]}
      ],
      "final_checks": [ ... ]                                         after the last turn
    }

Checks (every check may carry "label" and "informational": true, which reports without failing):

    {"type": "tool", "name": "memory_note", "called": true, "where": [PREDICATE, ...], "save": {"ref": "result.note_id"}}
        a call in this turn (in final checks: in any turn) of the tool named exactly, or ending in "__" + name ("name"
        may be a list of tools); PREDICATEs on its input, all on the same call (without "field": the whole input as
        JSON): {"field": F, "contains": S} {"field": F, "matches": REGEX}
        {"field": F, "equals": V} {"field": F, "nonempty": true} {"field": F, "includes_ref": REF} (a list field holds
        an id of REF, or a string field contains one); "save" keeps "result.PATH" or "input.PATH" of the first match
    {"type": "note_current", "matching": REGEX | "ref": REF, "present": true}     a current note (text or id)
    {"type": "note_replaces", "matching": REGEX, "ref": REF}     the current note matching REGEX replaced REF's note
    {"type": "boundary", "matching": REGEX, "present": true}     a topic boundary (topic or alias) in the service
    {"type": "erased", "ref": REF}                               every record REF names is gone from the service
    {"type": "memory_text", "contains": S, "roles": ["user"], "present": false}   any stored record holding S
    {"type": "file", "path": P, "contains": S, "ignore_case": true, "present": true}   (no "contains": exists)
    {"type": "context", "hook": "SessionStart", "contains": S, "present": false}   this turn's hook context
    {"type": "reply", "matches": REGEX, "present": true}         this turn's reply (case-insensitive)
    {"type": "for_lead", "label": L, "show": ["reply", "tool:memory_forget"]}     lists, judges nothing

State checks read the memory through the service after the turn; nothing is judged by a model.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
CHECK_TYPES = {"tool", "note_current", "note_replaces", "boundary", "erased", "memory_text", "file", "context",
               "reply", "for_lead"}
STATE_TYPES = {"note_current", "note_replaces", "boundary", "erased", "memory_text"}
PREDICATES = {"contains", "matches", "equals", "nonempty", "includes_ref"}

# Words a user message must not hold: they name a tool or remind the host to remember. A scenario about asking to
# remember or forget overrides them per message, with its reason.
LINT_RULES = (
    ("tool name", re.compile(r"\b(?:memory|membrain)_[a-z_]+\b|\bmcp__\w+|\bmy_replies\b", re.I)),
    ("tool name", re.compile(r"\b(?:ToolSearch|Bash|Glob|Grep)\b")),
    ("membrain", re.compile(r"\bmem-?brain\b|/membrain\b|\bplugin ui\b|--note\b", re.I)),
    ("note", re.compile(r"\bnot(?:e|es|ed|ing)\b", re.I)),
    ("remember", re.compile(r"\bremember\w*\b|\bremind\w*\b|\brecall\w*\b", re.I)),
    ("memory", re.compile(r"\bmemor(?:y|ies|ise|ize|ised|ized)\b", re.I)),
    ("forget", re.compile(r"\bforg[eo]t\w*\b", re.I)),
    ("save", re.compile(r"\b(?:save|store|record|write down|keep in mind|jot)\b", re.I)),
)


class ScenarioError(ValueError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lint_message(message: str, override: dict | None = None) -> list[str]:
    """Flagged words in one user message, minus the words its override allows."""
    allowed = {word.lower() for word in (override or {}).get("words", ())}
    found = []
    for rule, pattern in LINT_RULES:
        for match in pattern.finditer(message):
            word = match.group(0)
            if rule.lower() in allowed or word.lower() in allowed:
                continue
            found.append(f"{rule}: {word!r}")
    return found


def lint(scenario: dict) -> list[str]:
    problems = []
    for turn in turns(scenario):
        override = turn.get("lint_override")
        if override is not None and not (isinstance(override, dict) and isinstance(override.get("reason"), str)
                                         and override["reason"].strip() and isinstance(override.get("words"), list)
                                         and override["words"]):
            problems.append(f"{turn['name']}: an override names its words and gives a reason")
            continue
        for item in lint_message(turn["message"], override):
            problems.append(f"{turn['name']}: {item}")
    return problems


def turns(scenario: dict) -> list[dict]:
    """Every turn in order, each with its session's name and whether it starts a host session."""
    out = []
    for session in scenario["sessions"]:
        for index, turn in enumerate(session["turns"]):
            out.append({**turn, "session": session["name"], "new_session": index == 0})
    return out


def _check(check, where: str, refs: set[str]) -> list[str]:
    if not isinstance(check, dict) or check.get("type") not in CHECK_TYPES:
        return [f"{where}: unknown check {check!r}"]
    kind, problems = check["type"], []
    if kind == "tool":
        names = check.get("name") if isinstance(check.get("name"), list) else [check.get("name")]
        if not names or not all(isinstance(name, str) and name for name in names):
            problems.append(f"{where}: a tool check names its tool (or a list of tools)")
        for predicate in check.get("where", []):
            if not isinstance(predicate, dict) or not (set(predicate) - {"field"}) or \
                    not set(predicate) - {"field"} <= PREDICATES:
                problems.append(f"{where}: unknown predicate {predicate!r}")
            elif "matches" in predicate:
                re.compile(predicate["matches"])
            if isinstance(predicate, dict) and "includes_ref" in predicate and predicate["includes_ref"] not in refs:
                problems.append(f"{where}: ref {predicate['includes_ref']!r} is not defined before this check")
        for name, path in (check.get("save") or {}).items():
            if not (isinstance(path, str) and path.split(".", 1)[0] in ("result", "input")):
                problems.append(f"{where}: save takes result.PATH or input.PATH")
            refs.add(name)
    elif kind in ("note_current", "boundary") and "matching" in check:
        re.compile(check["matching"])
    elif kind == "reply":
        re.compile(check.get("matches", ""))
    elif kind == "file" and not isinstance(check.get("path"), str):
        problems.append(f"{where}: a file check names its path")
    if "ref" in check and check["ref"] not in refs:
        problems.append(f"{where}: ref {check['ref']!r} is not defined before this check")
    if kind == "note_current" and ("ref" in check) == ("matching" in check):
        problems.append(f"{where}: note_current takes matching or ref")
    return problems


def validate(scenario: dict) -> list[str]:
    problems = []
    if not isinstance(scenario, dict):
        return ["a scenario is a JSON object"]
    if not isinstance(scenario.get("name"), str) or not NAME.match(scenario["name"]):
        problems.append("name: letters, digits and dashes")
    memory = scenario.get("memory")
    if memory not in ({"new": True},) and not (isinstance(memory, dict) and set(memory) == {"continues"}
                                                and isinstance(memory["continues"], str)):
        problems.append('memory: {"new": true} or {"continues": "<scenario name>"}')
    project = scenario.get("project", {"files": {}})
    if not (project == {"continues": True} or isinstance(project, dict) and set(project) == {"files"}
            and isinstance(project["files"], dict)):
        problems.append('project: {"files": {...}} or {"continues": true}')
    elif "files" in project:
        for path, content in project["files"].items():
            parts = Path(path).parts
            if Path(path).is_absolute() or ".." in parts or not parts or not isinstance(content, str):
                problems.append(f"project file {path!r}: a relative path inside the project and its text")
    if project == {"continues": True} and "continues" not in (memory or {}):
        problems.append("project continues only with a memory that continues")
    sessions = scenario.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        return problems + ["sessions: at least one"]
    refs = set((scenario.get("refs") or {}))
    for name, spec in (scenario.get("refs") or {}).items():
        if not (isinstance(spec, dict) and set(spec) == {"note_matching"}):
            problems.append(f"ref {name}: {{\"note_matching\": REGEX}}")
    seen = set()
    for session in sessions:
        if not isinstance(session, dict) or not isinstance(session.get("name"), str) or \
                not isinstance(session.get("turns"), list) or not session["turns"]:
            problems.append("each session has a name and at least one turn")
            continue
        for turn in session["turns"]:
            if not isinstance(turn, dict) or not isinstance(turn.get("name"), str) or not NAME.match(turn["name"]):
                problems.append(f"turn {turn!r}: a name of letters, digits and dashes")
                continue
            if turn["name"] in seen:
                problems.append(f"turn {turn['name']}: names are unique")
            seen.add(turn["name"])
            if not isinstance(turn.get("message"), str) or not turn["message"].strip():
                problems.append(f"turn {turn['name']}: a message")
            for check in turn.get("checks", []):
                problems += _check(check, turn["name"], refs)
    for check in scenario.get("final_checks", []):
        problems += _check(check, "final", refs)
    if not isinstance(scenario.get("stop_on_failure", False), bool):
        problems.append("stop_on_failure: true or false")
    capture = scenario.get("page_capture")
    if capture is not None and not (isinstance(capture, dict) and set(capture) == {"note"} and capture["note"] in refs):
        problems.append('page_capture: {"note": REF}')
    return problems


def load(path: Path) -> dict:
    try:
        scenario = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ScenarioError(f"{path}: {error}") from None
    problems = validate(scenario)
    if problems:
        raise ScenarioError("; ".join(problems))
    return scenario


# Checks ------------------------------------------------------------------------------------------------------------

def _path(value, path: str):
    for part in path.split(".") if path else ():
        if isinstance(value, list) and part.isdigit():
            value = value[int(part)] if int(part) < len(value) else None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _ids(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _holds(call: dict, predicate: dict, refs: dict) -> bool:
    value = _path(call.get("input") or {}, predicate.get("field", ""))
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) if value is not None else ""
    if "contains" in predicate and predicate["contains"] not in text:
        return False
    if "matches" in predicate and not re.search(predicate["matches"], text):
        return False
    if "equals" in predicate and value != predicate["equals"]:
        return False
    if predicate.get("nonempty") and not value:
        return False
    if "includes_ref" in predicate:
        wanted = _ids(refs.get(predicate["includes_ref"]))
        if not wanted:
            return False
        if isinstance(value, list):
            if not set(wanted) & set(_ids(value)):
                return False
        elif not any(item in text for item in wanted):
            return False
    return True


def _matches_name(call: dict, name) -> bool:
    names = name if isinstance(name, list) else [name]
    return any(call["name"] == item or call["name"].endswith("__" + item) for item in names)


def _verdict(check: dict, ok: bool, detail: str) -> dict:
    if check.get("informational"):
        return {"verdict": "noted", "holds": ok, "detail": detail}
    return {"verdict": "pass" if ok else "FAIL", "detail": detail}


def evaluate(check: dict, *, turn: dict | None, calls: list[dict], state: dict | None, project: Path,
             refs: dict) -> dict:
    """One check's verdict. ``turn`` is the turn's parsed log (None in final checks), ``calls`` the tool calls the
    check may look at, ``state`` the memory read after the turn, ``refs`` the ids known so far (saved into)."""
    kind = check["type"]
    present = check.get("present", True)
    if kind == "tool":
        matching = [call for call in calls if _matches_name(call, check["name"])
                    and all(_holds(call, predicate, refs) for predicate in check.get("where", []))]
        expected = check.get("called", True)
        for name, path in (check.get("save") or {}).items():
            if matching:
                source, _, rest = path.partition(".")
                refs[name] = _path(matching[0].get(source), rest)
        named = [call for call in calls if _matches_name(call, check["name"])]
        detail = (f"{len(matching)} matching call(s) of {len(named)} call(s) of {check['name']}" +
                  (f"; first input {json.dumps(matching[0].get('input'), ensure_ascii=False)[:300]}" if matching else ""))
        return _verdict(check, bool(matching) == expected, detail)
    if kind in STATE_TYPES and state is None:
        return {"verdict": "FAIL", "detail": "the memory could not be read"}
    if kind == "note_current":
        notes = state["notes"]
        if "ref" in check:
            wanted = set(_ids(refs.get(check["ref"])))
            if not wanted:
                return {"verdict": "FAIL", "detail": f"ref {check['ref']} was never set"}
            found = [note for note in notes if note["event_id"] in wanted]
        else:
            found = [note for note in notes if re.search(check["matching"], note.get("text") or "", re.I)]
        return _verdict(check, bool(found) == present,
                        f"{len(found)} current note(s): " + "; ".join((note.get("text") or "")[:160] for note in found))
    if kind == "note_replaces":
        wanted = set(_ids(refs.get(check["ref"])))
        if not wanted:
            return {"verdict": "FAIL", "detail": f"ref {check['ref']} was never set"}
        notes = [note for note in state["notes"] if re.search(check["matching"], note.get("text") or "", re.I)]
        ok = any(wanted & {entry.get("event_id") for entry in note.get("replaced") or ()} for note in notes)
        return _verdict(check, ok, f"{len(notes)} current note(s) match; replaced ids "
                        f"{[[entry.get('event_id') for entry in note.get('replaced') or ()] for note in notes]}")
    if kind == "boundary":
        pattern = re.compile(check["matching"], re.I)
        found = [entry for entry in state["boundaries"]
                 if any(pattern.search(text or "") for text in [entry.get("topic"), *(entry.get("aliases") or [])])]
        return _verdict(check, bool(found) == present, f"boundaries: {json.dumps(state['boundaries'], ensure_ascii=False)[:300]}")
    if kind == "erased":
        wanted = _ids(refs.get(check["ref"]))
        if not wanted:
            return {"verdict": "FAIL", "detail": f"ref {check['ref']} was never set"}
        still = state.get("still_present")
        if still is None:
            return {"verdict": "FAIL", "detail": "the erasure was not read"}
        return _verdict(check, not still, f"{len(wanted)} id(s) asked for; still present: {still}")
    if kind == "memory_text":
        roles = set(check.get("roles") or ("user", "assistant"))
        found = [record for record in state["records"]
                 if record.get("role") in roles and check["contains"].lower() in (record.get("text") or "").lower()]
        found += [note for note in state["notes"] if "assistant" in roles
                  and check["contains"].lower() in (note.get("text") or "").lower()
                  and note["event_id"] not in {record.get("event_id") for record in found}]
        detail = f"{len(found)} stored record(s) hold it" + ("" if state.get("records_complete", True)
                                                            else " (the record list was cut short)")
        return _verdict(check, bool(found) == present, detail)
    if kind == "file":
        path = project / check["path"]
        if "contains" not in check:
            return _verdict(check, path.exists() == present, f"{check['path']} exists: {path.exists()}")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return _verdict(check, not present, f"{check['path']} cannot be read")
        needle = check["contains"]
        if check.get("ignore_case"):
            text, needle = text.lower(), needle.lower()
        return _verdict(check, (needle in text) == present, f"{check['path']} holds it: {needle in text}")
    if turn is None:
        return {"verdict": "FAIL", "detail": f"a {kind} check belongs to a turn"}
    if kind == "context":
        contexts = [hook["context"] for hook in turn["hooks"] if hook["event"] == check.get("hook", hook["event"])]
        holds = any(check["contains"].lower() in context.lower() for context in contexts)
        return _verdict(check, holds == present, f"{len(contexts)} hook context(s); holds it: {holds}")
    if kind == "reply":
        holds = bool(re.search(check["matches"], turn["reply"] or "", re.I))
        return _verdict(check, holds == present, f"reply matches: {holds}")
    if kind == "for_lead":
        shown = []
        for item in check.get("show", ["reply"]):
            if item == "reply":
                shown.append(("reply", turn["reply"] or ""))
            elif item.startswith("tool:"):
                for call in calls:
                    if _matches_name(call, item[5:]):
                        shown.append((f"{item[5:]} input", json.dumps(call.get("input"), ensure_ascii=False)))
                        shown.append((f"{item[5:]} result", json.dumps(call.get("result"), ensure_ascii=False)
                                      if not isinstance(call.get("result"), str) else call["result"]))
        return {"verdict": "for lead", "detail": check.get("label", ""), "shown": shown}
    return {"verdict": "FAIL", "detail": f"unknown check {kind}"}
