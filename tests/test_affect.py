"""A1 affect records (``user_affect``): feelings kept as evidence on their notes, never as a score."""
import datetime
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, host, notes
from membrain.affect import AFFECT_CONVERSATION, affect_records, clear_affect
from membrain.api import create_app
from membrain.config import configured_service
from membrain.helpers import DomainError, uid
from membrain.host_context import _notes
from membrain.local_profile import load_profile
from membrain.memory_map import REGIONS, memory_map
from membrain.notes import (
    AFFECT_CHARACTERS,
    NOTE_TOOL_DESCRIPTION,
    affect_phrase,
    check_affect,
    format_note,
    render_notes,
    save_note,
    store_note,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "membrain" / "web"
NERVOUS = {"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported", "topic": "Friday's interview"}


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def item(event_id, text, recorded="2026-10-20T09:00:00Z", **extra):
    return {"event_id": event_id, "text": text, "actor_role": "assistant", "producer": "membrain-notes",
            "recorded_at": recorded, **extra}


def record(note_id, label="nervous", basis="reported", felt_at=None, **extra):
    felt_at = felt_at or f"{datetime.date.today().year}-03-12"
    return {"id": "a-" + note_id + label, "note_id": note_id, "label": label, "valence": -1, "intensity": 2,
            "basis": basis, "felt_at": felt_at, **extra}


def ids(block):
    return re.findall(r"\(id: ([^)]+)\)", block or "")


# Checked readings ------------------------------------------------------------------------------------------------

def test_a_reading_is_checked_and_an_inferred_feeling_needs_the_message_it_was_read_from():
    today = datetime.date(2027, 3, 12)
    assert check_affect({**NERVOUS, "label": "  really   nervous "}, sourced=False, today=today) == {
        "label": "really nervous", "valence": -1, "intensity": 2, "basis": "reported", "felt_at": "2027-03-12",
        "topic": "Friday's interview"}
    with pytest.raises(ValueError, match="inferred feeling needs the message"):
        check_affect({**NERVOUS, "basis": "inferred"}, sourced=False)
    assert check_affect({**NERVOUS, "basis": "inferred"}, sourced=True)["basis"] == "inferred"
    for bad in ({**NERVOUS, "valence": 3}, {**NERVOUS, "intensity": -1}, {**NERVOUS, "valence": 1.0},
                {**NERVOUS, "valence": True}, {**NERVOUS, "label": ""}, {**NERVOUS, "label": "x" * 41},
                {**NERVOUS, "basis": "guessed"}, {**NERVOUS, "topic": "t" * 81}, {**NERVOUS, "felt_at": "12 Mar"},
                {**NERVOUS, "felt_at": "2027-03"}, {**NERVOUS, "score": 4}, "nervous"):
        with pytest.raises(ValueError):
            check_affect(bad, sourced=True)
    # Credentials are scrubbed from a label like from any note.
    assert "sk-" not in check_affect({**NERVOUS, "label": "sk-ant-abcdefghijklmnopqrstuvwx"}, sourced=False)["label"]


def test_save_note_sends_the_feeling_with_its_note_and_refuses_an_unsourced_inference():
    class Client:
        def __init__(self):
            self.calls = []

        def write_note(self, text, **fields):
            self.calls.append((text, fields))
            return {"note_id": "n1"}

    client = Client()
    save_note(client, "Job interview at Acme on Friday.", kind="plan", status="scheduled", affect=NERVOUS)
    text, fields = client.calls[0]
    assert text == "Job interview at Acme on Friday." and fields["affect"]["label"] == "nervous"
    assert fields["kind"] == "plan" and "affect" not in format_note(text, kind="plan")
    with pytest.raises(ValueError, match="inferred feeling"):
        save_note(client, "Interview on Friday.", affect={**NERVOUS, "basis": "inferred"})
    save_note(client, "Interview on Friday.", source_event_ids=["m1"], affect={**NERVOUS, "basis": "inferred"})
    assert client.calls[-1][1]["affect"]["basis"] == "inferred" and len(client.calls) == 2


# Context ----------------------------------------------------------------------------------------------------------

def test_reported_and_inferred_feelings_read_differently_and_carry_no_score():
    today = datetime.date(2027, 5, 1)
    reported = affect_phrase(record("n1", felt_at="2027-03-12"), today)
    inferred = affect_phrase(record("n1", basis="inferred", felt_at="2027-03-12"), today)
    assert reported == "(the user said they felt nervous, 12 Mar)"
    assert inferred == "(seemed nervous, inferred, 12 Mar)" and "said" not in inferred
    assert affect_phrase(record("n1", felt_at="2026-12-30"), today) == "(the user said they felt nervous, 30 Dec 2026)"

    response = {"items": [item("n2", "Prefers short replies."),
                          item("n1", format_note("Job interview at Acme on Friday.", kind="plan",
                                                 status="scheduled"))],
                "affect": [record("n1"), record("n2", "calm", basis="inferred")]}
    block = render_notes(response, tool="memory_note")
    assert "Job interview at Acme on Friday. (the user said they felt nervous, 12 Mar) (scheduled" in block
    assert "Prefers short replies. (seemed calm, inferred, 12 Mar) (id: n2)" in block
    assert "never present an inferred one as something the user said" in block
    # No overall score of the user's emotions, and the numbers stay out of the context.
    assert "valence" not in block and "intensity" not in block and "score" not in block
    assert "A feeling in brackets" not in render_notes({"items": response["items"]})
    assert render_notes(response, affect=False) == render_notes({"items": response["items"]})


def test_feelings_never_change_which_notes_are_shown_or_their_order():
    kinds = ("other", "plan", "person", "constraint", "preference", "routine")
    items = [item(f"n{index}", format_note(f"Fact number {index} about something that matters a little.",
                                           kind=kinds[index % len(kinds)],
                                           **({"status": "done"} if kinds[index % len(kinds)] == "plan" else {})),
                  recorded=f"2026-10-{1 + index % 28:02d}T09:00:00Z")
             for index in range(60)]
    plain = {"complete": True, "items": items}
    felt = {**plain, "affect": [record(f"n{index}", label=f"feeling {index}", basis=("reported", "inferred")[index % 2])
                                for index in range(60)]}
    for budget in (600, 1200, 2400):
        without, with_feelings = render_notes(plain, budget=budget), render_notes(felt, budget=budget)
        assert ids(with_feelings) == ids(without) and len(ids(without)) < 60
        assert "(the user said they felt" in with_feelings
    # The session-start fitting loop measures the notes without feelings, so it chooses the same notes too.
    for budget in (900, 2800, 3600):
        assert ids(_notes(felt, budget, tool="memory_note")) == ids(_notes(plain, budget, tool="memory_note"))
        assert len(_notes(felt, budget, tool="memory_note")) <= budget + AFFECT_CHARACTERS
    # Their own allowance: a flood of feelings is cut, never the notes.
    shown = render_notes(felt, budget=20_000)
    assert sum(len(phrase) + 1 for phrase in re.findall(r"\((?:the user said|seemed)[^)]*\)", shown)) <= AFFECT_CHARACTERS


def test_a_feeling_on_a_sensitive_note_follows_the_sensitive_rule_and_stays_out_of_role_play():
    response = {"items": [item("n1", format_note("Seeing a counsellor on Tuesdays.", kind="routine", sensitive=True)),
                          item("n2", "Prefers short replies.")],
                "affect": [record("n1", "anxious"), record("n2", "relaxed")]}
    line = next(line for line in render_notes(response).splitlines() if "(id: n1)" in line)
    assert "(the user said they felt anxious, 12 Mar)" in line
    assert "sensitive: mention only if the user brings it up" in line
    assert "on a sensitive note only if the user raises the topic" in render_notes(response)
    shared = render_notes(response, tool=None, real_life=True)
    assert "counsellor" not in shared and "relaxed" not in shared and "Prefers short replies." in shared


def test_list_notes_reads_feelings_when_the_client_can_and_still_shows_notes_when_it_cannot():
    timeline = {"items": [item("n1", "Prefers short replies.")], "complete": True}

    class Reader:
        def timeline(self, **_):
            return dict(timeline)

        def affect_records(self):
            return {"records": [record("n1", "calm")]}

    class Broken(Reader):
        def affect_records(self):
            raise httpx.ConnectError("down")

    class Old:
        def timeline(self, **_):
            return dict(timeline)

    assert notes.list_notes(Reader())["affect"][0]["label"] == "calm"
    assert "affect" not in notes.list_notes(Broken()) and "affect" not in notes.list_notes(Old())


# Who writes feelings ------------------------------------------------------------------------------------------

def test_every_note_tool_explains_when_to_attach_a_feeling():
    assert "add affect" in NOTE_TOOL_DESCRIPTION and "Never invent a feeling" in NOTE_TOOL_DESCRIPTION
    assert "inferred" in NOTE_TOOL_DESCRIPTION and "source" in NOTE_TOOL_DESCRIPTION
    assert notes.NOTE_FIELDS["affect"]["required"] == ["label", "valence", "intensity", "basis"]
    openclaw = (ROOT / "integrations/openclaw/membrain/index.js").read_text(encoding="utf-8")
    assert "add affect" in openclaw and "affect: { type: \"object\"" in openclaw
    astrbot = (ROOT / "integrations/astrbot/astrbot_plugin_membrain/main.py").read_text(encoding="utf-8")
    assert "add affect" in astrbot and "affect(object):" in astrbot and '"affect": affect' in astrbot
    skill = (ROOT / "plugins/membrain/skills/membrain/SKILL.md").read_text(encoding="utf-8")
    assert "`affect`" in skill and "Never invent a feeling" in skill
    assert "(seemed nervous, inferred, 12 Mar)" in skill and "must never be presented as something they said" in skill


# Page and map ------------------------------------------------------------------------------------------------

def test_the_feelings_section_and_the_emotions_region_are_on_the_page_in_english_and_chinese():
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    brain = (WEB / "brain.js").read_text(encoding="utf-8")
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    assert 'data-view="feelings"' in page and 'id="view-feelings"' in page and 'id="clear-feelings"' in page
    assert "/affect/reset" in script and 'forget("events", [record.id], "erase_content", AFFECT)' in script
    assert "if (!confirm(" in script[script.index('guard($("clear-feelings")'):]
    for text in ("you said", "inferred", "You said you felt this.", "On the note:", "Original message not linked.",
                 "Your agent inferred this from what you wrote; you did not say it.", "Feeling deleted.",
                 "Feelings cleared.", "This is a partial list of the most recent feelings.",
                 "Delete this feeling? The note and its messages stay.",
                 "Saving a correction also deletes any feeling recorded with this note.",
                 "No feelings recorded. When you tell your agent how you feel about something, it can keep that "
                 "with the note it belongs to.",
                 "Clear every recorded feeling, said or inferred? Notes and messages stay, and feelings are not "
                 "recreated from earlier messages."):
        assert f'"{text}"' in script, text
        assert re.search(rf'"{re.escape(text)}":\s*"[^"]*[一-鿿]', dictionary), text
    for text in ("A feeling you said you had", "A feeling your agent inferred; you did not say it",
                 "Delete this feeling", "Feelings"):
        assert f'"{text}"' in brain, text
        assert re.search(rf'"{re.escape(text)}":\s*"[^"]*[一-鿿]', dictionary), text
    # Sentences built at run time: the reset marker, a date and the evidence count.
    assert "`Feelings cleared on ${shortDate(marker.recorded_at)}`" in script
    for pattern, sample in ((r"\^Feelings cleared on \(\.\+\)\$", "Feelings cleared on 3 Nov 2026"),
                            (r"\^\(\\d\{1,2\}\) \(Jan\|Feb", "12 Mar 2027"),
                            (r"\^\(\\d\+\) original messages\?\$", "1 original message")):
        assert re.search(pattern, dictionary), pattern
    assert "feeling of" in dictionary and "|Feelings): (.*)$/s" in dictionary


def test_the_emotions_region_is_appended_to_the_fixed_region_order_everywhere():
    assert list(REGIONS.values())[-1] == "emotions" and REGIONS["affect"] == "emotions"
    assert list(REGIONS.values())[:-1] == ["people", "constraints", "preferences", "plans", "commitments",
                                            "routines", "milestones", "relationship", "other", "episodes"]
    brain = (WEB / "brain.js").read_text(encoding="utf-8")
    assert '{ id: "emotions", label: "Feelings", x: ' in brain
    showcase = (WEB / "showcase.js").read_text(encoding="utf-8")
    assert re.search(r'\bemotions: \[\d+, \d+, \d+\]', showcase) and re.search(r'\bemotions: "#[0-9a-f]{6}"', showcase)
    styles = (WEB / "memory.css").read_text(encoding="utf-8")
    assert "--r-emotions:" in styles and ".brain-node.region-emotions " in styles
    demo = json.loads((WEB / "memory-map-demo.json").read_text(encoding="utf-8"))
    feelings = [node for node in demo["nodes"] if node["region"] == "emotions"]
    assert feelings and all(any(edge["source"] == node["id"] and edge["type"] == "feeling_of"
                                and edge["target"].startswith("note:") for edge in demo["edges"]) for node in feelings)


# On a real service -------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    from unittest.mock import patch

    directory = tmp_path_factory.mktemp("affect") / "installation"
    with patch.dict("os.environ", {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield service, settings, directory
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation):
    service, settings, _ = installation
    principal = next(iter(settings.principals().values()))
    return service, principal, service.create_brain(principal, "Affect test")["id"]


def say(brain, text, *, role="user", conversation="chat"):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "affect-test", "actor_ref": role,
            "actor_role": role, "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "delivered" if role == "assistant" else "received",
            "parent_source_event_keys": [],
        }]},
    })
    assert result["outcome"] == "completed", result
    return result["result"]["accepted_event_ids"][0]


def write(brain, text, **fields):
    service, principal, ident = brain
    return store_note(service, principal, ident, {"request_id": uid(), "text": text, **fields})


def forget(brain, event_ids, conversation="chat", mode="erase_content"):
    service, principal, ident = brain
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": list(event_ids)}, "mode": mode,
                    "expected_scope_generation": generation}})
    assert result["outcome"] == "completed", result


def test_cross_session_a_reported_feeling_comes_back_with_its_note_and_goes_with_its_message(installation):
    _, _, directory = installation
    year = datetime.date.today().year
    # Session 1, Wednesday: the user says how they feel; the host saves the note with the feeling and its source.
    host.prompt_context(directory, "wednesday", "I'm really nervous about Friday's interview", turn_id="1")
    host.finish_turn(directory, "wednesday", "Good luck! You have prepared well.", turn_id="1")
    with host.ready_client(directory) as client:
        message = next(entry for entry in client.timeline(roles=("user",))["items"] if "nervous" in entry["text"])
        saved = save_note(client, "Job interview at Acme on Friday.", kind="plan", status="scheduled",
                          occurs_at=f"{year}-03-14", source_event_ids=[message["event_id"]],
                          affect={**NERVOUS, "felt_at": f"{year}-03-12"})
        assert saved["affect_id"]
    # Session 2, Saturday: the interview note carries what the user said they felt, so the companion can ask.
    saturday = host.session_context(directory, "saturday")
    line = next(line for line in saturday.splitlines() if line.startswith("- [") and "Job interview at Acme" in line)
    assert "(the user said they felt nervous, 12 Mar)" in line and "inferred" not in line
    with host.ready_client(directory) as client:
        listed = client.affect_records()["records"]
        assert [(entry["label"], entry["basis"], entry["note_id"]) for entry in listed] == [
            ("nervous", "reported", saved["note_id"])]
        assert listed[0]["source_event_ids"] == [message["event_id"]]
        # The user deletes that message; the note drawn from it and the feeling on the note go with it.
        generation = client.dashboard()["brain"]["scope_generation"]
        client.forget([message["event_id"]], kind="events", mode="erase_content",
                      expected_scope_generation=generation)
        assert client.affect_records()["records"] == []
    later = host.session_context(directory, "next week")
    assert "interview" not in later and "nervous" not in later


def test_the_service_refuses_an_inferred_feeling_without_its_source_message(brain):
    with pytest.raises(DomainError, match="inferred feeling needs the message"):
        write(brain, "Moving flat next month.", affect={**NERVOUS, "basis": "inferred"})
    source = say(brain, "ugh, the move is next month and nothing is packed")
    result = write(brain, "Moving flat next month.", source_event_ids=[source],
                   affect={"label": "stressed", "valence": -1, "intensity": 2, "basis": "inferred"})
    (listed,) = affect_records(*brain)["records"]
    assert listed["id"] == result["affect_id"] and listed["basis"] == "inferred"
    assert listed["source_event_ids"] == [source] and listed["written_by"] == "membrain-notes"
    # A note cannot cite a feeling (or another note) as its source.
    with pytest.raises(DomainError):
        write(brain, "Packing this weekend.", source_event_ids=[result["affect_id"]])


def test_correcting_the_note_deletes_its_feeling_and_deleting_a_feeling_keeps_the_note(brain):
    source = say(brain, "I'm so excited about the trip to Kyoto in April!")
    first = write(brain, "Trip to Kyoto in April.", kind="plan", source_event_ids=[source],
                  affect={"label": "so excited", "valence": 2, "intensity": 3, "basis": "reported"})
    corrected = write(brain, "Trip to Kyoto moved to May.", kind="plan", replaces=[first["note_id"]])
    assert affect_records(*brain)["records"] == []  # The correction did not carry the earlier reading.
    # A later reading is a new record; deleting it on the page erases the feeling and keeps the note.
    second = write(brain, "Trip to Kyoto in May.", kind="plan", replaces=[corrected["note_id"]],
                   affect={"label": "relieved", "valence": 1, "intensity": 1, "basis": "reported"})
    forget(brain, [second["affect_id"]], conversation=AFFECT_CONVERSATION)
    assert affect_records(*brain)["records"] == []
    service, principal, ident = brain
    current = service.timeline(principal, ident, roles=("assistant",), conversation_id=notes.NOTES_CONVERSATION)
    assert [entry["event_id"] for entry in current["items"]] == [second["note_id"]]


def test_clear_feelings_erases_every_record_writes_a_visible_marker_and_cannot_be_recomputed(brain):
    service, principal, ident = brain
    before = say(brain, "I'm worried about my mum's surgery on Monday.")
    kept = write(brain, "Mum's surgery is on Monday.", kind="plan", source_event_ids=[before], sensitive=True,
                 affect={"label": "worried", "valence": -2, "intensity": 2, "basis": "reported"})
    other = write(brain, "Prefers short replies.", kind="preference",
                  affect={"label": "fine", "valence": 0, "intensity": 0, "basis": "reported"})
    replaced = write(brain, "Prefers very short replies.", kind="preference", replaces=[other["note_id"]],
                     affect={"label": "happy", "valence": 1, "intensity": 1, "basis": "reported"})
    assert len(affect_records(*brain)["records"]) == 2

    result = clear_affect(*brain)
    assert result["cleared_records"] == 2
    marker = result["marker"]
    assert marker["marker"] == "cleared" and marker["recorded_at"] and marker["applies_from_sequence"] > 0
    listed = affect_records(*brain)
    assert listed["records"] == [] and listed["markers"][0]["id"] == marker["id"]
    # Every record is erased with tombstones, including the copy hidden when its note was corrected.
    with service.database.transaction(principal) as conn:
        rows = conn.execute(
            "SELECT id,deleted,document IS NULL AS erased FROM memory_events WHERE tenant_id=%s AND owner_id=%s "
            "AND brain_id=%s AND conversation_id=%s AND id<>%s", (*service._params(principal, ident),
                                                                  AFFECT_CONVERSATION, marker["id"])).fetchall()
        assert len(rows) == 3 and all(row["deleted"] and row["erased"] for row in rows)
        tombstones = conn.execute(
            "SELECT count(*) AS count FROM memory_tombstones WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND object_id=ANY(%s::text[]) AND mode='erase_content'",
            (*service._params(principal, ident), [row["id"] for row in rows])).fetchone()["count"]
        assert tombstones == 3
    # Notes and messages stay.
    current = service.timeline(principal, ident, roles=("assistant",), conversation_id=notes.NOTES_CONVERSATION)
    assert {entry["event_id"] for entry in current["items"]} == {kept["note_id"], replaced["note_id"]}
    assert service.timeline(principal, ident, roles=("user",), event_ids=[before])["items"]

    # Re-reading a message from before the marker never recreates a feeling; the note itself is still saved.
    again = write(brain, "Mum's surgery is on Monday at 9.", kind="plan", replaces=[kept["note_id"]],
                  source_event_ids=[before],
                  affect={"label": "worried", "valence": -2, "intensity": 2, "basis": "inferred"})
    assert again["affect_id"] is None and "cleared" in again["affect_refused"] and again["note_id"]
    assert affect_records(*brain)["records"] == []
    # A feeling expressed after the reset is kept.
    after = say(brain, "The surgery went well, I'm so relieved.")
    fresh = write(brain, "Mum's surgery went well.", kind="milestone", source_event_ids=[after],
                  affect={"label": "so relieved", "valence": 2, "intensity": 2, "basis": "reported"})
    assert [entry["id"] for entry in affect_records(*brain)["records"]] == [fresh["affect_id"]]
    assert fresh["affect_id"] and affect_records(*brain)["records"][0]["sequence"] > marker["applies_from_sequence"]

    # Erasing all memory removes the markers too.
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
                    "mode": "erase_content", "expected_scope_generation": generation}})
    assert affect_records(*brain) == {"records": [], "complete": True, "markers": []}


def test_affect_records_are_never_recalled_counted_or_shown_as_messages(brain):
    service, principal, ident = brain
    source = say(brain, "Honestly I'm dreading the dentist tomorrow.")
    write(brain, "Dentist appointment tomorrow.", kind="plan", source_event_ids=[source],
          affect={"label": "dreading", "valence": -2, "intensity": 2, "basis": "reported"})
    every = service.timeline(principal, ident, roles=("user", "assistant", "operator", "tool"),
                             max_characters=200_000)
    assert not any(entry["conversation_id"] == AFFECT_CONVERSATION for entry in every["items"])
    assert service.memory_status(principal, ident)["recorded_messages"] == 1


def test_the_memory_map_shows_one_emotion_per_record_linked_to_its_note(brain):
    source = say(brain, "I'm nervous about Friday's interview.")
    interview = write(brain, "Job interview on Friday.", kind="plan", source_event_ids=[source], affect=NERVOUS)
    private = write(brain, "Therapy on Tuesdays.", kind="routine", sensitive=True,
                    affect={"label": "anxious", "valence": -1, "intensity": 1, "basis": "reported"})
    result = memory_map(*brain)
    feelings = {node["id"]: node for node in result["nodes"] if node["region"] == "emotions"}
    assert set(feelings) == {"affect:" + interview["affect_id"], "affect:" + private["affect_id"]}
    shown = feelings["affect:" + interview["affect_id"]]
    assert shown["label"] == "nervous · Friday's interview" and shown["basis"] == "reported" and shown["kind"] == "affect"
    masked = feelings["affect:" + private["affect_id"]]
    assert masked["label"] == "Sensitive memory" and masked["basis"] is None and masked["date"] is None
    for ident, note_id in ((interview["affect_id"], interview["note_id"]), (private["affect_id"], private["note_id"])):
        assert {"source": "affect:" + ident, "target": "note:" + note_id, "type": "feeling_of",
                "basis": "note"} in result["edges"]
    assert {"source": "note:" + interview["note_id"], "target": "msg:" + source, "type": "derived_from",
            "basis": "source_event_ids"} in result["edges"]
    assert [region["id"] for region in result["regions"]] == list(REGIONS.values())
    assert next(region for region in result["regions"] if region["id"] == "emotions")["count"] == 2
    assert sum(region["count"] for region in result["regions"]) == len(result["nodes"])
    assert "anxious" in json.dumps(memory_map(*brain, include_sensitive=True))
    assert len(memory_map(*brain, max_nodes=2)["nodes"]) <= 2


def test_a_feeling_with_many_sources_still_appears_on_the_map(brain):
    sources = [say(brain, f"Message {index} about the move.") for index in range(64)]
    moving = write(brain, "Moving flat next month.", kind="plan", source_event_ids=sources,
                   affect={"label": "stressed", "valence": -1, "intensity": 2, "basis": "inferred",
                           "topic": "the move"})
    result = memory_map(*brain, max_nodes=200, max_edges=10)
    assert "affect:" + moving["affect_id"] in {node["id"] for node in result["nodes"]}


def learning_jobs(service, principal, ident):
    """Background learning was removed: no message or record queues an orient or consolidate job any more."""
    with service.database.transaction(principal) as conn:
        return conn.execute("SELECT count(*) AS value FROM memory_jobs WHERE tenant_id=%s AND brain_id=%s "
                            "AND kind IN ('orient','consolidate')", (principal.tenant_id, ident)).fetchone()["value"]


def test_saving_or_clearing_feelings_never_schedules_learning(brain):
    service, principal, ident = brain
    source = say(brain, "I'm thrilled about the new job.")
    write(brain, "Started a new job.", kind="milestone", source_event_ids=[source],
          affect={"label": "thrilled", "valence": 2, "intensity": 3, "basis": "reported"})
    from membrain.affect import clear_affect

    clear_affect(service, principal, ident)
    service.work_once(principal, ident)
    assert learning_jobs(service, principal, ident) == 0


def test_api_routes_list_and_clear_feelings_with_strict_bodies(installation, brain):
    service, principal, ident = brain
    headers = {"Authorization": "Bearer affect-test-key"}
    settings = replace(installation[1], api_keys={hashlib.sha256(b"affect-test-key").hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1") as client:
        body = {"request_id": uid(), "text": "Job interview on Friday.", "kind": "plan", "affect": NERVOUS}
        saved = client.post(f"/v1/brains/{ident}/notes", json=body, headers=headers).json()
        assert saved["affect_id"]
        for bad in ({**NERVOUS, "valence": 5}, {**NERVOUS, "valence": "-1"}, {**NERVOUS, "extra": 1},
                    {**NERVOUS, "basis": "inferred"}):
            response = client.post(f"/v1/brains/{ident}/notes", headers=headers,
                                   json={**body, "request_id": uid(), "affect": bad})
            assert response.status_code in (400, 422), bad
        listed = client.get(f"/v1/brains/{ident}/affect", headers=headers).json()
        assert [entry["label"] for entry in listed["records"]] == ["nervous"] and listed["markers"] == []
        assert "score" not in json.dumps(listed)
        cleared = client.post(f"/v1/brains/{ident}/affect/reset", headers=headers).json()
        assert cleared["cleared_records"] == 1 and cleared["marker"]["applies_from_sequence"]
        listed = client.get(f"/v1/brains/{ident}/affect", headers=headers).json()
        assert listed["records"] == [] and listed["markers"][0]["id"] == cleared["marker"]["id"]
        assert client.get(f"/v1/brains/{ident}/affect").status_code == 401
        assert client.get("/v1/brains/someone-else/affect", headers=headers).status_code in (403, 404)


def test_a_feeling_cannot_be_planted_by_writing_to_the_feelings_conversation(brain):
    service, principal, ident = brain
    text = json.dumps({"affect": {"label": "furious", "valence": -2, "intensity": 3, "basis": "reported"},
                       "note_id": None, "written_by": "someone", "source_event_ids": []})
    planted = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": AFFECT_CONVERSATION, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "membrain-affect", "actor_ref": "x",
            "actor_role": "system", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
        }]},
    })
    assert planted["outcome"] == "rejected" and planted["error"]["code"] == "invalid_evidence"
    assert affect_records(service, principal, ident)["records"] == []
