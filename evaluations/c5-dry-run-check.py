"""Check a two-arm dry run (practice scenario, stub host): each layer reached each arm's context, both arms carried the
same persona, P was offered the plugin's tools and the server's instructions, scripted tool calls (consolidation
included) succeeded, the scenario clock and the page actions took effect, every action removed only what its scope
names, F's history changed only for deleted messages, the arms ran one after the other with P's installation stopped
and its ports closed before F started, and nothing touched the network.

Usage: python c5-dry-run-check.py SCENARIO_FILE OUT_ROOT KEY
Prints one JSON summary (per layer: checks passed and failures) and exits 1 on any failure. Practice scenarios only:
it prints context excerpts in failure messages.

Arms are P and F (the proxy-with-extraction arm E of attempts 1 to 5 no longer exists). A scenario may name what the
check requires of P: EXPECT_TOOLS_P (tools that must be called, each without an error; default memory_boundary),
EXPECT_NOTE_FIELDS_P (note fields some note call must use; default shared and affect) and EXPECT_CONSOLIDATION_P
((session, turn) where P must take a consolidation batch and answer it).
"""
import importlib.util
import json
import re
import socket
import sys
from pathlib import Path

ARMS = ("P", "F")
P_PORTS = (8893, 55533)  # The run script's ports for arm P.
SERVER_TOOLS = {"memory_recall", "memory_note", "memory_boundary", "memory_pause", "memory_resume",
                "memory_consolidate", "memory_persona", "memory_manner_feedback"}
UNCHANGED = {  # Page fields each action must leave as they were (P).
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


def load(path, name="scenario"):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jsonl(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def context(arm: str, row: dict) -> str:
    """What memory gave the host for this message. A refreshed snapshot replaces the session start's blocks."""
    if arm == "F":
        return row.get("reference_persona", "") + "\n" + row["host_user_content"]
    if "<membrain-updates>" in row["host_user_content"]:
        return row["host_user_content"]
    return row["session_context"] + "\n" + row["host_user_content"]


def outside_relationship(text: str) -> str:
    return re.sub(r"<membrain-relationship>.*?</membrain-relationship>", "", text, flags=re.S)


def _supervision(run: Path) -> dict:
    """The run script's supervisor.log: {"started"|"finished"|"cleaned": epoch seconds}."""
    path = run / "supervisor.log"
    stamps = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        name, _, value = line.partition(" ")
        stamps[name] = float(value)
    return stamps


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def check(scenario_path: str, root: Path, key: str) -> dict:
    import datetime

    module = load(scenario_path)
    harness = load(str(Path(__file__).with_name("c5-harness.py")), "c5_harness_for_dry_run_check")
    stem = Path(scenario_path).stem
    report = {layer: {"passed": 0, "failures": []} for layer in
              ("persona", "affect", "mood", "relationship", "page_actions", "reference", "clock", "tools",
               "network", "run", "recording", "consolidation", "dates", "instructions", "sequence", "cleanup")}

    def verdict(layer, ok, failure):
        if ok:
            report[layer]["passed"] += 1
        else:
            report[layer]["failures"].append(failure)

    runs = {arm: root / f"{key}-{arm}" for arm in ARMS}
    verdict("run", not (root / f"{key}-E").exists(), "a run directory for the removed arm E exists")
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
        # Any harness event degrades a run (acceptance_review.py validity), whatever its kind; only kinds are read.
        verdict("run", not events[arm], f"{arm}: harness events {[event['kind'] for event in events[arm]]}")

    # Persona: one fixed persona in both arms, never the product's random first type or its announcement.
    personas = {}
    for arm, run in runs.items():
        try:
            personas[arm] = json.loads((run / "persona.json").read_text())
        except (OSError, ValueError):
            personas[arm] = None
        verdict("persona", personas[arm] is not None, f"{arm}: no persona.json")
    if all(personas.values()):
        same = {field: {personas[arm].get(field) for arm in ARMS}
                for field in ("source", "seed", "preset", "card_sha256", "version")}
        verdict("persona", all(len(values) == 1 for values in same.values()),
                f"the arms' personas differ: {sorted(field for field, values in same.items() if len(values) > 1)}")
        if personas["P"]["source"] == "seeded":
            drawing = load(str(Path(__file__).with_name("acceptance_persona.py")), "acceptance_persona_for_check")
            verdict("persona", personas["P"]["preset"] == drawing.draw(personas["P"]["seed"]),
                    "the persona is not the draw of its seed")
    for position, row in rows["P"].items():
        verdict("persona", "picked at random" not in context("P", row),
                f"P {position}: the product's random first persona or its announcement reached the host")

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

    # The server's instructions reach P's system prompt and never F's (the stub host reports what it saw).
    for arm in ARMS:
        expected = "server instructions: given" if arm == "P" else "server instructions: none"
        for position, row in rows[arm].items():
            if row["reply"].startswith("(stub reply"):
                verdict("instructions", expected in row["reply"], f"{arm} {position}: expected {expected!r}")
    tools = runs["P"] / "tools.json"
    offered = json.loads(tools.read_text()) if tools.exists() else {}
    verdict("instructions", bool(offered.get("server_instructions_chars")), "P: no server instructions recorded")
    verdict("tools", SERVER_TOOLS <= set(offered.get("offered", [])),
            f"P: not offered {sorted(SERVER_TOOLS - set(offered.get('offered', [])))}")

    # The scenario clock: each row's scenario time is the session's stated time (plus the minutes the run took).
    year = getattr(module, "YEAR", harness.YEAR)
    starts = {session: harness.session_start(messages[0], year) for session, messages in module.SESSIONS_LONG}
    for (session, turn), row in rows["P"].items():
        moment = datetime.datetime.fromisoformat(row["scenario_time"].replace("Z", "+00:00"))
        verdict("clock", starts[session] <= moment < starts[session] + datetime.timedelta(minutes=30),
                f"P {session} t{turn}: scenario time {row['scenario_time']}")
        verdict("dates", row["date"] == starts[session].date().isoformat(), f"P {session} t{turn}: row date")
    verdict("clock", not any(event["kind"] == "clock_already_past" for event in events["P"]),
            "P: a session started after the clock had passed its time")

    for session, turn, expected in getattr(module, "EXPECT_RECORDING_P", []):
        row = rows["P"].get((session, turn), {})
        verdict("recording", row.get("recorded") is expected, f"P {session} t{turn}: recording expected {expected}")

    # Tools: every scripted call succeeded; the scenario's required tools and note fields were used; F made none.
    calls = [call for row in rows["P"].values() for call in row["tool_calls"]]
    for name in getattr(module, "EXPECT_TOOLS_P", ("memory_boundary",)):
        verdict("tools", any(call["name"] == name for call in calls), f"P: {name} never called")
    for field in getattr(module, "EXPECT_NOTE_FIELDS_P", ("shared", "affect")):
        verdict("tools", any(call["name"] == "memory_note" and call["arguments"].get(field) for call in calls),
                f"P: no note with {field}")
    for call in calls:
        verdict("tools", '"error"' not in call["result"], f"P: {call['name']} failed: {call['result'][:200]}")
    verdict("tools", not any(row["tool_calls"] for row in rows["F"].values()), "F made a tool call")

    # Consolidation: the session notice asked, P took a batch and answered it with cues, and memory indexed them.
    for session, turn in getattr(module, "EXPECT_CONSOLIDATION_P", []):
        row = rows["P"].get((session, turn), {})
        verdict("consolidation", "earlier messages have not been indexed" in (row.get("session_context") or ""),
                f"P {session}: the session notice did not ask for consolidation")
        # Full tool results from the turn's transcript (tool_calls keeps only their first 2,000 characters).
        results = [item.get("content") or "" for item in row.get("transcript", []) if item.get("role") == "tool"]
        made = [(call, results[index] if index < len(results) else "")
                for index, call in enumerate(row.get("tool_calls", [])) if call["name"] == "memory_consolidate"]
        verdict("consolidation", len(made) == 2 and not made[0][0]["arguments"]
                and made[1][0]["arguments"].get("cues"),
                f"P {session} t{turn}: consolidation calls {[sorted(call['arguments']) for call, _ in made]}")
        if len(made) == 2:
            try:
                handed, answered = json.loads(made[0][1]), json.loads(made[1][1])
            except ValueError:
                handed, answered = {}, {}
            verdict("consolidation", bool(handed.get("messages")) and "instructions" in handed,
                    f"P {session} t{turn}: no batch handed out")
            verdict("consolidation", (answered.get("indexed") or 0) >= 1, f"P {session} t{turn}: nothing indexed")

    # Sequence and cleanup: P ran, was stopped and its ports closed before F started.
    stamps = {arm: _supervision(run) for arm, run in runs.items()}
    for arm in ARMS:
        verdict("sequence", {"started", "finished", "cleaned"} <= set(stamps[arm]),
                f"{arm}: supervisor stamps {sorted(stamps[arm])}")
    if all({"started", "cleaned"} <= set(stamps[arm]) for arm in ARMS):
        verdict("sequence", stamps["P"]["cleaned"] <= stamps["F"]["started"], "F started before P was cleaned up")
    cleanup = (runs["P"] / "cleanup.log").read_text().strip().splitlines() if (runs["P"] / "cleanup.log").exists() \
        else []
    try:
        cleaned = json.loads(cleanup[-1]) if cleanup else {}
    except ValueError:
        cleaned = {}
    verdict("cleanup", cleaned.get("ok") is True and cleaned.get("profiles", 0) >= 1,
            f"P cleanup: {cleaned or 'no report'}")
    verdict("cleanup", not any(_port_open(port) for port in P_PORTS), f"ports {P_PORTS} still open after the run")

    # Page actions: each removed only what its scope names; F's history changed only for deleted messages.
    scripted = list(getattr(module, "PAGE_ACTIONS", []))
    for arm in ARMS:
        expected = [action for _, _, action in scripted
                    if (not action.get("arms") or "P" in action["arms"])
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
    report["checks"] = sum(value["passed"] + len(value["failures"]) for value in report.values()
                           if isinstance(value, dict))
    report["ok"] = failures == 0
    return report


def _layer(needle: str) -> str:
    if needle.startswith("[20"):
        return "dates"
    if "indexed" in needle:
        return "consolidation"
    if "persona" in needle or "Juniper" in needle or "register" in needle or "picked at random" in needle:
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
