"""The C5 harness prerequisites (no model call, no network): tools, the session clock, page actions, the reference
arm's world, and the stubs used by the zero-network dry run."""
import asyncio
import datetime
import importlib.util
import json
import socket
from pathlib import Path

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
    monkeypatch.delenv(evaluation_clock.ENV, raising=False)
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
        SESSIONS_LONG = [("s1", ["Today is Monday, March 2, 20:00. Hi"])]
        PAGE_ACTIONS = [("s1", 0, {"do": "rename_everything"})]

    with pytest.raises(SystemExit, match="bad page action"):
        harness.check_actions(Scenario)
    Scenario.PAGE_ACTIONS = [("s1", 0, {"do": "accept_persona_proposal", "match": "casual"})]
    with pytest.raises(SystemExit, match="states the card"):
        harness.check_actions(Scenario)
    Scenario.PAGE_ACTIONS = [("s1", 0, {"do": "accept_persona_proposal", "match": "casual", "card": {}})]
    monkeypatch.setattr(harness, "STUB", False)
    monkeypatch.setattr(harness, "proposals_supported", lambda: False)
    with pytest.raises(SystemExit, match="no persona proposals"):  # A live run never silently skips an action.
        harness.check_actions(Scenario)


# Tools ----------------------------------------------------------------------------------------------------------

def test_arm_p_offers_the_boundary_tool_and_the_note_tools_companion_fields(tmp_path):
    directory = tmp_path / "installation"
    host.ensure_installation(directory)
    client = MemoryClient("http://127.0.0.1:9", "key", brain_id="brain")
    from membrain.mcp_server import create_server

    server = create_server(client, directory=directory)
    listed = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    offered = [name for name in harness.TOOLS if name in listed]
    assert offered == list(harness.TOOLS)
    assert "memory_boundary" in offered
    note = listed["memory_note"].inputSchema["properties"]
    assert {"affect", "shared"} <= set(note)
    assert listed["memory_boundary"].inputSchema["required"] == ["topic"]


# The reference arm ----------------------------------------------------------------------------------------------

def test_f_gets_the_persona_block_the_product_renders_and_follows_card_changes():
    from membrain.persona import render_persona

    reference = harness.Reference(practice.PERSONA)
    assert reference.block() == render_persona({"version": 1, "card": practice.PERSONA})
    reference.apply({"do": "accept_persona_proposal", "card": practice.ACCEPTED_CARD})
    assert reference.block().startswith('<membrain-persona version="2">') and "register casual" in reference.block()
    reference.apply({"do": "restore_persona", "version": 1})
    assert reference.block().startswith('<membrain-persona version="3">') and "register formal" in reference.block()
    reference.apply({"do": "set_persona", "card": practice.ACCEPTED_CARD})
    reference.apply({"do": "reset_persona"})  # Back to the host's default card, as a new version.
    assert reference.block().startswith('<membrain-persona version="5">') and "register formal" in reference.block()
    reference.apply({"do": "delete_persona_history"})
    assert reference.block() is None


@pytest.mark.parametrize("kind", ["clear_feelings", "delete_feeling", "delete_note", "reset_mood", "pin_mood",
                                  "reset_relationship", "add_boundary", "remove_boundary", "reset_persona",
                                  "delete_persona_history", "reject_persona_proposal"])
def test_only_a_deleted_message_leaves_fs_history(kind):
    reference = harness.Reference(practice.PERSONA)
    reference.history = [(("s1", 0, "user"), {"role": "user", "content": "a"}),
                         (("s1", 0, "assistant"), {"role": "assistant", "content": "b"}),
                         (("s1", 1, "user"), {"role": "user", "content": "c"})]
    reference.apply({"do": kind, "label": "x", "contains": "x", "topic": "x"})
    assert len(reference.history) == 3
    # F drops exactly what the product removed in P: here the message and the reply that answered it.
    removed = [["s1", 0, "assistant"], ["s1", 0, "user"]]
    result = reference.apply({"do": "delete_message", "session": "s1", "turn": 0, "role": "user", "removed": removed})
    assert result == {"deleted": 2, "removed": removed}
    assert [message["content"] for _, message in reference.history] == ["c"]
    assert reference.contains(removed) == 0


def test_f_waits_for_and_mirrors_ps_recorded_deletion(tmp_path):
    action = {"do": "delete_message", "session": "s1", "turn": 0, "role": "user"}
    (tmp_path / "k-P").mkdir()
    (tmp_path / "k-P" / "page-actions.jsonl").write_text(json.dumps({
        "action": "delete_message", "detail": {"session": "s1", "turn": 0, "role": "user"},
        "result": {"deleted": 1, "removed": [["s1", 0, "user"]]}}) + "\n")
    assert harness.removed_in_p(tmp_path / "k-F", action, []) == [["s1", 0, "user"]]
    with pytest.raises(SystemExit, match="never recorded"):
        harness.removed_in_p(tmp_path / "k-F", action, [action], timeout=0.1)


# Stubs ----------------------------------------------------------------------------------------------------------

def test_the_stub_host_calls_scripted_tools_with_the_current_source_then_replies(monkeypatch):
    monkeypatch.setattr(harness, "STUB", True)  # No key is read.
    stub = harness.StubHost({("s1", 0): [{"tool": "memory_note", "arguments": {"text": "x"}, "source": "current"},
                                         {"tool": "memory_pause", "arguments": {}}]})
    stub.key = ("s1", 0)
    host_model = harness.Host(cap=5, transport=httpx.MockTransport(stub))
    source = '<membrain-source>\nWhen saving a note ..., pass source_messages=[{"source_event_key": "k"}]. This'
    tools = [{"type": "function", "function": {"name": "memory_note"}}]
    message, _ = host_model.call([{"role": "system", "content": "<membrain-persona version=\"1\">"},
                                  {"role": "user", "content": source}], tools)
    (call,) = message["tool_calls"]  # memory_pause was not offered, so it is not called.
    assert json.loads(call["function"]["arguments"]) == {"text": "x", "source_messages": [{"source_event_key": "k"}]}
    reply, usage = host_model.call([{"role": "system", "content": "<membrain-persona version=\"1\">"},
                                    {"role": "user", "content": "hi"}, message,
                                    {"role": "tool", "tool_call_id": "call-0", "content": "{}"}])
    assert "membrain-persona" in reply["content"] and usage["total_tokens"] > 0


def test_the_dry_run_refuses_any_connection_off_this_machine(tmp_path, monkeypatch):
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
    start = datetime.datetime(2026, 3, 2, 20, 0, tzinfo=datetime.UTC)
    created = harness.Memory(tmp_path / "brain", None, None, start)
    try:
        yield created
    finally:
        monkeypatch.delenv(evaluation_clock.ENV, raising=False)
        harness.stop_started()


def test_page_actions_go_through_the_api_and_remove_only_what_they_name(memory):
    directory = memory.directory
    assert memory.now().startswith("2026-03-02T20:0")
    host.prompt_context(directory, "s1", "I'm nervous about Thursday's review.", turn_id="t0", include_source=True)
    host.finish_turn(directory, "s1", "Good luck.", turn_id="t0")
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
    ahead, result, after = act({"do": "remove_boundary", "topic": "Tom"})
    assert result == {"failed": "no boundary 'Tom'"} and after == ahead
