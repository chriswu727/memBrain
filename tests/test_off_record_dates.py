"""After an off-the-record stretch the host can say so honestly (evaluations/maturity-seventh-attempt-2026-11-16.md).

A turn left unrecorded by a pause leaves only its local date, host-side; the person's later session notices name
the dates. No service and no database: memory clients are stand-ins, and every installation is a temporary directory.
"""
import asyncio
import datetime
import io
import json
import time

import pytest
from test_hermes_adapter import Client as HermesClient
from test_hermes_adapter import provider as hermes_provider
from test_host import Client

from membrain import helpers, host, host_erasure, host_recording, local_recording, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.client import MemoryActionError
from membrain.mcp_server import create_server

SCENARIO = datetime.datetime(2026, 9, 12, 15, 0, tzinfo=datetime.UTC)
DAY = "2026-09-12"
SENTENCE = "was off the record and nothing of it was kept."


@pytest.fixture(autouse=True)
def fixed_day(monkeypatch):
    """A fixed clock and zone, as an evaluation's scenario clock gives the host side, so the date is known."""
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    monkeypatch.setattr(helpers, "_scenario_clock", lambda: SCENARIO)
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.UTC)


@pytest.fixture
def client(monkeypatch):
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    return client


def _files(directory):
    return {path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
            for path in (directory / "plugin").glob("off-record*") if path.is_file()} | {
        path.relative_to(directory).as_posix(): path.read_text(encoding="utf-8")
        for path in (directory / "plugin").glob("off-record-users/*.json")}


def _turn(directory, session, text, reply="Okay.", turn="t1", **options):
    host.prompt_context(directory, session, text, turn_id=turn, **options)
    return host.finish_turn(directory, session, reply, turn_id=turn, **options)


# Each kind of pause, and only a pause -----------------------------------------------------------------------------

def test_the_products_own_pause_on_the_users_words_keeps_only_the_date(tmp_path, client):
    # Claude Code's hooks: the message itself asks not to be kept.
    plugin.user_prompt({"session_id": "c1", "prompt": "Off the record: I'm job hunting at Initech.",
                        "prompt_id": "t1"}, tmp_path)
    plugin.stop({"session_id": "c1", "prompt_id": "t1", "last_assistant_message": "Okay, not keeping that."},
                tmp_path)
    assert client.observed == []
    assert host.off_record_dates(tmp_path) == [DAY]
    assert _files(tmp_path) == {"plugin/off-record.json": json.dumps({"dates": [DAY]})}
    opening = plugin.session_start({"session_id": "c2"}, tmp_path)
    assert f"At the user's request, part of your conversation on {DAY} {SENTENCE}" in opening
    assert "Initech" not in opening and "job hunting" not in opening


def test_the_host_ais_pause_tool_keeps_the_date_of_the_turn_it_left_out(tmp_path, client):
    server = create_server(Client(), directory=tmp_path)
    host.prompt_context(tmp_path, "m1", "Between us, don't remember the bit about my debt.", turn_id="t1")
    _, result = asyncio.run(server.call_tool("memory_pause", {"request": "don't remember the bit about my debt"}))
    assert result["recording"] == "paused"
    host.finish_turn(tmp_path, "m1", "Understood.", turn_id="t1")
    _turn(tmp_path, "m1", "And the amount is 4,000.", turn="t2")  # A later turn of the paused conversation.
    assert client.observed == [] and host.off_record_dates(tmp_path) == [DAY]
    assert "debt" not in json.dumps(_files(tmp_path)) and "4,000" not in json.dumps(_files(tmp_path))


@pytest.mark.parametrize("control", ["library", "device"])
def test_the_users_own_local_controls_keep_the_date(tmp_path, client, control):
    if control == "library":
        host_recording.pause(tmp_path)
    else:
        local_recording.change(tmp_path, paused=True)  # The memory page's device-capture control.
    _turn(tmp_path, "s1", "My sister moved to Leeds.")
    assert client.observed == [] and host.off_record_dates(tmp_path) == [DAY]


def test_the_server_recording_policy_keeps_the_date(tmp_path, monkeypatch):
    class Paused(Client):
        def recording_status(self):
            return {"paused": True, "revision": 2}

    client = Paused()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    receipt = {}
    host.prompt_context(tmp_path, "s1", "My sister moved to Leeds.", turn_id="t1")
    host.finish_turn(tmp_path, "s1", "Noted.", turn_id="t1", receipt=receipt)
    assert {item["reason"] for item in receipt["messages"]} == {"server_paused"}
    assert client.observed == [] and host.off_record_dates(tmp_path) == [DAY]


def test_a_queued_message_the_service_refuses_as_paused_keeps_the_date(tmp_path, monkeypatch):
    class Refusing(Client):
        def observe(self, **record):
            raise MemoryActionError({"error": {"code": "recording_paused", "retryable": False,
                                               "message": "Recording is paused."}})

    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Refusing())
    assert _turn(tmp_path, "s1", "My sister moved to Leeds.") == []
    assert host.off_record_dates(tmp_path) == [DAY]
    assert "Leeds" not in json.dumps(_files(tmp_path))


def test_a_recorded_turn_and_a_refused_pause_keep_nothing(tmp_path, client):
    _turn(tmp_path, "s1", "My sister moved to Leeds last week.", "Leeds is lovely.")
    host.prompt_context(tmp_path, "s1", "What should I cook tonight?", turn_id="t2")
    refused = host_recording.agent_pause(tmp_path, "don't remember this", conversation=True)
    assert refused["code"] == "pause_request_not_in_message"
    host.finish_turn(tmp_path, "s1", "Pasta.", turn_id="t2")
    assert len(client.observed) == 4
    assert host.off_record_dates(tmp_path) == [] and _files(tmp_path) == {}
    assert SENTENCE not in host.session_context(tmp_path, "s2")


def test_a_turn_resumed_at_the_users_request_is_recorded_and_adds_no_date(tmp_path, client):
    host_recording.pause(tmp_path)
    host.prompt_context(tmp_path, "s1", "Back on the record, please.", turn_id="t1")
    host_recording.resume(tmp_path, current_turn=True, session="s1")
    host.finish_turn(tmp_path, "s1", "Recording again.", turn_id="t1", prompt="Back on the record, please.")
    assert [record["text"] for record in client.observed] == ["Back on the record, please.", "Recording again."]
    assert host.off_record_dates(tmp_path) == []


# What is kept, and its date ---------------------------------------------------------------------------------------

def test_at_most_ten_distinct_dates_are_kept_and_never_any_text(tmp_path, client, monkeypatch):
    for day in range(1, 13):
        moment = datetime.datetime(2026, 10, day, 9, 0, tzinfo=datetime.UTC)
        monkeypatch.setattr(helpers, "_scenario_clock", lambda moment=moment: moment)
        for turn in ("a", "b"):  # Two turns on the same day are one date.
            host.prompt_context(tmp_path, "s1", f"Off the record: secret {day}{turn}.", turn_id=f"t{day}{turn}")
            host.finish_turn(tmp_path, "s1", "Okay.", turn_id=f"t{day}{turn}")
    assert host.off_record_dates(tmp_path) == [f"2026-10-{day:02d}" for day in range(3, 13)]
    stored = json.loads((tmp_path / "plugin" / "off-record.json").read_text(encoding="utf-8"))
    assert list(stored) == ["dates"] and len(stored["dates"]) == host.OFF_RECORD_DATES
    assert "secret" not in json.dumps(_files(tmp_path))


def test_the_date_is_the_users_local_date_on_the_clock_of_recorded_times(tmp_path, client, monkeypatch):
    # 05:00 UTC on the 12th is still the 11th ten hours west of UTC, as other dates written for the host are.
    monkeypatch.setattr(helpers, "_scenario_clock",
                        lambda: datetime.datetime(2026, 9, 12, 5, 0, tzinfo=datetime.UTC))
    monkeypatch.setattr(helpers, "display_zone", lambda: datetime.timezone(datetime.timedelta(hours=-10)))
    _turn(tmp_path, "s1", "Off the record: the surprise party.")
    assert host.off_record_dates(tmp_path) == ["2026-09-11"]
    assert host.local_date("2026-09-12T05:00:00Z") == "2026-09-11"


def test_an_abandoned_paused_turn_keeps_the_date_it_began_on(tmp_path, client, monkeypatch):
    monkeypatch.setattr(helpers, "_scenario_clock", None)  # The wall clock, as every installation has.
    host.prompt_context(tmp_path, "s1", "Off the record: the surprise party.", turn_id="t1")  # No reply came.
    began = time.time() - 3 * 24 * 3600
    state = host.session_state(tmp_path, "s1")
    for entry in state["turns"].values():
        entry["started"] = began
    host._write_session_state(tmp_path, "s1", state)
    host.session_context(tmp_path, "s2")  # A session start settles turns abandoned over half an hour ago.
    expected = host.local_date(datetime.datetime.fromtimestamp(began, datetime.UTC).isoformat())
    assert host.off_record_dates(tmp_path) == [expected]


# The notice ---------------------------------------------------------------------------------------------------------

def test_the_notice_names_the_five_latest_dates_oldest_first_and_only_when_there_are_any(tmp_path, client):
    assert host.off_record_notice([]) == "" and SENTENCE not in host.session_context(tmp_path, "s1")
    dates = [f"2026-10-{day:02d}" for day in range(1, 8)]
    host._write_state(host._off_record_file(tmp_path), {"dates": list(reversed(dates))})
    assert host.off_record_notice([DAY]) == (
        f"At the user's request, part of your conversation on {DAY} was off the record and nothing of it was kept. "
        "If the user asks about something from then, or about something they say they told you that you find no "
        "record of, tell them it may have been in that part and that you kept nothing of it because they asked; do "
        "not say it was not said, and do not guess.")
    opening = host.session_context(tmp_path, "s2")
    assert ("part of your conversation on 2026-10-03, 2026-10-04, 2026-10-05, 2026-10-06 and 2026-10-07 was off "
            "the record") in opening
    assert "2026-10-02" not in opening
    assert "on 2026-04-29 and 2026-05-12 was" in host.off_record_notice(["2026-04-29", "2026-05-12"])


def test_the_notice_is_shown_while_the_service_is_starting_too(tmp_path, monkeypatch):
    host._write_state(host._off_record_file(tmp_path), {"dates": [DAY]})
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: None)
    monkeypatch.setattr(host, "start_in_background", lambda directory: None)
    opening = host.session_context(tmp_path, "s1")
    assert "memBrain is starting" in opening and f"conversation on {DAY} {SENTENCE}" in opening


def test_a_persons_dates_are_shown_to_them_only_and_their_role_play_follows_them(tmp_path, client):
    _turn(tmp_path, "alice-1", "Off the record: about my health.", user_id="alice")
    assert host.off_record_dates(tmp_path, "alice") == [DAY]
    assert host.off_record_dates(tmp_path, "bob") == [] and host.off_record_dates(tmp_path) == []
    assert SENTENCE in host.session_context(tmp_path, "alice-2", user_id="alice")
    assert SENTENCE not in host.session_context(tmp_path, "bob-1", user_id="bob")
    assert SENTENCE not in host.session_context(tmp_path, "owner-1")
    # A pause in her role-play is her own, as its pauses are; and her role-play is told of hers.
    _turn(tmp_path, "carol-rp", "Off the record: the captain's log.", user_id="carol", roleplay="Captain Vale")
    assert host.off_record_dates(tmp_path, "carol") == [DAY]
    assert SENTENCE in host.session_context(tmp_path, "alice-rp", user_id="alice", roleplay="Mira")


# Erasure ------------------------------------------------------------------------------------------------------------

class Erasing(Client):
    def dashboard(self):
        return {"brain": {"scope_generation": 1}}

    def forget(self, ids, **options):
        return {"outcome": "applied"}


def test_erasing_a_persons_whole_memory_removes_their_dates_only(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Erasing())
    for user in ("alice", "bob", None):
        _turn(tmp_path, f"{user}-1", "Off the record: something.", user_id=user)
    assert host.erase_user(tmp_path, "alice")["erased"] == "applied"
    assert host.off_record_dates(tmp_path, "alice") == [] and host.off_record_dates(tmp_path, "bob") == [DAY]
    assert host.off_record_dates(tmp_path) == [DAY]
    host.erase_user(tmp_path, None)
    assert host.off_record_dates(tmp_path) == [] and not (tmp_path / "plugin" / "off-record.json").exists()


def test_erasing_single_messages_keeps_the_dates(tmp_path, monkeypatch):
    class Reconciling(Client):
        def recording_erasures(self, references):
            return {"erased": list(range(len(references))), "revision": 3, "has_erasures": True}

    client = Reconciling()
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: client)
    _turn(tmp_path, "s1", "Off the record: something.")
    _turn(tmp_path, "s1", "My sister moved to Leeds.", turn="t2")  # Recorded; then erased on the memory page.
    assert host_erasure.reconcile(tmp_path, client, None) is True
    assert host.off_record_dates(tmp_path) == [DAY]


def test_the_chat_bot_forget_removes_the_speakers_dates(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: Erasing())
    memory, mei = ChatMemory(tmp_path, roleplay="Captain Vale"), Speaker("qq", "mei")
    session = memory.session(mei)
    memory.context(mei, "Off the record: the treasure map.", session=session, turn_id="t1")
    memory.record(mei, "Aye.", session=session, turn_id="t1")
    assert host.off_record_dates(tmp_path, memory.user_id(mei)) == [DAY]
    memory.forget(mei)
    assert host.off_record_dates(tmp_path, memory.user_id(mei)) == []


# Hosts ----------------------------------------------------------------------------------------------------------

def test_the_chat_bot_pause_tool_keeps_the_speakers_date_and_tells_only_them(tmp_path, client):
    memory, mei, tom = ChatMemory(tmp_path), Speaker("discord", "mei"), Speaker("discord", "tom")
    session = memory.session(mei)
    memory.context(mei, "Please don't remember what I say about my ex.", session=session, turn_id="t1")
    assert memory.pause(mei, request="don't remember what I say about my ex")["recording"] == "paused"
    memory.record(mei, "Understood.", session=session, turn_id="t1")
    assert host.off_record_dates(tmp_path, memory.user_id(mei)) == [DAY]
    assert host.off_record_dates(tmp_path, memory.user_id(tom)) == []
    later = memory.session(mei, "later")
    assert SENTENCE in memory.context(mei, "Hi again.", session=later, turn_id="t2")
    assert SENTENCE not in (memory.context(tom, "Hello!", session=memory.session(tom), turn_id="t1") or "")


def test_hermes_keeps_the_date_and_tells_the_next_session(tmp_path, monkeypatch):
    instance = hermes_provider(tmp_path, monkeypatch, HermesClient())
    instance.prefetch("Off the record: my diagnosis came back.", session_id="h1")
    instance.sync_turn("Off the record: my diagnosis came back.", "I won't keep it.", session_id="h1")
    instance.on_session_switch("h2")
    block = instance.system_prompt_block()
    assert f"conversation on {DAY} {SENTENCE}" in block and "diagnosis" not in block


def test_openclaw_pause_through_the_tool_command_keeps_the_users_date(tmp_path, client, capsys):
    user = {"membrain_user": "openclaw:guest"}
    plugin.user_prompt({"session_id": "o1", "prompt": "这个别记，我刚换了工作。", "prompt_id": "t1", **user}, tmp_path,
                       producer="membrain-openclaw")
    plugin.run_tool("pause", tmp_path, io.BytesIO(json.dumps({"request": "这个别记", **user}).encode()))
    assert json.loads(capsys.readouterr().out)["recording"] == "paused"
    plugin.stop({"session_id": "o1", "prompt_id": "t1", "last_assistant_message": "好的。", **user}, tmp_path,
                producer="membrain-openclaw")
    assert client.observed == [] and host.off_record_dates(tmp_path, "openclaw:guest") == [DAY]
    assert host.off_record_dates(tmp_path) == []
    opening = plugin.session_start({"session_id": "o2", **user}, tmp_path, producer="membrain-openclaw")
    assert f"conversation on {DAY} {SENTENCE}" in opening and "换了工作" not in opening
    assert SENTENCE not in plugin.session_start({"session_id": "o3"}, tmp_path, producer="membrain-openclaw")
