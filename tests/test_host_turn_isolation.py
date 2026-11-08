import json

import pytest

from membrain import host
from membrain import host_turns as turns


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(host, "ready_client", lambda *args: None)
    monkeypatch.setattr(host, "start_in_background", lambda *args: None)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("owners", [("alice", "bob"), ("alice", "alice")])
def test_overlapping_turns_keep_their_input_owner_and_parent(tmp_path, reverse, owners):
    for i, owner in enumerate(owners):
        host.prompt_context(tmp_path, "shared", f"Question {i}", turn_id=f"turn:{i}", user_id=owner)
    for i in ([1, 0] if reverse else [0, 1]):
        records = host.finish_turn(tmp_path, "shared", f"Answer {i}", turn_id=f"turn:{i}", user_id=owners[i])
        assert [r["text"] for r in records] == [f"Question {i}", f"Answer {i}"]
        assert {r.get("_user") for r in records} == {owners[i]}
        assert records[1]["parent_source_event_keys"] == [f"shared:turn:{i}:user"]


def test_late_excluded_callback_does_not_take_or_revive_a_new_turn(tmp_path):
    host.prompt_context(tmp_path, "s", "Private draft", turn_id="private", user_id="alice")
    host.pause(tmp_path, user_id="alice")
    host.resume(tmp_path, user_id="alice")
    host.prompt_context(tmp_path, "s", "Public draft", turn_id="public", user_id="alice")
    for _ in range(2):
        assert host.finish_turn(tmp_path, "s", "Private reply", turn_id="private",
                                prompt="Private draft", user_id="alice") == []
    records = host.finish_turn(tmp_path, "s", "Public reply", turn_id="public", user_id="alice")
    assert [r["text"] for r in records] == ["Public draft", "Public reply"]
    assert "Private" not in "".join(p.read_text() for p in (tmp_path / "plugin").rglob("*.json*"))


def test_wrong_owner_producer_or_prompt_cannot_consume_a_turn(tmp_path):
    host.prompt_context(tmp_path, "s", "Alice question", turn_id="t", user_id="alice", producer="a")
    for options in ({"user_id": "bob", "producer": "a"}, {"user_id": "alice", "producer": "b"},
                    {"user_id": "alice", "producer": "a", "prompt": "Different question"}):
        assert host.finish_turn(tmp_path, "s", "Wrong reply", turn_id="t", **options) == []
    assert len(host.finish_turn(tmp_path, "s", "Correct reply", turn_id="t", user_id="alice", producer="a")) == 2


def test_callbacks_without_identity_do_not_guess_between_overlapping_turns(tmp_path):
    host.prompt_context(tmp_path, "s", "First")
    host.prompt_context(tmp_path, "s", "Second")
    assert host.finish_turn(tmp_path, "s", "Unknown reply") == []
    assert [r["text"] for r in host.finish_turn(tmp_path, "s", "Second reply", prompt="Second")] == [
        "Second", "Second reply"]


def test_session_refresh_does_not_remove_inflight_turns(tmp_path):
    host.prompt_context(tmp_path, "s", "First", turn_id="one")
    host.session_context(tmp_path, "s")
    host.prompt_context(tmp_path, "s", "Second", turn_id="two")
    assert [r["text"] for r in host.finish_turn(tmp_path, "s", "One", turn_id="one")] == ["First", "One"]


def test_reply_without_explicit_id_preserves_colons_in_staged_id(tmp_path):
    host.prompt_context(tmp_path, "s", "Question", turn_id="host:turn:1")
    records = host.finish_turn(tmp_path, "s", "Reply")
    assert records[1]["source_event_key"] == "s:host:turn:1:assistant"
    assert records[1]["parent_source_event_keys"] == [records[0]["source_event_key"]]


def test_duplicate_completion_has_no_second_receipt(tmp_path):
    host.prompt_context(tmp_path, "s", "Question", turn_id="one")
    assert len(host.finish_turn(tmp_path, "s", "Reply", turn_id="one", prompt="Question")) == 2
    assert host.finish_turn(tmp_path, "s", "Reply", turn_id="one", prompt="Question") == []
    records = [json.loads(line) for line in (tmp_path / "plugin" / "spool.jsonl").read_text().splitlines()]
    assert len(records) == 2


def test_pause_in_shared_session_preserves_other_owners(tmp_path):
    for owner in ("alice", "bob"):
        host.prompt_context(tmp_path, "s", f"{owner} question", turn_id="t", user_id=owner)
    host.pause(tmp_path, user_id="alice")
    host.resume(tmp_path, user_id="alice")
    assert host.finish_turn(tmp_path, "s", "Alice reply", turn_id="t", user_id="alice") == []
    assert [r["text"] for r in host.finish_turn(tmp_path, "s", "Bob reply", turn_id="t", user_id="bob")] == [
        "bob question", "Bob reply"]


def test_resume_does_not_guess_between_two_paused_turns(tmp_path):
    host.pause(tmp_path, user_id="alice")
    for turn in ("one", "two"):
        host.prompt_context(tmp_path, "s", f"Private {turn}", turn_id=turn, user_id="alice")
    result = host.resume(tmp_path, user_id="alice", current_turn=True, session="s")
    assert result["current_turn_resumed"] is False
    for turn in ("one", "two"):
        assert host.finish_turn(tmp_path, "s", "Private reply", turn_id=turn, user_id="alice",
                                prompt=f"Private {turn}") == []


def test_active_limit_does_not_evict_or_admit_unstaged_callbacks(tmp_path):
    for i in range(turns.MAX_ACTIVE):
        host.prompt_context(tmp_path, "s", f"Question {i}", turn_id=str(i))
    with pytest.raises(ValueError, match="Too many unfinished"):
        host.prompt_context(tmp_path, "s", "Overflow", turn_id="overflow")
    for i in range(turns.MAX_ACTIVE):
        assert len(host.finish_turn(tmp_path, "s", "Reply", turn_id=str(i))) == 2
    assert host.finish_turn(tmp_path, "s", "Late overflow", prompt="Overflow", turn_id="overflow") == []


@pytest.mark.parametrize("staged", [False, True])
def test_private_callback_stays_excluded_after_finished_cache_compaction(tmp_path, staged):
    private = "Off the record: a confidential draft."
    if staged:
        host.prompt_context(tmp_path, "s", private, turn_id="private")
    assert host.finish_turn(tmp_path, "s", "Private reply", prompt=private, turn_id="private") == []
    host.resume(tmp_path)
    for i in range(turns.MAX_FINISHED + 2):
        host.prompt_context(tmp_path, "s", f"Public {i}", turn_id=str(i))
        assert len(host.finish_turn(tmp_path, "s", "Reply", turn_id=str(i))) == 2
    state = host.session_state(tmp_path, "s")
    assert len(state["turns"]) <= turns.MAX_FINISHED
    assert host.finish_turn(tmp_path, "s", "Private reply", prompt=private, turn_id="private",
                            allow_unstaged=True) == []
    assert "confidential draft" not in (tmp_path / "plugin" / "spool.jsonl").read_text()


def test_parallel_stages_and_finishes_survive_client_recreation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: host.prompt_context(tmp_path, "s", f"Question {i}", turn_id=str(i)), range(32)))
        receipts = list(pool.map(lambda i: host.finish_turn(tmp_path, "s", f"Answer {i}", turn_id=str(i)),
                                 reversed(range(32))))
    assert [[r["text"] for r in records] for records in receipts] == [
        [f"Question {i}", f"Answer {i}"] for i in reversed(range(32))]


def test_legacy_pending_and_pause_migrate_without_taking_new_turns(tmp_path):
    record = host.message_record("s", "user", "Old question", turn_id="old", user_id="alice")
    host._write_session_state(tmp_path, "s", {"pending": record, "user_id": "alice"})
    host.prompt_context(tmp_path, "s", "New question", turn_id="new", user_id="alice")
    assert len(host.finish_turn(tmp_path, "s", "Old reply", turn_id="old", user_id="alice")) == 2
    assert len(host.finish_turn(tmp_path, "s", "New reply", turn_id="new", user_id="alice")) == 2
    host._write_session_state(tmp_path, "private", {"paused_turn": True, "user_id": "alice"})
    host.prompt_context(tmp_path, "private", "New question", turn_id="new", user_id="alice")
    assert len(host.finish_turn(tmp_path, "private", "New reply", turn_id="new", user_id="alice")) == 2
    assert host.finish_turn(tmp_path, "private", "Private reply", turn_id="old", user_id="alice",
                            prompt="Old private question") == []


def test_replayed_excluded_prompt_does_not_restore_private_cues(tmp_path):
    host.prompt_context(tmp_path, "s", "Confidential draft", turn_id="private")
    host.pause(tmp_path)
    host.resume(tmp_path)
    host.prompt_context(tmp_path, "s", "Confidential draft", turn_id="private")
    assert "Confidential draft" not in host._session_marker(tmp_path, "s").read_text()
    assert host.finish_turn(tmp_path, "s", "Private reply", turn_id="private") == []


def test_callback_with_reused_id_and_changed_input_does_not_change_context_owner(tmp_path):
    host.prompt_context(tmp_path, "s", "Alice question", turn_id="t", user_id="alice")
    host.prompt_context(tmp_path, "s", "Bob question", turn_id="t", user_id="bob")
    with pytest.raises(ValueError, match="different user messages"):
        host.prompt_context(tmp_path, "s", "Different question", turn_id="t", user_id="alice")
    state = host.session_state(tmp_path, "s")
    assert state["user_id"] == "bob" and state["last_prompt"] == "Bob question"


def test_identical_implicit_overlaps_are_excluded_without_guessing(tmp_path):
    host.prompt_context(tmp_path, "s", "Repeated question")
    host.prompt_context(tmp_path, "s", "Repeated question")
    assert host.finish_turn(tmp_path, "s", "First reply", prompt="Repeated question") == []
    assert host.finish_turn(tmp_path, "s", "Second reply", prompt="Repeated question") == []


def test_explicit_mixed_host_can_report_an_unstaged_turn_but_not_take_live_input(tmp_path):
    host.prompt_context(tmp_path, "s", "First", turn_id="one")
    assert host.finish_turn(tmp_path, "s", "Wrong", turn_id="two", prompt="Whole turn",
                            allow_unstaged=True) == []
    assert len(host.finish_turn(tmp_path, "s", "First reply", turn_id="one")) == 2
    assert len(host.finish_turn(tmp_path, "s", "Whole reply", turn_id="two", prompt="Whole turn",
                                allow_unstaged=True)) == 2


def test_erasure_keeps_other_owners_turns_and_rejects_late_callbacks(tmp_path, monkeypatch):
    from test_host import Client

    class Eraser(Client):
        def dashboard(self):
            return {"brain": {"scope_generation": 1}}

        def forget(self, ids, **options):
            return {"outcome": "completed"}

    for owner in ("alice", "bob"):
        host.prompt_context(tmp_path, "s", f"{owner} draft", turn_id="t", user_id=owner)
    with monkeypatch.context() as online:
        online.setattr(host, "ready_client", lambda *args: Eraser())
        assert host.erase_user(tmp_path, "alice")["erased"] == "completed"
    assert "alice draft" not in host._session_marker(tmp_path, "s").read_text()
    assert host.finish_turn(tmp_path, "s", "Alice reply", turn_id="t", prompt="alice draft",
                            user_id="alice", allow_unstaged=True) == []
    assert len(host.finish_turn(tmp_path, "s", "Bob reply", turn_id="t", user_id="bob")) == 2


def test_abandonment_uses_each_turns_age_and_does_not_guess_a_late_reply(tmp_path, monkeypatch):
    from test_host import Client

    client = Client()
    host.prompt_context(tmp_path, "s", "Old question", turn_id="old")
    state = host.session_state(tmp_path, "s")
    next(iter(state["turns"].values()))["started"] = 0
    host._write_session_state(tmp_path, "s", state)
    host.prompt_context(tmp_path, "s", "New question", turn_id="new")
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.session_context(tmp_path, "s")
    assert [r["text"] for r in client.observed] == ["Old question"]
    assert host.finish_turn(tmp_path, "s", "Late reply", turn_id="old", prompt="Old question") == []
    assert len(host.finish_turn(tmp_path, "s", "New reply", turn_id="new")) == 2


def test_resume_hook_selects_its_owner_while_another_user_has_an_active_turn(tmp_path):
    from membrain import plugin

    host.pause(tmp_path, user_id="alice")
    host.prompt_context(tmp_path, "s", "Back on the record", turn_id="a", user_id="alice")
    host.prompt_context(tmp_path, "s", "Bob question", turn_id="b", user_id="bob")
    host.resume(tmp_path, user_id="alice", current_turn=True, session="s")
    plugin.stop({"session_id": "s", "turn_id": "a", "membrain_user": "alice",
                 "prompt": "Back on the record", "last_assistant_message": "Alice reply"}, tmp_path)
    assert len(host.finish_turn(tmp_path, "s", "Bob reply", turn_id="b", user_id="bob")) == 2
    records = [json.loads(line) for line in (tmp_path / "plugin" / "spool.jsonl").read_text().splitlines()]
    assert [(r["_user"], r["text"]) for r in records] == [
        ("alice", "Back on the record"), ("alice", "Alice reply"), ("bob", "Bob question"), ("bob", "Bob reply")]


def test_roleplay_and_real_life_turns_with_the_same_id_stay_separate(tmp_path):
    for roleplay in (None, "Ada"):
        host.prompt_context(tmp_path, "s", f"Question {roleplay}", turn_id="t", user_id="alice", roleplay=roleplay)
    for roleplay in ("Ada", None):
        records = host.finish_turn(tmp_path, "s", "Reply", turn_id="t", user_id="alice", roleplay=roleplay)
        assert records[0]["text"] == f"Question {roleplay}"
        assert {r["_user"] for r in records} == {host.roleplay_user("alice", roleplay)}


def test_refresh_does_not_prematurely_abandon_a_legacy_pending_turn(tmp_path, monkeypatch):
    from test_host import Client

    client = Client()
    record = host.message_record("s", "user", "Old-format question", turn_id="old")
    host._write_session_state(tmp_path, "s", {"pending": record})
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    host.session_context(tmp_path, "s")
    assert client.observed == []
    assert len(host.finish_turn(tmp_path, "s", "Reply", turn_id="old")) == 2


def test_housekeeping_skips_decoding_completed_ledgers(tmp_path, monkeypatch):
    host.prompt_context(tmp_path, "s", "Question", turn_id="t")
    host.finish_turn(tmp_path, "s", "Reply", turn_id="t")
    monkeypatch.setattr(host.json, "load", lambda *args, **kwargs: pytest.fail("A completed ledger need not be decoded"))
    assert host._finish_abandoned(tmp_path, None) == 0
