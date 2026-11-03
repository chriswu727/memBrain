"""Check a C5 dry run (practice scenario, stub host): each layer reached each arm's context, the scenario clock and
the page actions took effect, every action removed only what its scope names, F's history changed only for deleted
messages, and nothing touched the network.

Usage: python c5-dry-run-check.py SCENARIO_FILE OUT_ROOT KEY
Prints one JSON summary (per layer: checks passed and failures) and exits 1 on any failure. Practice scenarios only:
it prints context excerpts in failure messages.
"""
import datetime
import importlib.util
import json
import re
import sys
from pathlib import Path

UNCHANGED = {  # Page fields each action must leave as they were (P and E).
    "delete_message": ("persona_version", "boundaries"),
    "delete_feeling": ("messages", "notes", "persona_version", "boundaries", "shared_moments"),
    "delete_note": ("messages", "persona_version", "boundaries"),
    "clear_feelings": ("messages", "notes", "persona_version", "boundaries", "shared_moments", "mood_pinned"),
    "reset_mood": ("messages", "notes", "feelings", "persona_version", "boundaries", "shared_moments"),
    "pin_mood": ("messages", "notes", "feelings", "persona_version", "boundaries", "shared_moments"),
    "add_boundary": ("messages", "notes", "feelings", "persona_version", "shared_moments"),
    "remove_boundary": ("messages", "notes", "feelings", "persona_version", "shared_moments"),
    "reset_relationship": ("messages", "feelings", "persona_version", "mood_pinned"),
    "set_persona": ("messages", "notes", "feelings", "boundaries", "shared_moments", "mood"),
    "restore_persona": ("messages", "notes", "feelings", "boundaries", "shared_moments", "mood"),
    "reset_persona": ("messages", "notes", "feelings", "boundaries", "shared_moments", "mood"),
    "delete_persona_history": ("messages", "notes", "feelings", "boundaries", "shared_moments", "mood"),
    "accept_persona_proposal": ("messages", "notes", "feelings", "boundaries", "shared_moments", "mood"),
    "reject_persona_proposal": ("messages", "notes", "feelings", "boundaries", "shared_moments", "mood",
                                "persona_version"),
}
LAYER = {"set_persona": "persona", "restore_persona": "persona", "reset_persona": "persona",
         "delete_persona_history": "persona", "accept_persona_proposal": "persona",
         "reject_persona_proposal": "persona", "clear_feelings": "affect", "delete_feeling": "affect",
         "delete_message": "affect", "delete_note": "affect", "reset_mood": "mood", "pin_mood": "mood",
         "add_boundary": "relationship", "remove_boundary": "relationship", "reset_relationship": "relationship"}


def load(path):
    spec = importlib.util.spec_from_file_location("scenario", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jsonl(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def context(arm: str, row: dict) -> str:
    """What memory gave the host for this message. A refreshed snapshot replaces the session start's blocks."""
    if arm == "F":
        return row.get("reference_persona", "") + "\n" + row["host_user_content"]
    if arm == "E":  # The proxy puts memory into each message; its session_context is a copy of the first one.
        return row["host_user_content"]
    if "<membrain-updates>" in row["host_user_content"]:
        return row["host_user_content"]
    return row["session_context"] + "\n" + row["host_user_content"]


def outside_relationship(text: str) -> str:
    return re.sub(r"<membrain-relationship>.*?</membrain-relationship>", "", text, flags=re.S)


def check(scenario_path: str, root: Path, key: str) -> dict:
    module = load(scenario_path)
    stem = Path(scenario_path).stem
    report = {layer: {"passed": 0, "failures": []} for layer in
              ("persona", "affect", "mood", "relationship", "page_actions", "reference", "clock", "tools",
               "network", "run")}

    def verdict(layer, ok, failure):
        if ok:
            report[layer]["passed"] += 1
        else:
            report[layer]["failures"].append(failure)

    runs = {arm: root / f"{key}-{arm}" for arm in "PEF"}
    rows = {arm: {(row["session"], row["turn"]): row for row in jsonl(run / f"results_{stem}_{arm}.jsonl")}
            for arm, run in runs.items()}
    events = {arm: jsonl(run / "harness-events.jsonl") for arm, run in runs.items()}
    actions = {arm: jsonl(run / "page-actions.jsonl") for arm, run in runs.items()}
    turns = [(session, index) for session, messages in module.SESSIONS_LONG for index in range(len(messages))]
    p2 = not any(event["kind"] == "page_action_unsupported" for arm in events for event in events[arm])
    report["p2_proposals"] = "exercised" if p2 else "skipped: this runtime has no persona proposals"

    for arm, run in runs.items():
        verdict("run", len(rows[arm]) == len(turns), f"{arm}: {len(rows[arm])} of {len(turns)} turns")
        log = (run / "run.log").read_text() if (run / "run.log").exists() else ""
        verdict("run", "Traceback" not in log, f"{arm}: Traceback in run.log")
        verdict("network", not any(event["kind"] == "network_refused" for event in events[arm]),
                f"{arm}: a network connection was attempted")
        verdict("run", not any(event["kind"] in ("page_action_failed", "index_wait_timed_out",
                                                 "extraction_unfinished") for event in events[arm]),
                f"{arm}: harness events {[event['kind'] for event in events[arm]]}")

    # Context per layer.
    expect = list(module.EXPECT) + (list(getattr(module, "EXPECT_P2", [])) if p2 else [])
    for session, turn, arms, present, absent in expect:
        for arm in arms:
            row = rows[arm].get((session, turn))
            if row is None:
                continue
            text = context(arm, row)
            for needle in present:
                verdict(_layer(needle), needle in text, f"{arm} {session} t{turn}: missing {needle!r}")
            for needle in absent:
                verdict(_layer(needle), needle not in outside_relationship(text),
                        f"{arm} {session} t{turn}: should not contain {needle!r}")

    # F is given the same persona block as P whenever P's context carries one.
    for position, row in rows["F"].items():
        block = row.get("reference_persona") or ""
        found = re.findall(r'<membrain-persona version="\d+">.*?</membrain-persona>', context("P", rows["P"][position]),
                           flags=re.S) if position in rows["P"] else []
        if found:
            verdict("reference", found[-1] == block, f"F {position}: persona block differs from P's")

    # The scenario clock: each row's scenario time is the session's stated time (plus the minutes the run took).
    starts = {}
    for session, messages in module.SESSIONS_LONG:
        found = re.search(r"(\w+) (\d+), (\d\d):(\d\d)", messages[0])
        month = datetime.datetime.strptime(found[1], "%B").month
        starts[session] = datetime.datetime(module.YEAR, month, int(found[2]), int(found[3]), int(found[4]),
                                            tzinfo=datetime.UTC)
    for arm in "PE":
        for (session, turn), row in rows[arm].items():
            moment = datetime.datetime.fromisoformat(row["scenario_time"].replace("Z", "+00:00"))
            verdict("clock", starts[session] <= moment < starts[session] + datetime.timedelta(minutes=30),
                    f"{arm} {session} t{turn}: scenario time {row['scenario_time']}")
        verdict("clock", not any(event["kind"] == "clock_already_past" for event in events[arm]),
                f"{arm}: a session started after the clock had passed its time")

    # Tools: P offers memory_boundary and the note tool's affect and shared fields; every scripted call succeeded.
    calls = [call for row in rows["P"].values() for call in row["tool_calls"]]
    verdict("tools", any(call["name"] == "memory_boundary" for call in calls), "P: memory_boundary never called")
    verdict("tools", any(call["arguments"].get("shared") for call in calls), "P: no shared note")
    verdict("tools", any(call["arguments"].get("affect") for call in calls), "P: no note with a feeling")
    for call in calls:
        verdict("tools", '"error"' not in call["result"], f"P: {call['name']} failed: {call['result'][:200]}")
    verdict("tools", not any(row["tool_calls"] for arm in "EF" for row in rows[arm].values()),
            "E or F made a tool call")

    # Page actions: each removed only what its scope names; F's history changed only for deleted messages.
    scripted = list(module.PAGE_ACTIONS)
    for arm in "PEF":
        expected = [action for _, _, action in scripted
                    if (not action.get("arms") or ("P" if arm == "F" else arm) in action["arms"])
                    and (p2 or not action["do"].endswith("_proposal"))]
        verdict("page_actions", [entry["action"] for entry in actions[arm]] == [a["do"] for a in expected],
                f"{arm}: page actions applied {[entry['action'] for entry in actions[arm]]}")
        for entry in actions[arm]:
            kind, before, after, result = entry["action"], entry["before"], entry["after"], entry["result"]
            layer = LAYER[kind]
            verdict(layer, not result.get("failed"), f"{arm} {kind}: {result.get('failed')}")
            if arm == "F":
                deleted = result.get("deleted", 0)
                if kind == "delete_message":
                    in_p = next((other["result"].get("removed") for other in actions["P"]
                                 if other["action"] == kind and other["detail"] == entry["detail"]), None)
                    target = [entry["detail"]["session"], entry["detail"]["turn"], entry["detail"].get("role", "user")]
                    report["deletion_cascade"] = in_p
                    verdict("reference", result.get("removed") == in_p and target in (in_p or []),
                            f"F {kind}: removed {result.get('removed')}, P's product removed {in_p}")
                    verdict("reference", after.get("removed_still_in_history") == 0
                            and after["history_items"] == before["history_items"] - deleted and deleted >= 1,
                            f"F {kind}: history {before['history_items']} -> {after['history_items']}, "
                            f"{after.get('removed_still_in_history')} removed messages still there")
                else:
                    verdict("reference", after["history_items"] == before["history_items"],
                            f"F {kind}: history changed {before['history_items']} -> {after['history_items']}")
                continue
            for field in UNCHANGED[kind]:
                verdict(layer, before[field] == after[field],
                        f"{arm} {kind}: {field} changed {before[field]} -> {after[field]}")
            if kind == "delete_message":
                verdict(layer, after["messages"] < before["messages"], f"{arm} {kind}: no message removed")
                target = [entry["detail"]["session"], entry["detail"]["turn"], entry["detail"].get("role", "user")]
                verdict(layer, target in result.get("removed", []) and len(result["removed"]) ==
                        before["messages"] - after["messages"], f"{arm} {kind}: removed {result.get('removed')}")
                verdict(layer, after["feelings"] < before["feelings"],
                        f"{arm} {kind}: the feeling drawn from the message was kept ({before['feelings']} -> "
                        f"{after['feelings']})")
            elif kind == "clear_feelings":
                verdict(layer, after["feelings"] == 0, f"{arm} {kind}: {after['feelings']} feelings left")
            elif kind == "reset_mood":
                verdict(layer, after["mood"] == "baseline", f"{arm} {kind}: mood {after['mood']}")
            elif kind == "add_boundary":
                verdict(layer, len(after["boundaries"]) == len(before["boundaries"]) + 1, f"{arm} {kind}")
            elif kind == "remove_boundary":
                verdict(layer, len(after["boundaries"]) == len(before["boundaries"]) - 1, f"{arm} {kind}")
            elif kind == "reset_relationship":
                verdict(layer, after["boundaries"] == [] and after["shared_moments"] == 0
                        and after["familiarity"] == "new", f"{arm} {kind}: {after}")
                verdict(layer, after["notes"] == before["notes"] - before["shared_moments"],
                        f"{arm} {kind}: notes {before['notes']} -> {after['notes']} with "
                        f"{before['shared_moments']} shared moments")
            elif kind in ("accept_persona_proposal", "set_persona", "restore_persona", "reset_persona"):
                verdict(layer, after["persona_version"] == before["persona_version"] + 1, f"{arm} {kind}")

    failures = sum(len(value["failures"]) for value in report.values() if isinstance(value, dict))
    report["ok"] = failures == 0
    return report


def _layer(needle: str) -> str:
    if "persona" in needle or "Juniper" in needle or "register" in needle:
        return "persona"
    if "mood" in needle or needle.startswith("glad"):
        return "mood"
    if "felt" in needle or "nervous" in needle or "review" in needle:
        return "affect"
    return "relationship"


if __name__ == "__main__":
    result = check(sys.argv[1], Path(sys.argv[2]), sys.argv[3])
    print(json.dumps(result, indent=1, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)
