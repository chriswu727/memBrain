"""A persona change the host AI proposed and the user confirms, through the hosts with a real service.

The user's yes must answer the question the agent asked in the same conversation (``persona_growth.confirm_change``).
Hooks record a turn when it ends, so the yes the AI cites is usually the current message, not recorded yet. The tool
must never tell the AI "confirmed" for a yes that cannot be applied, and a deferred confirmation that fails when the
turn is recorded must not vanish: the host is told once, at its next contact."""
import asyncio
import io
import json
import re

import pytest

from membrain import desktop, embedded_database, host, persona_growth, persona_tool, plugin
from membrain.adapters.chatbot import ChatMemory, Speaker
from membrain.mcp_server import create_server

TOOLS = plugin.HOST_TOOLS["claude-code"]
NOTICE = "Your confirmation of the persona change was not applied"
ONE_SENTENCE = {"voice": {"length": "one sentence"}}
REASON = "The user asked for one-sentence replies from now on."
QUESTION = "Shall I make one-sentence replies part of my persona?"


def source(context):
    found = re.search(r"pass source_messages=(\[.*?\])\. This reference", context or "")
    assert found, context
    return json.loads(found.group(1))


def capture(context):
    return json.loads(re.search(r'recording_capture=("[^"]+")', context).group(1))


# Without a database: how a waiting confirmation is settled ------------------------------------------------------

EXCHANGE = "a" * 32 + "." + "b" * 64


class Proposals:
    def __init__(self, status, kind="host"):
        self.status, self.kind, self.calls = status, kind, 0

    def persona_proposals(self):
        self.calls += 1
        return {"proposals": [{"id": "p1", "kind": self.kind, "status": self.status}]}


def user_message(state):
    return {"status": "observed", "messages": [{"role": "user", "state": state}, {"role": "assistant", "state": state}]}


@pytest.mark.parametrize("outcome, status, told, kept", [
    (user_message("recorded"), "open", True, False),  # Recorded, and the rule was not met.
    (user_message("failed"), "open", True, False),  # A refused replay, a full or failed journal.
    (user_message("excluded"), "open", True, False),  # A pause, an erasure.
    ({"status": "erased"}, "open", True, False),
    ({"status": "not_found"}, "open", True, False),  # The ledger entry expired or was removed.
    (user_message("recorded"), "accepted", False, False),  # Saved: nothing to say.
    (user_message("excluded"), "withdrawn", False, False),  # Replaced or decided otherwise: nothing to say.
    (user_message("excluded"), "rejected", False, False),
    (user_message("queued"), "open", False, True),  # Not known yet: asked again at the next contact.
    (user_message("unknown"), "open", False, True),
    ({"status": "awaiting_completion", "completed": False}, "open", False, True),
    ({"status": "unavailable", "reason": "store_busy"}, "open", False, True),
])
def test_a_waiting_confirmation_is_settled_by_its_turns_outcome_and_reported_once(tmp_path, monkeypatch, outcome,
                                                                                    status, told, kept):
    from membrain import host_outcomes

    monkeypatch.setattr(host_outcomes, "lookup", lambda directory, **names: outcome)
    persona_tool._remember(tmp_path, "someone", "p1", EXCHANGE)
    client = Proposals(status)
    notice = persona_tool.pending_notice(tmp_path, client, "someone")
    assert (notice == persona_tool.NOT_APPLIED + " proposal_id: p1.") is told and (notice == "") is not told
    path = persona_tool._pending_file(tmp_path, "someone", create=False)
    assert path.exists() is kept and (client.calls == 0) is kept
    assert persona_tool.pending_notice(tmp_path, client, "someone") == ""  # Once.
    assert persona_tool.pending_notice(tmp_path, client, None) == ""  # Another owner's memory has none.


def test_a_waiting_confirmation_is_given_up_silently_after_a_week_and_erased_with_the_memory(tmp_path, monkeypatch):
    from membrain import host_outcomes

    monkeypatch.setattr(host_outcomes, "lookup", lambda directory, **names: user_message("queued"))
    persona_tool._remember(tmp_path, None, "p1", EXCHANGE)
    persona_tool._remember(tmp_path, None, "p1", EXCHANGE)  # The same confirmation twice is kept once.
    path = persona_tool._pending_file(tmp_path, None, create=False)
    assert len(persona_tool._pending(path)) == 1
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert set(stored["pending"][0]) == {"proposal_id", "exchange", "at"}  # Ids only, never text.
    stored["pending"][0]["at"] -= persona_tool.PENDING_SECONDS + 1
    path.write_text(json.dumps(stored), encoding="utf-8")
    assert persona_tool.pending_notice(tmp_path, Proposals("open"), None) == "" and not path.exists()
    persona_tool._remember(tmp_path, None, "p2", EXCHANGE)
    persona_tool.forget_pending(tmp_path, None)
    assert not path.exists()


def test_a_damaged_file_or_a_failing_service_never_costs_the_context(tmp_path, monkeypatch):
    from membrain import host_outcomes

    monkeypatch.setattr(host_outcomes, "lookup", lambda directory, **names: user_message("recorded"))
    path = persona_tool._pending_file(tmp_path, None)
    path.write_text("{not json", encoding="utf-8")
    assert persona_tool.pending_notice(tmp_path, Proposals("open"), None) == ""
    persona_tool._remember(tmp_path, None, "p1", EXCHANGE)

    class Down:
        def persona_proposals(self):
            raise RuntimeError("service hiccup")

    assert persona_tool.pending_notice(tmp_path, Down(), None) == ""
    assert len(persona_tool._pending(path)) == 1  # Kept for the next contact.
    assert persona_tool.staged_turn(tmp_path, {"producer_ref": 1}) == (None, None)
    assert persona_tool.staged_turn(tmp_path, "not a reference") == (None, None)


# On a real service ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def directory(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("confirm") / "brain"
    try:
        host.start(directory)
        yield directory
    finally:
        desktop.stop(directory)


class Host:
    """One person on the plugin path: hooks for each turn and ``membrain plugin tool persona`` for the AI's calls
    (OpenClaw, Codex), or with ``mcp`` the MCP tool ``memory_persona`` (Claude Code, the installation's own memory)."""

    def __init__(self, directory, capsys, user, *, mcp=False):
        self.directory, self.capsys, self.user, self.mcp = directory, capsys, None if mcp else user, mcp
        self.turns = 0

    def prompt(self, session, text):
        self.turns += 1
        self.turn_id = str(self.turns)
        self.context = host.prompt_context(self.directory, session, text, turn_id=self.turn_id, user_id=self.user,
                                           include_source=True, tools=TOOLS) or ""
        return self.context

    def finish(self, session, reply):
        receipt = {}
        host.finish_turn(self.directory, session, reply, turn_id=self.turn_id, user_id=self.user, receipt=receipt)
        return {item["role"]: item for item in receipt.get("messages", [])}

    def tool(self, **arguments):
        if self.mcp:
            with host.ready_client(self.directory) as client:
                _, result = asyncio.run(create_server(client, directory=self.directory).call_tool(
                    "memory_persona", arguments))
            return result
        payload = {**arguments, **({"membrain_user": self.user} if self.user else {})}
        assert plugin.run_tool("persona", self.directory, stream=io.BytesIO(json.dumps(payload).encode())) == 0
        return json.loads(self.capsys.readouterr().out)

    def cited(self, **extra):
        return {"source_messages": source(self.context), "recording_capture": capture(self.context), **extra}

    def propose(self, session):
        self.prompt(session, "From now on, keep replies to one sentence.")
        proposal = self.tool(action="propose", changes=ONE_SENTENCE, reason=REASON, **self.cited())
        assert proposal["proposal_id"], proposal
        return proposal["proposal_id"]

    def persona(self):
        with host.ready_client(self.directory, self.user) as client:
            return client.persona()

    def proposal(self, proposal_id):
        with host.ready_client(self.directory, self.user) as client:
            return next(item for item in client.persona_proposals()["proposals"] if item["id"] == proposal_id)


def start(directory, capsys, user, **options):
    person = Host(directory, capsys, user, **options)
    host.session_context(directory, f"{user}-start", tools=TOOLS, user_id=person.user)
    assert person.persona()["version"] == 1  # The first persona, a random personality type.
    return person


def test_a_yes_in_another_conversation_is_refused_at_once_and_nothing_is_reported_saved(directory, capsys):
    """Case (b): the agent asked in one conversation, the user's yes opens a new one."""
    person = start(directory, capsys, "elsewhere")
    proposal = person.propose("elsewhere-1")
    person.finish("elsewhere-1", QUESTION)
    person.prompt("elsewhere-2", "Yes, do it.")  # A new conversation; nothing of the agent's is recorded in it.
    answer = person.tool(action="confirm", proposal_id=proposal, **person.cited())
    assert answer == {"error": persona_growth.NOT_HERE, "code": "source_unavailable"}, answer
    assert "Confirmed" not in json.dumps(answer)
    person.finish("elsewhere-2", "Sure, let me ask properly.")
    assert person.persona()["version"] == 1
    assert (person.proposal(proposal)["status"], person.proposal(proposal)["waiting_for_confirmation"]) == ("open", False)
    assert NOTICE not in person.prompt("elsewhere-2", "Hello?")  # Nothing deferred, so nothing to report.
    assert not pending(person)


def pending(person):
    return persona_tool._pending(persona_tool._pending_file(person.directory, person.user, create=False))


def saved_with_the_change(person, proposal, version=2):
    saved = person.persona()
    assert (saved["version"], saved["action"], saved["card"]["voice"]["length"]) == (version, "proposal", "one sentence")
    assert saved["host_proposal"]["proposal_id"] == proposal and saved["host_proposal"]["confirmed_by"]
    assert person.proposal(proposal)["status"] == "accepted"


def test_a_yes_in_the_same_conversation_waits_for_its_turn_and_is_saved_without_a_notice(directory, capsys):
    """Case (a), the normal one: the yes is the next message of the conversation in which the agent asked."""
    person = start(directory, capsys, "same")
    proposal = person.propose("same-1")
    person.finish("same-1", QUESTION)
    person.prompt("same-1", "Yes, do it.")
    answer = person.tool(action="confirm", proposal_id=proposal, **person.cited())
    assert answer["status"] == "waiting_for_message" and answer["note"] == persona_tool.NOTES["waiting_for_message"]
    assert answer["note"].startswith("Not saved yet") and "Confirmed" not in answer["note"]
    assert person.persona()["version"] == 1 and len(pending(person)) == 1
    person.finish("same-1", "Done: one sentence from now on.")
    saved_with_the_change(person, proposal)
    following = person.prompt("same-1", "Thanks.")
    assert NOTICE not in following and '<membrain-persona version="2">' in following
    assert not pending(person)  # Settled: saved, so nothing to say.


def test_a_yes_after_the_agent_asked_again_in_the_new_conversation_is_saved(directory, capsys):
    """Case (c): the yes is in a new conversation, after the agent described the change there too."""
    person = start(directory, capsys, "asked-again")
    proposal = person.propose("again-1")
    person.finish("again-1", QUESTION)
    person.prompt("again-2", "Yes, do it.")
    assert person.tool(action="confirm", proposal_id=proposal, **person.cited())["error"] == persona_growth.NOT_HERE
    person.finish("again-2", "Just to be sure: shall I keep my replies to one sentence from now on?")
    person.prompt("again-2", "Yes, I'm sure.")
    assert person.tool(action="confirm", proposal_id=proposal, **person.cited())["status"] == "waiting_for_message"
    person.finish("again-2", "Done.")
    saved_with_the_change(person, proposal)
    assert NOTICE not in person.prompt("again-2", "Great.") and not pending(person)


def test_a_confirmation_in_the_proposals_own_turn_is_refused_also_after_a_reply_elsewhere(directory, capsys):
    """Case (d): the AI proposes and confirms in one turn. Unchanged when nothing was said since; when another
    conversation's reply was recorded meanwhile, the service used to keep it waiting and then drop it."""
    person = start(directory, capsys, "same-turn")
    proposal = person.propose("turn-1")
    answer = person.tool(action="confirm", proposal_id=proposal, **person.cited())
    assert answer == {"error": persona_growth.TOO_EARLY, "code": "source_unavailable"}
    other = Host(directory, capsys, "same-turn")  # The same person in a second conversation at the same time.
    other.turns = 100
    other.prompt("turn-2", "Unrelated question.")
    other.finish("turn-2", "Unrelated answer.")
    answer = person.tool(action="confirm", proposal_id=proposal, **person.cited())
    assert answer == {"error": persona_growth.NOT_HERE, "code": "source_unavailable"}
    person.finish("turn-1", QUESTION)
    assert person.persona()["version"] == 1 and person.proposal(proposal)["status"] == "open"
    assert not pending(person)


def test_a_confirmation_whose_message_is_not_recorded_is_reported_once(directory, capsys):
    """Case (e), a pause: the tool kept the confirmation waiting, then recording was paused before the turn ended,
    so the yes was never recorded. The host is told once, at its next contact after the pause."""
    person = start(directory, capsys, "unrecorded")
    proposal = person.propose("unrecorded-1")
    person.finish("unrecorded-1", QUESTION)
    person.prompt("unrecorded-1", "Yes, do it.")
    assert person.tool(action="confirm", proposal_id=proposal, **person.cited())["status"] == "waiting_for_message"
    host.pause(directory, user_id=person.user)
    assert person.finish("unrecorded-1", "Done.")["user"]["state"] == "excluded"
    assert NOTICE not in (person.prompt("unrecorded-1", "Still there?") or "")  # Not while paused.
    host.resume(directory, user_id=person.user)
    told = person.prompt("unrecorded-1", "Back again.")
    assert told.count(NOTICE) == 1 and f"proposal_id: {proposal}." in told
    assert persona_tool.NOT_APPLIED in told
    person.finish("unrecorded-1", "Welcome back.")
    assert NOTICE not in person.prompt("unrecorded-1", "And now?")  # Once only.
    assert NOTICE not in host.session_context(directory, "unrecorded-2", tools=TOOLS, user_id=person.user)
    assert person.persona()["version"] == 1 and person.proposal(proposal)["status"] == "open"
    assert not pending(person)


@pytest.mark.parametrize("mode", ["erase_content", "suppress_recall"])
def test_a_confirmation_whose_question_was_removed_is_reported_once_at_the_next_session(directory, capsys, mode):
    """Case (e), the question removed: the conversation's question was there when the AI confirmed and was erased or
    hidden on the memory page before the turn ended. The removal makes the turn's capture stale, so the yes is not
    recorded at all; the proposal stays open and the next contact, here a new session, says so once."""
    person = start(directory, capsys, f"removed-{mode}")
    proposal = person.propose(f"{mode}-1")
    question = person.finish(f"{mode}-1", QUESTION)["assistant"]
    assert question["state"] == "recorded"
    person.prompt(f"{mode}-1", "Yes, do it.")
    assert person.tool(action="confirm", proposal_id=proposal, **person.cited())["status"] == "waiting_for_message"
    with host.ready_client(directory, person.user) as client:
        generation = client.dashboard()["brain"]["scope_generation"]
        client.forget([question["event_id"]], kind="events", mode=mode, expected_scope_generation=generation)
    yes = person.finish(f"{mode}-1", "Done.")["user"]
    assert (yes["state"], yes["reason"]) == ("excluded", "capture_stale")
    assert person.persona()["version"] == 1 and person.proposal(proposal)["status"] == "open"
    opening = host.session_context(directory, f"{mode}-2", tools=TOOLS, user_id=person.user)
    assert opening.count(NOTICE) == 1 and f"proposal_id: {proposal}." in opening
    assert NOTICE not in person.prompt(f"{mode}-2", "Hi.")
    assert NOTICE not in host.session_context(directory, f"{mode}-3", tools=TOOLS, user_id=person.user)


def test_a_recorded_yes_that_fails_the_rule_is_reported_once_where_the_conversation_was_not_known(
        directory, capsys, monkeypatch):
    """The original defect's path: a confirmation kept waiting without its conversation (as for a turn whose
    conversation the host could not tell) is recorded, fails the same-conversation rule and leaves the proposal open.
    It is no longer silent: the next per-message context says so once."""
    found = persona_tool.staged_turn
    monkeypatch.setattr(persona_tool, "staged_turn", lambda *args: (found(*args)[0], None))
    person = start(directory, capsys, "unknown-conversation")
    proposal = person.propose("unknown-1")
    person.finish("unknown-1", QUESTION)
    person.prompt("unknown-2", "Yes, do it.")
    answer = person.tool(action="confirm", proposal_id=proposal, **person.cited())
    assert answer["status"] == "waiting_for_message" and "Confirmed" not in answer["note"]
    assert person.finish("unknown-2", "It takes effect from your next message.")["user"]["state"] == "recorded"
    assert person.persona()["version"] == 1 and person.proposal(proposal)["status"] == "open"
    told = person.prompt("unknown-2", "Thanks.")
    assert told.count(NOTICE) == 1 and f"proposal_id: {proposal}." in told
    person.finish("unknown-2", "You're welcome.")
    assert NOTICE not in person.prompt("unknown-2", "Bye.") and not pending(person)


def test_the_mcp_tool_and_a_chat_bot_refuse_a_yes_from_another_conversation_the_same_way(directory, capsys):
    """Claude Code's ``memory_persona`` (the installation's own memory) and a chat bot's persona tool."""
    person = start(directory, capsys, "installation", mcp=True)
    proposal = person.propose("mcp-1")
    person.finish("mcp-1", QUESTION)
    person.prompt("mcp-2", "Yes, do it.")
    assert person.tool(action="confirm", proposal_id=proposal, **person.cited()) == {
        "error": persona_growth.NOT_HERE, "code": "source_unavailable"}
    person.finish("mcp-2", "Let me ask here.")
    person.prompt("mcp-2", "Hm?")
    person.finish("mcp-2", QUESTION)
    person.prompt("mcp-2", "Yes.")
    assert person.tool(action="confirm", proposal_id=proposal, **person.cited())["status"] == "waiting_for_message"
    person.finish("mcp-2", "Done.")
    saved_with_the_change(person, proposal)

    memory, speaker = ChatMemory(directory), Speaker("telegram", "confirm-bot")
    memory.context(speaker, "hello", session="bot-0", turn_id="0")
    memory.record(speaker, "Hi!", session="bot-0", turn_id="0")
    context = memory.context(speaker, "From now on, keep replies to one sentence.", session="bot-1", turn_id="1")
    proposed = memory.persona(speaker, "propose", changes=ONE_SENTENCE, reason=REASON,
                              source_messages=source(context), recording_capture=capture(context))
    memory.record(speaker, QUESTION, session="bot-1", turn_id="1")
    context = memory.context(speaker, "Yes, do it.", session="bot-2", turn_id="2")
    answer = memory.persona(speaker, "confirm", proposal_id=proposed["proposal_id"],
                            source_messages=source(context), recording_capture=capture(context))
    assert answer == {"error": persona_growth.NOT_HERE, "code": "source_unavailable"}


def test_without_the_capture_the_staged_turn_is_still_found_and_a_foreign_reference_is_left_to_the_service(
        directory, capsys):
    """The AI may leave out recording_capture: the cited message's staged turn is found among the recent session
    ledgers. A reference no staged turn here names (another host recording through the API) gets the service's own
    rule only: it is not refused early and not followed up."""
    person = start(directory, capsys, "no-capture")
    proposal = person.propose("nocap-1")
    person.finish("nocap-1", QUESTION)
    person.prompt("nocap-2", "Yes, do it.")
    answer = person.tool(action="confirm", proposal_id=proposal, source_messages=source(person.context))
    assert answer == {"error": persona_growth.NOT_HERE, "code": "source_unavailable"}
    person.finish("nocap-2", QUESTION)
    person.prompt("nocap-2", "Yes.")
    foreign = [{"producer_ref": "some-sdk-host", "source_event_key": "elsewhere:1:user", "source_revision": 1}]
    assert person.tool(action="confirm", proposal_id=proposal, source_messages=foreign)["status"] == (
        "waiting_for_message")
    assert not pending(person)
    assert person.tool(action="confirm", proposal_id=proposal,
                       source_messages=source(person.context))["status"] == "waiting_for_message"
    person.finish("nocap-2", "Done.")
    saved_with_the_change(person, proposal)
