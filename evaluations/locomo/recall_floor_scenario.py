"""The busy-week scenario worlds (``tests/resume_correction_world.py``) under the candidate rules of ``recall_floor.py``.

Builds a world exactly as the scenario tests do (its own service process, on the scenario clock), but stops before
day 8 is recorded: the three day-8 wordings are only received, as in the tests, and that is the "before" capture.
The service is then run in this process (no recall worker pool) on the same installation, so the scores the host
never sees can be read, and each wording is received again in a new session under each rule. No model call; no
source file is changed. Needs MEMBRAIN_TEST_EMBEDDING_MODEL for the worlds with the model.

    python recall_floor_scenario.py OUT_DIR lazy_busy_keywords,lazy_busy,diligent_busy rule[,rule...]
"""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

WORLDS = {"lazy_busy_keywords": ("lazy", False), "lazy_busy": ("lazy", True), "diligent_busy": ("diligent", True)}


class Factory:
    def __init__(self, root: Path):
        self.root = root

    def mktemp(self, name):
        path = self.root / name
        path.mkdir(parents=True)
        return path


def summarize(world_module, text):
    block = world_module.block(text, "membrain-memory")
    lines = [line for line in block.splitlines() if line.startswith("- [")]
    filler = [line for line in lines if "(round " in line or "Here is a first pass on that (" in line]
    return {"recall_characters": len(block), "lines": len(lines), "filler_lines": len(filler),
            "filler_characters": sum(len(line) + 1 for line in filler),
            "correction": world_module.CORRECTION in block, "decision": world_module.DECISION in block,
            "other_lines": [line[:110] for line in lines if line not in filler]}


def main():
    import resume_correction_world as scenario
    import uvicorn
    from recall_floor import (
        CAPTURE,
        Context,
        _brain_terms,
        _install_service_probes,
        _provenance,
        install_follow_switch,
        rule_function,
    )

    from membrain import desktop, embedded_database, evaluation_clock, host, plugin
    from membrain.api import create_app
    from membrain.local_profile import load_profile

    out = Path(sys.argv[1])
    worlds = sys.argv[2].split(",")
    rules = ["none", *[rule for rule in sys.argv[3].split(",") if rule != "none"]]
    results = {}

    def day8_received_only(self):
        captures = self.captures.setdefault("day8", {})
        for key in ("dev_machine", "chinese", "finish"):
            session = f"tidepool-day8-{key}"
            opening = plugin.session_start({"session_id": session}, self.directory)
            prompt = plugin.user_prompt({"session_id": session, "prompt": scenario.PROMPTS[key], "prompt_id": "t0"},
                                        self.directory)
            captures[key] = {"session_start": opening, "user_prompt": prompt}

    scenario.World.day8 = day8_received_only
    _install_service_probes()
    install_follow_switch()
    for name in worlds:
        kind, model = WORLDS[name]
        with scenario.built_world(Factory(out / "worlds"), kind, busy=True, model=model) as world:
            directory = world.directory
            before = copy.deepcopy(world.captures["day8"])
        # The world's own service is stopped now. Run it again in this process, at the same scenario time.
        os.environ[evaluation_clock.ENV] = str(directory / evaluation_clock.CLOCK)
        evaluation_clock.enable(directory)
        profile = load_profile(directory)
        desktop._prepare_database(profile)
        settings = dataclasses.replace(profile.settings(), recall_processes=0)
        server = uvicorn.Server(uvicorn.Config(create_app(settings), host="127.0.0.1", port=profile.api_port,
                                               log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        status, original_recall = desktop.status, host.recall
        desktop.status = lambda directory=None: {"ready": True, "state": "ready"}
        state = {}
        try:
            while not server.started:
                time.sleep(0.1)
            with host.ready_client(directory) as client:
                texts, frequencies = _brain_terms(client)

            def recall(client, query, cues=(), **options):
                CAPTURE.clear()
                response = original_recall(client, query, cues, **options)
                state["last"] = (copy.deepcopy(response), Context(" ".join([query, *cues]), CAPTURE, frequencies,
                                                                 len(texts)))
                if state.get("rule", "none") != "none" and not options.get("deliberate"):
                    context = Context(" ".join([query, *cues]), CAPTURE, frequencies, len(texts))
                    override = rule_function(state["rule"])((response.get("result") or {}).get("items", []), context)
                    for limit_name, limit in (override or {}).items():
                        setattr(host, limit_name, limit)
                return response

            host.recall = recall
            world_result = {"before_subprocess_service": {key: summarize(scenario, value["user_prompt"])
                                                          for key, value in before.items()}}
            for rule in rules:
                state["rule"] = rule
                world_result[rule] = {}
                for key in ("dev_machine", "chinese", "finish"):
                    session = f"tidepool-day8-{key}-{rule.replace(':', '-').replace('+', '-')}"
                    plugin.session_start({"session_id": session}, directory)
                    saved = (host.VECTOR_ONLY_STATEMENTS, host.MAX_MESSAGES)
                    try:
                        prompt = plugin.user_prompt({"session_id": session, "prompt": scenario.PROMPTS[key],
                                                     "prompt_id": "t0"}, directory)
                    finally:
                        host.VECTOR_ONLY_STATEMENTS, host.MAX_MESSAGES = saved
                        host.FOLLOW_ONLY = None
                    world_result[rule][key] = summarize(scenario, prompt)
                    world_result[rule][key]["text"] = scenario.block(prompt, "membrain-memory")
                    if rule == "none" and "last" in state:  # What the host's selection was offered, with scores.
                        response, context = state.pop("last")
                        offered = _provenance(response, context, session)
                        world_result[rule][key]["offered"] = [
                            {**{name: value for name, value in entry.items() if name not in ("keyword", "cue")},
                             "text": texts.get(event, "")[:90]}
                            for event, entry in sorted(offered.items(), key=lambda pair: pair[1]["rank"])]
                        world_result[rule][key]["top_similarity"] = context.top_similarity
                    state.pop("last", None)
            # The deliberate search, which no rule touches.
            state["rule"] = "none"
            client, server_tools, _schemas, _instructions = world.memory.tools()
            try:
                world_result["memory_recall"] = {query: summarize(scenario, (scenario.call(
                    server_tools, "memory_recall", {"query": query}) or {}).get("context"))
                    for query in scenario.QUERIES}
            finally:
                client.close()
        finally:
            host.recall, desktop.status = original_recall, status
            server.should_exit = True
            thread.join(timeout=30)
            embedded_database.stop(profile)
            evaluation_clock.disable()
            os.environ.pop(evaluation_clock.ENV, None)
        results[name] = world_result
        (out / "scenario-results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(name, "done", flush=True)


if __name__ == "__main__":
    main()
