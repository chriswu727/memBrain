"""Review pipeline for the final behavioral acceptance (frozen by hash in the attempt plan).

  split   SHEET VERDICTS BLIND_DIR SCENARIO OUT_DIR   one file per case for the second review; refuses to write a
                                                      case file unless every reply appears in it in full
  tally   REVIEW_DIR BLIND_DIR SCENARIO KEY           final scores per arm, literal and with written resolutions

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


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "split":
        split(Path(args[0]), Path(args[1]), Path(args[2]), args[3], Path(args[4]))
    elif command == "tally":
        tally(Path(args[0]), Path(args[1]), args[2], args[3])
    else:
        raise SystemExit(__doc__)
