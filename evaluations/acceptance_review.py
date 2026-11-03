"""Review pipeline for the final behavioral acceptance (frozen by hash in the attempt plan).

  split   SHEET VERDICTS BLIND_DIR SCENARIO OUT_DIR   one file per case for the second review; refuses to write a
                                                      case file unless every reply appears in it in full
  tally   REVIEW_DIR BLIND_DIR SCENARIO KEY           final scores per arm, literal and with written resolutions
  attribution-inputs REVIEW_DIR BLIND_DIR SCENARIO KEY OUT_DIR   one arm-blind file per gated reply with a standing
                                                      critical error, for attribute.md
  validity RUN_DIR...                                 refuse an attempt whose runs degraded
  r5-inputs REVIEW_DIR BLIND_DIR SCENARIO KEY OUT_DIR   after the re-checks: one arm-blind file per reply with a
                                                      candidate type 4 mark, with that reply's own earlier
                                                      assistant replies, for rule R5 (assistant-claims.md)
  r5-check INPUT_DIR ANSWER_DIR RESULT_DIR             validate both R5 checkers' answers (an invalid one is set
                                                      aside to be redone once), then write each reply's result
  verdicts VERDICTS SCENARIO                          check a first review before the split; rename prefix keys
                                                      ("L01") to case ids, keeping the original as .raw.json
  diagnose RUN_DIR...                                 for an invalid attempt: error lines and where each arm
                                                      stopped, by position, without any case content
  gate REVIEW_DIR KEY...                              the attempt-3 pass rule from tallies and attributions

verdicts, tally and gate accept --companion for C5 (critical types 1–9). C5 writes gate-c5.json and never writes
an R4 result. Standing boundary/deletion errors (types 7/8) fail C5 regardless of attribution.
A failed C5 gate writes its report and exits nonzero; the legacy R4 command's exit behavior is unchanged.

Final score of a reply: 0 when a critical error stands, otherwise the first reviewer's score_ignoring_critical.
A mark stands when the first reviewer made it and the second confirmed it, or the second added it; written
resolutions (resolution-KEY.json, made before unsealing by the resolution reviewer) then add or remove marks.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path


def load(path: str):
    spec = importlib.util.spec_from_file_location("scenario", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_marks(value, maximum):
    return isinstance(value, list) and all(type(mark) is int and 1 <= mark <= maximum for mark in value)


def replies(blind_dir: Path, module, scenario: str) -> dict:
    """(case, label) -> reply text, from the results the blinded sheet was built from."""
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    rows = {}
    for path in blind_dir.glob(f"results_{scenario}_*.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rows[(row["arm"], row["session"], row["turn"])] = row
    found = {}
    for session, turn, case, _criteria in module.CASES:
        for label, arm in sealed[case].items():
            found[(case, label)] = rows[(arm, session, turn)]["reply"] or "(no reply)"
    return found


def split(sheet: Path, verdicts: Path, blind_dir: Path, scenario_path: str, out: Path) -> None:
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    text, marks = sheet.read_text(), json.loads(verdicts.read_text())
    cases = [case for _, _, case, _ in module.CASES]
    starts = sorted((m.start(), m.group(1)) for m in re.finditer(r"(?m)^## (\S+)\n", text) if m.group(1) in cases)
    if [case for _, case in starts] != cases:
        raise SystemExit("case headings missing or out of order in the sheet")
    truth = text[text.index("## Ground truth"):starts[0][0]]
    full = replies(blind_dir, module, scenario)
    out.mkdir(parents=True, exist_ok=True)
    for index, (start, case) in enumerate(starts):
        body = text[start:starts[index + 1][0] if index + 1 < len(starts) else len(text)]
        for label in "ABC":
            if body.count(f"\n### {label}\n") != 1 or full[(case, label)].strip() not in body:
                raise SystemExit(f"{case}: reply {label} is not complete in its case file")
        first = {label: {"critical": verdict.get("critical", []), "conditions": verdict.get("conditions", [])}
                 for label, verdict in marks[case].items()}
        (out / f"{case}.md").write_text(truth + body + "\n\n## First reviewer's critical-error marks\n\n"
                                        + json.dumps(first, ensure_ascii=False) + "\n")
        print(case, "ok")


def r5_inputs(review: Path, blind_dir: Path, scenario_path: str, key: str, out: Path) -> None:
    """One file per reply with a candidate type 4 mark, for rule R5 (claims about what the assistant itself said).

    Each file holds the ground truth, the case and that reply only, both reviewers' marks and evidence for it, and
    that reply's own earlier assistant replies with the user message each answered, oldest first, up to the case's
    message. It names the reply by case prefix and label, never by arm."""
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    rows = {}
    for path in blind_dir.glob(f"results_{scenario}_*.jsonl"):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            rows[(row["arm"], row["session"], row["turn"])] = row
    turns = {session: messages for session, messages in module.SESSIONS_LONG}
    order = [(session, index) for session, messages in module.SESSIONS_LONG for index in range(len(messages))]
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    if out.exists():
        raise SystemExit(f"{out} exists: R5 inputs are written once, into a new folder")
    files = {}
    for session, turn, case, _criteria in module.CASES:
        case_text = (review / f"recheck-{key}" / f"{case}.md").read_text()
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        head = case_text[:case_text.index("\n### A\n")]
        for label, arm in sealed[case].items():
            mine, theirs = first[case].get(label, {}), second.get(label, {})
            if 4 not in set(mine.get("critical", [])) | set(theirs.get("critical", [])) | set(theirs.get("added", [])):
                continue
            body = case_text[case_text.index(f"\n### {label}\n"):]
            following = [body.find(f"\n### {other}\n", 1) for other in "ABC" if other != label]
            ends = [index for index in following + [body.find("\n## First reviewer", 1)] if index > 0]
            reply = body[:min(ends)] if ends else body
            lines = [head.rstrip(), reply.rstrip(), "", "## The reviewers' marks on this reply", "",
                     "First reviewer: " + json.dumps({k: mine.get(k) for k in ("critical", "conditions", "reason")},
                                                     ensure_ascii=False),
                     "Second reviewer: " + json.dumps(theirs, ensure_ascii=False), "",
                     "## This reply's own earlier assistant replies, oldest first", ""]
            for earlier_session, earlier_turn in order[:order.index((session, turn))]:
                row = rows.get((arm, earlier_session, earlier_turn))
                if row is None:
                    raise SystemExit(f"{case.split('-')[0]}/{label}: a turn before the case is missing from the results")
                lines += [f"### {row['date']} · {earlier_session}, message {earlier_turn + 1}", "",
                          "User: " + turns[earlier_session][earlier_turn], "",
                          "Assistant: " + ((row.get("reply") or "").strip() or "(no reply)"), ""]
            files[f"{case.split('-')[0]}-{label}.md"] = "\n".join(lines)
    out.mkdir(parents=True)  # Only once every file is ready: a failure leaves no partial folder.
    for name, text in files.items():
        (out / name).write_text(text)
    print(json.dumps(sorted(files)))


_ENTRY = re.compile(r"(?m)^### (\d{4}-\d{2}-\d{2}) · (\S+), message (\d+)$")


def _r5_problem(answer, entries: set) -> str | None:
    """Why one R5 checker's answer is invalid, or None."""
    if not isinstance(answer, dict) or not isinstance(answer.get("claims"), list) or not answer["claims"]:
        return "no claims"
    for claim in answer["claims"]:
        if not isinstance(claim, dict) or claim.get("kind") not in ("assistant_speech", "adopted", "user_fact"):
            return "a claim has no valid kind"
        if claim["kind"] == "assistant_speech" and not isinstance(claim.get("supported"), bool):
            return "an assistant_speech claim has no boolean supported"
        if claim["kind"] != "assistant_speech" and claim.get("supported") is not None:
            return "only assistant_speech claims can be supported"
        if claim.get("supported") is True:
            match = _ENTRY.fullmatch("### " + str(claim.get("entry", "")).strip())
            if not match or match.group(0) not in entries or match.group(2).startswith("roleplay-"):
                return "a supported claim does not name a real-life entry of the file"
    cleared = all(claim["kind"] == "assistant_speech" and claim["supported"] is True for claim in answer["claims"])
    if answer.get("type4_cleared") is not cleared:
        return "type4_cleared does not follow from the claims"
    return None


def r5_check(inputs: Path, outputs: Path, results: Path) -> None:
    """Validate both R5 checkers' answers for every input; set an invalid answer aside as .rejected (it is redone
    once); write each reply's result for resolution: cleared only when both answers are valid and both clear it."""
    redo, final = [], {}
    for source in sorted(inputs.glob("*.md")):
        entries = {match.group(0) for match in _ENTRY.finditer(source.read_text())}
        cleared = True
        for checker in ("1", "2"):
            answer_path = outputs / f"{source.stem}.{checker}.json"
            rejected = outputs / f"{source.stem}.{checker}.rejected.json"
            try:
                problem = _r5_problem(json.loads(answer_path.read_text()), entries)
            except (OSError, ValueError):
                problem = "missing or not JSON"
            if problem and not rejected.exists():
                if answer_path.exists():
                    answer_path.rename(rejected)
                redo.append(f"{source.stem}.{checker}: {problem}")
            cleared = cleared and problem is None and json.loads(answer_path.read_text())["type4_cleared"]
        final[source.stem] = cleared
    if redo:
        print(json.dumps({"redo": redo}))
        return
    results.mkdir(parents=True, exist_ok=True)
    for name, cleared in final.items():
        (results / f"{name}.json").write_text(json.dumps({"type4_cleared": cleared}))
    print(json.dumps({"results": final}))


def tally(review: Path, blind_dir: Path, scenario_path: str, key: str, *, companion=False) -> None:
    verdicts(review / f"verdicts-{key}.json", scenario_path, companion=companion)
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    path = review / f"resolution-{key}.json"
    resolution = json.loads(path.read_text()) if path.exists() else {}
    totals, rows = {"literal": {}, "resolved": {}}, []
    for _, _, case, _ in module.CASES:
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        if not isinstance(second, dict) or set(second) != set("ABC"):
            raise SystemExit(f"invalid second review: {case} must cover A, B and C")
        for label, verdict in first[case].items():
            arm = sealed[case][label]
            check = second.get(label, {})
            change = resolution.get(f"{case}/{label}", {})
            maximum = 9 if companion else 5
            if (not isinstance(check, dict) or not isinstance(change, dict)
                    or any(not _valid_marks(check.get(field), maximum)
                           for field in ("critical", "confirmed", "rejected", "added"))
                    or not isinstance(check.get("evidence"), str)
                    or any(not _valid_marks(change.get(field, []), maximum) for field in ("remove", "add"))):
                raise SystemExit(f"invalid review marks: {case}/{label}")
            marks = set(verdict["critical"])
            confirmed, rejected, added = (set(check[field]) for field in ("confirmed", "rejected", "added"))
            if (confirmed & rejected or confirmed | rejected != marks or added & marks
                    or set(check["critical"]) != confirmed | added
                    or ((marks or added) and not check["evidence"].strip())
                    or ((change.get("remove") or change.get("add"))
                        and (not isinstance(change.get("reason"), str) or not change["reason"].strip()))):
                raise SystemExit(f"invalid review marks: {case}/{label}")
            literal = (marks & set(check.get("confirmed", []))) | set(check.get("added", []))
            resolved = (literal - set(change.get("remove", []))) | set(change.get("add", []))
            base = verdict["score_ignoring_critical"]
            for name, standing in (("literal", literal), ("resolved", resolved)):
                totals[name][arm] = totals[name].get(arm, 0) + (0 if standing else base)
            rows.append({"case": case, "label": label, "arm": arm, "base": base, "literal": sorted(literal),
                         "resolved": sorted(resolved), "reason": change.get("reason")})
    result = {"totals": totals, "rows": rows}
    if companion:
        result["gate"] = "C5"
    (review / f"tally-{key}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(totals))
    for row in rows:
        if row["base"] < 1 or row["literal"] or row["resolved"]:
            print(row["case"], row["label"], row["arm"], "base", row["base"], "literal", row["literal"],
                  "resolved", row["resolved"], row["reason"] or "")


def _turn_rows(blind_dir: Path, scenario: str, arm: str) -> dict:
    rows = {}
    for line in (blind_dir / f"results_{scenario}_{arm}.jsonl").read_text().splitlines():
        row = json.loads(line)
        rows[(row["session"], row["turn"])] = row
    return rows


def _content(item: dict) -> str:
    text = item.get("content") or ""
    calls = item.get("tool_calls") or []
    if calls:
        text += "".join(f"\n[tool call] {call['function']['name']}({call['function'].get('arguments', '')})"
                        for call in calls)
    return text


def attribution_inputs(review: Path, blind_dir: Path, scenario_path: str, key: str, out: Path,
                       gated: str = "PE") -> None:
    """One file per gated reply with a standing critical error: the marks and evidence, taken from the review files,
    and everything memory gave the host in that session up to and including the scored turn. Files are named by
    case and label only; nothing is written by hand."""
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    tally_rows = json.loads((review / f"tally-{key}.json").read_text())["rows"]
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    path = review / f"resolution-{key}.json"
    resolution = json.loads(path.read_text()) if path.exists() else {}
    out.mkdir(parents=True, exist_ok=True)
    for row in tally_rows:
        if not row["resolved"] or sealed[row["case"]][row["label"]] not in gated:
            continue
        case, label = row["case"], row["label"]
        session, turn = next((s, t) for s, t, c, _ in module.CASES if c == case)
        rows = _turn_rows(blind_dir, scenario, sealed[case][label])
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text()).get(label, {})
        marks = (f"Standing critical error type(s): {row['resolved']}\n\nFirst reviewer: {first[case][label].get('reason', '')}"
                 f"\n\nSecond reviewer: {second.get('evidence', '')}"
                 f"\n\nResolution: {resolution.get(f'{case}/{label}', {}).get('reason', 'none')}")
        earlier = []
        for index in range(turn):
            previous = rows[(session, index)]
            earlier.append(f"## Message {index + 1} of this session\n\n" + "\n\n".join(
                f"[{item['role']}] {_content(item)}" for item in previous["transcript"]))
        current = rows[(session, turn)]
        calls = "\n".join(f"- {call['name']}({json.dumps(call['arguments'], ensure_ascii=False)}) -> {call['result']}"
                          for call in current.get("tool_calls", []))
        (out / f"{case.split('-')[0]}-{label}.md").write_text(
            f"# Critical error\n\n{marks}\n\n# Context at the start of this session (the session-start memory, or "
            f"for hosts without hooks the memory added to the session's first message)\n\n"
            f"{current.get('session_context') or '(none)'}\n\n# Earlier messages in this session, as the assistant saw "
            f"them\n\n{chr(10).join(earlier) or '(none: this is the first message)'}\n\n# The scored message as the "
            f"assistant received it (memory added before the user's text)\n\n{current['host_user_content']}\n\n"
            f"# Memory tool calls in this message\n\n{calls or '(none)'}\n\n# Reply\n\n{current['reply']}\n")
        print(out / f"{case.split('-')[0]}-{label}.md")


def _run(run: Path) -> tuple[list[dict], list[tuple[str, int]], str]:
    """A run directory's result rows, the scenario's turns in order (session, turn) and its log ("" if none)."""
    results = list(run.glob("results_*.jsonl"))
    rows = [json.loads(line) for line in results[0].read_text().splitlines()] if len(results) == 1 else []
    order = []
    if rows:
        scenario = load(str(Path(__file__).parent / (rows[0]["scenario"] + ".py")))
        order = [(session, index) for session, turns in scenario.SESSIONS_LONG for index in range(len(turns))]
    log = (run / "run.log").read_text(errors="replace") if (run / "run.log").exists() else ""
    return rows, order, log


def _position(order: list, row: dict) -> str:
    """Where a turn is, without naming its session (session ids describe content)."""
    key = (row["session"], row["turn"])
    return f"turn {order.index(key) + 1} of {len(order)}" if key in order else "an unknown turn"


def validity(run_dirs: list[Path]) -> None:
    """Refuse an attempt whose runs degraded: a missing or unfinished log, missing or empty replies, a call cap, a
    harness error or an index timeout in any arm. Names turns by position only. Prints the reference arm's largest
    prompt and each arm's count of retried empty replies."""
    problems, largest, retried = [], 0, {}
    for run in run_dirs:
        rows, order, log = _run(run)
        if not rows:
            problems.append(f"{run}: expected one results file with rows")
            continue
        arm, scenario = rows[0]["arm"], rows[0]["scenario"]
        if len(rows) != len(order):
            problems.append(f"{run}: {len(rows)} of {len(order)} turns")
        problems += [f"{run}: empty reply at {_position(order, row)}" for row in rows if not row["reply"].strip()]
        lines = [line for line in log.splitlines() if line.strip()]
        if not lines or not lines[-1].endswith(f"{arm} {scenario} finished"):
            problems.append(f"{run}: run.log missing, empty or not ending with the finished line")
        problems += [f"{run}: {marker}" for marker in ("cap reached", "Traceback") if marker in log]
        retried[f"{run.name} ({arm})"] = log.count("host error ValueError empty reply")
        events = run / "harness-events.jsonl"
        if events.exists() and "index_wait_timed_out" in events.read_text():
            problems.append(f"{run}: index wait timed out")
        if arm == "F":
            largest = max(largest, max(row["usage"].get("prompt_tokens", 0) for row in rows))
    print(json.dumps({"valid": not problems, "problems": problems, "reference_largest_prompt_tokens": largest,
                      "empty_replies_retried": retried}))


_ERROR = re.compile(r"\bhost error\b|cap reached|harness event|^Traceback|^\S*(Error|Exception)\b")


def diagnose(run_dirs: list[Path]) -> None:
    """What an invalid run's diagnosis may read: error lines from the log (never the per-turn progress lines, which
    show memory tool arguments) and where each arm stopped, by position. No input, reply, context or transcript."""
    for run in run_dirs:
        rows, order, log = _run(run)
        print(f"== {run.name}: {len(rows)} of {len(order)} turns done"
              + (f"; last done {_position(order, rows[-1])}" if rows else ""))
        for row in rows:
            if not row["reply"].strip():
                print(f"   empty reply at {_position(order, row)}")
        frame = False
        for line in log.splitlines():
            text = line.split(" ", 1)[1] if re.match(r"\d\d:\d\d:\d\d ", line) else line
            if _ERROR.search(text) or (frame and line.startswith("  File ")):
                frame = text.startswith("Traceback") or (frame and not _ERROR.search(text))
                print("   " + text[:200])
            else:
                frame = frame and line.startswith(" ")


def verdicts(path: Path, scenario_path: str, *, companion=False) -> None:
    """Check a first-review file before the split, and rename prefix keys ("L01") to full case ids.

    Refuses unless the result covers exactly the scenario's cases, each with labels A, B and C, a score of 0, 0.5 or
    1, and critical types from 1 to 5 (1 to 9 for C5). A rename happens only when every key is the prefix of one case; the
    original is kept as <name>.raw.json and nothing but the top-level keys changes."""
    ids = [case for _, _, case, _ in load(scenario_path).CASES]
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        raise SystemExit(f"invalid: not JSON ({error})")
    if not isinstance(data, dict):
        raise SystemExit("invalid: not an object")
    renamed = {}
    for key in data:
        matches = [case for case in ids if case == key or case.split("-")[0] == key]
        if len(matches) != 1:
            raise SystemExit(f"invalid: key {key!r} does not name exactly one case")
        renamed[key] = matches[0]
    if sorted(renamed.values()) != sorted(ids):
        raise SystemExit("invalid: the keys do not cover exactly the scenario's cases")
    for key, verdict in data.items():
        if not isinstance(verdict, dict) or sorted(verdict) != ["A", "B", "C"]:
            raise SystemExit(f"invalid: {renamed[key].split('-')[0]} does not have exactly labels A, B and C")
        for label, item in verdict.items():
            critical = item.get("critical") if isinstance(item, dict) else None
            if (not isinstance(item, dict) or type(item.get("score_ignoring_critical")) not in (int, float)
                    or item["score_ignoring_critical"] not in (0, 0.5, 1)
                    or not _valid_marks(critical, 9 if companion else 5)):
                raise SystemExit(f"invalid: {renamed[key].split('-')[0]}/{label} has a bad score or critical list")
    changed = [key for key, case in renamed.items() if key != case]
    if changed:
        raw = path.with_name(path.stem + ".raw.json")
        raw.write_bytes(path.read_bytes())
        path.write_text(json.dumps({renamed[key]: value for key, value in data.items()}, ensure_ascii=False, indent=1))
    print(json.dumps({"valid": True, "renamed_keys": len(changed)}))


def _checked_tally(path: Path, *, companion=False) -> dict:
    try:
        data = json.loads(path.read_text())
        totals, rows = data["totals"]["resolved"], data["rows"]
        if data.get("gate", "R4") != ("C5" if companion else "R4"):
            raise ValueError("tally belongs to a different gate")
        if (not isinstance(totals, dict) or set(totals) != set("PEF")
                or not isinstance(rows, list) or not rows):
            raise ValueError("missing totals or rows")
        calculated, cases = dict.fromkeys("PEF", 0), {}
        for row in rows:
            case, label, arm, base, marks = (row[field] for field in ("case", "label", "arm", "base", "resolved"))
            if (not isinstance(case, str) or not case or label not in ("A", "B", "C")
                    or arm not in ("P", "E", "F") or type(base) not in (int, float)
                    or base not in (0, 0.5, 1) or not _valid_marks(marks, 9 if companion else 5)):
                raise ValueError("bad row")
            labels = cases.setdefault(case, {})
            if label in labels:
                raise ValueError("duplicate case label")
            labels[label] = arm
            calculated[arm] += 0 if marks else base
        if any(set(labels) != set("ABC") or set(labels.values()) != set("PEF") for labels in cases.values()):
            raise ValueError("incomplete case")
        if any(type(value) not in (int, float) or value != calculated[arm] for arm, value in totals.items()):
            raise ValueError("totals disagree with rows")
        return data
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"invalid tally {path.name}: {error}") from error


def gate(review: Path, keys: list[str], *, companion=False) -> dict:
    """The attempt-3 pass rule from the tallies and the attributions (two per gated reply; disagreement or a
    missing or invalid answer counts as memory). C5 also refuses every standing boundary or deletion error."""
    if not keys or len(set(keys)) != len(keys):
        raise SystemExit("invalid tally: expected distinct scenario keys")
    tallies = [_checked_tally(review / f"tally-{key}.json", companion=companion) for key in keys]
    seen_cases = set()
    for data in tallies:
        cases = {row["case"] for row in data["rows"]}
        if overlap := seen_cases & cases:
            raise SystemExit(f"invalid tally: duplicate case {sorted(overlap)[0].split('-')[0]} across scenarios")
        seen_cases.update(cases)
    totals, critical, causes, protected = {}, {}, {}, {}
    for key, data in zip(keys, tallies, strict=True):
        for arm, value in data["totals"]["resolved"].items():
            totals[arm] = totals.get(arm, 0) + value
        for row in data["rows"]:
            if row["resolved"]:
                critical.setdefault(row["arm"], []).append(f"{row['case']}/{row['label']}")
                if companion and set(row["resolved"]) & {7, 8}:
                    protected.setdefault(row["arm"], []).append(f"{row['case']}/{row['label']}")
                if row["arm"] in "PE":
                    answers = []
                    for attempt in ("1", "2"):
                        path = review / f"attribution-{key}" / f"{row['case'].split('-')[0]}-{row['label']}.{attempt}.json"
                        try:
                            answer = json.loads(path.read_text())
                            answers.append(answer.get("cause") if isinstance(answer, dict) else None)
                        except (OSError, ValueError):
                            answers.append(None)
                    cause = "host" if answers == ["host", "host"] else "memory"
                    causes[f"{row['case']}/{row['label']}"] = {"answers": answers, "cause": cause}
    reference = totals.get("F", 0)
    verdict = {}
    for arm in "PE":
        replies = critical.get(arm, [])
        memory = [reply for reply in replies if causes[reply]["cause"] == "memory"]
        host = [reply for reply in replies if causes[reply]["cause"] == "host"]
        verdict[arm] = {"total": totals.get(arm, 0), "reference": reference,
                        "not_worse": totals.get(arm, 0) >= reference - 1, "memory_caused": memory,
                        "host_caused": host, "reference_critical": len(critical.get("F", [])),
                        "passes": totals.get(arm, 0) >= reference - 1 and not memory
                        and len(host) <= len(critical.get("F", [])) and not protected.get(arm)}
        if companion:
            verdict[arm]["boundary_or_deletion_errors"] = protected.get(arm, [])
    name = "C5" if companion else "R4"
    result = {"arms": verdict, "attributions": causes, name: all(item["passes"] for item in verdict.values())}
    if companion:
        result["strict_boundaries_and_deletions"] = True
    (review / ("gate-c5.json" if companion else "gate.json")).write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return result


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    companion = "--companion" in args
    if companion:
        if command not in ("verdicts", "tally", "gate") or args.count("--companion") != 1:
            raise SystemExit("--companion is valid once for verdicts, tally or gate")
        args.remove("--companion")
    if command == "split":
        split(Path(args[0]), Path(args[1]), Path(args[2]), args[3], Path(args[4]))
    elif command == "tally":
        tally(Path(args[0]), Path(args[1]), args[2], args[3], companion=companion)
    elif command == "attribution-inputs":
        attribution_inputs(Path(args[0]), Path(args[1]), args[2], args[3], Path(args[4]))
    elif command == "validity":
        validity([Path(arg) for arg in args])
    elif command == "r5-inputs":
        r5_inputs(Path(args[0]), Path(args[1]), args[2], args[3], Path(args[4]))
    elif command == "r5-check":
        r5_check(Path(args[0]), Path(args[1]), Path(args[2]))
    elif command == "verdicts":
        verdicts(Path(args[0]), args[1], companion=companion)
    elif command == "diagnose":
        diagnose([Path(arg) for arg in args])
    elif command == "gate":
        result = gate(Path(args[0]), args[1:], companion=companion)
        if companion and not result["C5"]:
            raise SystemExit(1)
    else:
        raise SystemExit(__doc__)
