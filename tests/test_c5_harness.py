"""The C5 harness prerequisites (no model call, no network): tools, the session clock, page actions, the reference
arm's world, and the stubs used by the zero-network dry run."""
import asyncio
import datetime
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


def test_a_deletion_during_the_session_in_progress_never_reaches_fs_later_history():
    reference = harness.Reference(practice.PERSONA)
    current = [(("s2", 0, "user"), {"role": "user", "content": "keep"}),
               (("s2", 0, "assistant"), {"role": "assistant", "content": "kept reply"}),
               (("s2", 1, "user"), {"role": "user", "content": "erased later in s2"})]
    # A page action before s2's turn 2 deletes turn 1: the running transcript keeps it, the history must not.
    reference.apply({"do": "delete_message", "session": "s2", "turn": 1, "role": "user",
                     "removed": [["s2", 1, "user"]]})
    reference.end_session(current)
    assert [message["content"] for _, message in reference.history] == ["keep", "kept reply"]
    assert reference.contains([["s2", 1, "user"]]) == 0


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
    monkeypatch.setattr(harness, "STUB", True)
    start = datetime.datetime(2026, 3, 2, 20, 0, tzinfo=datetime.UTC)
    monkeypatch.setenv(evaluation_clock.ENV, "")  # The harness sets it in os.environ; this restores it after.
    try:
        yield harness.Memory(tmp_path / "brain", None, None, start)
    finally:
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
    ahead, result, after = act({"do": "remove_boundary", "topic": "Tom"})
    assert result == {"failed": "no boundary 'Tom'"} and after == ahead


class _ProposalClient:
    """A client whose accepted proposal leads to ``stored`` (no database or model)."""

    def __init__(self, stored):
        self.stored = stored

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def persona_proposals(self):
        return {"proposals": [{"id": "p1", "status": "open", "kind": "less_formal"}]}

    def accept_persona_proposal(self, proposal_id):
        return {"persona": {"version": 2, "card": self.stored}}

    def persona(self):
        return {"version": 2, "card": self.stored}


@pytest.mark.parametrize("same", [True, False])
def test_an_accepted_proposal_fails_unless_ps_card_is_the_card_f_gets(same):
    stored = practice.ACCEPTED_CARD if same else practice.PERSONA
    # The stored form may differ in whitespace only; that is the same card.
    stored = {**stored, "name": f"  {stored['name']} "}
    memory = SimpleNamespace(client=lambda: _ProposalClient(stored))
    action = {"do": "accept_persona_proposal", "match": "formal", "card": practice.ACCEPTED_CARD}
    result = harness.apply_page_action(memory, action, {})
    if same:
        assert result == {"proposal": "p1", "version": 2}
    else:
        assert result["failed"] == "the accepted card differs from the scenario's card"
        assert result["differing_fields"] == ["voice"]


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
