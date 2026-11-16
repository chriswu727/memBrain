"""The C5 harness prerequisites (no model call, no network): tools, the session clock, page actions, the reference
arm's world, and the stubs used by the zero-network dry run."""
import asyncio
import datetime
import hashlib
import importlib.util
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from membrain import embedded_database, evaluation_clock, host
from membrain.client import MemoryClient
from membrain.notes import save_note

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load("c5_harness", ROOT / "evaluations" / "c5-harness.py")
practice = _load("c5_practice", ROOT / "evaluations" / "c5-practice-scenario.py")


@pytest.fixture(autouse=True)
def clean_clock(monkeypatch):
    # Register restoration even when the variable was absent before the harness writes it directly.
    monkeypatch.setenv(evaluation_clock.ENV, "")
    yield
    evaluation_clock.disable()


# Scenario format ------------------------------------------------------------------------------------------------

def test_every_session_states_a_date_and_a_time():
    assert harness.session_start("Today is Tuesday, March 3, 21:00. Hi") == datetime.datetime(
        2026, 3, 3, 21, 0, tzinfo=datetime.UTC)
    assert harness.session_start("今天是3月14日 09:30，你好") == datetime.datetime(2026, 3, 14, 9, 30,
                                                                             tzinfo=datetime.UTC)
    with pytest.raises(ValueError, match="no scenario time"):
        harness.session_start("Today is Tuesday, March 3. Hi")
    with pytest.raises(ValueError, match="no scenario date"):
        harness.session_start("Hi there, 21:00")


def test_live_transport_requires_the_shared_billing_ledger_before_network(monkeypatch):
    monkeypatch.delenv("C5_BILLING_LEDGER", raising=False)
    with pytest.raises(SystemExit, match="shared C5_BILLING_LEDGER"):
        harness.billing_transport()


def test_every_arm_checks_a_failed_billing_ledger(monkeypatch):
    class Stopped:
        def check(self):
            raise RuntimeError("billing stopped")

    monkeypatch.setattr(harness, "BILLING", Stopped())
    with pytest.raises(RuntimeError, match="billing stopped"):
        harness.check_billing()


@pytest.mark.parametrize("fails", [False, True])
def test_term_stops_the_shared_attempt_and_unwinds_for_service_cleanup(monkeypatch, fails):
    calls = []

    class Guard:
        def stop(self, reason):
            calls.append(reason)
            if fails:
                raise OSError("offline stop fixture")

    monkeypatch.setattr(harness, "BILLING", Guard())
    with pytest.raises(SystemExit) as error:
        harness.interrupted(harness.signal.SIGTERM, None)
    assert error.value.code == 143 and calls == ["arm_interrupted"]


def test_a_billing_stop_is_not_retried_by_the_host(monkeypatch):
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")
    calls = []

    def refused(request):
        calls.append(request)
        raise RuntimeError("billing stopped")

    host_model = harness.Host(cap=5, transport=httpx.MockTransport(refused))
    try:
        with pytest.raises(RuntimeError, match="billing stopped"):
            host_model.call([{"role": "user", "content": "fixture"}])
    finally:
        host_model.client.close()
    assert len(calls) == 1 and host_model.calls == 1


@pytest.mark.parametrize("name", ["MEMORY_COGNITION_API_KEY", "MEMORY_EMBEDDING_API_KEY", "MEMBRAIN_EXTRACT_MODEL",
                                "MEMBRAIN_EXTRACT_KEY", "MEMBRAIN_UPSTREAM_KEY", "OPENAI_API_KEY"])
def test_live_memory_refuses_other_providers_before_creating_a_service(tmp_path, monkeypatch, name):
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setenv(name, "unrelated-fixture")
    directory = tmp_path / "not-created"
    with pytest.raises(SystemExit, match="unrelated provider"):
        harness.Memory(directory, None, None, datetime.datetime(2026, 3, 2, tzinfo=datetime.UTC))
    assert not directory.exists()


def test_local_service_start_has_no_provider_key_and_restores_the_parent_environment(monkeypatch):
    import os

    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-key")
    monkeypatch.setenv("MEMORY_COGNITION_API_KEY", "other-fixture-key")
    monkeypatch.setenv("HF_TOKEN", "private-fixture-token")
    monkeypatch.setenv("MEMBRAIN_EVALUATION_CLOCK", "/disposable/clock.json")
    before = dict(os.environ)
    with harness.local_environment():
        assert all(name not in os.environ for name in ["DEEPSEEK_API_KEY", "MEMORY_COGNITION_API_KEY", "HF_TOKEN"])
        assert os.environ["MEMBRAIN_EVALUATION_CLOCK"] == "/disposable/clock.json"
        assert os.environ["PYTHON_DOTENV_DISABLED"] == "1"
        assert os.environ["PATH"] == before["PATH"]
    assert dict(os.environ) == before


def test_the_practice_scenario_is_valid_and_public(monkeypatch):
    assert "practice" in Path(practice.__file__).name
    starts = [harness.session_start(turns[0]) for _, turns in practice.SESSIONS_LONG]
    assert starts == sorted(starts) and (starts[-1] - starts[0]).days >= 9
    monkeypatch.setattr(harness, "STUB", True)
    assert harness.check_actions(practice) == practice.PAGE_ACTIONS
    assert {(session, turn) for session, turn, *_ in practice.EXPECT} <= {
        (session, turn) for session, turns in practice.SESSIONS_LONG for turn in range(len(turns))}


def test_page_actions_are_checked_before_any_model_call(monkeypatch):
    class Scenario:
        SESSIONS_LONG = [("s1", ["Today is Monday, March 2, 20:00. Hi", "Two"]),
                         ("s2", ["Today is Tuesday, March 3, 20:00. Hi", "Four"])]
        PAGE_ACTIONS = [("s1", 0, {"do": "rename_everything"})]

    monkeypatch.setattr(harness, "STUB", True)
    with pytest.raises(SystemExit, match="bad page action"):
        harness.check_actions(Scenario)
    # Selecting a record by text the host wrote is not in the vocabulary; nor is the old proposal match by text.
    for action in ({"do": "accept_persona_proposal", "match": "casual"}, {"do": "delete_note", "contains": "x"},
                   {"do": "delete_feeling", "label": "x"}, {"do": "reset_persona"}, {"do": "restore_persona",
                                                                                     "version": 1}):
        Scenario.PAGE_ACTIONS = [("s2", 0, action)]
        with pytest.raises(SystemExit, match="bad page action"):
            harness.check_actions(Scenario)
    for action in ({"do": "clear_feelings", "label": "x"}, {"do": "accept_proposal", "match": "casual"},
                   {"do": "accept_proposal", "origin": "the agent"}, {"do": "accept_proposal", "position": 0},
                   {"do": "delete_message", "session": "s2", "turn": 0},  # At the action's own position.
                   {"do": "delete_note_from", "session": "s9", "turn": 0},
                   {"do": "cap_familiarity", "level": "close"}, {"do": "switch_persona", "preset": "ENFP-ish"},
                   {"do": "remove_boundary", "topic": "work"}):  # No earlier page action added it.
        Scenario.PAGE_ACTIONS = [("s2", 0, action)]
        with pytest.raises(SystemExit, match="bad page action"):
            harness.check_actions(Scenario)
    Scenario.PAGE_ACTIONS = [("s2", 1, {"do": "remove_boundary", "topic": "Work "}),
                             ("s2", 0, {"do": "add_boundary", "topic": "work", "aliases": ["deadlines"]}),
                             ("s2", 0, {"do": "delete_feeling_from", "session": "s1", "turn": 1}),
                             ("s2", 1, {"do": "accept_proposal", "origin": "host", "position": 2}),
                             ("s2", 1, {"do": "switch_persona", "preset": "random"})]
    assert harness.check_actions(Scenario) == Scenario.PAGE_ACTIONS  # Applied in position order: add, then remove.
    assert harness.application_order(Scenario.PAGE_ACTIONS, Scenario.SESSIONS_LONG) == [1, 2, 0, 3, 4]
    Scenario.PAGE_ACTIONS = [("s2", 0, {"do": "accept_proposal"})]
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "proposals_supported", lambda: False)
    with pytest.raises(SystemExit, match="no persona proposals"):  # A live run never silently skips an action.
        harness.check_actions(Scenario)


# Tools ----------------------------------------------------------------------------------------------------------

def test_arm_p_offers_every_tool_the_plugins_server_lists_with_its_instructions(tmp_path, monkeypatch):
    directory = tmp_path / "installation"
    host.ensure_installation(directory)
    client = MemoryClient("http://127.0.0.1:9", "key", brain_id="brain")
    from membrain.mcp_server import create_server

    listed = {tool.name: tool for tool in asyncio.run(create_server(client, directory=directory).list_tools())}
    memory = SimpleNamespace(directory=directory, host=host, client=lambda: client)
    returned, _server, schemas, instructions = harness.Memory.tools(memory)
    offered = [schema["function"]["name"] for schema in schemas]
    assert returned is client and offered == list(listed)  # Every tool, in the server's own order.
    assert {"memory_boundary", "memory_consolidate", "memory_persona", "memory_manner_feedback"} <= set(offered)
    assert instructions == host.server_instructions() and "memory_consolidate" in instructions
    schema = {item["function"]["name"]: item["function"] for item in schemas}
    assert schema["memory_note"]["description"] == listed["memory_note"].description
    note = schema["memory_note"]["parameters"]["properties"]
    assert {"affect", "shared", "recording_capture"} <= set(note)
    assert schema["memory_boundary"]["parameters"]["required"] == ["topic"]


# The reference arm ----------------------------------------------------------------------------------------------

def _p_rows(tmp_path, rows, scenario="zq"):
    run = tmp_path / "k-P"
    run.mkdir(parents=True, exist_ok=True)
    (run / f"results_{scenario}_P.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return tmp_path / "k-F"


def test_f_is_given_ps_persona_block_of_the_same_turn_whatever_changed_it(tmp_path, monkeypatch):
    from membrain import persona_presets
    from membrain.persona import render_persona

    monkeypatch.setattr(harness, "BILLING", None)
    first = render_persona({"version": 1, "card": persona_presets.card("istp")})
    switched = render_persona({"version": 2, "card": persona_presets.card("enfp")})  # e.g. the host's own switch
    out = _p_rows(tmp_path, [
        {"session": "s1", "turn": 0, "persona_block": first, "persona_turn": harness.persona_turn(1, first)},
        {"session": "s1", "turn": 1, "persona_block": switched, "persona_turn": harness.persona_turn(2, switched)},
        {"session": "s2", "turn": 0, "persona_block": "", "persona_turn": harness.persona_turn(0, "")}])
    cache = {}
    assert harness.p_persona(out, "zq", "s1", 0, cache) == (first, harness.persona_turn(1, first))
    block, turn = harness.p_persona(out, "zq", "s1", 1, cache)
    assert block == switched and turn == {"format": 1, "version": 2,
                                          "sha256": hashlib.sha256(switched.encode()).hexdigest()}
    assert harness.p_persona(out, "zq", "s2", 0, cache) == ("", {"format": 1, "version": 0, "sha256": None})
    with pytest.raises(SystemExit, match="never recorded the persona of a turn"):
        harness.p_persona(out, "zq", "s2", 1, cache, timeout=0.05)
    # A block that is not the one its identity names is refused, never passed on to F.
    out = _p_rows(tmp_path / "other", [{"session": "s1", "turn": 0, "persona_block": switched,
                                        "persona_turn": harness.persona_turn(1, first)}])
    with pytest.raises(SystemExit, match="does not match its identity"):
        harness.p_persona(out, "zq", "s1", 0, {})
    assert not hasattr(harness.Reference(), "block")  # F has no persona of its own.


def test_fs_page_line_lists_only_page_settings_in_a_fixed_format():
    import datetime as dt

    reference = harness.Reference()
    assert reference.page_line() is None
    tenth, eleventh = dt.date(2026, 3, 10), dt.date(2026, 3, 11)
    done = {"status": "done"}
    reference.apply({"do": "add_boundary", "topic": "work  deadlines", "aliases": ["deadlines"]}, done, tenth)
    reference.apply({"do": "add_boundary", "topic": "Tom"}, done, tenth)
    reference.apply({"do": "clear_feelings"}, done, tenth)
    reference.apply({"do": "set_support_style", "text": "Listen first."}, done, tenth)
    reference.apply({"do": "cap_familiarity", "level": "getting_to_know"}, done, tenth)
    reference.apply({"do": "pin_mood", "pinned": True}, done, tenth)
    reference.apply({"do": "reset_mood"}, done, tenth)  # Not a setting the line names.
    assert reference.page_line() == (
        'Memory page settings the user chose (not part of the conversation above): topics not to bring up: '
        '"work deadlines" (also "deadlines"), "Tom"; feelings cleared on 2026-03-10; support style: "Listen first."; '
        'familiarity limited to getting to know; simulated mood held at its baseline.')
    reference.apply({"do": "remove_boundary", "topic": "tom"}, done, tenth)
    reference.apply({"do": "reset_relationship"}, done, eleventh)  # Erases boundaries, support style and cap.
    assert reference.page_line() == (
        "Memory page settings the user chose (not part of the conversation above): relationship reset on 2026-03-11; "
        "feelings cleared on 2026-03-10; simulated mood held at its baseline.")
    # An action P found no target for changes nothing in F either.
    assert reference.apply({"do": "remove_boundary", "topic": "x"}, {"status": "not_applicable",
                                                                       "reason": "boundary_not_present"}) == {
        "not_applicable": "boundary_not_present"}
    reference.apply({"do": "pin_mood", "pinned": False}, done, eleventh)
    reference.apply({"do": "set_support_style", "text": ""}, done, eleventh)
    assert reference.page_line().endswith("relationship reset on 2026-03-11; feelings cleared on 2026-03-10.")


@pytest.mark.parametrize("kind", ["clear_feelings", "delete_feeling_from", "delete_note_from", "reset_mood",
                                  "pin_mood", "reset_relationship", "add_boundary", "remove_boundary",
                                  "set_support_style", "cap_familiarity", "switch_persona", "set_persona",
                                  "delete_persona_history", "accept_proposal", "reject_proposal"])
def test_only_a_deleted_message_leaves_fs_history(kind):
    reference = harness.Reference()
    reference.history = [(("s1", 0, "user"), {"role": "user", "content": "a"}),
                         (("s1", 0, "assistant"), {"role": "assistant", "content": "b"}),
                         (("s1", 1, "user"), {"role": "user", "content": "c"})]
    reference.apply({"do": kind, "session": "s1", "turn": 0, "topic": "x", "text": "x", "level": "new",
                     "preset": "random", "card": {}}, {"status": "done"})
    assert len(reference.history) == 3
    # F drops exactly what the product removed in P: here the message and the reply that answered it.
    removed = [["s1", 0, "assistant"], ["s1", 0, "user"]]
    result = reference.apply({"do": "delete_message", "session": "s1", "turn": 0, "role": "user", "removed": removed})
    assert result == {"deleted": 2, "removed": removed}
    assert [message["content"] for _, message in reference.history] == ["c"]
    assert reference.contains(removed) == 0


def test_a_deletion_during_the_session_in_progress_never_reaches_fs_later_history():
    reference = harness.Reference()
    current = [(("s2", 0, "user"), {"role": "user", "content": "keep"}),
               (("s2", 0, "assistant"), {"role": "assistant", "content": "kept reply"}),
               (("s2", 1, "user"), {"role": "user", "content": "erased later in s2"})]
    # A page action before s2's turn 2 deletes turn 1: the running transcript keeps it, the history must not.
    reference.apply({"do": "delete_message", "session": "s2", "turn": 1, "role": "user",
                     "removed": [["s2", 1, "user"]]})
    reference.end_session(current)
    assert [message["content"] for _, message in reference.history] == ["keep", "kept reply"]
    assert reference.contains([["s2", 1, "user"]]) == 0


def test_f_waits_for_and_mirrors_ps_recorded_outcome_of_each_action(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "BILLING", None)
    action = {"do": "delete_message", "session": "s1", "turn": 0, "role": "user"}
    unrecorded = {"do": "delete_message", "session": "s1", "turn": 1, "role": "user"}
    (tmp_path / "k-P").mkdir()

    def record(index, entry, status, **extra):
        return {"format": 2, "index": index, "action": entry["do"], "detail": harness.action_detail(entry),
                "status": status, **extra}

    (tmp_path / "k-P" / "page-actions.jsonl").write_text("".join(json.dumps(entry) + "\n" for entry in (
        record(0, action, "done", result={"deleted": 1, "removed": [["s1", 0, "user"]]}),
        record(1, unrecorded, "not_applicable", reason="message_not_recorded", result={}))))
    out = tmp_path / "k-F"
    assert harness.p_page_action(out, 0, action)["result"]["removed"] == [["s1", 0, "user"]]
    assert harness.p_page_action(out, 1, unrecorded)["reason"] == "message_not_recorded"
    with pytest.raises(SystemExit, match="not this scenario's"):  # Another action at that index.
        harness.p_page_action(out, 1, action)
    with pytest.raises(SystemExit, match="never recorded"):
        harness.p_page_action(out, 2, action, timeout=0.1)
    (tmp_path / "k-P" / "page-actions.jsonl").write_text(json.dumps(record(0, action, "failed", result={
        "failed": "x"})) + "\n")
    with pytest.raises(SystemExit, match="could not apply"):
        harness.p_page_action(out, 0, action)
    # F's world: the deletion P made, and nothing for the one that found no message.
    reference = harness.Reference()
    reference.history = [(("s1", 0, "user"), {"role": "user", "content": "a"})]
    assert reference.apply({**unrecorded, "removed": []}, {"status": "not_applicable",
                                                           "reason": "message_not_recorded"}) == {
        "not_applicable": "message_not_recorded"}
    assert reference.apply({**action, "removed": [["s1", 0, "user"]]}, {"status": "done"})["deleted"] == 1


# Stubs ----------------------------------------------------------------------------------------------------------

def test_the_stub_host_calls_scripted_tools_with_the_current_source_then_replies(monkeypatch):
    monkeypatch.setattr(harness, "STUB", True)  # No key is read.
    stub = harness.StubHost({("s1", 0): [{"tool": "memory_note", "arguments": {"text": "x"}, "source": "current"},
                                         {"tool": "memory_pause", "arguments": {}}]})
    stub.key = ("s1", 0)
    host_model = harness.Host(cap=5, transport=httpx.MockTransport(stub))
    source = '<membrain-source>\nWhen saving a note ..., pass source_messages=[{"source_event_key": "k"}]. This recording_capture="abc.def".'
    tools = [{"type": "function", "function": {"name": "memory_note"}}]
    message, _ = host_model.call([{"role": "system", "content": "<membrain-persona version=\"1\">"},
                                  {"role": "user", "content": source}], tools)
    (call,) = message["tool_calls"]  # memory_pause was not offered, so it is not called.
    assert json.loads(call["function"]["arguments"]) == {
        "text": "x", "source_messages": [{"source_event_key": "k"}], "recording_capture": "abc.def"}
    reply, usage = host_model.call([{"role": "system", "content": "<membrain-persona version=\"1\">"},
                                    {"role": "user", "content": "hi"}, message,
                                    {"role": "tool", "tool_call_id": "call-0", "content": "{}"}])
    assert "membrain-persona" in reply["content"] and usage["total_tokens"] > 0


def test_the_stub_host_chains_calls_within_a_turn_and_across_turns(monkeypatch):
    monkeypatch.setattr(harness, "STUB", True)
    script = {("s1", 0): [{"tool": "memory_persona", "arguments": {"action": "list"}},
                          {"tool": "memory_persona", "round": 1, "arguments": {
                              "action": "switch", "preset": {"$result": ["s1", 0, 0, "first"]}}}],
              ("s2", 0): [{"tool": "memory_persona", "arguments": {
                  "action": "confirm", "proposal_id": {"$result": ["s1", 1, 0, "proposal_id"]}}}],
              ("s1", 1): [{"tool": "memory_persona", "arguments": {"action": "propose", "changes": {}}}],
              ("s3", 0): [{"tool": "memory_persona", "arguments": {
                  "action": "decline", "proposal_id": {"$result": ["s9", 0, 0, "proposal_id"]}}}]}
    stub = harness.StubHost(script)
    model = harness.Host(cap=20, transport=httpx.MockTransport(stub))
    tools = [{"type": "function", "function": {"name": "memory_persona", "parameters": {"properties": {}}}}]
    answers = {"list": {"first": "intj"}, "propose": {"proposal_id": "zq-proposal-1"}}

    def turn(key):
        stub.key = key
        messages = [{"role": "system", "content": "x"}, {"role": "user", "content": "hi"}]
        made = []
        while True:
            message, _ = model.call(messages, tools)
            if not message.get("tool_calls"):
                return made
            messages.append(message)
            for call in message["tool_calls"]:
                arguments = json.loads(call["function"]["arguments"])
                made.append(arguments)
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps(answers.get(arguments["action"], {}))})

    # Round 1 of the same turn uses round 0's result; a later turn (another session) uses an earlier turn's.
    assert turn(("s1", 0)) == [{"action": "list"}, {"action": "switch", "preset": "intj"}]
    assert turn(("s1", 1)) == [{"action": "propose", "changes": {}}]
    assert turn(("s2", 0)) == [{"action": "confirm", "proposal_id": "zq-proposal-1"}]
    assert turn(("s3", 0)) == [{"action": "decline"}]  # No such result: the argument is left out.


def test_the_dry_run_refuses_any_connection_off_this_machine(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "STUB", True)  # A live arm would stop on the event instead (hardening U2).
    original = socket.socket.connect
    monkeypatch.setattr(socket.socket, "connect", original)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")
    harness.refuse_network(tmp_path)
    with socket.socket() as connection, pytest.raises(OSError, match="refused"):
        connection.connect(("192.0.2.1", 443))
    assert "HTTPS_PROXY" not in __import__("os").environ
    assert json.loads((tmp_path / "harness-events.jsonl").read_text())["kind"] == "network_refused"


# Page actions on a real service ----------------------------------------------------------------------------------

@pytest.fixture
def memory(tmp_path, monkeypatch):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setattr(harness, "STUB", True)
    start = datetime.datetime(2026, 3, 2, 20, 0, tzinfo=datetime.UTC)
    monkeypatch.setenv(evaluation_clock.ENV, "")  # The harness sets it in os.environ; this restores it after.
    try:
        yield harness.Memory(tmp_path / "brain", None, None, start)
    finally:
        service_log = tmp_path / "brain" / "service.log"
        if service_log.exists():
            print("Scenario service lifecycle:\n" + service_log.read_text(encoding="utf-8"))
        harness.stop_started()


def test_page_actions_go_through_the_api_and_remove_only_what_they_name(memory):
    directory = memory.directory
    assert memory.now().startswith("2026-03-02T20:0")
    host.prompt_context(directory, "s1", "I'm nervous about Thursday's review.", turn_id="t0", include_source=True)
    host.finish_turn(directory, "s1", "Good luck.", turn_id="t0")
    memory.record_turn("s1", 0)
    with memory.client() as client:
        message = next(item for item in client.timeline(roles=("user",))["items"] if "nervous" in item["text"])
        save_note(client, "Review on 2026-03-05.", kind="plan", status="scheduled", occurs_at="2026-03-05",
                  source_event_ids=[message["event_id"]],
                  affect={"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported"})
        save_note(client, "A silly pun contest together.", kind="milestone", shared=True)
        client.add_boundary("Tom")
        before = harness.world(client)
    assert before["feelings"] == 1 and before["shared_moments"] == 1 and before["boundaries"] == ["Tom"]
    assert before["mood"] == "concerned"
    turns = {("s1", 0, "user"): "I'm nervous about Thursday's review.", ("s1", 0, "assistant"): "Good luck."}

    def act(action):
        with memory.client() as client:
            ahead = harness.world(client)
        result = harness.apply_page_action(memory, action, turns)
        with memory.client() as client:
            return ahead, result, harness.world(client)

    ahead, result, after = act({"do": "reset_mood"})
    assert after["mood"] == "baseline" and {k: v for k, v in after.items() if k != "mood"} == {
        k: v for k, v in ahead.items() if k != "mood"}
    ahead, result, after = act({"do": "reset_relationship"})
    assert after["boundaries"] == [] and after["shared_moments"] == 0 and after["notes"] == ahead["notes"] - 1
    assert (after["messages"], after["feelings"]) == (ahead["messages"], ahead["feelings"])
    ahead, result, after = act({"do": "delete_message", "session": "s1", "turn": 0})
    assert result["deleted"] == 1 and ["s1", 0, "user"] in result["removed"]
    assert after["messages"] == ahead["messages"] - len(result["removed"])
    assert after["feelings"] == 0 and after["notes"] == ahead["notes"] - 1  # The note and feeling drawn from it.
    # The relationship reset erased the boundary: removing it finds nothing, which is not a fault.
    ahead, result, after = act({"do": "remove_boundary", "topic": "tom"})
    assert result == {"not_applicable": "boundary_not_present"} and after == ahead
    assert harness.page_status(result) == ("not_applicable", "boundary_not_present")


def test_page_actions_select_records_by_source_position_and_find_no_target_without_failing(memory):
    """Notes and feelings by the scenario position of their source message, never by their text; settings by the
    scenario's own words; a missing target is not applicable, with its reason code."""
    directory = memory.directory
    for turn, (text, reply) in enumerate((("I feel lost in this new city.", "That sounds hard."),
                                          ("My sister Ana visits on the 14th.", "Lovely!"))):
        host.prompt_context(directory, "s1", text, turn_id=f"t{turn}", include_source=True)
        host.finish_turn(directory, "s1", reply, turn_id=f"t{turn}")
        memory.record_turn("s1", turn)
    memory.record_turn("s1", 2, recorded=False)  # A turn the host's pause left unrecorded.
    first, second = (next(event for event, at in memory.positions.items() if at == ("s1", turn, "user"))
                     for turn in (0, 1))
    with memory.client() as client:
        save_note(client, "zq-planted note about the move.", kind="milestone", source_event_ids=[first],
                  affect={"label": "zq-planted-label", "valence": -1, "intensity": 1, "basis": "inferred"})
        save_note(client, "Ana visits on 2026-03-14.", kind="plan", source_event_ids=[second])
    source = {"session": "s1", "turn": 0}

    def act(action, **page):
        with memory.client() as client:
            ahead = harness.world(client)
        result = harness.apply_page_action(memory, action, page)
        with memory.client() as client:
            return ahead, result, harness.world(client)

    ahead, result, after = act({"do": "delete_feeling_from", **source})
    assert result == {"deleted": 1} and (after["feelings"], after["notes"]) == (0, ahead["notes"])
    assert act({"do": "delete_feeling_from", **source})[1] == {"not_applicable": "no_feeling_from_message"}
    ahead, result, after = act({"do": "delete_note_from", **source})
    assert result == {"deleted": 1} and after["notes"] == ahead["notes"] - 1 and after["messages"] == ahead["messages"]
    assert act({"do": "delete_note_from", **source})[1] == {"not_applicable": "no_note_from_message"}
    assert act({"do": "delete_note_from", "session": "s1", "turn": 2})[1] == {
        "not_applicable": "message_not_recorded"}
    assert act({"do": "delete_message", "session": "s1", "turn": 2})[1] == {"not_applicable": "message_not_recorded"}
    ahead, result, after = act({"do": "delete_message", "session": "s1", "turn": 1})
    assert result["deleted"] == 1 and ["s1", 1, "user"] in result["removed"] and after["notes"] == ahead["notes"] - 1
    assert act({"do": "delete_message", "session": "s1", "turn": 1})[1] == {"not_applicable": "message_already_removed"}
    ahead, result, after = act({"do": "set_support_style", "text": "Listen first."})
    assert after["support_style"] is True and harness.page_status(result) == ("done", None)
    ahead, result, after = act({"do": "cap_familiarity", "level": "new"})
    assert after["familiarity_cap"] == "new"
    ahead, result, after = act({"do": "pin_mood", "pinned": True})
    assert after["mood_pinned"] is True and after["mood"] == "baseline"
    assert act({"do": "accept_proposal"})[1] == {"not_applicable": "no_open_proposal", "open": 0}
    # A page "pick another type at random": the harness's seeded pick, the same for the same seed and index.
    with memory.client() as client:
        before = client.persona_presets()["current"]
    now = before["preset"]["id"] if before["kind"] == "preset" else None
    ahead, result, after = act({"do": "switch_persona", "preset": "random"}, seed="zq-seed", index=4)
    assert result["seeded_random"] is True and result["preset"] == harness.seeded_random_preset("zq-seed", 4, now)
    assert result["preset"] != now and after["persona_version"] == ahead["persona_version"] + 1
    ahead, result, after = act({"do": "switch_persona", "preset": "istj"})
    assert (result["preset"], result["seeded_random"]) == ("istj", False)
    ahead, result, after = act({"do": "set_persona", "card": {"name": "Juniper", "traits": ["warm"]}})
    assert after["persona_version"] == ahead["persona_version"] + 1
    with memory.client() as client:
        assert client.persona()["card"]["name"] == "Juniper" and client.persona()["made_by"] == "user"


class _Proposals:
    """A client listing open suggestions in the page's order (open first, newest first)."""

    def __init__(self, entries):
        self.entries, self.decisions = entries, []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def persona_proposals(self):
        return {"proposals": self.entries}

    def accept_persona_proposal(self, ident):
        self.decisions.append(("accept", ident))
        return {"persona": {"version": 3}}

    def reject_persona_proposal(self, ident):
        self.decisions.append(("reject", ident))
        return {"version": None}


@pytest.mark.parametrize("decision", ["accept", "reject"])
def test_a_suggestion_is_decided_by_origin_and_order_never_by_text(decision):
    entries = [{"id": "p-host", "kind": "host", "status": "open", "label": "zq casual words"},
               {"id": "p-new", "kind": "more_playful", "status": "open", "label": "more casual"},
               {"id": "p-old", "kind": "less_formal", "status": "open", "label": "more casual"},
               {"id": "p-done", "kind": "shorter", "status": "rejected"}]
    for action, chosen in (({}, "p-host"), ({"origin": "feedback"}, "p-new"),
                           ({"origin": "feedback", "position": 2}, "p-old"), ({"origin": "host"}, "p-host")):
        client = _Proposals(entries)
        result = harness.apply_page_action(SimpleNamespace(client=lambda: client),
                                           {"do": f"{decision}_proposal", **action})
        assert client.decisions == [(decision, chosen)] and result["proposal"] == chosen
    for action in ({"origin": "feedback", "position": 3}, {"origin": "host", "position": 2}):
        client = _Proposals(entries)
        result = harness.apply_page_action(SimpleNamespace(client=lambda: client),
                                           {"do": f"{decision}_proposal", **action})
        assert result["not_applicable"] == "no_open_proposal" and client.decisions == []  # A closed one never.


def test_a_service_refusal_or_an_exception_is_a_failure_with_a_code():
    request = httpx.Request("POST", "http://127.0.0.1/x")

    class Refusing(_Proposals):
        def persona_proposals(self):
            raise httpx.HTTPStatusError("no", request=request, response=httpx.Response(409, request=request))

    result = harness.apply_page_action(SimpleNamespace(client=lambda: Refusing([])), {"do": "accept_proposal"})
    assert harness.page_status(result) == ("failed", "service_refused") and result["status"] == 409

    class Raising(_Proposals):
        def persona_proposals(self):
            raise KeyError("zq-planted")

    result = harness.apply_page_action(SimpleNamespace(client=lambda: Raising([])), {"do": "accept_proposal"})
    assert harness.page_status(result) == ("failed", "exception") and "zq-planted" not in json.dumps(result)
    assert harness.page_status({"not_applicable": "zq-not-a-code"}) == ("failed", "not_found")


def test_the_seeded_random_pick_is_reproducible_uniform_in_kind_and_never_the_current_type():
    from membrain import persona_presets

    picks = {harness.seeded_random_preset("zq-attempt", index, "enfp") for index in range(200)}
    assert picks == set(persona_presets.IDS) - {"enfp"}  # Every other type can come, never the current one.
    assert harness.seeded_random_preset("zq-attempt", 3, None) == harness.seeded_random_preset("zq-attempt", 3, None)
    digest = hashlib.sha256(json.dumps(["switch_persona", "zq-attempt", 3], separators=(",", ":")).encode()).hexdigest()
    assert harness.seeded_random_preset("zq-attempt", 3, None) == persona_presets.IDS[int(digest, 16) % 16]


def test_the_index_wait_uses_the_runtimes_count_of_jobs_that_can_still_run(tmp_path, monkeypatch):
    # The listed jobs (the latest 100) show nothing runnable, but an older queued job is still pending.
    dashboard = {"jobs": [{"state": "completed"}, {"state": "superseded"}],
                 "status": {"pending_jobs": 1, "index_lag": 0}}

    class Client:
        def dashboard(self):
            return dashboard

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(harness, "STUB", True)  # A live arm would stop on the event instead (hardening U2).
    memory = object.__new__(harness.Memory)
    memory.host = SimpleNamespace(ready_client=lambda directory, user: Client())
    memory.directory, memory.user = tmp_path / "brain", "person"
    monkeypatch.setattr(harness.time, "sleep", lambda seconds: dashboard["status"].update(pending_jobs=0))
    memory.wait_until_indexed(timeout=30)
    assert not (tmp_path / "harness-events.jsonl").exists()
    dashboard["status"]["pending_jobs"] = 1
    monkeypatch.setattr(harness.time, "sleep", lambda seconds: None)
    memory.wait_until_indexed(timeout=0.05)
    assert "index_wait_timed_out" in (tmp_path / "harness-events.jsonl").read_text()


def test_a_deletion_finds_its_turn_by_identity_even_when_another_turn_says_the_same(memory):
    directory = memory.directory
    for session in ("s1", "s2"):
        host.prompt_context(directory, session, "Thanks.", turn_id="t0", include_source=True)
        host.finish_turn(directory, session, "You're welcome.", turn_id="t0")
        memory.record_turn(session, 0)
    result = harness.apply_page_action(memory, {"do": "delete_message", "session": "s2", "turn": 0}, {})
    assert result["deleted"] == 1 and "failed" not in result
    assert ["s2", 0, "user"] in result["removed"] and ["s1", 0, "user"] not in result["removed"]
    with memory.client() as client:
        left = [(memory.positions[item["event_id"]], item["text"]) for item in harness._messages(client).values()]
    assert (("s1", 0, "user"), "Thanks.") in left and all(position[0] == "s1" or position[2] == "assistant"
                                                          for position, _ in left)
    # A deletion of a turn whose messages were never identified fails instead of guessing by text.
    assert harness.apply_page_action(memory, {"do": "delete_message", "session": "s9", "turn": 0}, {}) == {
        "failed": "message not found"}


@pytest.mark.parametrize("pause_at", ["before", "during", "during_then_resume"])
def test_a_legitimately_unrecorded_turn_does_not_degrade_the_harness(memory, pause_at):
    if pause_at == "before":
        host.pause(memory.directory)
    host.prompt_context(memory.directory, "private", "A private practice turn.", turn_id="t0")
    if pause_at != "before":
        host.pause(memory.directory)
    if pause_at == "during_then_resume":
        host.resume(memory.directory)
    recorded = host.finish_turn(memory.directory, "private", "Understood.", turn_id="t0")
    assert recorded == []
    memory.record_turn("private", 0, recorded=bool(recorded))
    assert memory.positions == {} and not (memory.directory.parent / "harness-events.jsonl").exists()
    host.resume(memory.directory)
    host.prompt_context(memory.directory, "private", "Back on the record.", turn_id="t1")
    recorded = host.finish_turn(memory.directory, "private", "Welcome back.", turn_id="t1")
    assert len(recorded) == 2
    memory.record_turn("private", 1, recorded=bool(recorded))
    assert set(memory.positions.values()) == {("private", 1, "user"), ("private", 1, "assistant")}


def test_an_unrecorded_turn_cannot_silently_add_messages_to_memory(memory):
    host.prompt_context(memory.directory, "private", "A practice privacy error.", turn_id="t0")
    host.finish_turn(memory.directory, "private", "Understood.", turn_id="t0")
    memory.record_turn("private", 0, recorded=False)
    event = json.loads((memory.directory.parent / "harness-events.jsonl").read_text())
    assert event["kind"] == "unexpected_recording" and event["new_messages"] == 2
    assert "practice privacy error" not in json.dumps(event)


@pytest.mark.parametrize("code", [
    "database_initialization_failed", "native_adoption_blocked", "native_transition_authority",
    "evaluation_clock_refused", "port_conflict",
])
def test_permanent_local_start_errors_do_not_wait_ten_minutes(tmp_path, monkeypatch, code):
    from membrain import desktop, local_profile

    directory = tmp_path / "disposable"
    monkeypatch.setattr(harness, "STUB", True)
    monkeypatch.setattr(local_profile, "ensure_profile", lambda *args, **kwargs: None)
    monkeypatch.setattr(evaluation_clock, "mark_disposable", lambda *args: None)
    monkeypatch.setattr(evaluation_clock, "advance", lambda *args, **kwargs: None)
    monkeypatch.setattr(evaluation_clock, "enable", lambda *args: None)
    monkeypatch.setattr(host, "ensure_installation", lambda *args: None)
    error = desktop.DesktopError(code, "A permanent startup failure")
    def fail(*args):
        raise error
    monkeypatch.setattr(host, "start", fail)
    monkeypatch.setattr(desktop, "status", lambda *args: pytest.fail("Do not poll after a permanent failure"))
    monkeypatch.setattr(harness.time, "sleep", lambda *args: pytest.fail("Do not hide a permanent failure"))
    try:
        with pytest.raises(desktop.DesktopError) as raised:
            harness.Memory(directory, None, None, datetime.datetime(2026, 3, 2, tzinfo=datetime.UTC))
        assert raised.value is error
    finally:
        harness.STARTED.remove(directory)


def test_a_slow_local_start_can_still_finish_becoming_ready(tmp_path, monkeypatch):
    from membrain import desktop, local_profile

    directory = tmp_path / "disposable"
    directory_created = []
    def profile(*args, **kwargs):
        directory.mkdir()
        (directory / "service.log").write_text("evaluation_clock_enabled")
        directory_created.append(directory)
    monkeypatch.setattr(harness, "STUB", True)
    monkeypatch.setattr(local_profile, "ensure_profile", profile)
    monkeypatch.setattr(evaluation_clock, "mark_disposable", lambda *args: None)
    monkeypatch.setattr(evaluation_clock, "advance", lambda *args, **kwargs: None)
    monkeypatch.setattr(evaluation_clock, "enable", lambda *args: None)
    monkeypatch.setattr(host, "ensure_installation", lambda *args: None)
    def delayed(*args):
        raise desktop.DesktopError("service_start_timeout", "Service is still starting")
    monkeypatch.setattr(host, "start", delayed)
    states = iter([{"ready": False}, {"ready": True}])
    monkeypatch.setattr(desktop, "status", lambda *args: next(states))
    slept = []
    monkeypatch.setattr(harness.time, "sleep", slept.append)
    try:
        memory = harness.Memory(directory, None, None, datetime.datetime(2026, 3, 2, tzinfo=datetime.UTC))
        assert memory.directory == directory and slept == [5] and directory_created == [directory]
    finally:
        harness.STARTED.remove(directory)
