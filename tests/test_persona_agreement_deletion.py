"""Deleting, hiding or erasing a persona version never makes an agreement larger than what the user accepted (outside
review of 2026-11-18). An agreement is what the user accepted, as recorded when they accepted it: for a manner
suggestion, the change its kind states; for a host proposal, the changes the accepted version records
(``agreed_changes``), or for a version saved before that field, what the proposal it names states. It is never a
difference against another version, so removing the version before it cannot turn the personality type's own traits,
values and mood into something the user agreed to.

The first tests drive the normal host entry points on a real service: the plugin hooks record the user's comments,
the page's routes accept, delete (the page's "forget" action on the version's record) and switch. The property test
runs thousands of random sequences of accepting, confirming, editing, deleting, hiding, restoring, switching and
deleting the history without a database; the last test runs one such sequence on the service."""
import json
import random

import pytest
from test_persona_agreements import LONG_COMMENTS, PATIENT, SHORT_COMMENTS, agreed_change
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation
from test_persona_growth import said

from membrain import host, persona, persona_presets, plugin
from membrain.helpers import DomainError, uid
from membrain.persona import (
    AGREEMENT_LISTS,
    EMPTY_CARD,
    PERSONA_CONVERSATION,
    _kept,
    agreements_by_version,
    current_persona,
    normalize_card,
    persona_versions,
    restore_persona,
    with_agreements,
)
from membrain.persona_growth import KINDS, _apply, _merged, accept_proposal, persona_proposals
from membrain.persona_presets import switch_preset

SHORTER = KINDS["shorter"]["value"]["en"]


def talk(directory, user, text):
    """One exchange through the hooks Claude Code calls, in a conversation of its own."""
    session = "s-" + uid()
    plugin.session_start({"session_id": session, "membrain_user": user}, directory)
    plugin.user_prompt({"session_id": session, "prompt": text, "prompt_id": "t1", "membrain_user": user}, directory)
    plugin.stop({"session_id": session, "last_assistant_message": "Noted.", "prompt_id": "t1", "membrain_user": user},
                directory)
    return session


def forget_version(client, version):
    """What the page's "forget" action does to one record: the version's event, in the persona conversation."""
    generation = client.dashboard()["brain"]["scope_generation"]
    result = client.forget([version["event_id"]], kind="events", mode="erase_content",
                           expected_scope_generation=generation, conversation_id=PERSONA_CONVERSATION)
    assert result.get("outcome") == "completed", result


def numbered(client, number):
    return next(item for item in client.persona_versions()["versions"] if item["version"] == number)


def only_length(card, preset):
    """``card`` is the type's own card with nothing added but the agreed length."""
    plain = persona_presets.card(preset)
    return card == {**plain, "voice": {**plain["voice"], "length": SHORTER}}


# Through the host entry points, on a real service -------------------------------------------------------------------

def test_deleting_the_version_before_an_accepted_suggestion_keeps_only_what_was_accepted(installation):
    directory, _, _ = installation
    user = "agreement-deleted-before-" + uid()
    with host.ready_client(directory, user) as client:
        assert client.switch_persona_preset("intj")["version"] == 1  # A type, as the page saves it.
    for text in SHORT_COMMENTS:  # Three manner comments, recorded by the hooks.
        talk(directory, user, text)
    with host.ready_client(directory, user) as client:
        proposal = next(item for item in client.persona_proposals()["proposals"]
                        if item["kind"] == "shorter" and item["status"] == "open")
        assert client.accept_persona_proposal(proposal["id"])["persona"]["version"] == 2  # The page's Accept.
        forget_version(client, numbered(client, 1))
        listed = client.persona_versions()
        assert [item["version"] for item in listed["versions"]] == [2]
        assert [item["changes"] for item in listed["agreements"]] == [{"voice": {"length": SHORTER}}]
        switched = client.switch_persona_preset("enfp")  # The page's switch.
        assert only_length(switched["card"], "enfp"), switched["card"]
        listed = client.persona_versions()
        assert [item["changes"] for item in listed["agreements"]] == [{"voice": {"length": SHORTER}}]
        assert listed["versions"][0]["base_card"] == persona_presets.card("enfp") | {
            "voice": {**persona_presets.card("enfp")["voice"], "length": ""}}
    # The agent's own switch (OpenClaw's tool command) on the user's request keeps the same one thing.
    asked = talk(directory, user, "Could you switch to ISFJ?")
    with host.ready_client(directory, user) as client:
        cited = [item["event_id"] for item in client.timeline(roles=("user",), conversation_id=asked)["items"]]
    import io

    code = plugin.run_tool("persona", directory, stream=io.BytesIO(json.dumps(
        {"action": "switch", "preset": "isfj", "source_event_ids": cited, "membrain_user": user}).encode()))
    assert code == 0
    with host.ready_client(directory, user) as client:
        assert only_length(client.persona()["card"], "isfj"), client.persona()["card"]


def test_deleting_the_version_before_a_confirmed_change_keeps_only_what_the_agent_proposed(installation):
    directory, _, _ = installation
    user = "agreement-deleted-proposal-" + uid()
    with host.ready_client(directory, user) as client:
        client.switch_persona_preset("istj")
        asked = client.observe("From now on, be patient with me.", conversation_id="chat", branch_id="main",
                               source_event_key=uid(), producer_ref="agreements-test")
        changed = client.propose_persona_change({"traits": ["patient"], "values": [PATIENT]}, reason="Asked for it.",
                                                source_event_ids=asked["result"]["accepted_event_ids"])
        client.observe("Shall I?", conversation_id="chat", branch_id="main", source_event_key=uid(),
                       producer_ref="agreements-test", role="assistant", delivery_state="delivered")
        yes = client.observe("Yes.", conversation_id="chat", branch_id="main", source_event_key=uid(),
                             producer_ref="agreements-test")
        saved = client.confirm_persona_change(changed["proposal"]["id"],
                                              source_event_ids=yes["result"]["accepted_event_ids"])
        assert saved["persona"]["version"] == 2
        forget_version(client, numbered(client, 1))
        switched = client.switch_persona_preset("enfp")
        plain = persona_presets.card("enfp")
        assert switched["card"] == {**plain, "traits": [*plain["traits"], "patient"],
                                    "values": [*plain["values"], PATIENT]}, switched["card"]
        # The accepted version records what was agreed, as the proposal stated it.
        assert numbered(client, 2)["agreed_changes"] == {"traits": ["patient"], "values": [PATIENT]}


# Without a database: what each accepted record states ------------------------------------------------------------

def entry(number, card, **fields):
    return {"version": number, "card": {**EMPTY_CARD, **normalize_card(card)}, "made_by": "user", "action": "edit",
            "feedback": None, "host_proposal": None, "agreed_changes": None, "restored_from": None, "reason": None,
            "recorded_at": f"t{number}", **fields}


def test_a_manner_suggestion_states_its_kind_only_and_an_earlier_value_still_counts():
    base = persona_presets.card("intj")
    for kind, spec in KINDS.items():
        accepted, _ = _apply(kind, base, "en")
        if accepted is None:
            continue
        version = entry(2, accepted, made_by="feedback", action="feedback",
                        feedback={"proposal_id": "p", "kind": kind, "source_event_ids": ["a", "b", "c"]})
        field = spec["field"]
        expected = ({"traits": [spec["value"]["en"]]} if field == "traits"
                    else {"voice": {field.split(".")[1]: spec["value"]["en"]}})
        assert persona.stated_by(version) == expected, kind
        # The same record with no earlier version, or after any other, states the same thing.
        assert agreements_by_version([version])[2][0]["changes"] == expected
    # A card accepted before "shorter" stated a limit kept "short"; that is still the agreement.
    old = entry(2, {**base, "voice": {**base["voice"], "length": "short"}}, made_by="feedback", action="feedback",
                feedback={"proposal_id": "p", "kind": "shorter", "source_event_ids": ["a", "b", "c"]})
    assert persona.stated_by(old) == {"voice": {"length": "short"}}
    # An unknown kind, or a card without the kind's value, records nothing that can be known: nothing is carried.
    odd = {**old, "feedback": {**old["feedback"], "kind": "sing_more"}}
    assert persona.stated_by(odd) == {} and agreements_by_version([odd])[2] == []
    edited = entry(2, base, made_by="feedback", action="feedback",
                   feedback={"proposal_id": "p", "kind": "shorter", "source_event_ids": ["a", "b", "c"]})
    assert persona.stated_by(edited) == {}


def legacy_record(base_card, changes, base_version):
    """A host proposal as ``persona_growth.propose_change`` stores it: lists merged with the card it was made on."""
    proposed = _merged(base_card, changes)
    stored = {field: {name: proposed["voice"][name] for name in changes["voice"]} if field == "voice"
              else proposed[field] for field in changes}
    return {"id": "p1", "type": "proposal", "kind": "host", "changes": stored, "proposed_card": proposed,
            "base_version": base_version}, proposed


def test_a_host_proposal_saved_before_agreed_changes_keeps_only_the_voice_name_and_mood_it_states():
    base = persona_presets.card("intj")
    record, proposed = legacy_record(base, {"traits": ["patient"], "voice": {"emoji": "never"}, "name": "Wren",
                                            "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}, 1)
    first = entry(1, base, action="preset", preset="intj")
    accepted = entry(2, proposed, action="proposal", host_proposal={"proposal_id": "p1", "confirmed_by": "m"})
    proposals = {"p1": record}
    stated = {"voice": {"emoji": "never"}, "name": "Wren",
              "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}
    # The list entries it added were stored merged with the type's own, and no other version is read to tell them
    # apart: whatever versions are kept around it, only what the proposal states on its own is carried.
    for history in ([first, accepted], [accepted], [entry(1, persona_presets.card("enfp")), accepted]):
        assert agreements_by_version(history, proposals)[2][0]["changes"] == stated
    # Without the proposal, or with a card that is not the one it proposed, nothing is carried.
    assert agreements_by_version([first, accepted], {})[2] == []
    changed = entry(2, {**proposed, "name": "Ash"}, action="proposal",
                    host_proposal={"proposal_id": "p1", "confirmed_by": "m"})
    assert agreements_by_version([first, changed], proposals)[2] == []


def test_a_recorded_agreement_is_limited_to_what_its_card_holds():
    base = persona_presets.card("intj")
    card = {**base, "traits": [*base["traits"], "patient"]}
    claimed = entry(2, card, action="proposal", host_proposal={"proposal_id": "p", "confirmed_by": None},
                    agreed_changes={"traits": ["patient", "brave"], "values": ["Never lies"]})
    assert persona.stated_by(claimed) == {"traits": ["patient"]}


# Property: no sequence makes an agreement larger than what was accepted ------------------------------------------

PRESETS = persona_presets.IDS
TRAITS = ["patient", "curious", "gentle", "brave"]
VALUES = [PATIENT, "Says when it is unsure", "Checks before assuming"]
LENGTHS = ["two sentences at most", "a paragraph"]


def within(changes, stated):
    """Whether ``changes`` is part of ``stated``: the same voice fields with the same values, list entries among the
    stated ones, the same name or mood."""
    if not set(changes) <= set(stated):
        return False
    for field, value in changes.items():
        if field == "voice":
            if any(stated["voice"].get(name) != text for name, text in value.items()):
                return False
        elif field in AGREEMENT_LISTS:
            if any(item not in stated[field] for item in value):
                return False
        elif value != stated[field]:
            return False
    return True


class History:
    """The persona history as the service keeps it, without a database: versions in order, numbered from the newest
    kept one, deleted or hidden versions gone, and what each accepted version's user actually accepted."""

    def __init__(self, seed):
        self.random, self.kept, self.accepted, self.proposals, self.clock = random.Random(seed), [], {}, {}, 0

    def card(self):
        return self.kept[-1]["card"] if self.kept else dict(EMPTY_CARD)

    def save(self, card, **fields):
        self.clock += 1
        number = (self.kept[-1]["version"] if self.kept else 0) + 1
        self.kept.append(entry(number, card, recorded_at=f"t{self.clock}", **fields))
        return self.kept[-1]

    def in_force(self):
        return (agreements_by_version(self.kept, self.proposals).get(self.kept[-1]["version"], [])
                if self.kept else [])

    def step(self):
        pick = self.random.choice(("switch", "switch", "manner", "manner", "host", "edit", "delete", "delete",
                                   "restore", "history"))
        if pick == "switch":
            try:
                card = with_agreements(persona_presets.card(self.random.choice(PRESETS)), self.in_force())
            except DomainError:
                return
            self.save(card, action="preset")
        elif pick == "manner":
            kind = self.random.choice(sorted(KINDS))
            card, _ = _apply(kind, self.card(), self.random.choice(("en", "zh")))
            if card is not None:
                saved = self.save(card, made_by="feedback", action="feedback",
                                  feedback={"proposal_id": uid(), "kind": kind, "source_event_ids": ["a", "b", "c"]})
                field = KINDS[kind]["field"]
                value = (saved["card"]["traits"][-1] if field == "traits"
                         else saved["card"]["voice"][field.split(".")[1]])
                self.accepted[saved["recorded_at"]] = ({"traits": [value]} if field == "traits"
                                                       else {"voice": {field.split(".")[1]: value}})
        elif pick == "host":
            asked = {}
            if self.random.random() < 0.6:
                asked["traits"] = self.random.sample(TRAITS, self.random.randint(1, 2))
            if self.random.random() < 0.5:
                asked["values"] = [self.random.choice(VALUES)]
            if self.random.random() < 0.4 or not asked:
                asked["voice"] = {"length": self.random.choice(LENGTHS)}
            try:
                proposed = _merged(self.card(), asked)
            except DomainError:
                return
            if proposed == normalize_card(self.card()):
                return
            stored = {field: {name: proposed["voice"][name] for name in asked["voice"]} if field == "voice"
                      else proposed[field] for field in asked}
            ident = uid()
            if self.random.random() < 0.3:  # Accepted by an earlier runtime: no agreed_changes, only the proposal.
                self.proposals[ident] = {"id": ident, "type": "proposal", "kind": "host", "changes": stored,
                                         "proposed_card": proposed, "base_version": self.kept[-1]["version"]
                                         if self.kept else 0}
                saved = self.save(proposed, action="proposal", host_proposal={"proposal_id": ident,
                                                                              "confirmed_by": "m"})
                # Such a record keeps only the voice fields the proposal states, never its list additions.
                self.accepted[saved["recorded_at"]] = {"voice": asked["voice"]} if "voice" in asked else {}
                return
            agreed = _kept(persona.proposal_change(stored, self.card()), proposed)
            saved = self.save(proposed, action="proposal", host_proposal={"proposal_id": ident, "confirmed_by": "m"},
                              agreed_changes=agreed)
            # What the user was asked and said yes to: the asked voice fields and the entries not already there.
            self.accepted[saved["recorded_at"]] = {
                **({"voice": asked["voice"]} if "voice" in asked else {}),
                **{field: [item for item in asked[field] if item not in self.card_before(saved)[field]]
                   for field in AGREEMENT_LISTS if field in asked}}
        elif pick == "edit" and self.kept:
            card = json.loads(json.dumps(self.card()))
            field = self.random.choice(("traits", "values", "voice", "name"))
            if field == "voice":
                card["voice"]["length"] = self.random.choice(["", "medium", SHORTER])
            elif field == "name":
                card["name"] = self.random.choice(["", "Wren", "Mira"])
            elif card[field]:
                card[field].pop(self.random.randrange(len(card[field])))
            self.save(card)
        elif pick == "delete" and self.kept:  # Deleting, hiding or erasing one version: it is no longer kept.
            self.kept.pop(self.random.randrange(len(self.kept)))
        elif pick == "restore" and len(self.kept) > 1:
            chosen = self.random.choice(self.kept[:-1])
            self.save(chosen["card"], action="restore", restored_from=chosen["version"])
        elif pick == "history" and self.random.random() < 0.3:  # Deleting the personality history.
            self.kept = []

    def card_before(self, saved):
        position = self.kept.index(saved)
        return {**EMPTY_CARD, **(self.kept[position - 1]["card"] if position else EMPTY_CARD)}

    def check(self):
        found = agreements_by_version(self.kept, self.proposals)
        for version in self.kept:
            for agreement in found[version["version"]]:
                stated = self.accepted.get(agreement["made_at"])
                assert stated is not None, agreement  # Only an accepted record starts an agreement.
                assert within(agreement["changes"], stated), (agreement, stated)
                assert within(agreement["changes"], {**EMPTY_CARD, **version["card"]}), agreement  # Still on the card.


def test_no_sequence_of_deleting_hiding_restoring_or_switching_widens_an_agreement():
    for seed in range(400):
        history = History(seed)
        for _ in range(30):
            history.step()
            history.check()
        # After a switch, everything the card has beyond the type is something the user accepted.
        if history.kept:
            preset = history.random.choice(PRESETS)
            try:
                switched = with_agreements(persona_presets.card(preset), history.in_force())
            except DomainError:
                continue
            plain = persona_presets.card(preset)
            accepted = list(history.accepted.values())
            for field in AGREEMENT_LISTS:
                for item in switched[field]:
                    assert item in plain[field] or any(item in stated.get(field, ()) for stated in accepted), item
            for name, text in switched["voice"].items():
                assert text == plain["voice"][name] or any(
                    (stated.get("voice") or {}).get(name) == text for stated in accepted), (name, text)
            assert switched["baseline_mood"] == plain["baseline_mood"] and switched["name"] == plain["name"]


# The same on a real service --------------------------------------------------------------------------------------

def accept(brain, kind, comments):
    service, principal, ident = brain
    for text in comments:
        said(brain, text)
    proposal = next(item for item in persona_proposals(service, principal, ident)["proposals"]
                    if item["kind"] == kind and item["status"] == "open")
    return accept_proposal(service, principal, ident, proposal["id"])["persona"]


def hide(brain, number, mode):
    service, principal, ident = brain
    version = next(item for item in persona_versions(service, principal, ident)["versions"]
                   if item["version"] == number)
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": PERSONA_CONVERSATION, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": [version["event_id"]]},
                    "mode": mode, "expected_scope_generation": generation}})
    assert result["outcome"] == "completed", result


def carried(brain):
    service, principal, ident = brain
    return [item["changes"] for item in persona_versions(service, principal, ident)["agreements"]]


def test_deleting_hiding_and_restoring_versions_on_the_service_never_widens_an_agreement(brain):
    service, principal, ident = brain
    switch_preset(service, principal, ident, "intj")  # 1
    accept(brain, "shorter", SHORT_COMMENTS)  # 2
    agreed_change(brain, {"traits": ["patient"], "values": [PATIENT]})  # 3
    switch_preset(service, principal, ident, "enfp")  # 4
    assert carried(brain) == [{"voice": {"length": SHORTER}}, {"traits": ["patient"], "values": [PATIENT]}]
    hide(brain, 1, "erase_content")  # The type before both: nothing changes.
    assert carried(brain) == [{"voice": {"length": SHORTER}}, {"traits": ["patient"], "values": [PATIENT]}]
    hide(brain, 2, "suppress_recall")  # The accepted suggestion's own record hidden: that agreement goes.
    assert carried(brain) == [{"traits": ["patient"], "values": [PATIENT]}]
    plain = persona_presets.card("istj")
    switched = switch_preset(service, principal, ident, "istj")  # 5
    assert switched["card"] == {**plain, "traits": [*plain["traits"], "patient"], "values": [*plain["values"], PATIENT]}
    restore_persona(service, principal, ident, 4, made_by="user")  # 6: ENFP with both on its card.
    assert carried(brain) == [{"traits": ["patient"], "values": [PATIENT]}]
    hide(brain, 3, "erase_content")  # The confirmed change's record erased: nothing is carried any more.
    assert carried(brain) == []
    assert switch_preset(service, principal, ident, "esfp")["card"] == persona_presets.card("esfp")
    # An opposite suggestion accepted now is its own agreement and nothing else.
    accept(brain, "longer", LONG_COMMENTS)
    assert carried(brain) == [{"voice": {"length": KINDS["longer"]["value"]["en"]}}]


def stored_proposal(brain, proposal_id):
    """The proposal's stored record: its text, or None once it is erased (or gone)."""
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        row = conn.execute("SELECT document->'observed'->'content'->>'text' AS text FROM memory_events "
                           "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND id=%s AND is_current",
                           (*service._params(principal, ident), proposal_id)).fetchone()
    return row["text"] if row else None


@pytest.mark.parametrize("mode", ["erase_content", "suppress_recall"])
def test_deleting_or_hiding_a_version_removes_the_proposals_made_on_it(brain, mode):
    """A host proposal keeps a copy of the card it was made on. Deleting that version takes the proposal with it, open
    or withdrawn, as "Delete personality history" takes every proposal; a proposal made on another version stays."""
    from test_persona_confirmation import propose

    service, principal, ident = brain
    switch_preset(service, principal, ident, "intj")  # 1
    asked = said(brain, "From now on, be patient with me.")
    withdrawn = propose(brain, {"traits": ["patient"]}, source_event_ids=[asked])  # Made on version 1.
    switch_preset(service, principal, ident, "enfp")  # 2: the first proposal is withdrawn.
    kept = propose(brain, {"values": [PATIENT]}, source_event_ids=[asked])  # Made on version 2.
    assert "reserved" in stored_proposal(brain, withdrawn["id"])  # INTJ's own trait, copied into the proposal.
    hide(brain, 1, mode)
    assert stored_proposal(brain, withdrawn["id"]) is None or mode == "suppress_recall"
    listed = {item["id"]: item for item in persona_proposals(service, principal, ident)["proposals"]}
    assert withdrawn["id"] not in listed and listed[kept["id"]]["status"] == "open"
    hide(brain, 2, mode)  # Now the open one goes too.
    assert kept["id"] not in {item["id"] for item in persona_proposals(service, principal, ident)["proposals"]}


def test_a_proposal_from_before_the_dependency_does_not_reopen_on_the_card_that_takes_its_number(brain):
    """Deleting the newest version frees its number for the next save. A proposal stored by an earlier runtime (with no
    dependency on its version, so it survives the deletion) must stay withdrawn: a yes to it would put the deleted card
    back, as agreed."""
    from test_persona_confirmation import propose

    service, principal, ident = brain
    switch_preset(service, principal, ident, "intj")  # 1
    switch_preset(service, principal, ident, "enfp")  # 2
    asked = said(brain, "From now on, be patient with me.")
    proposal = propose(brain, {"traits": ["patient"]}, source_event_ids=[asked])
    assert proposal["base_version"] == 2
    with service.database.transaction(principal) as conn:  # As an earlier runtime stored it.
        conn.execute("DELETE FROM memory_event_dependencies WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                     "AND output_event_id=%s", (*service._params(principal, ident), proposal["id"]))
    hide(brain, 2, "erase_content")
    switch_preset(service, principal, ident, "istj")  # 2 again
    assert current_persona(service, principal, ident)["version"] == 2
    listed = next(item for item in persona_proposals(service, principal, ident)["proposals"]
                  if item["id"] == proposal["id"])
    assert (listed["status"], listed["withdrawn_because"]) == ("withdrawn", "persona_changed")
