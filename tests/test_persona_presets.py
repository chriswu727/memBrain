"""Preset personas: a new memory's first persona is a preset picked at random, once; the user switches presets when
they ask, and switching changes only the card: one relationship and one mood, whatever the persona. Nothing calls a
model; the random choice is injected wherever the result matters."""
import datetime
import hashlib
import json
import re
import threading
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_persona_growth import CARD, said
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation

from membrain import persona_presets
from membrain.api import create_app
from membrain.helpers import DomainError, Principal, uid
from membrain.mood import derive, mood_state
from membrain.notes import store_note
from membrain.persona import (
    PERSONA_CHARACTERS,
    current_persona,
    delete_persona_history,
    normalize_card,
    persona_versions,
    render_persona,
    reset_persona,
    restore_persona,
    set_persona,
)
from membrain.persona_presets import (
    IDS,
    PRESETS,
    assign_first_persona,
    current_choice,
    listing,
    switch_preset,
)
from membrain.relationship import add_boundary, relationship, set_support_style

ROOT = Path(__file__).parents[1]
WEB = ROOT / "src" / "membrain" / "web"
UTC = datetime.UTC
JOB = {"label": "thrilled", "valence": 2, "intensity": 3, "basis": "reported", "topic": "the new job"}


def first(brain, ident="wry"):
    service, principal, brain_id = brain
    return assign_first_persona(service, principal, brain_id, choose=lambda ids: ident)


# Without a database ---------------------------------------------------------------------------------------------

def test_every_preset_validates_renders_within_limits_and_leaves_the_name_to_the_host():
    assert IDS == ("steady", "bright", "wry", "gentle", "blunt") and len(set(IDS)) == len(IDS)
    for preset in PRESETS:
        assert set(preset) == {"id", "label", "summary", "card"}
        assert preset["label"] and "\n" not in preset["summary"] and len(preset["summary"]) <= 80
        card = normalize_card(preset["card"])
        assert card["name"] == "" and card["voice"]["language"] == ""  # The host's name, the user's language.
        assert card["traits"] and card["values"] and card["baseline_mood"]
        block = render_persona({"version": 1, "card": card})
        assert block.startswith('<membrain-persona version="1">') and len(block) < PERSONA_CHARACTERS
        # The block's header, not the card, says the persona has no real feelings and follows the user.
        assert "do not claim to feel emotions" in block and "follow the user" in block
        assert not re.search(r"\b(?:I feel|real feelings|always|ignore)\b", json.dumps(preset["card"]), re.I)


def test_each_preset_baseline_is_its_resting_mood_and_the_mood_rules_still_move_it():
    start = datetime.datetime(2027, 3, 14, 21, tzinfo=UTC)
    for preset in PRESETS:
        baseline = {**preset["card"]["baseline_mood"], "source": "persona"}
        rest = derive(baseline, [], [], start)
        assert (rest["label"], rest["at_baseline"]) == (baseline["label"], True)
        for rule, label in (("reported_good_news", "glad"), ("reported_distress", "concerned"),
                            ("shared_play", "playful")):
            trigger = {"rule": rule, "strength": 1.0, "at": start, "sequence": 1, "reason": "test",
                       "source": {"kind": "affect", "id": "a1"}}
            moved = derive(baseline, [trigger], [], start + datetime.timedelta(hours=1))
            assert (moved["at_baseline"], moved["label"]) == (False, label), (preset["id"], rule)


def test_the_current_choice_names_the_preset_a_custom_card_or_none():
    wry = {"version": 3, "empty": False, "preset": "wry", "based_on": None}
    assert current_choice(wry) == {"kind": "preset", "version": 3, "based_on": None, "preset": {
        "id": "wry", "label": "Wry", "summary": PRESETS[2]["summary"]}}
    edited = current_choice({"version": 4, "empty": False, "preset": None, "based_on": "wry"})
    assert (edited["kind"], edited["preset"], edited["based_on"]["id"]) == ("custom", None, "wry")
    assert current_choice({"version": 5, "empty": True, "preset": None})["kind"] == "none"
    assert current_choice({"version": 0})["kind"] == "none"
    # A preset id no longer in the table reads as a card of its own.
    assert current_choice({"version": 6, "empty": False, "preset": "retired"})["kind"] == "custom"
    with pytest.raises(DomainError, match="preset must be one of steady, bright, wry, gentle, blunt or random"):
        persona_presets.preset("cheerful")


def test_the_page_shows_and_switches_presets_in_english_and_chinese():
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    current = page.split('class="card persona-current"', 1)[1].split("<!--", 1)[0]
    assert 'id="persona-preset"' in current and 'id="persona-preset-choice"' in current
    assert 'id="persona-preset-switch"' in current
    assert 'api(personaPath("/presets"))' in script and 'api(personaPath("/preset"), {' in script
    for preset in PRESETS:  # The service's labels and summaries are interface text, translated whole.
        assert f'"{preset["label"]}": "' in dictionary and f'"{preset["summary"]}": "' in dictionary
    for text in ("Preset:", "Your own card", "No preset", "based on", "first preset, picked at random",
                 "switched preset", "Switch to a preset", "Switch"):
        assert f'"{text}": "' in dictionary, text


def test_the_sdk_reaches_the_preset_routes():
    from membrain.client import MemoryClient

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode(),
                         json.loads(request.content) if request.content else None))
        return httpx.Response(200, json={})

    reference = {"producer_ref": "p", "source_event_key": "k", "source_revision": 1}
    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my brain",
                      transport=httpx.MockTransport(handler)) as client:
        client.persona_presets()
        client.assign_first_persona()
        client.switch_persona_preset("random", source_messages=[reference])
    assert requests == [
        ("GET", "/v1/brains/my%20brain/persona/presets", None), ("POST", "/v1/brains/my%20brain/persona/first", None),
        ("POST", "/v1/brains/my%20brain/persona/preset", {"preset": "random", "made_by": "user",
                                                           "source_event_ids": [], "source_messages": [reference]})]


# On a real service ---------------------------------------------------------------------------------------------

def test_a_new_memory_gets_one_preset_once_and_reset_returns_to_it(brain):
    service, principal, ident = brain
    chosen = []
    given = assign_first_persona(service, principal, ident, choose=lambda ids: chosen.append(ids) or "gentle")
    assert chosen == [IDS] and given["assigned"] is True and given["preset"]["label"] == "Gentle"
    saved = given["persona"]
    assert (saved["version"], saved["made_by"], saved["action"], saved["host_default"], saved["preset"]) == (
        1, "host", "preset", True, "gentle")
    assert saved["card"] == persona_presets.card("gentle") and saved["block"]
    assert first(brain, "blunt") == {"assigned": False, "preset": None}  # Never twice.
    assert len(persona_versions(service, principal, ident)["versions"]) == 1
    assert listing(service, principal, ident)["current"]["preset"]["id"] == "gentle"
    # A user who later edits and resets gets the random first preset back, still as that preset.
    set_persona(service, principal, ident, CARD, made_by="user")
    back = reset_persona(service, principal, ident, made_by="user")
    assert (back["version"], back["preset"], back["restored_from"]) == (3, "gentle", 1)
    assert listing(service, principal, ident)["current"]["kind"] == "preset"


def test_without_a_choice_the_first_preset_is_random(brain):
    service, principal, ident = brain
    given = assign_first_persona(service, principal, ident)
    assert given["assigned"] and given["preset"]["id"] in IDS


@pytest.mark.parametrize("earlier", ["reset_to_empty", "deleted_history", "deleted_empty_history", "own_card"])
def test_a_memory_that_ever_had_a_persona_record_gets_no_preset(brain, earlier):
    service, principal, ident = brain
    if earlier == "reset_to_empty":
        set_persona(service, principal, ident, CARD, made_by="user")
        reset_persona(service, principal, ident, made_by="user")  # No host default: an empty card.
    elif earlier == "deleted_history":
        set_persona(service, principal, ident, CARD, made_by="user")
        delete_persona_history(service, principal, ident)
    elif earlier == "deleted_empty_history":
        delete_persona_history(service, principal, ident)  # Only the "history deleted" marker.
    else:
        set_persona(service, principal, ident, CARD, made_by="host")
    before = current_persona(service, principal, ident)
    assert first(brain) == {"assigned": False, "preset": None}
    assert current_persona(service, principal, ident) == before


def test_concurrent_first_assignments_save_one_version(brain):
    service, principal, ident = brain
    barrier, results = threading.Barrier(6), []

    def assign(ident_):
        barrier.wait()
        results.append(assign_first_persona(service, principal, ident, choose=lambda ids: ident_))

    threads = [threading.Thread(target=assign, args=(preset,)) for preset in (*IDS, "wry")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(result["assigned"] for result in results) == 1
    versions = persona_versions(service, principal, ident)["versions"]
    assert [version["version"] for version in versions] == [1]
    assert versions[0]["preset"] == next(result["preset"]["id"] for result in results if result["assigned"])


def mood_and_relationship(brain, when):
    service, principal, ident = brain
    mood = mood_state(service, principal, ident, now=when)
    bond = relationship(service, principal, ident, today=when.date())
    return mood, {key: bond[key] for key in ("familiarity", "shared_moments", "boundaries", "support_style",
                                              "commitments", "markers")}


def test_switching_presets_changes_only_the_card_and_the_moods_resting_point(brain):
    service, principal, ident = brain
    first(brain, "steady")
    news = said(brain, "I got the job!!")
    store_note(service, principal, ident, {"request_id": uid(), "text": "Got the job at Acme.", "kind": "milestone",
                                           "affect": JOB, "source_event_ids": [news]})
    store_note(service, principal, ident, {"request_id": uid(), "text": "We laughed about the cake together.",
                                           "kind": "milestone", "shared": True, "moment": "play"})
    add_boundary(service, principal, ident, "my ex", ["前任"])
    set_support_style(service, principal, ident, "listen first, advice only when asked")
    when = datetime.datetime.now(UTC)
    mood_before, bond_before = mood_and_relationship(brain, when)
    assert mood_before["triggers"] and bond_before["shared_moments"] and bond_before["boundaries"]
    request = said(brain, "Switch to the wry one, please.")

    switched = switch_preset(service, principal, ident, "wry", source_event_ids=[request])
    assert (switched["version"], switched["preset"], switched["made_by"], switched["action"]) == (2, "wry", "user",
                                                                                                  "preset")
    assert switched["source"] == {"event_id": request} and switched["choice"]["preset"]["id"] == "wry"
    mood_after, bond_after = mood_and_relationship(brain, when)
    assert bond_after == bond_before  # One relationship, whatever the persona.
    assert mood_after["triggers"] == mood_before["triggers"]  # Every trigger, with its status and reason.
    assert mood_before["baseline"]["label"] == "calm" and mood_after["baseline"] == {
        **persona_presets.card("wry")["baseline_mood"], "source": "persona"}
    for key in ("pinned", "pinned_at", "marker"):  # No pin, reset or marker comes with a switch.
        assert mood_after[key] == mood_before[key], key


def test_switching_checks_the_preset_and_the_source_and_random_picks_another(brain):
    service, principal, ident = brain
    first(brain, "bright")
    with pytest.raises(DomainError, match="preset must be one of"):
        switch_preset(service, principal, ident, "cheerful")
    reply = said(brain, "Sure, switching.", role="assistant")
    with pytest.raises(DomainError) as refused:
        switch_preset(service, principal, ident, "wry", source_event_ids=[reply])
    assert refused.value.code == "source_unavailable"
    with pytest.raises(DomainError, match="Cite"):
        switch_preset(service, principal, ident, "wry", source_event_ids=["a", "b"])
    assert switch_preset(service, principal, ident, "bright")["unchanged"] is True  # Already current.
    offered = []
    other = switch_preset(service, principal, ident, "random", choose=lambda ids: offered.append(ids) or ids[-1])
    assert offered == [tuple(item for item in IDS if item != "bright")] and other["preset"] == "blunt"
    # A reference to the current message, not recorded yet, is kept as the source.
    reference = {"producer_ref": "growth-test", "source_event_key": "turn-" + uid(), "source_revision": 1}
    kept = switch_preset(service, principal, ident, "steady", source_messages=[reference])
    assert kept["source"] == {"message": reference}


def test_an_edited_preset_is_a_custom_card_based_on_it_and_restoring_the_preset_is_the_preset_again(brain):
    service, principal, ident = brain
    first(brain, "wry")
    edited = set_persona(service, principal, ident, {**persona_presets.card("wry"), "name": "Pip"}, made_by="user")
    assert (edited["preset"], edited["based_on"]) == (None, "wry")
    choice = listing(service, principal, ident)["current"]
    assert (choice["kind"], choice["based_on"]["label"]) == ("custom", "Wry")
    again = set_persona(service, principal, ident, {**persona_presets.card("wry"), "name": "Pippa"}, made_by="user")
    assert again["based_on"] == "wry"
    restored = restore_persona(service, principal, ident, 1, made_by="user")
    assert (restored["preset"], restored["based_on"]) == ("wry", None)
    host_card = set_persona(service, principal, ident, CARD, made_by="host")  # The host's own card is its own.
    assert (host_card["preset"], host_card["based_on"]) == (None, None)


def test_the_preset_routes_check_keys_owners_and_bodies(installation, brain):
    service, principal, ident = brain
    settings = replace(installation[2], api_keys={hashlib.sha256(b"preset-test-key").hexdigest(): principal})
    foreign = service.create_brain(Principal(principal.tenant_id, uid()), "Foreign")["id"]
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer preset-test-key"}) as api:
        base = f"/v1/brains/{ident}/persona"
        assert api.post(f"{base}/first", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert api.post(f"/v1/brains/{foreign}/persona/first").status_code == 404
        given = api.post(f"{base}/first").json()
        assert given["assigned"] is True and given["preset"]["id"] in IDS
        assert api.post(f"{base}/first").json() == {"assigned": False, "preset": None}
        listed = api.get(f"{base}/presets").json()
        assert [item["id"] for item in listed["presets"]] == list(IDS)
        assert listed["current"]["preset"]["id"] == given["preset"]["id"]
        assert api.post(f"{base}/preset", json={"preset": "wry", "made_by": "feedback"}).status_code == 422
        assert api.post(f"{base}/preset", json={"preset": "wry", "note": "x"}).status_code == 422
        assert api.post(f"{base}/preset", json={"preset": "cheerful"}).status_code == 422
        target = "wry" if given["preset"]["id"] != "wry" else "steady"
        switched = api.post(f"{base}/preset", json={"preset": target})
        assert switched.status_code == 200 and switched.json()["choice"]["preset"]["id"] == target
