"""The host AI as a source of feedback on the companion's manner (P2): ``memory_manner_feedback``.

The host AI reports the kind of feedback and the user messages it came from. The reports feed the same counting as
the fixed table (three messages, the 30-day pause after a rejection, decisions using up feedback, contradictions);
a message seen by both sources counts once. Cited messages are checked like the table's own matches, a report on the
current message counts once that message is recorded, and nothing is recorded while recording is paused.
Nothing calls a model.
"""
import asyncio
import hashlib
import inspect
import io
import json
import re
import types
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_persona_growth import CARD, _restored, forget, later, listing, said
from test_persona_growth import brain as brain
from test_persona_growth import installation as installation

from membrain import desktop, embedded_database, host, manner_feedback, notes, plugin, plugin_cli
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.api import create_app
from membrain.helpers import DomainError, Principal, uid
from membrain.mcp_server import create_server
from membrain.persona import delete_persona_history, set_persona
from membrain.persona_growth import (
    KINDS,
    PROPOSALS_CONVERSATION,
    REPORTED_PREFIX,
    _records,
    _reports,
    detect,
    persona_proposals,
    reject_proposal,
    report_feedback,
)

ROOT = Path(__file__).parents[1]
OPENCLAW = ROOT / "integrations/openclaw/membrain"
# Feedback the fixed table cannot read: paraphrases and other languages.
UNREAD = ("Could you lighten up a bit? You sound like a legal notice.", "Bitte etwas lockerer, du klingst so steif.",
          "Sois moins guindé, s'il te plaît.")


def report(brain, kind, *ids, messages=(), **kwargs):
    service, principal, ident = brain
    return report_feedback(service, principal, ident, kind, source_event_ids=list(ids), source_messages=list(messages),
                           **kwargs)


def stored_reports(brain):
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        return _reports(service, conn, principal, ident)


def proposal_rows(brain):
    service, principal, ident = brain
    with service.database.transaction(principal) as conn:
        return [entry for entry in _records(service, conn, principal, ident) if entry["type"] == "proposal"]


# Without a database ---------------------------------------------------------------------------------------------

def test_the_tool_offers_exactly_the_kinds_the_ledger_counts():
    assert manner_feedback.KINDS == tuple(KINDS)
    for text in UNREAD:
        assert detect(text) == []  # The table misses them; only the host AI can report them.
    description = manner_feedback.TOOL_DESCRIPTION
    assert "only when they actually said so" in description and "Never record your own guess" in description
    assert "source_messages" in description
    skill = (ROOT / "plugins/membrain/skills/membrain/SKILL.md").read_text(encoding="utf-8")
    assert "memory_manner_feedback" in skill and all(kind in skill for kind in KINDS)
    assert "manner_feedback" in plugin.TOOLS


class Unused:
    """A client the refused calls must never reach."""
    brain_id = "brain"

    def report_manner_feedback(self, *args, **kwargs):
        raise AssertionError("nothing may be sent while recording is paused")


def test_the_tool_refuses_and_sends_nothing_while_recording_is_paused(tmp_path, capsys):
    server = create_server(Unused(), directory=tmp_path)
    assert "memory_manner_feedback" in {tool.name for tool in asyncio.run(server.list_tools())}
    assert "memory_manner_feedback" not in {tool.name for tool in asyncio.run(create_server(Unused()).list_tools())}
    host.ensure_installation(tmp_path)
    host.pause(tmp_path)
    _, result = asyncio.run(server.call_tool("memory_manner_feedback", {
        "kind": "shorter", "source_event_ids": ["evt-1"]}))
    assert "paused" in result["error"] and "Nothing was saved" in result["error"]
    assert "paused" in manner_feedback.report(tmp_path, Unused(), "shorter", source_event_ids=["e"])["error"]


def test_openclaw_and_astrbot_offer_the_tool_with_the_same_text_and_kinds(monkeypatch, tmp_path):
    from test_chatbot_adapter import _load_astrbot_plugin

    script = (OPENCLAW / "index.js").read_text(encoding="utf-8")
    declared = script[script.index('name: "membrain_manner_feedback"'):]
    description = declared[declared.index("description:"):declared.index("parameters:")]
    assert "".join(re.findall(r'"([^"]*)"', description)) == manner_feedback.TOOL_DESCRIPTION  # Written out in JS.
    kinds = re.search(r"kind: \{ type: \"string\", enum: \[([^\]]*)\]", declared).group(1)
    assert tuple(re.findall(r'"(\w+)"', kinds)) == manner_feedback.KINDS
    manifest = json.loads((OPENCLAW / "openclaw.plugin.json").read_text(encoding="utf-8"))
    assert "membrain_manner_feedback" in manifest["contracts"]["tools"]
    assert manifest["toolMetadata"]["membrain_manner_feedback"] == {"sideEffecting": True}
    _, handlers = _load_astrbot_plugin(monkeypatch, tmp_path)
    doc = inspect.getdoc(handlers["membrain_manner_feedback"])
    assert doc.startswith(manner_feedback.TOOL_DESCRIPTION) and all(kind in doc for kind in manner_feedback.KINDS)


class Reported:
    """A client that keeps the reports a host passes on."""
    brain_id = "brain"

    def __init__(self):
        self.reports = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def report_manner_feedback(self, kind, **sources):
        self.reports.append((kind, sources))
        return {"recorded": 1, "unchanged": 0, "waiting_for_message": 1}


def test_openclaw_and_astrbot_pass_the_report_and_its_sources_and_send_nothing_while_paused(tmp_path, monkeypatch,
                                                                                            capsys):
    from test_chatbot_adapter import Event, _load_astrbot_plugin

    client, users = Reported(), []
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: users.append(user_id) or client)
    reference = [{"producer_ref": "membrain-openclaw", "source_event_key": "turn-1", "source_revision": 1}]
    stranger = "openclaw:telegram::-1:7"

    def openclaw(arguments):  # OpenClaw's membrain_manner_feedback runs `membrain plugin tool manner_feedback`.
        assert plugin.run_tool("manner_feedback", tmp_path, stream=io.BytesIO(json.dumps(arguments).encode())) == 0
        return json.loads(capsys.readouterr().out)

    module, _ = _load_astrbot_plugin(monkeypatch, tmp_path)
    bot = module.MembrainPlugin.__new__(module.MembrainPlugin)
    bot.memory = ChatMemory(tmp_path)
    event = Event("1001", "Way too long, honestly.")
    person = bot.memory.user_id(module._speaker(event))

    def astrbot(kind, **sources):
        return json.loads(asyncio.run(bot.membrain_manner_feedback(event, kind, **sources)))

    assert openclaw({"kind": "shorter", "source_messages": reference, "membrain_user": stranger})["recorded"] == 1
    assert "memory page" in astrbot("shorter", source_event_ids=["evt-1"])["note"]
    assert client.reports == [("shorter", {"source_event_ids": [], "source_messages": reference}),
                              ("shorter", {"source_event_ids": ["evt-1"], "source_messages": []})]
    assert users == [stranger, person]  # Each in the memory of the person who said it.
    unrecorded = ChatMemory(tmp_path, record_groups=False).manner_feedback(Speaker("telegram", "42", "9"), "shorter")
    assert "not available" in unrecorded["error"] and len(users) == 2
    # Each person's own pause covers their reports.
    host.pause(tmp_path, user_id=stranger)
    host.pause(tmp_path, user_id=person)
    assert "paused" in openclaw({"kind": "longer", "source_messages": reference, "membrain_user": stranger})["error"]
    assert "paused" in astrbot("longer", source_event_ids=["evt-1"])["error"]
    assert len(client.reports) == 2


def test_the_sdk_and_the_cli_reach_the_feedback_route(capsys):
    from membrain.client import MemoryClient

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode(), json.loads(request.content)))
        return httpx.Response(200, json={"recorded": 1})

    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my brain",
                      transport=httpx.MockTransport(handler)) as client:
        client.report_manner_feedback("shorter", source_messages=[
            {"producer_ref": "p", "source_event_key": "k", "source_revision": 1}])
    assert requests == [("POST", "/v1/brains/my%20brain/persona/feedback", {
        "kind": "shorter", "source_event_ids": [],
        "source_messages": [{"producer_ref": "p", "source_event_key": "k", "source_revision": 1}]})]
    import argparse

    parser = argparse.ArgumentParser()
    plugin_cli.add_commands(parser.add_subparsers(dest="command"))
    assert parser.parse_args(["plugin", "tool", "manner_feedback"]).name == "manner_feedback"


# On a real service ---------------------------------------------------------------------------------------------

def test_reports_in_any_wording_reach_the_same_threshold(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    ids = [said(brain, text) for text in UNREAD]
    assert listing(brain)["proposals"] == []  # The table sees nothing.
    first = report(brain, "less_formal", ids[0])
    assert (first["recorded"], first["unchanged"], first["waiting_for_message"]) == (1, 0, 0)
    assert "proposal" not in json.dumps(first) and "open" not in first  # Nothing about suggestions.
    report(brain, "less_formal", ids[1])
    assert listing(brain)["proposals"] == []  # Two make none.
    report(brain, "less_formal", ids[2])
    assert len(proposal_rows(brain)) == 1  # Stored by the report itself, before anyone lists.
    proposal = listing(brain)["proposals"][0]
    assert (proposal["kind"], proposal["status"], proposal["source_count"]) == ("less_formal", "open", 3)
    assert [source["event_id"] for source in proposal["sources"]] == ids
    assert proposal["change"] == {"field": "voice.register", "before": "formal", "after": "casual"}
    # A report stores the kind and ids only.
    with service.database.transaction(principal) as conn:
        texts = [row["text"] for row in conn.execute(
            "SELECT document->'observed'->'content'->>'text' AS text FROM memory_events WHERE brain_id=%s "
            "AND conversation_id=%s AND document->'observed'->'content'->>'text' LIKE %s",
            (ident, PROPOSALS_CONVERSATION, REPORTED_PREFIX + "%"))]
    assert len(texts) == 3 and not any("legal notice" in text or "steif" in text for text in texts)


def test_one_message_seen_by_both_sources_counts_once(brain):
    both = said(brain, "Your replies are too long")  # The table reads it.
    again = report(brain, "shorter", both)  # And the host AI reports it as well.
    assert again["recorded"] == 1
    assert report(brain, "shorter", both)["unchanged"] == 1  # The same report twice changes nothing.
    other = said(brain, "Way too much text, mate.")
    report(brain, "shorter", other, other)  # The same id twice in one call counts once.
    assert listing(brain)["proposals"] == []  # Two messages, however many sightings.
    third = said(brain, "Keep it short, please")
    proposal = listing(brain)["proposals"][0]
    assert [source["event_id"] for source in proposal["sources"]] == [both, other, third]
    # A message giving two kinds counts once for each.
    two = said(brain, "回复太长了，也太正式了")
    report(brain, "less_formal", two)
    assert [item for item in listing(brain)["proposals"] if item["kind"] == "less_formal"] == []


@pytest.mark.parametrize("case", ["assistant", "page", "import", "roleplay", "note", "missing", "before_reset",
                                  "deleted", "other_brain", "mixed"])
def test_reports_citing_messages_that_cannot_count_are_refused_and_store_nothing(brain, case):
    service, principal, ident = brain
    good = said(brain, "Could you lighten up a bit?")
    if case == "assistant":
        cited = [said(brain, "Sure, I'll lighten up.", role="assistant")]
    elif case == "page":
        cited = [said(brain, "lighten up", conversation="membrain-memory-page", producer="membrain-memory-page")]
    elif case == "import":
        cited = [said(brain, "lighten up", producer="membrain-import:chatgpt")]
    elif case == "roleplay":
        cited = [said(brain, "Lighten up, knight!", hint="roleplay")]
    elif case == "note":
        cited = [notes.store_note(service, principal, ident, {"request_id": uid(), "text": "Likes brevity."})["note_id"]]
    elif case == "missing":
        cited = ["evt-" + uid()]
    elif case == "before_reset":
        cited = [good]
        delete_persona_history(service, principal, ident)
    elif case == "deleted":
        cited = [good]
        forget(brain, [good])
    elif case == "other_brain":
        cited = [said((service, principal, service.create_brain(principal, "Other")["id"]), "lighten up")]
    else:
        cited = [good, said(brain, "lighten up", role="assistant")]
    before = stored_reports(brain)
    with pytest.raises(DomainError) as refused:
        report(brain, "less_formal", *cited)
    assert refused.value.code == "source_unavailable" and "Nothing was recorded" in refused.value.message
    assert stored_reports(brain) == before


def test_malformed_reports_are_refused(brain):
    good = said(brain, "Could you lighten up a bit?")
    for kind, ids, messages in (("friendlier", [good], []), ("shorter", [], []), ("shorter", [], [{}]),
                                ("shorter", [f"e{n}" for n in range(11)], []),
                                ("shorter", [], [{"producer_ref": "p", "source_event_key": "k",
                                                  "source_revision": 0}])):
        with pytest.raises(DomainError) as refused:
            report(brain, kind, *ids, messages=messages)
        assert refused.value.code == "validation_failed", (kind, ids, messages)
    service, principal, ident = brain
    with pytest.raises(DomainError):
        report_feedback(service, principal, ident, "shorter", source_event_ids="evt")
    assert stored_reports(brain) == []


def say_as(brain, text, key, producer="growth-test", role="user"):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": key, "source_revision": 1, "producer_ref": producer, "actor_ref": role,
            "actor_role": role, "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": "unknown", "delivery_state": "received" if role == "user" else "delivered",
            "parent_source_event_keys": []}]}})
    assert result["outcome"] == "completed", result
    return result["result"]["accepted_event_ids"][0]


def test_a_report_on_the_current_message_counts_once_it_is_recorded(brain):
    earlier = [said(brain, text) for text in UNREAD[:2]]
    for ident in earlier:
        report(brain, "less_formal", ident)
    key = "turn-" + uid()
    reference = {"producer_ref": "growth-test", "source_event_key": key, "source_revision": 1}
    waiting = report(brain, "less_formal", messages=[reference])
    assert (waiting["recorded"], waiting["waiting_for_message"]) == (1, 1)
    assert report(brain, "less_formal", messages=[reference])["unchanged"] == 1
    assert listing(brain)["proposals"] == []  # Not recorded yet, so it does not count.
    current = say_as(brain, UNREAD[2], key)  # The turn finishes and the message is recorded.
    assert len(proposal_rows(brain)) == 1  # Counted when it arrived.
    assert {entry.get("event_id") for entry in stored_reports(brain)} >= {current}  # Now tied to the id too.
    proposal = listing(brain)["proposals"][0]
    assert [source["event_id"] for source in proposal["sources"]] == [*earlier, current]
    # A reference that turns out to be a message which cannot count (here the assistant's reply) never counts.
    for text in ("Shorter answers, please.", "Too much text."):
        report(brain, "shorter", said(brain, text))
    key = "turn-" + uid()
    reply = {"producer_ref": "growth-test", "source_event_key": key, "source_revision": 1}
    report(brain, "shorter", messages=[reply])
    say_as(brain, "Sure, I will keep it shorter.", key, role="assistant")
    assert [p["kind"] for p in listing(brain)["proposals"]] == ["less_formal"]
    with pytest.raises(DomainError):  # Once recorded, such a message is refused outright.
        report(brain, "shorter", messages=[reply])


def test_host_reports_follow_the_pause_the_decisions_and_the_contradictions(brain):
    service, principal, ident = brain
    start = later(0)
    first = [said(brain, text) for text in ("Shorter answers, please.", "Too much text.", "TL;DR next time?")]
    for ident_ in first:
        report(brain, "shorter", ident_, now=start)
    proposal = listing(brain, now=start)["proposals"][0]
    reject_proposal(service, principal, ident, proposal["id"], now=start)
    # The rejection used them up: reporting them again brings nothing back, even after the pause.
    for ident_ in first:
        assert report(brain, "shorter", ident_, now=start)["unchanged"] == 1
    assert listing(brain, now=later(31))["open"] == 0
    # New reports during the pause: nothing on day 29, one proposal on day 31, from the new messages only.
    fresh = [said(brain, text) for text in ("Can you trim it down?", "Less waffle, please.", "Just the gist.")]
    for ident_ in fresh:
        report(brain, "shorter", ident_, now=later(1))
    assert listing(brain, now=later(29))["open"] == 0
    opened = [p for p in listing(brain, now=later(31))["proposals"] if p["status"] == "open"]
    assert [s["event_id"] for s in opened[0]["sources"]] == fresh
    # The table's opposite reading contradicts the host AI's reports, and the other way round.
    said(brain, "Your replies are too short")
    assert [p["withdrawn_because"] for p in listing(brain, now=later(31))["proposals"]][:1] == ["contradicted"]
    longer = [said(brain, text) for text in ("More detail would help.", "Go deeper, please.")]
    for ident_ in longer:
        report(brain, "longer", ident_, now=later(31))
    statuses = {p["kind"]: p["status"] for p in listing(brain, now=later(31))["proposals"] if p["status"] == "open"}
    assert statuses == {"longer": "open"}
    report(brain, "shorter", said(brain, "Ugh, too much again."), now=later(31))
    assert all(p["status"] != "open" or p["kind"] != "longer" for p in listing(brain, now=later(31))["proposals"])


def test_deleting_a_reported_message_withdraws_and_deleting_the_history_erases_the_reports(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    ids = [said(brain, text) for text in UNREAD]
    for ident_ in ids:
        report(brain, "less_formal", ident_)
    proposal = listing(brain)["proposals"][0]
    forget(brain, [ids[0]])
    withdrawn = listing(brain)["proposals"][0]
    assert (withdrawn["id"], withdrawn["status"], withdrawn["withdrawn_because"]) == (
        proposal["id"], "withdrawn", "sources_removed")
    assert "legal notice" not in json.dumps(withdrawn)
    assert stored_reports(brain)  # Ids only; the deleted message no longer counts.
    delete_persona_history(service, principal, ident)
    assert stored_reports(brain) == [] and listing(brain)["proposals"] == []
    # Messages from before the reset never count again, by either source.
    with pytest.raises(DomainError):
        report(brain, "less_formal", ids[1])


def test_reports_survive_an_archive_restore(brain):
    service, principal, ident = brain
    ids = [said(brain, text) for text in UNREAD[:2]]
    for ident_ in ids:
        report(brain, "less_formal", ident_)
    key = "turn-" + uid()
    report(brain, "less_formal", messages=[{"producer_ref": "growth-test", "source_event_key": key,
                                            "source_revision": 1}])
    say_as(brain, "Ok, that was a joke, but honestly: relax a little.", key)
    original = listing(brain)["proposals"]
    assert [(p["kind"], p["source_count"]) for p in original] == [("less_formal", 3)]
    copy_brain = _restored(brain, "Restored reports")
    restored = persona_proposals(service, principal, copy_brain)["proposals"]
    assert [(p["kind"], p["status"], p["source_count"]) for p in restored] == [("less_formal", "open", 3)]


def test_the_api_route_checks_keys_owners_and_strict_bodies(installation, brain):
    service, principal, ident = brain
    settings = replace(installation[2], api_keys={hashlib.sha256(b"growth-test-key").hexdigest(): principal})
    foreign = service.create_brain(Principal(principal.tenant_id, uid()), "Foreign")["id"]
    ids = [said(brain, text) for text in UNREAD]
    path = f"/v1/brains/{ident}/persona/feedback"
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer growth-test-key"}) as api:
        body = {"kind": "shorter", "source_event_ids": ids[:1]}
        assert api.post(path, json=body, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert api.post(f"/v1/brains/{foreign}/persona/feedback", json=body).status_code == 404
        assert api.post(path, json={**body, "note": "x"}).status_code == 422
        assert api.post(path, json={**body, "kind": "friendlier"}).status_code == 422
        missing = api.post(path, json={**body, "source_event_ids": ["evt-nope"]})
        assert missing.status_code == 409 and missing.json()["error"]["code"] == "source_unavailable"
        saved = api.post(path, json=body)
        assert saved.status_code == 200 and saved.json()["recorded"] == 1
        assert api.post(path, json=body).json()["unchanged"] == 1


# The whole path, as a host AI uses it --------------------------------------------------------------------------

@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_openclaw_and_astrbot_reports_count_toward_a_suggestion(tmp_path, monkeypatch, capsys):
    from test_chatbot_adapter import Event, _load_astrbot_plugin

    directory = tmp_path / "brain"
    module, _ = _load_astrbot_plugin(monkeypatch, tmp_path)

    def source(context):
        found = re.search(r"pass source_messages=(\[.*?\])\. This reference", context or "")
        assert found, context
        return json.loads(found.group(1))

    def hook(event, payload):  # OpenClaw's hooks and tools are these commands with --host openclaw.
        assert plugin.run_hook(event, directory, stream=io.BytesIO(json.dumps(payload).encode()),
                               host_name="openclaw") == 0
        output = capsys.readouterr().out
        return json.loads(output)["hookSpecificOutput"]["additionalContext"] if output else None

    def tool(arguments):
        assert plugin.run_tool("manner_feedback", directory, stream=io.BytesIO(json.dumps(arguments).encode())) == 0
        return json.loads(capsys.readouterr().out)

    async def astrbot_turn(event, kind):
        request = types.SimpleNamespace(system_prompt="", prompt=event.text,
                                        conversation=types.SimpleNamespace(cid="c1"))
        await bot.add_memory(event, request)
        result = json.loads(await bot.membrain_manner_feedback(event, kind,
                                                               source_messages=source(request.system_prompt)))
        await bot.store_turn(event, types.SimpleNamespace(role="assistant", completion_text="Got it."))
        return result

    try:
        host.start(directory)
        bot = module.MembrainPlugin(context=None, config={"directory": str(directory)})
        hook("session-start", {"session_id": "oc"})
        for number, text in enumerate(UNREAD, start=1):
            # Each host reports the comment before its turn is recorded, citing the turn's source block.
            context = hook("user-prompt", {"session_id": "oc", "prompt_id": f"t{number}", "prompt": text})
            result = tool({"kind": "less_formal", "source_messages": source(context)})
            assert (result["recorded"], result["waiting_for_message"]) == (1, 1) and "memory page" in result["note"]
            hook("stop", {"session_id": "oc", "prompt_id": f"t{number}", "last_assistant_message": "Got it."})
            result = asyncio.run(astrbot_turn(Event("1001", text, message_id=f"m{number}"), "less_formal"))
            assert (result["recorded"], result["waiting_for_message"]) == (1, 1)
        for user in (None, bot.memory.user_id(Speaker("aiocqhttp", "1001"))):
            with host.ready_client(directory, user) as client:
                proposals = client.persona_proposals()["proposals"]
            assert [(p["kind"], p["status"], p["source_count"]) for p in proposals] == [("less_formal", "open", 3)]
            assert [s["text"] for s in proposals[0]["sources"]] == list(UNREAD)

        # A kind memBrain does not count is refused with the reason, by each host.
        context = hook("user-prompt", {"session_id": "oc", "prompt_id": "t9", "prompt": "Be friendlier."})
        refused = tool({"kind": "friendlier", "source_messages": source(context)})
        assert refused["code"] == "validation_failed" and "kind must be one of" in refused["error"]
        refused = asyncio.run(astrbot_turn(Event("1001", "Be friendlier.", message_id="m9"), "friendlier"))
        assert refused["code"] == "validation_failed" and "kind must be one of" in refused["error"]

        host.pause(directory)
        assert "paused" in tool({"kind": "shorter", "source_event_ids": ["evt-1"]})["error"]
        assert "paused" in json.loads(asyncio.run(bot.membrain_manner_feedback(
            Event("1001", "Shorter, please."), "shorter", source_event_ids=["evt-1"])))["error"]
    finally:
        desktop.stop(directory)


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_a_host_ai_reports_feedback_and_marks_a_playful_moment_through_its_tools(tmp_path):
    directory = tmp_path / "brain"

    def call(server, name, arguments):
        _, result = asyncio.run(server.call_tool(name, arguments))
        return result

    def source(context):
        found = re.search(r"pass source_messages=(\[.*?\])\. This reference", context or "")
        assert found, context
        return json.loads(found.group(1))

    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)
            host.session_context(directory, "s1")
            # Three turns: in each, the host AI reports the comment on its manner before the turn is recorded.
            for number, text in enumerate(UNREAD, start=1):
                context = host.prompt_context(directory, "s1", text, turn_id=str(number), include_source=True)
                result = call(server, "memory_manner_feedback", {"kind": "less_formal",
                                                                 "source_messages": source(context)})
                assert (result["recorded"], result["waiting_for_message"]) == (1, 1) and "memory page" in result["note"]
                host.finish_turn(directory, "s1", "Got it.", turn_id=str(number))
            proposals = client.persona_proposals()["proposals"]
            assert [(p["kind"], p["status"], p["source_count"]) for p in proposals] == [("less_formal", "open", 3)]
            assert [s["text"] for s in proposals[0]["sources"]] == list(UNREAD)
            # Nothing about the suggestion reaches the AI's context.
            assert "less_formal" not in (host.session_context(directory, "s2") or "")

            # A playful shared moment the word list cannot read is playful because the host AI says so.
            saved = call(server, "memory_note", {"text": "Wir haben uns über den Kuchen kaputtgelacht.",
                                                 "kind": "milestone", "shared": True, "moment": "play",
                                                 "recording_capture": None})
            assert "error" in saved  # Plugin connections need this turn's capture, as for every note.
            context = host.prompt_context(directory, "s2", "Remember the cake?", turn_id="9", include_source=True)
            capture = re.search(r'recording_capture=("[^"]+")', context).group(1)
            saved = call(server, "memory_note", {"text": "Wir haben uns über den Kuchen kaputtgelacht.",
                                                 "kind": "milestone", "shared": True, "moment": "play",
                                                 "recording_capture": json.loads(capture)})
            assert "note_id" in saved, saved
            host.finish_turn(directory, "s2", "Ha, yes.", turn_id="9")
            mood = client.mood()
            assert mood["label"] == "playful" and mood["triggers"][0]["rule"] == "shared_play"

            for number, text in enumerate(("Trim it down, please.", "Less waffle!"), start=11):
                context = host.prompt_context(directory, "s3", text, turn_id=str(number), include_source=True)
                call(server, "memory_manner_feedback", {"kind": "shorter", "source_messages": source(context)})
                host.finish_turn(directory, "s3", "Okay.", turn_id=str(number))
            assert [p["kind"] for p in client.persona_proposals()["proposals"]] == ["less_formal"]
    finally:
        desktop.stop(directory)
