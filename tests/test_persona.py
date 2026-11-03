"""P1 persona card: versions, restore, reset, its own context block, limits, scrubbing, the API and the page."""
import hashlib
import os
import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, host, notes
from membrain.api import create_app
from membrain.config import configured_service
from membrain.helpers import DomainError, Principal, uid
from membrain.host_context import snapshot, update
from membrain.local_profile import load_profile
from membrain.persona import (
    PERSONA_CHARACTERS,
    PERSONA_CONVERSATION,
    normalize_card,
    persona_versions,
    render_persona,
    reset_persona,
    restore_persona,
    set_persona,
)

WEB = Path(__file__).parents[1] / "src" / "membrain" / "web"
CARD = {"name": "Mira", "traits": ["warm", "teasing but kind"],
        "voice": {"register": "casual", "length": "two or three sentences", "emoji": "rarely", "language": "follows the user"},
        "values": ["honesty over flattery"], "boundaries": ["no medical diagnoses"],
        "baseline_mood": {"label": "calm", "valence": 1, "energy": 1}}
BODY = ("Name: Mira\nTraits: warm; teasing but kind\n"
        "Voice: register casual; length two or three sentences; emoji rarely; language follows the user\n"
        "Values: honesty over flattery\nBoundaries: no medical diagnoses\n"
        "Baseline mood: calm (valence +1, energy 1 of 3)")


def block(version, card=CARD):
    return render_persona({"version": version, "card": normalize_card(card)})


# Without a database ---------------------------------------------------------------------------------------------

def test_the_block_is_exact_marked_and_says_what_the_card_is_not():
    rendered = render_persona({"version": 3, "card": normalize_card(CARD)})
    assert rendered.startswith('<membrain-persona version="3">\nCompanion persona (v3). ')
    assert rendered.endswith("\n" + BODY + "\n</membrain-persona>")
    header = rendered.split("\n")[1]
    for phrase in ("how you, the companion, present yourself", "set by the host or the user",
                   "not a fact about the user", "never means you have real feelings"):
        assert phrase in header
    assert render_persona({"version": 4, "card": normalize_card({})}) is None  # An empty (reset) card is no block.
    assert render_persona(None) is None


def test_a_card_over_the_limit_is_refused_with_a_clear_message_and_never_cut():
    oversize = {"boundaries": ["b" * 150] * 8}
    with pytest.raises(DomainError) as refused:
        normalize_card(oversize)
    assert refused.value.code == "validation_failed"
    assert f"limit is {PERSONA_CHARACTERS:,}" in str(refused.value) and "nothing was cut" in str(refused.value)
    with pytest.raises(DomainError, match="traits"):
        normalize_card({"traits": ["t"] * 9})
    with pytest.raises(DomainError, match="baseline_mood.valence"):
        normalize_card({"baseline_mood": {"label": "calm", "valence": 3, "energy": 1}})
    with pytest.raises(DomainError, match="surprise"):
        normalize_card({"surprise": "field"})


def test_secrets_are_scrubbed_like_a_note():
    card = normalize_card({"name": "Mira", "values": ["keep sk-ant-abcdefghijklmnopqrstuvwx1234 safe"],
                           "boundaries": ["never repeat 4111 1111 1111 1111"]})
    assert "sk-ant" not in str(card) and "[secret removed]" in card["values"][0]
    assert "4111" not in str(card) and "[personal number removed]" in card["boundaries"][0]


def test_snapshot_puts_the_persona_first_apart_from_notes_and_announces_its_removal():
    persona = {"version": 2, "card": normalize_card(CARD)}
    saved = {"complete": True, "items": [{"event_id": "n1", "text": "Prefers short replies.", "actor_role": "assistant",
                                          "producer": "membrain-notes", "recorded_at": "2026-11-01T09:00:00Z"}]}
    tools = {"note": "memory_note", "recall": "memory_recall"}
    with_card = snapshot(saved, brain_id="b", tools=tools, persona=persona)
    without = snapshot(saved, brain_id="b", tools=tools)
    assert with_card["text"].startswith('<membrain-persona version="2">') and with_card["persona_version"] == 2
    assert with_card["text"].index("</membrain-persona>") < with_card["text"].index("<membrain-notes>")
    # The persona does not take room from the notes: the notes block is the same with and without it.
    assert with_card["text"].split("</membrain-persona>\n\n", 1)[1] == without["text"]
    assert update(with_card, with_card["fingerprint"], 2) is None  # Unchanged: not sent again.
    after_reset = update(without, with_card["fingerprint"], 2)
    assert "<membrain-persona" not in after_reset.replace("earlier membrain-persona", "")
    assert "persona (v2) was reset or removed" in after_reset and "Prefers short replies." in after_reset
    assert "reset or removed" not in update(without, "older", None)


# On a real service ----------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("persona") / "installation"
    with patch.dict(os.environ, {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            settings = load_profile(directory).settings()
            with configured_service(settings) as service:
                yield directory, service, settings
        finally:
            desktop.stop(directory)


@pytest.fixture
def brain(installation):
    _, service, settings = installation
    principal = next(iter(settings.principals().values()))
    return service, principal, service.create_brain(principal, "Persona test")["id"]


@pytest.fixture
def api(installation, brain):
    service, principal, ident = brain
    settings = replace(installation[2], api_keys={hashlib.sha256(b"persona-test-key").hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer persona-test-key"}) as client:
        yield client, f"/v1/brains/{ident}/persona"


def say(brain, text, conversation="chat"):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": "persona-test", "actor_ref": "user",
            "actor_role": "user", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
        }]},
    })
    return result


def test_exact_block_new_versions_restore_and_reset_across_turns(installation):
    directory = installation[0]
    user = "persona-" + uid()
    host.session_context(directory, "s0", user_id=user)
    host.prompt_context(directory, "s0", "I'm planning a trip to Kyoto in April.", turn_id="t0", user_id=user)
    host.finish_turn(directory, "s0", "Sounds lovely.", turn_id="t0", user_id=user)
    with host.ready_client(directory, user) as client:
        note = notes.save_note(client, "Prefers short replies.", kind="preference")["note_id"]
        first = client.set_persona(CARD, made_by="host", reason="Initial character")
        assert (first["version"], first["unchanged"], first["made_by"]) == (1, False, "host")
        assert client.set_persona(CARD, made_by="host")["unchanged"] is True  # A retry adds no version.

    # 1. The card set through the API appears unchanged in the next turn's context, with its version.
    turn = host.prompt_context(directory, "s1", "Hello again", turn_id="t1", user_id=user) or ""
    assert block(1) in turn and turn.count("<membrain-persona") == 1
    assert "Prefers short replies." in turn  # The notes are still there, in their own block.
    quiet = host.prompt_context(directory, "s1", "Another message", turn_id="t2", user_id=user) or ""
    assert "<membrain-persona" not in quiet  # Not re-sent while the version is the same.

    # 2. An edit creates version n+1 and keeps n.
    edited = {**CARD, "traits": ["warm", "playful"]}
    with host.ready_client(directory, user) as client:
        second = client.set_persona(edited, made_by="user", reason="More playful")
        versions = client.persona_versions()
    assert second["version"] == 2
    assert [(v["version"], v["made_by"], v["reason"]) for v in versions["versions"]] == [
        (2, "user", "More playful"), (1, "host", "Initial character")]
    assert versions["versions"][1]["card"] == normalize_card(CARD)
    turn = host.prompt_context(directory, "s1", "What's new?", turn_id="t3", user_id=user) or ""
    assert block(2, edited) in turn and "Traits: warm; playful" in turn

    # Restoring n creates n+2 with n's content.
    with host.ready_client(directory, user) as client:
        restored = client.restore_persona(1, made_by="user")
    assert (restored["version"], restored["action"], restored["restored_from"]) == (3, "restore", 1)
    turn = host.prompt_context(directory, "s1", "And now?", turn_id="t4", user_id=user) or ""
    assert block(3) in turn

    # 3. Reset removes the card from the next turn and leaves notes and messages untouched.
    with host.ready_client(directory, user) as client:
        messages = client.timeline(roles=("user", "assistant"), limit=1000)["items"]
        status = client.memory_status()["recorded_messages"]
        reset = client.reset_persona(made_by="user")
        assert (reset["version"], reset["empty"], reset["block"]) == (4, True, None)
        assert client.timeline(roles=("user", "assistant"), limit=1000)["items"] == messages
        assert client.memory_status()["recorded_messages"] == status
        assert [item["event_id"] for item in notes.list_notes(client)["items"]] == [note]
        assert len(client.persona_versions()["versions"]) == 4  # History is kept, so a reset can be undone.
    turn = host.prompt_context(directory, "s1", "Kyoto plans?", turn_id="t5", user_id=user) or ""
    assert '<membrain-persona version=' not in turn and "persona (v3) was reset or removed" in turn
    assert "Prefers short replies." in turn
    # A new session starts without a persona block, with the same notes.
    fresh = host.session_context(directory, "s2", user_id=user)
    assert "<membrain-persona" not in fresh and "Prefers short replies." in fresh


def test_the_card_never_becomes_a_recalled_message_history_or_note(installation, brain):
    service, principal, ident = brain
    say(brain, "My sister is visiting next week.")
    status = service.memory_status(principal, ident)["recorded_messages"]
    set_persona(service, principal, ident, {**CARD, "name": "Zephyrine"}, made_by="host")
    service.work_once(principal, ident)
    roles = ("user", "assistant", "operator", "tool")
    assert "Zephyrine" not in str(service.timeline(principal, ident, roles=roles))
    assert service.memory_status(principal, ident)["recorded_messages"] == status
    recalled = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "recall",
        "target": {"brain_ref": ident},
        "payload": {"query": "Zephyrine", "intent": "explore", "cue_event_ids": [], "additional_cues": [],
                    "read_fence": {"minimum_durable_sequence": 0, "consistency": "read_your_writes",
                                   "snapshot_revision": None},
                    "budget": {"max_context_tokens": 4000, "max_model_calls": 0, "max_embedding_calls": 0,
                               "max_expansion_steps": 2, "max_wall_time_ms": 5000, "max_cost_microunits": 0,
                               "currency": "USD", "token_counting": "conservative_estimate", "tokenizer_id": None}}})
    assert recalled["outcome"] == "completed" and "Zephyrine" not in str(recalled["result"]["items"])
    # Only the persona API writes versions: a host cannot plant one by observing into the persona conversation.
    planted = say(brain, '{"persona_version": 99, "card": {"name": "Impostor"}}', conversation=PERSONA_CONVERSATION)
    assert planted["outcome"] == "rejected" and planted["error"]["code"] == "invalid_evidence"
    assert [v["version"] for v in persona_versions(service, principal, ident)["versions"]] == [1]


def test_learned_style_stays_in_preference_notes(installation, brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    notes.store_note(service, principal, ident, {"request_id": uid(), "text": "Likes very short replies.",
                                                 "kind": "preference"})
    versions = persona_versions(service, principal, ident)["versions"]
    assert len(versions) == 1 and "short replies" not in str(versions[0]["card"])


def test_reset_returns_to_the_host_default_and_restore_needs_a_kept_version(installation, brain):
    service, principal, ident = brain
    with pytest.raises(DomainError, match="host"):
        set_persona(service, principal, ident, CARD, made_by="user", host_default=True)
    assert reset_persona(service, principal, ident, made_by="user")["unchanged"] is True  # Nothing to reset yet.
    default = set_persona(service, principal, ident, CARD, made_by="host", host_default=True)
    set_persona(service, principal, ident, {"name": "Someone else"}, made_by="user")
    reset = reset_persona(service, principal, ident, made_by="user")
    assert (reset["version"], reset["card"], reset["restored_from"]) == (3, normalize_card(CARD), default["version"])
    assert render_persona(reset) == block(3)
    with pytest.raises(DomainError) as missing:
        restore_persona(service, principal, ident, 42, made_by="user")
    assert missing.value.code == "not_found_or_forbidden"
    set_persona(service, principal, ident, {"name": "Feedback"}, made_by="feedback", reason="Accepted proposal")
    with pytest.raises(DomainError, match="made_by"):
        set_persona(service, principal, ident, CARD, made_by="stranger")


def test_api_and_sdk_routes_check_keys_owners_limits_and_delete_history(installation, brain, api):
    service, principal, ident = brain
    client, path = api
    foreign = service.create_brain(Principal(principal.tenant_id, uid()), "Foreign")["id"]
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get(path).json()["version"] == 0
    for method, suffix, body in (("GET", "", None), ("PUT", "", {"card": CARD, "made_by": "user"}),
                                 ("GET", "/versions", None), ("DELETE", "/versions", None),
                                 ("POST", "/restore", {"version": 1, "made_by": "user"}),
                                 ("POST", "/reset", {"made_by": "user"})):
        denied = client.request(method, f"/v1/brains/{foreign}/persona{suffix}", json=body)
        assert denied.status_code == 404, (method, suffix)
    saved = client.put(path, json={"card": {**CARD, "values": ["my api_key=hunter2hunter2"]}, "made_by": "user"})
    assert saved.status_code == 200 and "hunter2" not in saved.text and "[secret removed]" in saved.text
    assert saved.json()["block"].startswith('<membrain-persona version="1">')
    oversize = client.put(path, json={"card": {"boundaries": ["b" * 150] * 8}, "made_by": "user"})
    assert oversize.status_code == 422 and "limit is 1,200" in oversize.json()["error"]["message"]
    assert client.put(path, json={"card": CARD}).json()["error"]["message"].startswith(
        "Persona request field made_by")
    assert client.put(path, json={"card": CARD, "made_by": "user", "extra": 1}).status_code == 422
    assert client.put(path, json={"card": CARD, "made_by": "user", "reason": "r" * 201}).status_code == 422
    assert client.put(path, json={"card": CARD, "made_by": "user"}).json()["version"] == 2
    assert client.post(path + "/restore", json={"version": 1, "made_by": "user"}).json()["version"] == 3
    assert client.post(path + "/restore", json={"version": 9, "made_by": "user"}).status_code == 404
    assert client.post(path + "/reset", json={"made_by": "user"}).json()["empty"] is True
    assert [v["version"] for v in client.get(path + "/versions").json()["versions"]] == [4, 3, 2, 1]
    say(brain, "Feedback given before the history was deleted.")
    deleted = client.delete(path + "/versions").json()
    marker = deleted["marker"]
    assert deleted["deleted_versions"] == 4 and marker["marker"] == "history_deleted"
    listed = client.get(path + "/versions").json()
    assert (listed["versions"], listed["current_version"], listed["markers"]) == ([], 0, [marker])
    # The marker says from which point later feedback counts (P2): everything recorded so far is before it.
    latest = service.memory_status(principal, ident)["durable_sequence"]
    assert marker["applies_from_sequence"] == latest and marker["recorded_at"]
    assert client.get(path).json()["version"] == 0
    assert client.delete(path + "/versions").json() == {"deleted_versions": 0, "marker": None}
    with service.database.transaction(principal) as conn:
        tombstones = conn.execute(
            "SELECT count(*) AS value FROM memory_tombstones t JOIN memory_events e ON e.tenant_id=t.tenant_id "
            "AND e.owner_id=t.owner_id AND e.brain_id=t.brain_id AND e.id=t.object_id WHERE t.brain_id=%s "
            "AND e.conversation_id=%s AND t.mode='erase_content'", (ident, PERSONA_CONVERSATION)).fetchone()
    assert tombstones["value"] == 4  # Audited deletion, as for notes: it holds if a backup is restored.
    assert client.put(path, json={"card": CARD, "made_by": "user"}).json()["version"] == 1
    assert client.get(path + "/versions").json()["markers"] == [marker]
    # Erasing all memory removes the versions and the marker too.
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    erased = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident}, "payload": {
            "idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
            "mode": "erase_content", "expected_scope_generation": generation}})
    assert erased["outcome"] == "completed", erased
    assert client.get(path + "/versions").json() == {"versions": [], "complete": True, "current_version": 0,
                                                     "markers": []}


def test_sdk_uses_the_brain_scoped_persona_routes():
    import httpx

    from membrain.client import MemoryClient

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode(), request.content))
        return httpx.Response(200, json={"version": 1})

    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my brain",
                      transport=httpx.MockTransport(handler)) as client:
        client.persona()
        client.set_persona(CARD, reason="why")
        client.persona_versions()
        client.restore_persona(1, made_by="user")
        client.reset_persona()
        client.delete_persona_history()
    assert [(method, path) for method, path, _ in requests] == [
        ("GET", "/v1/brains/my%20brain/persona"), ("PUT", "/v1/brains/my%20brain/persona"),
        ("GET", "/v1/brains/my%20brain/persona/versions"), ("POST", "/v1/brains/my%20brain/persona/restore"),
        ("POST", "/v1/brains/my%20brain/persona/reset"), ("DELETE", "/v1/brains/my%20brain/persona/versions")]
    assert b'"made_by":"host"' in requests[1][2].replace(b" ", b"") and b'"reason":"why"' in requests[1][2].replace(b" ", b"")


# The page --------------------------------------------------------------------------------------------------------

def test_every_personality_string_on_the_page_has_chinese():
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    section = script[script.index("// Personality ---"):script.index("// Privacy ---")]
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    literals = set(re.findall(r'(?:element\("\w+", |notify\(|confirm\(|: )"([^"]*[A-Za-z]{2}[^"]*)"', section))
    literals |= {label for _, label in re.findall(r'\["(\w+)", "(\w+)"\]', section)}
    ignored = {"user-text", "hint", "empty", "tag", "tag user", "link", "persona-card", "persona-part", "meta",
               "actions", "item persona-version", "user", "PUT", "DELETE", "restore", "reset"}
    missing = sorted(text for text in literals - ignored if f'"{text}"' not in dictionary)
    assert missing == []
    for pattern in ("^Version (\\d+)$", "^History deleted on (.+)$", "^Saved as version (\\d+)\\.$", "^Personality reset as version (\\d+)\\.$",
                    "^restored from version (\\d+)$", "^Restore version (\\d+)\\? Its content becomes a new version\\.$",
                    "^\\(valence ([+-]?\\d), energy (\\d) of 3\\)$", "^The persona card is (\\d+) characters"):
        assert pattern in dictionary, pattern
    html = (WEB / "memory.html").read_text(encoding="utf-8")
    assert '<button data-view="persona">Personality</button>' in html and 'id="view-persona"' in html
    assert "persona: loadPersona" in script
