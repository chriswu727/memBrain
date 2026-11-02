"""Review pipeline for the final behavioral acceptance (frozen by hash in the attempt plan).

  split   SHEET VERDICTS BLIND_DIR SCENARIO OUT_DIR   one file per case for the second review; refuses to write a
                                                      case file unless every reply appears in it in full
  tally   REVIEW_DIR BLIND_DIR SCENARIO KEY           final scores per arm, literal and with written resolutions
  attribution-inputs REVIEW_DIR BLIND_DIR SCENARIO KEY OUT_DIR   one arm-blind file per gated reply with a standing
                                                      critical error, for attribute.md
  validity RUN_DIR...                                 refuse an attempt whose runs degraded
  gate REVIEW_DIR KEY...                              the attempt-3 pass rule from tallies and attributions

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


def tally(review: Path, blind_dir: Path, scenario_path: str, key: str) -> None:
    module = load(scenario_path)
    scenario = Path(scenario_path).stem
    sealed = json.loads((blind_dir / f"sealed_{scenario}.json").read_text())
    first = json.loads((review / f"verdicts-{key}.json").read_text())
    path = review / f"resolution-{key}.json"
    resolution = json.loads(path.read_text()) if path.exists() else {}
    totals, rows = {"literal": {}, "resolved": {}}, []
    for _, _, case, _ in module.CASES:
        second = json.loads((review / f"recheck-{key}" / f"{case}.json").read_text())
        for label, verdict in first[case].items():
            arm = sealed[case][label]
            marks, check = set(verdict.get("critical", [])), second.get(label, {})
            literal = (marks & set(check.get("confirmed", []))) | set(check.get("added", []))
            change = resolution.get(f"{case}/{label}", {})
            resolved = (literal - set(change.get("remove", []))) | set(change.get("add", []))
            base = verdict["score_ignoring_critical"]
            for name, standing in (("literal", literal), ("resolved", resolved)):
                totals[name][arm] = totals[name].get(arm, 0) + (0 if standing else base)
            rows.append({"case": case, "label": label, "arm": arm, "base": base, "literal": sorted(literal),
                         "resolved": sorted(resolved), "reason": change.get("reason")})
    (review / f"tally-{key}.json").write_text(json.dumps({"totals": totals, "rows": rows}, indent=1,
                                                          ensure_ascii=False))
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


def validity(run_dirs: list[Path]) -> None:
    """Refuse an attempt whose runs degraded: empty or missing replies, a call cap, a harness error or an index
    timeout in any arm. Prints the reference arm's largest prompt."""
    problems, largest = [], 0
    for run in run_dirs:
        results = list(run.glob("results_*.jsonl"))
        if len(results) != 1:
            problems.append(f"{run}: expected one results file")
            continue
        rows = [json.loads(line) for line in results[0].read_text().splitlines()]
        scenario = load(str(Path(__file__).parent / (rows[0]["scenario"] + ".py")))
        expected = sum(len(turns) for _, turns in scenario.SESSIONS_LONG)
        if len(rows) != expected:
            problems.append(f"{run}: {len(rows)} of {expected} turns")
        problems += [f"{run}: empty reply at {row['session']} {row['turn']}" for row in rows if not row["reply"].strip()]
        log = (run / "run.log").read_text() if (run / "run.log").exists() else ""
        problems += [f"{run}: {marker}" for marker in ("cap reached", "Traceback") if marker in log]
        events = run / "harness-events.jsonl"
        if events.exists() and "index_wait_timed_out" in events.read_text():
            problems.append(f"{run}: index wait timed out")
        if rows and rows[0]["arm"] == "F":
            largest = max(largest, max(row["usage"].get("prompt_tokens", 0) for row in rows))
    print(json.dumps({"valid": not problems, "problems": problems, "reference_largest_prompt_tokens": largest}))


def gate(review: Path, keys: list[str]) -> None:
    """The attempt-3 pass rule from the tallies and the attributions (two per gated reply; disagreement or a
    missing or invalid answer counts as memory)."""
    totals, critical, causes = {}, {}, {}
    for key in keys:
        data = json.loads((review / f"tally-{key}.json").read_text())
        for arm, value in data["totals"]["resolved"].items():
            totals[arm] = totals.get(arm, 0) + value
        for row in data["rows"]:
            if row["resolved"]:
                critical.setdefault(row["arm"], []).append(f"{row['case']}/{row['label']}")
                if row["arm"] in "PE":
                    answers = []
                    for attempt in ("1", "2"):
                        path = review / f"attribution-{key}" / f"{row['case'].split('-')[0]}-{row['label']}.{attempt}.json"
                        try:
                            answers.append(json.loads(path.read_text()).get("cause"))
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
                        and len(host) <= len(critical.get("F", []))}
    result = {"arms": verdict, "attributions": causes, "R4": all(item["passes"] for item in verdict.values())}
    (review / "gate.json").write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "split":
        split(Path(args[0]), Path(args[1]), Path(args[2]), args[3], Path(args[4]))
    elif command == "tally":
        tally(Path(args[0]), Path(args[1]), args[2], args[3])
    elif command == "attribution-inputs":
        attribution_inputs(Path(args[0]), Path(args[1]), args[2], args[3], Path(args[4]))
    elif command == "validity":
        validity([Path(arg) for arg in args])
    elif command == "gate":
        gate(Path(args[0]), args[1:])
    else:
        raise SystemExit(__doc__)
