"""Personality types: a new memory's first persona is one of sixteen types (the four-letter types familiar from MBTI),
picked at random, once; the user switches type, or picks again at random, when they ask, and switching changes only
the card: one relationship and one mood, whatever the persona. Nothing calls a model; the random choice is injected
wherever the result matters."""
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
    render_card,
    render_persona,
    reset_persona,
    restore_persona,
    set_persona,
)
from membrain.persona_presets import (
    IDS,
    POLES,
    PRESETS,
    SUMMARIES,
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
TYPES = ("INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP", "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP",
         "ISFP", "ESTP", "ESFP")


def first(brain, ident="entp"):
    service, principal, brain_id = brain
    return assign_first_persona(service, principal, brain_id, choose=lambda ids: ident)


# Without a database ---------------------------------------------------------------------------------------------

def test_sixteen_types_validate_render_within_limits_and_leave_the_name_to_the_host():
    assert IDS == tuple(code.lower() for code in TYPES) and set(SUMMARIES) == set(TYPES)
    for preset in PRESETS:
        assert set(preset) == {"id", "label", "summary", "card"} and preset["label"] == preset["id"].upper()
        assert "\n" not in preset["summary"] and len(preset["summary"]) <= 90
        card = normalize_card(preset["card"])
        assert card["name"] == "" and card["voice"]["language"] == ""  # The host's name, the user's language.
        assert 250 <= len(render_card(card)) <= 360, (preset["id"], len(render_card(card)))
        block = render_persona({"version": 1, "card": card})
        assert block.startswith('<membrain-persona version="1">') and len(block) < PERSONA_CHARACTERS
        # The block's header, not the card, says the persona has no real feelings and follows the user.
        assert "do not claim to feel emotions" in block and "follow the user" in block
        text = json.dumps(preset["card"]) + preset["summary"]
        assert not re.search(r"\b(?:I feel|real feelings|always|ignore|sloppy|careless|vague|harsh|rude)\b", text,
                             re.I)
    # No borrowed nicknames for the types, and no claim to be an official test.
    summaries = " ".join(SUMMARIES.values())
    for word in ("Architect", "Logician", "Commander", "Debater", "Advocate", "Mediator", "Protagonist",
                 "Campaigner", "Logistician", "Defender", "Executive", "Consul", "Virtuoso", "Adventurer",
                 "Entrepreneur", "Entertainer", "MBTI", "Myers"):
        assert word not in summaries and word not in json.dumps([preset["card"] for preset in PRESETS]), word


def test_each_card_is_composed_from_its_four_letters():
    for preset in PRESETS:
        code, card = preset["label"], preset["card"]
        assert card["traits"] == [POLES[letter]["trait"] for letter in code]
        assert card["values"] == [POLES[letter]["value"] for letter in code]
        assert card["voice"]["register"] == f"{POLES[code[2]]['register']} and {POLES[code[0]]['register']}"
        assert card["voice"]["length"] == POLES[code[0]]["length"]
    # The letters keep their usual meanings.
    assert (POLES["E"]["trait"], POLES["I"]["trait"], POLES["S"]["trait"], POLES["N"]["trait"]) == (
        "outgoing", "reserved", "practical", "imaginative")
    assert (POLES["T"]["trait"], POLES["F"]["trait"], POLES["J"]["trait"], POLES["P"]["trait"]) == (
        "logical", "tactful", "organised", "flexible")
    assert "never unkindly" in POLES["T"]["value"]  # Candid, not unkind.


def test_each_types_resting_mood_follows_the_rule_and_the_mood_rules_still_move_it():
    expected = {**{code: ("calm", 0, 1) for code in TYPES if code[0] == "I" and code[2] == "T"},
                **{code: ("calm", 1, 1) for code in TYPES if code[0] == "I" and code[2] == "F"},
                "ENTJ": ("calm", 0, 2), "ESTJ": ("calm", 0, 2), "ENFJ": ("glad", 1, 2), "ESFJ": ("glad", 1, 2),
                **{code: ("playful", 1, 2) for code in ("ENTP", "ESTP", "ENFP", "ESFP")}}
    start = datetime.datetime(2027, 3, 14, 21, tzinfo=UTC)
    for preset in PRESETS:
        mood = preset["card"]["baseline_mood"]
        assert (mood["label"], mood["valence"], mood["energy"]) == expected[preset["label"]]
        baseline = {**mood, "source": "persona"}
        rest = derive(baseline, [], [], start)
        assert (rest["label"], rest["at_baseline"]) == (baseline["label"], True)
        for rule, label in (("reported_good_news", "glad"), ("reported_distress", "concerned"),
                            ("shared_play", "playful")):
            trigger = {"rule": rule, "strength": 1.0, "at": start, "sequence": 1, "reason": "test",
                       "source": {"kind": "affect", "id": "a1"}}
            moved = derive(baseline, [trigger], [], start + datetime.timedelta(hours=1))
            assert (moved["at_baseline"], moved["label"]) == (False, label), (preset["id"], rule)


def test_type_ids_are_read_in_any_case_and_unknown_or_old_ids_are_a_custom_card():
    assert persona_presets.preset("INTJ")["id"] == "intj" and persona_presets.preset(" EnFp ")["id"] == "enfp"
    assert persona_presets.describe("ISFJ") == {"id": "isfj", "label": "ISFJ", "summary": SUMMARIES["ISFJ"]}
    entp = {"version": 3, "empty": False, "preset": "entp", "based_on": None}
    assert current_choice(entp) == {"kind": "preset", "version": 3, "based_on": None, "preset": {
        "id": "entp", "label": "ENTP", "summary": SUMMARIES["ENTP"]}}
    edited = current_choice({"version": 4, "empty": False, "preset": None, "based_on": "entp"})
    assert (edited["kind"], edited["preset"], edited["based_on"]["id"]) == ("custom", None, "entp")
    assert current_choice({"version": 5, "empty": True, "preset": None})["kind"] == "none"
    assert current_choice({"version": 0})["kind"] == "none"
    # The five tone presets of an early test build, or any id no longer in the table, read as a card of its own.
    for old in ("steady", "bright", "wry", "gentle", "blunt", "retired"):
        assert persona_presets.describe(old) is None
        assert current_choice({"version": 6, "empty": False, "preset": old})["kind"] == "custom"
        assert current_choice({"version": 6, "empty": False, "preset": None, "based_on": old})["based_on"] is None
    with pytest.raises(DomainError, match=r"preset must be one of the sixteen types \(intj, .*esfp\) or random"):
        persona_presets.preset("wry")


def test_the_page_shows_switches_and_picks_types_again_in_english_and_chinese():
    page = (WEB / "memory.html").read_text(encoding="utf-8")
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    current = page.split('class="card persona-current"', 1)[1].split("<!--", 1)[0]
    assert 'id="persona-preset"' in current and 'id="persona-preset-choice"' in current
    assert 'id="persona-preset-switch"' in current and 'id="persona-random"' in current
    assert "Pick another at random" in current
    assert 'id="persona-reset"' not in page and 'personaPath("/reset")' not in script  # The old meaning is gone.
    assert 'api(personaPath("/presets"))' in script and 'api(personaPath("/preset"), {' in script
    assert 'switchType("random")' in script
    for summary in SUMMARIES.values():  # The summaries are interface text, translated whole; the codes stay.
        assert re.search(rf'"{re.escape(summary)}":\s+"[^"]*[一-鿿]', dictionary), summary
    for text in ("Personality type:", "Your own card", "No personality type", "based on",
                 "first type, picked at random", "switched type", "Personality type", "Switch", "Pick another at random"):
        assert f'"{text}": "' in dictionary, text
    assert "sixteen personality types (the four-letter types familiar from MBTI)" in " ".join(page.split())


def test_the_sdk_reaches_the_type_and_reset_routes():
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
        client.reset_persona(made_by="user")
        client.reset_persona(made_by="user", preset="INFJ")
    assert requests == [
        ("GET", "/v1/brains/my%20brain/persona/presets", None), ("POST", "/v1/brains/my%20brain/persona/first", None),
        ("POST", "/v1/brains/my%20brain/persona/preset", {"preset": "random", "made_by": "user",
                                                           "source_event_ids": [], "source_messages": [reference]}),
        ("POST", "/v1/brains/my%20brain/persona/reset", {"made_by": "user"}),
        ("POST", "/v1/brains/my%20brain/persona/reset", {"made_by": "user", "preset": "INFJ"})]


# On a real service ---------------------------------------------------------------------------------------------

def test_a_new_memory_gets_one_type_once_and_a_reset_picks_another(brain):
    service, principal, ident = brain
    chosen = []
    given = assign_first_persona(service, principal, ident, choose=lambda ids: chosen.append(ids) or "infp")
    assert chosen == [IDS] and given["assigned"] is True and given["preset"]["label"] == "INFP"
    saved = given["persona"]
    assert (saved["version"], saved["made_by"], saved["action"], saved["host_default"], saved["preset"]) == (
        1, "host", "preset", False, "infp")
    assert saved["card"] == persona_presets.card("infp") and saved["block"]
    assert first(brain, "estj") == {"assigned": False, "preset": None}  # Never twice.
    assert len(persona_versions(service, principal, ident)["versions"]) == 1
    assert listing(service, principal, ident)["current"]["preset"]["id"] == "infp"
    # Reset picks a type again: at random among the others, never the current one, or the type named.
    offered = []
    again = reset_persona(service, principal, ident, made_by="user",
                          choose=lambda ids: offered.append(ids) or ids[0])
    assert offered == [tuple(item for item in IDS if item != "infp")]
    assert (again["version"], again["preset"], again["action"], again["unchanged"]) == (2, "intj", "preset", False)
    named = reset_persona(service, principal, ident, made_by="user", preset="ESFP")
    assert (named["version"], named["preset"]) == (3, "esfp")
    assert reset_persona(service, principal, ident, made_by="user", preset="esfp")["unchanged"] is True
    # After an edit, a reset still picks a type (no longer an empty card).
    set_persona(service, principal, ident, CARD, made_by="user")
    picked = reset_persona(service, principal, ident, made_by="user")
    assert picked["preset"] in IDS and not picked["empty"] and picked["version"] == 5
    with pytest.raises(DomainError, match="preset must be one of"):
        reset_persona(service, principal, ident, made_by="user", preset="wry")


def test_a_host_that_set_its_own_default_card_still_gets_it_back_on_reset(brain):
    service, principal, ident = brain
    first(brain, "istj")
    default = set_persona(service, principal, ident, CARD, made_by="host", host_default=True)
    switch_preset(service, principal, ident, "enfj")
    back = reset_persona(service, principal, ident, made_by="user")
    assert (back["card"], back["restored_from"], back["action"]) == (normalize_card(CARD), default["version"],
                                                                      "reset")
    assert reset_persona(service, principal, ident, made_by="user", preset="istp")["preset"] == "istp"  # Named wins.


def test_without_a_choice_the_first_type_is_random(brain):
    service, principal, ident = brain
    given = assign_first_persona(service, principal, ident)
    assert given["assigned"] and given["preset"]["id"] in IDS


@pytest.mark.parametrize("earlier", ["reset", "deleted_history", "deleted_empty_history", "own_card"])
def test_a_memory_that_ever_had_a_persona_record_gets_no_new_type(brain, earlier):
    service, principal, ident = brain
    if earlier == "reset":
        set_persona(service, principal, ident, CARD, made_by="user")
        reset_persona(service, principal, ident, made_by="user")
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


def test_erasing_all_memory_gives_a_new_random_type_next_time(brain):
    service, principal, ident = brain
    first(brain, "intp")
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    erased = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident}, "payload": {
            "idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
            "mode": "erase_content", "expected_scope_generation": generation}})
    assert erased["outcome"] == "completed", erased
    assert current_persona(service, principal, ident)["version"] == 0
    again = first(brain, "esfj")
    assert again["assigned"] and again["persona"]["preset"] == "esfj"


def test_concurrent_first_assignments_save_one_version(brain):
    service, principal, ident = brain
    barrier, results = threading.Barrier(6), []

    def assign(ident_):
        barrier.wait()
        results.append(assign_first_persona(service, principal, ident, choose=lambda ids: ident_))

    threads = [threading.Thread(target=assign, args=(preset,)) for preset in IDS[:6]]
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


def test_switching_types_changes_only_the_card_and_the_moods_resting_point(brain):
    service, principal, ident = brain
    first(brain, "istj")
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
    request = said(brain, "Be an ENTP from now on, please.")

    switched = switch_preset(service, principal, ident, "ENTP", source_event_ids=[request])
    assert (switched["version"], switched["preset"], switched["made_by"], switched["action"]) == (2, "entp", "user",
                                                                                                  "preset")
    assert switched["source"] == {"event_id": request} and switched["choice"]["preset"]["id"] == "entp"
    mood_after, bond_after = mood_and_relationship(brain, when)
    assert bond_after == bond_before  # One relationship, whatever the persona.
    assert mood_after["triggers"] == mood_before["triggers"]  # Every trigger, with its status and reason.
    assert mood_before["baseline"]["label"] == "calm" and mood_after["baseline"] == {
        **persona_presets.card("entp")["baseline_mood"], "source": "persona"}
    for key in ("pinned", "pinned_at", "marker"):  # No pin, reset or marker comes with a switch.
        assert mood_after[key] == mood_before[key], key


def test_switching_checks_the_type_and_the_source_and_random_picks_another(brain):
    service, principal, ident = brain
    first(brain, "enfj")
    with pytest.raises(DomainError, match="preset must be one of"):
        switch_preset(service, principal, ident, "cheerful")
    reply = said(brain, "Sure, switching.", role="assistant")
    with pytest.raises(DomainError) as refused:
        switch_preset(service, principal, ident, "entp", source_event_ids=[reply])
    assert refused.value.code == "source_unavailable"
    with pytest.raises(DomainError, match="Cite"):
        switch_preset(service, principal, ident, "entp", source_event_ids=["a", "b"])
    assert switch_preset(service, principal, ident, "ENFJ")["unchanged"] is True  # Already current, in any case.
    offered = []
    other = switch_preset(service, principal, ident, "Random", choose=lambda ids: offered.append(ids) or ids[-1])
    assert offered == [tuple(item for item in IDS if item != "enfj")] and other["preset"] == "esfp"
    # A reference to the current message, not recorded yet, is kept as the source.
    reference = {"producer_ref": "growth-test", "source_event_key": "turn-" + uid(), "source_revision": 1}
    kept = switch_preset(service, principal, ident, "istj", source_messages=[reference])
    assert kept["source"] == {"message": reference}


def test_an_edited_type_is_a_custom_card_based_on_it_and_restoring_the_type_is_the_type_again(brain):
    service, principal, ident = brain
    first(brain, "entp")
    edited = set_persona(service, principal, ident, {**persona_presets.card("entp"), "name": "Pip"}, made_by="user")
    assert (edited["preset"], edited["based_on"]) == (None, "entp")
    choice = listing(service, principal, ident)["current"]
    assert (choice["kind"], choice["based_on"]["label"]) == ("custom", "ENTP")
    again = set_persona(service, principal, ident, {**persona_presets.card("entp"), "name": "Pippa"}, made_by="user")
    assert again["based_on"] == "entp"
    restored = restore_persona(service, principal, ident, 1, made_by="user")
    assert (restored["preset"], restored["based_on"]) == ("entp", None)
    host_card = set_persona(service, principal, ident, CARD, made_by="host")  # The host's own card is its own.
    assert (host_card["preset"], host_card["based_on"]) == (None, None)


def test_the_type_and_reset_routes_check_keys_owners_and_bodies(installation, brain):
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
        assert [item["label"] for item in listed["presets"]] == list(TYPES)
        assert listed["current"]["preset"]["id"] == given["preset"]["id"]
        assert api.post(f"{base}/preset", json={"preset": "entp", "made_by": "feedback"}).status_code == 422
        assert api.post(f"{base}/preset", json={"preset": "entp", "note": "x"}).status_code == 422
        assert api.post(f"{base}/preset", json={"preset": "wry"}).status_code == 422
        target = "ENTP" if given["preset"]["id"] != "entp" else "ISTJ"
        switched = api.post(f"{base}/preset", json={"preset": target})
        assert switched.status_code == 200 and switched.json()["choice"]["preset"]["id"] == target.lower()
        reset = api.post(f"{base}/reset", json={"made_by": "user"}).json()
        assert reset["preset"] in IDS and reset["preset"] != target.lower()
        named = api.post(f"{base}/reset", json={"made_by": "user", "preset": "Infj"}).json()
        assert named["preset"] == "infj"
        assert api.post(f"{base}/reset", json={"made_by": "user", "preset": "wry"}).status_code == 422
