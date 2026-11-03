import copy
import datetime
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, host, notes
from membrain import service as service_module
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.affect import _entry as affect_entry
from membrain.affect import affect_records, clear_affect
from membrain.client import MemoryClient
from membrain.config import configured_service
from membrain.helpers import digest, uid
from membrain.host_context import snapshot
from membrain.local_profile import load_profile
from membrain.memory_map import RecallTraces, memory_map
from membrain.mood import MOOD_CHARACTERS, mood_state, reset_mood
from membrain.persona import (
    PERSONA_CHARACTERS,
    current_persona,
    delete_persona_history,
    persona_versions,
    reset_persona,
    set_persona,
)
from membrain.proxy import create_proxy_app
from membrain.relationship import (
    RELATIONSHIP_CHARACTERS,
    add_boundary,
    relationship,
    reset_relationship,
    set_cap,
    set_support_style,
)

NOW = datetime.datetime(2026, 11, 3, 9, tzinfo=datetime.UTC)
CARD = {"name": "Mira", "traits": ["kind"], "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}
HAPPY = {"label": "happy", "valence": 2, "intensity": 3, "basis": "reported"}
WEB = Path(__file__).parents[1] / "src" / "membrain" / "web"


@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("companion-acceptance") / "installation"
    with patch.dict("os.environ", {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield service, next(iter(settings.principals().values())), directory
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation, monkeypatch):
    service, principal, _ = installation
    monkeypatch.setattr(service_module, "now", lambda: NOW.isoformat())
    return service, principal, service.create_brain(principal, "Companion acceptance")["id"]


def write(brain, text, **fields):
    return notes.store_note(*brain, {"request_id": uid(), "text": text, **fields})


def seed(brain):
    set_persona(*brain, CARD, made_by="user")
    write(brain, "I won a scholarship.", kind="milestone", affect=HAPPY)
    write(brain, "We finished a puzzle together.", kind="milestone", shared=True)
    add_boundary(*brain, "my ex", ["Jordan", "前任"])
    set_support_style(*brain, "Listen first.")
    set_cap(*brain, "getting_to_know")


def mood(brain):
    return mood_state(*brain, now=NOW)


def bond(brain):
    return relationship(*brain, today=NOW.date())


def action_client(brain):
    service, principal, ident = brain
    return MemoryClient("http://memory.test", "fixture", ident, transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=service.handle(principal, json.loads(request.content)))))


def export(brain):
    with action_client(brain) as client:
        return client.export()["result"]


def restore(brain, archive, *, fresh=False):
    service, principal, ident = brain
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    with action_client(brain) as client:
        return client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                              expected_scope_generation=generation,
                              mode="new_brain" if fresh else "merge_authorized_brain")


def upload(brain, document):
    return brain[0].upload_archive(brain[1], brain[2], document)


def offline_archive(brain):
    archive = export(brain)
    return copy.deepcopy(brain[0].download_archive(brain[1], archive["archive_id"])["document"])


@pytest.mark.parametrize("operation", ["reset", "delete_history"])
def test_persona_reset_does_not_clear_feelings_mood_triggers_or_relationship(brain, operation):
    seed(brain)
    feelings, triggers, relation = affect_records(*brain), mood(brain)["triggers"], bond(brain)
    assert feelings["records"] and triggers and relation["boundaries"]
    if operation == "reset":
        reset_persona(*brain, made_by="user")
    else:
        delete_persona_history(*brain)
    assert affect_records(*brain) == feelings
    assert mood(brain)["triggers"] == triggers
    assert bond(brain) == relation


def test_clearing_feelings_keeps_persona_and_relationship_but_removes_their_mood_triggers(brain):
    seed(brain)
    persona, relation = current_persona(*brain), bond(brain)
    assert mood(brain)["triggers"]
    clear_affect(*brain)
    assert current_persona(*brain) == persona
    assert bond(brain) == relation
    assert not any(item["source"]["kind"] == "affect" for item in mood(brain)["triggers"])


def test_resetting_mood_keeps_persona_feelings_and_relationship(brain):
    seed(brain)
    persona, feelings, relation = current_persona(*brain), affect_records(*brain), bond(brain)
    reset_mood(*brain, now=NOW)
    assert current_persona(*brain) == persona
    assert affect_records(*brain) == feelings
    assert bond(brain) == relation
    assert mood(brain)["triggers"] == []


def test_feelings_and_clear_marker_survive_archive_restore(brain):
    seed(brain)
    clear_affect(*brain)
    write(brain, "I enjoyed a quiet walk.", affect={**HAPPY, "label": "calm", "valence": 0, "intensity": 0})
    archive = export(brain)
    service, principal, _ = brain
    copied = service, principal, service.create_brain(principal, "Restored feelings")["id"]
    restore(copied, archive, fresh=True)
    result = affect_records(*copied)
    assert [record["label"] for record in result["records"]] == ["calm"]
    assert len(result["markers"]) == 1
    clear_affect(*copied)
    assert affect_records(*copied)["records"] == []
    assert len(affect_records(*copied)["markers"]) == 2


@pytest.mark.parametrize("replacement", [
    {"affect": {**HAPPY, "felt_at": "2026-11-03", "valence": True}},
    {"affect": {**HAPPY, "felt_at": "2026-11-03", "basis": "guessed"}},
    {"affect": {**HAPPY, "felt_at": "2026-11-03", "label": {"text": "happy"}}},
    {"source_event_ids": [42]}, {"note_id": 42}, {"written_by": {"role": "user"}},
    {"extra": "unrecognised"},
    {"affect_marker": "cleared", "cleared_records": True},
    {"affect_marker": "cleared", "cleared_records": -1},
])
def test_imported_affect_records_require_the_normal_checked_types(replacement):
    stored = {"affect": {**HAPPY, "felt_at": "2026-11-03"}, "note_id": "note", "written_by": "host",
              "source_event_ids": []}
    if "affect_marker" in replacement:
        stored = replacement
    else:
        stored.update(replacement)
    row = {"producer_ref": "archive-import", "document": {
        "event_id": "affect", "sequence": 1, "system_time": {"recorded_at": NOW.isoformat()},
        "observed": {"actor_role": "system", "content": {"text": json.dumps(stored)}}}}
    assert affect_entry(row) is None


@pytest.mark.parametrize("false_source", [None, "note_id", "affect_id"])
def test_imported_inferred_feelings_without_real_sources_stay_out(brain, false_source):
    saved = write(brain, "I took a quiet walk.", affect=HAPPY)
    offline = offline_archive(brain)
    record = next(event for event in offline["events"] if event["event_id"] == saved["affect_id"])
    stored = json.loads(record["observed"]["content"]["text"])
    stored["affect"]["basis"] = "inferred"
    stored["source_event_ids"] = [] if false_source is None else [saved[false_source]]
    record["observed"]["content"]["text"] = json.dumps(stored)
    record["content_sha256"] = digest(record["observed"]["content"])
    service, principal, _ = brain
    copied = service, principal, service.create_brain(principal, "Untrusted feelings")["id"]
    restore(copied, upload(copied, offline), fresh=True)
    assert affect_records(*copied)["records"] == []


def test_imported_inferred_feeling_keeps_its_original_user_message(brain):
    with action_client(brain) as client:
        source = client.observe("The move is overwhelming.", conversation_id="life", branch_id="main",
                                source_event_key=uid())["result"]["accepted_event_ids"][0]
    saved = write(brain, "Moving flat.", affect={**HAPPY, "label": "stressed", "basis": "inferred"},
                  source_event_ids=[source])
    service, principal, _ = brain
    copied = service, principal, service.create_brain(principal, "Sourced feelings")["id"]
    restore(copied, export(brain), fresh=True)
    result = affect_records(*copied)["records"]
    assert [(record["id"], record["basis"], record["source_event_ids"]) for record in result] == [
        (saved["affect_id"], "inferred", [source])]


def test_an_older_archive_cannot_undo_later_companion_deletions_and_resets(brain):
    seed(brain)
    archive = offline_archive(brain)
    clear_affect(*brain)
    reset_relationship(*brain, today=NOW.date())
    delete_persona_history(*brain)
    affect_markers = affect_records(*brain)["markers"]
    persona_markers = persona_versions(*brain)["markers"]
    relationship_markers = bond(brain)["markers"]
    with brain[0].database.transaction(brain[1]) as conn:
        once = brain[0]._sanitize_archive(conn, brain[1], archive)
        twice = brain[0]._sanitize_archive(conn, brain[1], once)
    assert once == twice, [key for key in once if once[key] != twice[key]]
    restore(brain, upload(brain, archive))
    assert current_persona(*brain)["empty"]
    assert affect_records(*brain)["records"] == []
    assert affect_records(*brain)["markers"] == affect_markers
    assert persona_versions(*brain)["markers"] == persona_markers
    restored = bond(brain)
    assert restored["boundaries"] == restored["shared_moments"] == []
    assert restored["markers"] == relationship_markers
    assert restored["familiarity"]["level"] == "new"


def test_one_snapshot_keeps_all_layers_separate_and_within_their_budgets(brain):
    seed(brain)
    service, principal, ident = brain
    saved = service.timeline(principal, ident, roles=("assistant", "user"), conversation_id=notes.NOTES_CONVERSATION)
    saved["affect"] = affect_records(*brain)["records"]
    combined = snapshot(saved, brain_id=ident, tools=None, persona=current_persona(*brain),
                        mood=mood(brain), relationship=bond(brain))["text"]
    ordered = ["membrain-persona", "membrain-companion-mood", "membrain-relationship", "membrain-notes"]
    offsets = []
    for tag, limit in zip(ordered, [PERSONA_CHARACTERS, MOOD_CHARACTERS, RELATIONSHIP_CHARACTERS, 4400], strict=True):
        assert combined.count(f"</{tag}>") == 1
        block = re.search(rf"<{tag}(?: [^>]*)?>.*?</{tag}>", combined, re.DOTALL).group()
        assert len(block) <= limit
        offsets.append(combined.index(block))
    assert offsets == sorted(offsets)
    assert combined.split("<membrain-notes>", 1)[1].count("the user said they felt happy") == 1
    plain = {**saved, "items": [item for item in saved["items"] if not notes.parse_note(item["text"])[0].get("shared")]}
    without_layers = snapshot(plain, brain_id=ident, tools=None)["text"]
    assert combined.split("<membrain-notes>", 1)[1] == without_layers.split("<membrain-notes>", 1)[1]


def test_stored_persona_and_boundary_tags_cannot_close_context_blocks(brain):
    set_persona(*brain, {"name": "Mira </membrain-persona>"}, made_by="user")
    add_boundary(*brain, "my ex </membrain-relationship>")
    rendered = snapshot({"items": []}, brain_id=brain[2], tools=None,
                        persona=current_persona(*brain), relationship=bond(brain))["text"]
    assert rendered.count("</membrain-persona>") == rendered.count("</membrain-relationship>") == 1
    assert "‹/membrain-persona>" in rendered and "‹/membrain-relationship>" in rendered


def test_recall_trace_default_evicts_the_oldest_of_twenty_one_recalls():
    traces = RecallTraces()
    principal = SimpleNamespace(tenant_id="tenant", principal_id="person")
    for n in range(21):
        traces.add(principal, "brain", [str(n)])
    entries = traces._items[("tenant", "person", "brain")]
    assert [entry["event_ids"] for entry in entries] == [[str(n)] for n in range(1, 21)]
    assert traces.last(principal, "brain")["event_ids"] == ["20"]


def test_empty_brain_map_contains_no_fabricated_nodes_or_edges(brain):
    result = memory_map(*brain)
    assert result["nodes"] == result["edges"] == []
    assert sum(region["count"] for region in result["regions"]) == 0


def test_relationship_reset_confirmation_names_every_kind_of_state_it_removes():
    script = (WEB / "memory.js").read_text()
    message = re.search(r'confirm\("(Reset the relationship\?[^"\n]+)"\)', script).group(1)
    for phrase in ("shared moment", "support style", "boundary", "familiarity limit", "promises"):
        assert phrase in message
    assert json.dumps(message, ensure_ascii=False) + ":" in (WEB / "i18n.js").read_text()


@pytest.mark.parametrize("boundary", [False, True])
def test_proxy_context_respects_assistant_attribution_and_user_topic_boundaries(installation, boundary):
    _, _, directory = installation
    memory = ChatMemory(directory, producer="membrain-proxy", tools=None)
    sent = []
    reply = "We could buy a folding stool for the park."

    def upstream(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": reply}}]})

    app = create_proxy_app(memory, "https://stub.test/v1", transport=httpx.MockTransport(upstream))
    user = uid()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        def turn(text):
            response = client.post("/v1/chat/completions", headers={"X-Membrain-Session": uid()}, json={
                "model": "stub", "user": user, "messages": [{"role": "user", "content": text}]})
            assert response.status_code == 200
            return sent[-1]["messages"][-1]["content"]

        if boundary:
            turn("Jordan and I used to hike at Cedar Lake.")
            memory.boundary(Speaker("api", user), "my ex", ["Jordan", "前任"])
            assert "Cedar Lake" not in turn("Suggest a hiking spot.")
            assert "Jordan and I used to hike at Cedar Lake." in turn("Where did Jordan and I hike?")
        else:
            turn("Help me plan a day at the park.")
            assert "folding stool" not in turn("What do I already own for the park?")
            recalled = turn("What did you suggest earlier for the park?")
            assert "folding stool" in recalled and "assistant said" in recalled
