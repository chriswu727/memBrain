"""Blinded review sheet for one Phase B scenario across arms; the label mapping is sealed in a separate file.

Usage: python v1-2026-10-29-phase-b-blind.py OUT_DIR SCENARIO_FILE PONF [--companion]
Writes OUT_DIR/blind_<scenario>.md (facts, then each case with shuffled labels) and OUT_DIR/sealed_<scenario>.json.

Companion mode (C5) is on with --companion or when the scenario has PAGE_ACTIONS. Then each case also shows, after
its date and before its criteria, what is the same for every reply of the case and that reviewers need to judge
persona and page-action cases:
- the page actions applied before the case's user message, in the order the harness applied them, each with its
  number, position, kind, the scenario's own arguments and its outcome (`done`, or `not_applicable` and the reason
  code), read from OUT_DIR/page-actions_<scenario>_<arm>.jsonl (copies of each arm's page-actions.jsonl); the
  outcome must be the same in every arm, or the sheet is refused;
- the persona in effect as the case's turn began: the version and the product-rendered block from the per-turn
  persona record (arm P's persona_block, arm F's reference_persona, with the same persona_turn); it must be the same
  in every arm, or the sheet is refused;
- since 2026-11-17, the persona versions so far: each change of the persona version up to the case's message, with
  the position it took effect and its origin as far as records shared by both arms show it (a page action by
  number and kind, or "in the conversation" during the message before, without saying whether a switch or a
  confirmed change, which only P's tool calls would show). Reviewers judge persona cases against what the user asked
  for and agreed to (FACTS and the criteria); the persona block and this list are context.
The scenario is read as a live run reads it (scenario_literals.py), never by running it.
Nothing that differs between arms (counts before and after an action, times, what the host was shown) is printed.
An R4 scenario (no PAGE_ACTIONS, no --companion) gets exactly the sheet it got before companion mode existed.
"""
import hashlib
import importlib.util
import json
import secrets
import sys
from pathlib import Path

PAGE_RECORD_FORMAT = 2  # c5-harness.py PAGE_RECORD_FORMAT
PERSONA_TURN_FORMAT = 1  # c5-harness.py PERSONA_TURN_FORMAT
NOT_APPLICABLE = ("message_not_recorded", "message_already_removed", "no_note_from_message",
                  "no_feeling_from_message", "boundary_not_present", "no_open_proposal", "page_refused")
# Page actions that make a new persona version when done (a decision only when it accepts).
VERSION_ACTIONS = ("switch_persona", "set_persona", "accept_proposal")


def refuse(text: str):
    raise SystemExit(f"blind sheet refused: {text}")


def page_records(out: Path, scenario: str, arms: list, actions: list, order: list) -> list:
    """Each action's (status, reason) in application order, the same in every arm (checked)."""
    outcomes = None
    for arm in arms:
        path = out / f"page-actions_{scenario}_{arm}.jsonl"
        if not path.exists():
            refuse(f"companion mode needs {path.name} (a copy of that arm's page-actions.jsonl)")
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if len(records) != len(order) or any(
                not isinstance(record, dict) or record.get("format") != PAGE_RECORD_FORMAT
                or record.get("index") != index or record.get("session") != actions[index][0]
                or record.get("before_turn") != actions[index][1] or record.get("action") != actions[index][2]["do"]
                for record, index in zip(records, order)):
            refuse("a page-actions file does not hold exactly the scenario's PAGE_ACTIONS in order")
        mine = []
        for record in records:
            status, reason = record.get("status"), record.get("reason")
            if not ((status == "done" and reason is None) or (status == "not_applicable" and reason in NOT_APPLICABLE)):
                refuse("a page action has no valid outcome (failed, or an unknown reason)")
            mine.append((status, reason))
        if outcomes is not None and mine != outcomes:
            refuse("the page-action outcomes differ between arms")
        outcomes = mine
    return outcomes


def persona_of(row: dict, arm: str):
    """(version, block) from a row's per-turn persona record, or None when the record is missing or malformed."""
    block = row.get("reference_persona") if arm == "F" else row.get("persona_block")
    turn = row.get("persona_turn")
    if not isinstance(block, str) or not isinstance(turn, dict) or set(turn) != {"format", "version", "sha256"} \
            or turn["format"] != PERSONA_TURN_FORMAT or type(turn["version"]) is not int:
        return None
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest() if block else None
    if turn["sha256"] != digest or (turn["version"] > 0) != bool(block):
        return None
    return turn["version"], block


def describe(number: int, action: dict, at: tuple, names: list, outcome: tuple) -> str:
    """One page action as the sheet lists it: positions by index, the scenario's own arguments, the outcome."""
    session, before = at
    details = {key: value for key, value in action.items() if key not in ("do", "arms")}
    if "session" in details and details.get("session") in names:
        target = (f"session {names.index(details.pop('session')) + 1}, message {details.pop('turn') + 1}, "
                  f"{details.pop('role', 'user')}")
        details = {"message": target, **details}
    shown = ", ".join(f"{key} {json.dumps(value, ensure_ascii=False)}" if key != "message" else f"message: {value}"
                      for key, value in details.items())
    status, reason = outcome
    result = "done" if status == "done" else f"not_applicable ({reason})"
    return (f"Action {number}, before message {before + 1} of session {names.index(session) + 1}: {action['do']}"
            f"{' (' + shown + ')' if shown else ''}: **{result}**")


def persona_history(turns: list, records: dict, actions: list, order: list, outcomes: list, names: list) -> list:
    """Each persona version change up to and including each turn, from records that are the same in every arm: the
    per-turn persona version (persona_turn, checked equal across arms) and the page actions' outcomes. Returns, per
    position in ``turns`` (the scenario's turns in order), the list of lines so far.

    Between the start of one turn and the start of the next, the persona can change in two ways: during the earlier
    turn, in the conversation (the companion's tool: a switch the user asked for, or a change the user confirmed), or
    by a page action applied before the later turn. A done page action of VERSION_ACTIONS makes one version; the
    rest of the step in the version number happened in the conversation. The records both replies share do not say
    which conversational change it was, so that origin is given as "in the conversation" only. When the step does
    not fit (fewer versions than done page actions, or a version going back), the lines give the version and
    position only and say that the origin cannot be read from the shared records."""
    done_before = {}
    for index, (status, _) in zip(order, outcomes):
        at = (actions[index][0], actions[index][1])
        if status == "done" and actions[index][2]["do"] in VERSION_ACTIONS:
            done_before.setdefault(at, []).append(index)
    history, lines, previous = [], [], None
    for number, (session, turn) in enumerate(turns):
        version = records[(session, turn)]
        where = f"message {turn + 1} of session {names.index(session) + 1}"
        page = done_before.get((session, turn), [])
        if previous is None:
            lines.append(f"Version {version}, in effect at {where} (the first message): the starting personality"
                         + (", with the page actions before that message" if page else ""))
        elif version != previous:
            before = turns[number - 1]
            spoken = f"message {before[1] + 1} of session {names.index(before[0]) + 1}"
            talk = version - previous - len(page)
            if version < previous or talk < 0:
                lines.append(f"Version {version}, in effect from {where} (after version {previous}): the shared "
                             "records do not show how it changed")
            else:
                for step in range(talk):
                    lines.append(f"Version {previous + step + 1}, made in the conversation during {spoken} (not a "
                                 "page action; the records both replies share do not say whether it was a switch "
                                 "or a change the user confirmed), in effect from the next message")
                for step, index in enumerate(page):
                    detail = actions[index][2]
                    origin = (f" (origin {json.dumps(detail['origin'])})" if "origin" in detail else "")
                    lines.append(f"Version {previous + talk + step + 1}, made by page action {index + 1} "
                                 f"({detail['do']}{origin}) before {where}")
        previous = version
        history.append(list(lines))
    return history


def fence(text: str) -> str:
    longest, run = 0, 0
    for character in text:
        run = run + 1 if character == "`" else 0
        longest = max(longest, run)
    marks = "`" * max(3, longest + 1)
    return f"{marks}text\n{text}\n{marks}"


def main(argv: list) -> None:
    out, scenario_path, arms = Path(argv[0]), argv[1], list(argv[2])
    companion_flag = argv[3:] == ["--companion"]
    if argv[3:] and not companion_flag:
        raise SystemExit("usage: v1-2026-10-29-phase-b-blind.py OUT_DIR SCENARIO_FILE PONF [--companion]")
    # Read as a live run reads it, never by running it (scenario_literals.py: literal assignments only).
    spec = importlib.util.spec_from_file_location("scenario_literals_for_blind",
                                                  Path(__file__).resolve().with_name("scenario_literals.py"))
    literals = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(literals)
    try:
        module = literals.read(scenario_path)
    except literals.NotLiteral as error:
        raise SystemExit(f"blind sheet refused: the scenario is not literal assignments only ({error.code})") from None
    scenario = Path(scenario_path).stem
    labels = "ABCD"[:len(arms)]
    rows = {}
    for arm in arms:
        for line in (out / f"results_{scenario}_{arm}.jsonl").read_text().splitlines():
            row = json.loads(line)
            rows[(arm, row["session"], row["turn"])] = row
    actions = list(getattr(module, "PAGE_ACTIONS", None) or [])
    companion = companion_flag or bool(actions)
    names = [name for name, _ in module.SESSIONS_LONG]
    order = sorted(range(len(actions)), key=lambda index: (names.index(actions[index][0]), actions[index][1], index))
    outcomes = page_records(out, scenario, arms, actions, order) if companion else []
    histories = {}
    if companion:
        turns = [(session, turn) for session, messages in module.SESSIONS_LONG for turn in range(len(messages))]
        versions = {}
        for key in turns:
            found = {(persona_of(rows[(arm, *key)], arm) or (None,))[0] if (arm, *key) in rows else None
                     for arm in arms}
            if None in found or len(found) != 1:
                refuse("the persona record of a turn is missing or differs between arms")
            versions[key] = found.pop()
        histories = dict(zip(turns, persona_history(turns, versions, actions, order, outcomes, names)))
    sheet, mapping = [f"# {scenario}\n\n## Ground truth\n\n{module.FACTS.strip()}\n"], {}
    for session, turn, case_id, criteria in module.CASES:
        shuffled = list(arms)
        secrets.SystemRandom().shuffle(shuffled)
        mapping[case_id] = dict(zip(labels, shuffled))
        first = rows[(shuffled[0], session, turn)]
        position = names.index(session)
        companion_text = ""
        if companion:
            # Action numbers are PAGE_ACTIONS indexes from 1, as validity reports them; the list is in the order
            # the harness applied them. An action before message N comes before user message N.
            done = [describe(index + 1, actions[index][2], (actions[index][0], actions[index][1]), names, outcome)
                    for index, outcome in zip(order, outcomes)
                    if (names.index(actions[index][0]), actions[index][1]) <= (position, turn)]
            personas = {persona_of(rows[(arm, session, turn)], arm) for arm in arms}
            if None in personas:
                refuse(f"{case_id.split('-')[0]}: a reply's turn has no valid persona record")
            if len(personas) != 1:
                refuse(f"{case_id.split('-')[0]}: the persona in effect differs between arms")
            version, block = personas.pop()
            persona = (f"version {version}; the same for every reply of this case:\n\n{fence(block)}" if block
                       else "none; the same for every reply of this case.")
            companion_text = (
                "**Page actions so far** (what the user did on the memory page before this message, in order; the "
                "same for every reply of this case. `not_applicable` means the action found nothing to act on and "
                "changed nothing):\n\n" + ("\n".join(f"- {line}" for line in done) if done else "- none") + "\n\n"
                f"**Persona in effect at this message:** {persona}\n\n"
                "**Persona versions so far** (each change of the persona up to this message, with where it took "
                "effect and what made it, as far as the records both replies share show it; the same for every "
                "reply of this case. Judge a persona case against what the user asked for and agreed to, as the "
                "facts and the criteria state it: this list and the block above are context, not the yardstick):\n\n"
                + "\n".join(f"- {line}" for line in histories[(session, turn)]) + "\n\n")
        sheet.append(f"## {case_id}\n\n**Date:** {first['date']} (session {position + 1} of {len(module.SESSIONS_LONG)}, "
                     f"message {turn + 1} of that session; earlier messages that day come before it)\n\n"
                     f"{companion_text}**Criteria:** {criteria.removeprefix('Criteria:').strip()}\n\n"
                     f"**User:** {first['input']}\n")
        for label, arm in zip(labels, shuffled):
            sheet.append(f"### {label}\n\n{rows[(arm, session, turn)]['reply'] or '(no reply)'}\n")
    (out / f"blind_{scenario}.md").write_text("\n".join(sheet))
    (out / f"sealed_{scenario}.json").write_text(json.dumps(mapping, indent=1))
    print(scenario, "cases:", len(module.CASES))


if __name__ == "__main__":
    main(sys.argv[1:])
