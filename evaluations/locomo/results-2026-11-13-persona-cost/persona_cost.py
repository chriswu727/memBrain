"""As run on 2026-11-13; local paths are replaced by the placeholders REPOSITORY, RUNS, SCRATCH and MODEL_CACHE,
so set them before running it again.

What a persona block (and mood / relationship blocks) costs LoCoMo evidence in the session context.

No model call. Reuses stored brains (development conversations only), measures states:
  A: no persona (harness default), B: preset "wry" current, C: B plus a shared-moment note (mood trigger and
  relationship moment) and a support style (relationship block).
Then returns each brain to A and checks the session context equals A's again (no companion blocks).

Run from REPOSITORY with PYTHON_DOTENV_DISABLED=1 and the repo venv.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
import traceback
from pathlib import Path

REPO = Path("REPOSITORY")
sys.path.insert(0, str(REPO / "evaluations" / "locomo"))
from retrieval_recall import evidence_ids, needles, present, stored_turns  # noqa: E402
from run_locomo import questions, start  # noqa: E402

DATA = Path("SCRATCH/"
            "locomo-data/locomo10.json")
RUN = Path("RUNS/locomo-recall-context-20261110")
OUT = Path(__file__).resolve().parent / "results"
STATES = ("A", "B", "C")
TAGS = {"persona": "membrain-persona", "mood": "membrain-companion-mood", "relationship": "membrain-relationship",
        "history": "membrain-history"}
MOMENT_TEXT = "We laughed together over a running joke about the office coffee machine."
SUPPORT_TEXT = "Practical suggestions first, then a little encouragement."


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def block(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}[ >].*?</{tag}>", text, re.S)
    return match.group(0) if match else ""


def history_messages(history: str) -> int:
    return sum(1 for line in history.splitlines() if line.startswith("- ["))


def measure(directory: Path, sample: dict, state: str, todo, identify, turns, out_rows: list, sessions_used: list):
    from membrain import host

    first_opening = None
    for qid, qa in todo:
        wanted = evidence_ids(qa, turns)
        session = f"persona-cost-{state}-{qid}"
        sessions_used.append(session)
        opening = host.session_context(directory, session)
        recalled = host.prompt_context(directory, session, qa["question"]) or ""
        context = opening + "\n\n" + recalled
        history = block(opening, TAGS["history"])
        if first_opening is None:
            first_opening = opening
        out_rows.append({
            "state": state, "id": qid, "conversation": sample["sample_id"], "category": qa["category"],
            "evidence": wanted, "M": present(context, wanted, identify),
            "session_only": present(opening, wanted, identify), "M_recall_only": present(recalled, wanted, identify),
            "history_only": present(history, wanted, identify),
            "characters": len(context), "session_characters": len(opening), "recall_characters": len(recalled),
            "history_characters": len(history), "history_messages": history_messages(history),
            **{f"{name}_characters": len(block(opening, tag)) for name, tag in TAGS.items() if name != "history"}})
    return first_opening


def set_state(directory: Path, state: str, added: dict):
    from membrain import host, persona_presets

    with host.ready_client(directory) as client:
        if state == "B":
            result = client.switch_persona_preset("wry", made_by="host")
            log("switch wry", result.get("version"), result.get("choice"))
            log("card is wry preset:", client.persona().get("card") == persona_presets.card("wry"))
        elif state == "C":
            note = client.write_note(MOMENT_TEXT, kind="milestone", shared=True, moment="play")
            log("moment note", note)
            if note.get("shared_refused"):
                log("shared moment refused:", note["shared_refused"])
            added["note_id"] = note["note_id"]
            style = client.set_support_style(SUPPORT_TEXT)
            log("support style", style.get("support_style"))
            added["support_style"] = True
            mood = client.mood()
            log("mood", {key: mood.get(key) for key in ("label", "at_baseline", "reason", "pinned")})


def restore(directory: Path, added: dict):
    from membrain import host
    from membrain.notes import NOTES_CONVERSATION

    with host.ready_client(directory) as client:
        if added.get("note_id"):
            generation = client.dashboard()["brain"]["scope_generation"]
            result = client.forget([added["note_id"]], kind="events", mode="erase_content",
                                   expected_scope_generation=generation, conversation_id=NOTES_CONVERSATION,
                                   branch_id="main")
            log("erased moment note", json.dumps(result)[:400])
        if added.get("support_style"):
            client.set_support_style("")
            log("support style removed")
        if client.persona().get("version"):
            client.delete_persona_history()
            log("persona history deleted")
        persona = client.persona()
        relationship = client.relationship()
        mood = client.mood()
        return {"persona_version": persona.get("version"), "persona_block": bool(persona.get("block")),
                "support_style": relationship.get("support_style"),
                "shared_moments": len(relationship.get("shared_moments") or []),
                "mood_at_baseline": mood.get("at_baseline"), "mood_label": mood.get("label")}


def main():
    from membrain import desktop, host

    OUT.mkdir(parents=True, exist_ok=True)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    selected = data[:3]
    assert [sample["sample_id"] for sample in selected] == ["conv-26", "conv-30", "conv-41"]
    rows, checks = [], {}
    for sample in selected:
        directory = RUN / f"brain-{sample['sample_id']}"
        marker_dir = host.state_directory(directory) / "sessions"
        before_markers = {path.name for path in marker_dir.glob("*.json")}
        sessions_used: list[str] = []
        added: dict = {}
        check = checks.setdefault(sample["sample_id"], {})
        started = time.monotonic()
        try:
            start(directory)
            with host.ready_client(directory) as client:
                initial = client.persona()
                check["initial_persona_version"] = initial.get("version")
                check["initial_persona_markers"] = len(client.persona_versions().get("markers") or [])
                relationship = client.relationship()
                check["initial_relationship"] = {"support_style": relationship.get("support_style"),
                                                 "shared_moments": len(relationship.get("shared_moments") or []),
                                                 "familiarity": (relationship.get("familiarity") or {}).get("reason")}
                if initial.get("version"):
                    log("WARNING: brain had a persona before measuring; deleting its history for state A")
                    client.delete_persona_history()
            todo = list(questions(sample, {1, 2, 3, 4}))
            turns, identify = stored_turns(sample), needles(sample)
            openings = {}
            for state in STATES:
                if state != "A":
                    set_state(directory, state, added)
                t0 = time.monotonic()
                openings[state] = measure(directory, sample, state, todo, identify, turns, rows, sessions_used)
                (OUT / f"opening-{sample['sample_id']}-{state}.txt").write_text(openings[state], encoding="utf-8")
                present_tags = {name: (f"<{tag}" in openings[state]) for name, tag in TAGS.items()}
                check[f"tags_{state}"] = present_tags
                log(sample["sample_id"], state, len(todo), "questions", round(time.monotonic() - t0, 1), "s",
                    present_tags)
            check["restored"] = restore(directory, added)
            added = {}
            final = host.session_context(directory, f"persona-cost-final-{sample['sample_id']}")
            sessions_used.append(f"persona-cost-final-{sample['sample_id']}")
            (OUT / f"opening-{sample['sample_id']}-final.txt").write_text(final, encoding="utf-8")
            check["final_tags"] = {name: (f"<{tag}" in final) for name, tag in TAGS.items()}
            check["final_equals_A"] = final == openings["A"]
            log(sample["sample_id"], "final", check["final_tags"], "equals A:", check["final_equals_A"])
        except Exception:
            traceback.print_exc()
            check["error"] = traceback.format_exc()
            if added:
                try:
                    check["restored_after_error"] = restore(directory, added)
                except Exception:
                    traceback.print_exc()
        finally:
            removed = 0
            for session in sessions_used:
                path = host._session_marker(directory, session)
                if path.name not in before_markers and path.exists():
                    path.unlink()
                    removed += 1
            check["session_markers_removed"] = removed
            check["leftover_new_markers"] = sorted(
                {path.name for path in marker_dir.glob("*.json")} - before_markers)
            try:
                desktop.stop(directory)
                check["stopped"] = True
            except desktop.DesktopError as error:
                check["stopped"] = f"stop error {error}"
            check["status_after_stop"] = desktop.status(directory).get("ready")
            log(sample["sample_id"], "done", round(time.monotonic() - started, 1), "s", check.get("stopped"))
        with (OUT / "rows.jsonl").open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")
        (OUT / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    summarize(rows)


def summarize(rows):
    summary = {}
    for state in STATES:
        items = [row for row in rows if row["state"] == state]
        scored = [row for row in items if row["evidence"]]
        if not scored:
            continue
        entry = {"n_questions": len(items), "n_with_evidence": len(scored)}
        for arm in ("M", "session_only", "M_recall_only", "history_only"):
            entry[arm] = {
                "all_evidence": sum(len(row[arm]) == len(row["evidence"]) for row in scored) / len(scored),
                "evidence_share": statistics.fmean(len(row[arm]) / len(row["evidence"]) for row in scored)}
        for name in ("characters", "session_characters", "recall_characters", "history_characters",
                     "history_messages", "persona_characters", "mood_characters", "relationship_characters"):
            entry["mean_" + name] = statistics.fmean(row[name] for row in items)
        summary[state] = entry
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    if sys.argv[1:] == ["--summarize"]:
        summarize([json.loads(line) for line in (OUT / "rows.jsonl").read_text().splitlines()])
    else:
        main()
