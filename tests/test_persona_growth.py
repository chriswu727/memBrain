"""P2 persona development from explicit feedback: deterministic detection, one quoting proposal per kind, accept,
reject with a 30-day pause, rollback, reset markers, deleted and role-play feedback, archive restore, the API and the
page. Every test runs on a fixed clock where time matters, and nothing calls a model."""
import ast
import copy
import datetime
import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from membrain import desktop, embedded_database, host
from membrain.api import create_app
from membrain.client import default_budget
from membrain.config import configured_service
from membrain.helpers import DomainError, Principal, digest, uid
from membrain.local_profile import load_profile
from membrain.persona import (
    PERSONA_CONVERSATION,
    REASON_CHARACTERS,
    delete_persona_history,
    normalize_card,
    persona_versions,
    render_persona,
    restore_persona,
    set_persona,
)
from membrain.persona import _entry as persona_entry
from membrain.persona_growth import (
    KINDS,
    PROPOSALS_CONVERSATION,
    accept_proposal,
    detect,
    persona_proposals,
    reason_for,
    reject_proposal,
)
from membrain.persona_growth import _entry as proposal_entry

ROOT = Path(__file__).parents[1]
WEB = ROOT / "src" / "membrain" / "web"
CARD = {"name": "Mira", "traits": ["warm"],
        "voice": {"register": "formal", "length": "two or three sentences", "emoji": "", "language": ""},
        "values": ["honesty over flattery"], "boundaries": [], "baseline_mood": None}
CASUAL = {**CARD, "voice": {**CARD["voice"], "register": "casual"}}
UTC = datetime.UTC


def later(days: float) -> datetime.datetime:
    return datetime.datetime.now(UTC) + datetime.timedelta(days=days)


# Detection, without a database -----------------------------------------------------------------------------------

@pytest.mark.parametrize("text, kind", [
    ("you're too formal", "less_formal"), ("You are way too formal.", "less_formal"),
    ("Can you be more casual?", "less_formal"), ("be more casual please", "less_formal"),
    ("Stop being so formal", "less_formal"), ("be more playful", "more_playful"),
    ("I wish you would be more playful", "more_playful"), ("replies are too long", "shorter"),
    ("Your replies are too long", "shorter"), ("Keep it short, please", "shorter"),
    ("please use fewer emojis", "less_emoji"), ("can you be more formal?", "more_formal"),
    ("太正式了", "less_formal"), ("我觉得你说话太正式了", "less_formal"), ("能不能随意一点", "less_formal"),
    ("能不能活泼一点", "more_playful"), ("回复太长了", "shorter"), ("你回复得太长了", "shorter"),
    ("回答详细一点", "longer"), ("能不能少用点表情", "less_emoji"),
])
def test_the_feedback_table_recognises_english_and_chinese_feedback(text, kind):
    assert detect(text) == [kind]


@pytest.mark.parametrize("text", [
    # About something else, or about the user, not the companion's manner.
    "the formal dinner was too long", "I am too formal at work", "The meeting was too formal",
    "That movie was too long", "I like how formal you are", "you're too funny", "too formal",
    "这个会议太正式了", "电影太长了", "太长了", "短一点", "剪短一点", "他太正式了", "头发太短了",
    # Reported, conditional, negated, quoted, role-play, hypothetical or dreamt.
    "My boss said your replies are too long", "if you were less formal it would be odd",
    "you are not too formal", "I never said you're too formal", '"you\'re too formal" is a line from the play',
    "let's role-play: you're too formal, knight!", "我们来角色扮演，你太正式了", "imagine you were more playful",
    "I dreamt you were too formal", "如果你太正式了就不好", "朋友说你太正式了",
    # Quoted or reported with single, curly or no quotes, a colon, or as an example or a character's line.
    "'you're too formal' is an example sentence.", "‘you are too formal’ is what the character says.",
    "My friend: you are too formal.", "The example sentence is: you are too formal.",
    "'be more playful' was the note on the script", "She wrote: be more casual",
    "例句：你太正式了。", "「你太正式了」是他的台词", "朋友：你太正式了", "“你太正式了”这句话怎么翻译",
    # A quote that opens in an earlier sentence of the same message.
    '"Hello. You are too formal for this chat."', '“Hi there. You are too formal.”', "「你好。你太正式了。」",
    # Code is quoted text too: fenced blocks (closed or not) and inline code.
    "```\nYou are too formal for this chat.\n```", "`You are too formal for this chat.`",
    "Here is the fixture:\n```text\nyou're too formal\n", "~~~\n你太正式了\n~~~",
    "", "x" * 2001,
])
def test_narrow_patterns_ignore_false_positives(text):
    assert detect(text) == []


@pytest.mark.parametrize("text, kind", [
    # Ordinary feedback with an apostrophe, a comma or an aside still counts.
    ("You're too formal, honestly", "less_formal"), ("you're too formal", "less_formal"),
    ("I can't lie, you're too formal", "less_formal"), ("Honestly, can you be more casual?", "less_formal"),
    ("你太正式了，放松一点", "less_formal"), ("Use `ls` please. You are too formal.", "less_formal"),
])
def test_quote_and_colon_guards_leave_ordinary_feedback_alone(text, kind):
    assert detect(text) == [kind]


def test_every_kind_proposes_one_field_in_both_languages():
    for kind, spec in KINDS.items():
        assert spec["field"] in ("traits", "voice.register", "voice.length", "voice.emoji"), kind
        assert set(spec["value"]) == {"en", "zh"} and len(spec["label"]) == 2, kind


def test_the_reason_names_the_kind_and_dates_but_never_copies_the_messages():
    sources = [{"text": "can you be more casual?", "recorded_at": "2026-11-01T10:00:00Z"},
               {"text": "you're too formal, Zephyrine", "recorded_at": "2026-11-02T11:00:00Z"},
               {"text": "Be more casual please, " + "really " * 60, "recorded_at": "2026-11-03T09:00:00Z"}]
    reason = reason_for({"language": "en", "kind": "less_formal", "sources": sources})
    assert reason == "Accepted suggestion: more casual, from 3 messages (1 Nov; 2 Nov; 3 Nov)"
    assert "Zephyrine" not in reason and "casual please" not in reason and len(reason) <= REASON_CHARACTERS
    chinese = reason_for({"language": "zh", "kind": "shorter",
                          "sources": [{"text": "回复太长了", "recorded_at": "2026-11-02T10:00:00Z"}] * 3})
    assert chinese == "接受的建议：回复更简短，来自你的 3 条消息（11月2日、11月2日、11月2日）"


def _row(stored, producer="archive-import", role="system"):
    return {"producer_ref": producer, "document": {
        "event_id": "evt-" + uid(), "sequence": 7, "system_time": {"recorded_at": "2026-11-03T10:00:00Z"},
        "observed": {"actor_role": role, "content": {"text": json.dumps(stored)}}}}


def test_records_from_an_archive_are_read_back_strictly():
    proposal = {"persona_proposal": "less_formal", "source_event_ids": ["a", "b", "c"], "language": "en",
                "proposed_at": "2026-11-03T10:00:00Z"}
    decision = {"persona_proposal_decision": "rejected", "proposal_id": "p", "kind": "less_formal",
                "decided_at": "2026-11-03T10:00:00Z", "version": None}
    assert proposal_entry(_row(proposal))["kind"] == "less_formal"
    assert proposal_entry(_row(proposal, producer="membrain-persona-proposals"))["type"] == "proposal"
    assert proposal_entry(_row(decision))["decision"] == "rejected"
    for bad in ({**proposal, "extra": 1}, {**proposal, "persona_proposal": "be_evil"},
                {**proposal, "source_event_ids": ["a", "b"]}, {**proposal, "source_event_ids": ["a", "a", "b"]},
                {**proposal, "language": "fr"}, {**proposal, "proposed_at": "yesterday"},
                {**decision, "version": 3}, {**decision, "persona_proposal_decision": "accepted"},
                {**decision, "persona_proposal_decision": "maybe"}, ["not", "an", "object"]):
        assert proposal_entry(_row(bad)) is None, bad
    assert proposal_entry(_row(proposal, producer="someone-else")) is None
    assert proposal_entry(_row(proposal, role="user")) is None
    # A persona version that claims to come from feedback is checked the same way, and never breaks the listing.
    version = {"persona_version": 2, "card": CARD, "made_by": "feedback", "reason": "r", "action": "feedback",
               "feedback": {"proposal_id": "p", "kind": "less_formal", "source_event_ids": ["a", "b", "c"]}}
    assert persona_entry(_row(version))["feedback"]["kind"] == "less_formal"
    for bad in ({**version, "feedback": {"proposal_id": "p"}}, {**version, "feedback": "text"},
                {**version, "made_by": "user"}):
        assert persona_entry(_row(bad)) is None, bad


@pytest.mark.parametrize("field,stamp", [
    ("proposed_at", "0001-01-01T00:00:00+23:59"), ("proposed_at", "9999-12-31T23:59:59-23:59"),
    ("decided_at", "0001-01-01T00:00:00+23:59"), ("decided_at", "9999-12-31T23:59:59-23:59"),
    ("decided_at", "9999-12-31T23:59:59Z"),
])
def test_archived_proposal_times_and_rejection_deadlines_must_fit_in_utc(field, stamp):
    proposal = {"persona_proposal": "less_formal", "source_event_ids": ["a", "b", "c"], "language": "en",
                "proposed_at": stamp}
    decision = {"persona_proposal_decision": "rejected", "proposal_id": "p", "kind": "less_formal",
                "decided_at": stamp, "version": None}
    assert proposal_entry(_row(proposal if field == "proposed_at" else decision)) is None


def _imports(module: str) -> tuple[set[str], set[str]]:
    package = ROOT / "src" / "membrain"
    inside, outside, pending = set(), set(), [module]
    while pending:
        name = pending.pop()
        if name in inside:
            continue
        inside.add(name)
        path = package / f"{name}.py"
        if not path.is_file():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    pending.extend([node.module.split(".")[0]] if node.module else [a.name for a in node.names])
                elif node.module:
                    outside.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                outside.update(alias.name.split(".")[0] for alias in node.names)
    return inside, outside


def test_persona_growth_imports_no_model_or_network_client():
    # The same guard as the companion layers' (tests/test_maturity_matrix.py once it is merged).
    inside, outside = _imports("persona_growth")
    assert not inside & {"extraction", "semantic", "semantic_provider", "chat_provider", "recall_provider",
                         "answer_review_provider", "embeddings", "local_embeddings", "local_semantics", "cognition",
                         "reasoning", "learning", "outbound", "client", "runtime_client"}
    assert not outside & {"httpx", "requests", "aiohttp", "urllib", "http", "socket", "openai", "anthropic"}


def test_sdk_uses_the_brain_scoped_proposal_routes():
    import httpx

    from membrain.client import MemoryClient

    requests = []

    def handler(request):
        requests.append((request.method, request.url.raw_path.decode()))
        return httpx.Response(200, json={"proposals": []})

    with MemoryClient("http://127.0.0.1:8790", "test", brain_id="my brain",
                      transport=httpx.MockTransport(handler)) as client:
        client.persona_proposals()
        client.accept_persona_proposal("evt/1")
        client.reject_persona_proposal("evt 2")
    assert requests == [("GET", "/v1/brains/my%20brain/persona/proposals"),
                        ("POST", "/v1/brains/my%20brain/persona/proposals/evt%2F1/accept"),
                        ("POST", "/v1/brains/my%20brain/persona/proposals/evt%202/reject")]


def test_every_suggestion_string_on_the_page_has_chinese():
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    start = script.index("// Persona suggestions from feedback (P2) ---")
    section = script[start:script.index("// End of persona suggestions", start)]
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    literals = set(re.findall(r'(?:element\("\w+", |notify\(|confirm\(|: )"([^"]*[A-Za-z]{2}[^"]*)"', section))
    ignored = {"hint", "empty", "tag", "user-text", "secondary", "proposal-side", "proposal-arrow", "proposal-sources",
               "persona-card proposal-diff", "row persona-actions", "meta", "del", "ins", "span"}
    missing = sorted(text for text in literals - ignored if f'"{text}"' not in dictionary)
    assert missing == [] and len(literals - ignored) >= 25
    for kind in KINDS:
        assert f"{kind}:" in section  # Every kind has a label on the page.
    for pattern in ("^(.+): from (\\d+) messages$", "^Accepted on (.+) as version (\\d+)\\.$",
                    "^Rejected on (.+)\\. None of this kind until (.+)\\.$", "^(\\d+) waiting$",
                    "^(.+): paused until (.+) after you rejected it\\.$"):
        assert pattern in dictionary, pattern
    for message in ("That suggestion is not available.", "That suggestion is no longer open.",
                    "The card already has this change.", "accepted suggestion"):
        assert f'"{message}"' in dictionary, message
    # The proposal's header reads like the design's example ("more casual: from 3 messages").
    assert "`${PROPOSAL_KINDS[proposal.kind] || proposal.kind}: from ${proposal.source_count} messages`" in section
    assert "30 days" in section and "proposalChange(proposal.change)" in section
    html = (WEB / "memory.html").read_text(encoding="utf-8")
    block = html[html.index("<!-- Persona suggestions from feedback (P2) -->"):html.index("<!-- End of persona suggestions -->")]
    assert 'id="persona-proposals"' in block and "30 days" in block
    assert block in html[html.index('id="view-persona"'):]  # On the Companion tab.
    # Any change to the card refreshes the suggestions: one may be withdrawn once the card already has it.
    assert "await Promise.all([loadMood(), loadProposals()]);" in script


# On a real service ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("growth") / "installation"
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
    return service, principal, service.create_brain(principal, "Persona growth test")["id"]


def say(brain, text, conversation="chat", *, role="user", producer="growth-test", hint="unknown"):
    service, principal, ident = brain
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
        "target": {"brain_ref": ident, "conversation_ref": conversation, "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "events": [{
            "source_event_key": uid(), "source_revision": 1, "producer_ref": producer, "actor_ref": role,
            "actor_role": role, "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
            "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
            "interpretation_hint": hint, "delivery_state": "received" if role == "user" else "delivered",
            "parent_source_event_keys": [],
        }]},
    })
    return result


def said(brain, text, **kwargs):
    result = say(brain, text, **kwargs)
    assert result["outcome"] == "completed", result
    return result["result"]["accepted_event_ids"][0]


def listing(brain, **kwargs):
    service, principal, ident = brain
    return persona_proposals(service, principal, ident, **kwargs)


def forget(brain, event_ids):
    service, principal, ident = brain
    generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
    result = service.handle(principal, {
        "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
        "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
        "payload": {"idempotency_key": uid(), "selector": {"kind": "events", "ids": list(event_ids)},
                    "mode": "erase_content", "expected_scope_generation": generation}})
    assert result["outcome"] == "completed", result


def test_cross_session_three_requests_make_one_proposal_accept_then_roll_back(installation):
    directory = installation[0]
    user = "growth-" + uid()
    host.session_context(directory, "s1", user_id=user)
    with host.ready_client(directory, user) as client:
        assert client.set_persona(CARD, made_by="host", reason="Initial character")["version"] == 1

    # Sessions 1 and 2: the user asks three times, in different words, for more casual replies.
    host.prompt_context(directory, "s1", "Can you be more casual?", turn_id="t1", user_id=user)
    host.finish_turn(directory, "s1", "Certainly. I shall endeavour to be more casual.", turn_id="t1", user_id=user)
    host.prompt_context(directory, "s1", "You're too formal, honestly", turn_id="t2", user_id=user)
    host.finish_turn(directory, "s1", "Understood.", turn_id="t2", user_id=user)
    with host.ready_client(directory, user) as client:
        assert client.persona_proposals()["proposals"] == []  # Two are not enough.
    host.session_context(directory, "s2", user_id=user)
    host.prompt_context(directory, "s2", "Please be more casual with me", turn_id="t3", user_id=user)
    host.finish_turn(directory, "s2", "Very well.", turn_id="t3", user_id=user)

    # Session 3: one proposal, quoting the three messages; the context and the versions have not changed.
    turn = host.session_context(directory, "s3", user_id=user)
    assert '<membrain-persona version="1">' in turn and "Voice: register formal" in turn
    assert "proposal" not in turn.lower() and "from your feedback" not in turn.lower()  # Not even a notice.
    with host.ready_client(directory, user) as client:
        listed = client.persona_proposals()
        assert listed["open"] == 1 and len(listed["proposals"]) == 1
        proposal = listed["proposals"][0]
        assert (proposal["kind"], proposal["label"], proposal["source_count"]) == ("less_formal", "more casual", 3)
        assert [source["text"] for source in proposal["sources"]] == [
            "Can you be more casual?", "You're too formal, honestly", "Please be more casual with me"]
        assert all(source["event_id"] and source["recorded_at"] for source in proposal["sources"])
        assert proposal["change"] == {"field": "voice.register", "before": "formal", "after": "casual"}
        assert proposal["proposed_card"] == normalize_card(CASUAL)
        assert [v["version"] for v in client.persona_versions()["versions"]] == [1]
        brain_id = client.brain_id
    host.prompt_context(directory, "s3", "Be more casual!", turn_id="t4", user_id=user)  # A fourth: still one.
    with host.ready_client(directory, user) as client:
        assert len(client.persona_proposals()["proposals"]) == 1

        accepted = client.accept_persona_proposal(proposal["id"])
        version = accepted["persona"]
        assert (version["version"], version["made_by"], version["action"]) == (2, "feedback", "feedback")
        assert version["card"] == normalize_card(CASUAL)
        assert version["reason"].startswith("Accepted suggestion: more casual, from 3 messages (")
        quoted = [m["text"] for m in client.persona_versions()["versions"][0]["feedback_messages"]]
        for text in ("Can you be more casual?", "You're too formal, honestly", "Please be more casual with me"):
            assert text not in version["reason"] and text in quoted  # Quoted live, never copied into the version.
        assert version["feedback"] == {"proposal_id": proposal["id"], "kind": "less_formal",
                                       "source_event_ids": [s["event_id"] for s in proposal["sources"]]}
        assert accepted["proposal"]["status"] == "accepted" and accepted["proposal"]["version"] == 2
        assert client.persona_proposals()["open"] == 0  # The fourth message was used up by the decision.

    # Session 4: the context carries version 2, made by accepted feedback.
    turn = host.session_context(directory, "s4", user_id=user)
    assert render_persona({"version": 2, "card": normalize_card(CASUAL)}) in turn
    with host.ready_client(directory, user) as client:
        assert client.persona_versions()["versions"][0]["made_by"] == "feedback"
        # Rollback: restoring version 1 saves its content as version 3.
        restored = client.restore_persona(1, made_by="user")
    assert (restored["version"], restored["restored_from"]) == (3, 1)
    turn = host.session_context(directory, "s5", user_id=user)
    assert render_persona({"version": 3, "card": normalize_card(CARD)}) in turn
    assert brain_id


def test_three_make_one_two_make_none_and_only_the_users_own_messages_count(brain):
    service, principal, ident = brain
    said(brain, "you're too formal")
    said(brain, "Can you be more casual?", conversation="another-session")
    # None of these count: the assistant, the memory page, an import, role-play, a hypothetical, a quotation.
    said(brain, "you're too formal", role="assistant")
    said(brain, "you're too formal", producer="membrain-memory-page", conversation="membrain-memory-page")
    said(brain, "you're too formal", producer="membrain-import:chatgpt")
    for hint in ("roleplay", "hypothetical", "quotation", "dream"):
        said(brain, "you're too formal", hint=hint)
    said(brain, "the formal dinner was too long")
    assert listing(brain)["proposals"] == []
    third = said(brain, "Please be less formal")
    proposals = listing(brain)["proposals"]
    assert len(proposals) == 1 and proposals[0]["status"] == "open" and proposals[0]["sources"][-1]["event_id"] == third
    for text in ("you're too formal", "be more casual", "太正式了"):
        said(brain, text)
    assert len(listing(brain)["proposals"]) == 1  # Six matching messages: still one proposal.
    # Different kinds are counted apart: two "too long" and one "more playful" make nothing more.
    said(brain, "your replies are too long")
    said(brain, "回复太长了")
    said(brain, "be more playful")
    assert [p["kind"] for p in listing(brain)["proposals"]] == ["less_formal"]


def test_chinese_feedback_proposes_a_chinese_card_value(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    for text in ("太正式了", "你说话太正式了吧", "能不能随意一点"):
        said(brain, text)
    proposal = listing(brain)["proposals"][0]
    assert (proposal["kind"], proposal["language"]) == ("less_formal", "zh")
    assert proposal["change"] == {"field": "voice.register", "before": "formal", "after": "随意"}
    accepted = accept_proposal(service, principal, ident, proposal["id"])["persona"]
    assert accepted["card"]["voice"]["register"] == "随意"
    assert accepted["reason"].startswith("接受的建议：更随意，来自你的 3 条消息（") and "太正式了" not in accepted["reason"]
    quoted = [m["text"] for m in persona_versions(service, principal, ident)["versions"][0]["feedback_messages"]]
    assert "太正式了" in quoted
    # A playful trait is added to the traits, not put in place of them.
    for text in ("能不能活泼一点", "你可以活泼一点吗", "be more playful"):
        said(brain, text)
    proposal = next(p for p in listing(brain)["proposals"] if p["status"] == "open")
    assert proposal["change"] == {"field": "traits", "before": ["warm"], "after": ["warm", "活泼"]}


def test_a_rejected_kind_pauses_for_30_days_and_needs_new_feedback(brain):
    service, principal, ident = brain
    start = later(0)
    for text in ("replies are too long", "Keep it short, please", "回复太长了"):
        said(brain, text)
    proposal = listing(brain, now=start)["proposals"][0]
    rejected = reject_proposal(service, principal, ident, proposal["id"], now=start)
    assert rejected["proposal"]["status"] == "rejected" and rejected["open"] == 0
    assert "persona" not in rejected and persona_versions(service, principal, ident)["versions"] == []
    until = rejected["proposal"]["paused_until"]
    assert datetime.datetime.fromisoformat(until.replace("Z", "+00:00")) == start + datetime.timedelta(days=30)
    assert rejected["pauses"] == [{"kind": "shorter", "label": "shorter replies", "until": until}]
    with pytest.raises(DomainError) as twice:
        reject_proposal(service, principal, ident, proposal["id"], now=start)
    assert twice.value.code == "version_conflict"
    # After the pause, the feedback the rejection used never comes back on its own.
    assert listing(brain, now=later(31))["open"] == 0
    # New feedback during the pause: nothing on day 29, one proposal on day 31, from the new messages only.
    fresh = [said(brain, text) for text in ("your replies are too long", "be shorter", "你回复得太长了")]
    on_29 = listing(brain, now=later(29))
    assert on_29["open"] == 0 and [p["kind"] for p in on_29["pauses"]] == ["shorter"]
    on_31 = listing(brain, now=later(31))
    opened = [p for p in on_31["proposals"] if p["status"] == "open"]
    assert len(opened) == 1 and [s["event_id"] for s in opened[0]["sources"]] == fresh
    assert on_31["pauses"] == []
    # Another kind was never paused.
    for text in ("be more playful", "be more playful!", "could you be more playful"):
        said(brain, text)
    assert {p["kind"] for p in listing(brain, now=later(1))["proposals"] if p["status"] == "open"} == {
        "shorter", "more_playful"}


def test_feedback_before_the_persona_reset_marker_never_counts(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    said(brain, "you're too formal")
    said(brain, "be more casual")
    deleted = delete_persona_history(service, principal, ident)
    assert deleted["marker"]["marker"] == "history_deleted"
    after = [said(brain, "Please be less formal")]
    assert listing(brain)["proposals"] == []
    after += [said(brain, "you're too formal"), said(brain, "太正式了")]
    proposal = listing(brain)["proposals"][0]
    assert [source["event_id"] for source in proposal["sources"]] == after
    assert proposal["change"]["before"] == ""  # The history (and the card) was deleted.
    # "Delete personality history" erases the suggestions too, and the next one starts after the new marker.
    delete_persona_history(service, principal, ident)
    assert listing(brain)["proposals"] == []


def test_deleting_an_empty_history_still_cuts_off_earlier_feedback(brain):
    service, principal, ident = brain
    said(brain, "you're too formal")
    said(brain, "be more casual")
    # No persona version and no suggestion yet; feedback recorded without eligibility records (older data) too.
    with service.database.transaction(principal) as conn:
        conn.execute("UPDATE memory_events SET deleted=true WHERE brain_id=%s AND conversation_id=%s",
                     (ident, PROPOSALS_CONVERSATION))
    deleted = delete_persona_history(service, principal, ident)
    assert deleted["deleted_versions"] == 0 and deleted["marker"]["marker"] == "history_deleted"
    said(brain, "Can you be more casual?")
    assert listing(brain)["proposals"] == []  # The two earlier messages are before the cut-off.


def test_deleting_a_source_withdraws_the_proposal_and_is_never_quoted(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    first = said(brain, "you're too formal, Zephyrine")
    said(brain, "be more casual")
    said(brain, "Can you be more casual?")
    proposal = listing(brain)["proposals"][0]
    forget(brain, [first])
    withdrawn = listing(brain)["proposals"][0]
    assert (withdrawn["id"], withdrawn["status"], withdrawn["withdrawn_because"]) == (
        proposal["id"], "withdrawn", "sources_removed")
    assert withdrawn["source_count"] == 2 and "Zephyrine" not in json.dumps(withdrawn)
    with pytest.raises(DomainError) as refused:
        accept_proposal(service, principal, ident, proposal["id"])
    assert refused.value.code == "version_conflict"
    assert [v["version"] for v in persona_versions(service, principal, ident)["versions"]] == [1]
    # One more message makes three again: a new proposal, never the deleted message.
    said(brain, "stop being so formal")
    proposals = listing(brain)["proposals"]
    assert [p["status"] for p in proposals] == ["open", "withdrawn"] and "Zephyrine" not in json.dumps(proposals)
    # The card already having the change withdraws a proposal too.
    set_persona(service, principal, ident, CASUAL, made_by="user")
    assert [p["withdrawn_because"] for p in listing(brain)["proposals"]] == ["already_in_card", "sources_removed"]


def test_a_deleted_feedback_message_leaves_an_accepted_version_and_its_rollback(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    first = said(brain, "you're too formal, Zephyrine")
    said(brain, "be more casual")
    said(brain, "Can you be more casual?")
    proposal = listing(brain)["proposals"][0]
    accept_proposal(service, principal, ident, proposal["id"])
    accepted = persona_versions(service, principal, ident)["versions"][0]
    assert [message["text"] for message in accepted["feedback_messages"]][0] == "you're too formal, Zephyrine"
    forget(brain, [first])
    # The change the user accepted stays; the deleted message's words are gone from the history.
    history = persona_versions(service, principal, ident)
    assert history["versions"][0]["card"]["voice"]["register"] == "casual"
    assert len(history["versions"][0]["feedback_messages"]) == 2 and "Zephyrine" not in json.dumps(history)
    restore_persona(service, principal, ident, 1, made_by="user")  # Rolling back keeps them gone too.
    history = persona_versions(service, principal, ident)
    assert history["versions"][0]["card"]["voice"]["register"] != "casual" and "Zephyrine" not in json.dumps(history)
    assert "Zephyrine" not in json.dumps(listing(brain))


def test_an_archive_from_before_the_deletion_cannot_bring_the_words_back(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    first = said(brain, "you're too formal, Zephyrine")
    said(brain, "be more casual")
    said(brain, "Can you be more casual?")
    accept_proposal(service, principal, ident, listing(brain)["proposals"][0]["id"])

    def act(brain_id, action, payload):
        result = service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": action,
            "target": {"brain_ref": brain_id, "conversation_ref": "chat", "branch_ref": "main"}, "payload": payload})
        assert result["outcome"] == "completed", result
        return result["result"]

    def generation(brain_id):
        return service.dashboard(principal, brain_id)["brain"]["scope_generation"]

    exported = act(ident, "export", {"include_events": True, "include_working_states": True,
                                     "include_assertions": True, "include_provenance": True,
                                     "include_tombstones": True, "budget": default_budget(64000)})
    offline = copy.deepcopy(service.download_archive(principal, exported["archive_id"])["document"])
    assert "Zephyrine" in json.dumps(offline)
    forget(brain, [first])
    copy_brain = service.create_brain(principal, "Restored after deletion")["id"]
    uploaded = service.upload_archive(principal, copy_brain, offline)
    act(copy_brain, "restore", {"uploaded_archive_ref": uploaded["archive_id"],
                                "expected_manifest_sha256": uploaded["manifest_sha256"], "mode": "new_brain",
                                "apply_current_tombstones": True, "expected_scope_generation": generation(copy_brain),
                                "budget": default_budget(64000)})
    restored = persona_versions(service, principal, copy_brain)
    assert restored["versions"][0]["made_by"] == "feedback" and "Zephyrine" not in json.dumps(restored)
    assert "Zephyrine" not in json.dumps(persona_proposals(service, principal, copy_brain))


def _restored(brain, name):
    import httpx

    from membrain.client import MemoryClient

    service, principal, ident = brain

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        restored = service.create_brain(principal, name)["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=restored)
    return restored


def test_feedback_from_imported_or_page_conversations_never_counts_even_after_a_restore(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    for text in ("you're too formal", "be more casual", "Can you be more casual?"):
        said(brain, text, producer="membrain-import:chatgpt")
    for text in ("be more playful", "be more playful!", "could you be more playful"):
        said(brain, text, conversation="page-chat", producer="membrain-memory-page")
    assert listing(brain)["proposals"] == []
    # A restore files every message under archive-import and loses who wrote it; it must not turn another
    # assistant's conversation, or text typed on the page, into feedback to this companion.
    copy_brain = _restored(brain, "Restored imports")
    assert persona_proposals(service, principal, copy_brain)["proposals"] == []


def test_suggestions_made_before_a_backup_stay_valid_after_the_restore(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    for text in ("you're too formal", "be more casual", "Can you be more casual?"):
        said(brain, text)
    original = listing(brain)["proposals"]
    assert [(p["kind"], p["status"], p["source_count"]) for p in original] == [("less_formal", "open", 3)]
    copy_brain = _restored(brain, "Restored suggestion")
    restored = persona_proposals(service, principal, copy_brain)["proposals"]
    assert [(p["kind"], p["status"], p["source_count"]) for p in restored] == [("less_formal", "open", 3)]
    assert accept_proposal(service, principal, copy_brain, restored[0]["id"])["persona"]["made_by"] == "feedback"


@pytest.mark.parametrize("field,stamp", [("proposed_at", "0001-01-01T00:00:00+23:59"),
                                       ("decided_at", "9999-12-31T23:59:59Z")])
def test_restoring_malformed_proposal_times_keeps_the_companion_api_available(installation, brain, field, stamp):
    import httpx

    from membrain.client import MemoryClient

    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    for text in ("you're too formal", "be more casual", "Can you be more casual?"):
        said(brain, text)
    proposal = listing(brain)["proposals"][0]
    if field == "decided_at":
        reject_proposal(service, principal, ident, proposal["id"])

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        exported = client.export()["result"]
        document = service.download_archive(principal, exported["archive_id"])["document"]
        changed = 0
        for event in document["events"]:
            try:
                content = json.loads(event["observed"]["content"].get("text") or "")
            except ValueError:
                continue
            if isinstance(content, dict) and field in content:
                content[field] = stamp
                event["observed"]["content"]["text"] = json.dumps(content)
                event["content_sha256"] = digest(event["observed"]["content"])
                changed += 1
        assert changed == 1
        restored = service.create_brain(principal, "Malformed proposal time")['id']
        uploaded = service.upload_archive(principal, restored, document)
        client.restore(uploaded["archive_id"], expected_manifest_sha256=uploaded["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=restored)
    key = "proposal-time-fixture"
    settings = replace(installation[2], api_keys={hashlib.sha256(key.encode()).hexdigest(): principal})
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1", raise_server_exceptions=False) as page:
        response = page.get(f"/v1/brains/{restored}/persona/proposals", headers={"Authorization": f"Bearer {key}"})
    assert response.status_code == 200, response.text
    assert stamp not in response.text


def test_native_feedback_given_before_a_backup_still_counts_after_the_restore(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    said(brain, "you're too formal")
    said(brain, "be more casual")
    for text in ("be more casual please", "Can you be more casual?", "you are too formal"):
        said(brain, text, producer="membrain-import:chatgpt")  # Another assistant's chat never counts.
    assert listing(brain)["proposals"] == []
    copy_brain = _restored(brain, "Restored progress")
    assert persona_proposals(service, principal, copy_brain)["proposals"] == []
    third = said((service, principal, copy_brain), "Please be more casual with me")
    proposals = persona_proposals(service, principal, copy_brain)["proposals"]
    assert [(p["kind"], p["status"], p["source_count"]) for p in proposals] == [("less_formal", "open", 3)]
    quoted = [s["text"] for s in proposals[0]["sources"]]
    assert quoted == ["you're too formal", "be more casual", "Please be more casual with me"]
    assert proposals[0]["sources"][-1]["event_id"] == third


def test_decisions_leave_the_other_layers_unchanged(brain):
    from membrain.affect import affect_records
    from membrain.mood import mood_state
    from membrain.relationship import add_boundary, relationship

    service, principal, ident = brain
    today, now = datetime.date.today(), later(0)
    set_persona(service, principal, ident, {**CARD, "baseline_mood": {"label": "calm", "valence": 1, "energy": 1}},
                made_by="host")
    add_boundary(service, principal, ident, "my job", [])

    def layers():
        return (relationship(service, principal, ident, today=today), mood_state(service, principal, ident, now=now),
                affect_records(service, principal, ident))

    for text in ("you're too formal", "be more casual", "be less formal", "be more playful", "be more playful!",
                 "could you be more playful"):
        said(brain, text)
    before = layers()
    proposals = {p["kind"]: p for p in listing(brain)["proposals"]}
    accept_proposal(service, principal, ident, proposals["less_formal"]["id"])
    reject_proposal(service, principal, ident, proposals["more_playful"]["id"])
    restore_persona(service, principal, ident, 1, made_by="user")
    assert layers() == before


def test_records_are_never_learned_recalled_or_counted_and_cannot_be_planted(brain, monkeypatch):
    from membrain import learning_windows

    service, principal, ident = brain
    scheduled = []
    monkeypatch.setattr(learning_windows, "enqueue_window",
                        lambda conn, svc, who, brain_row, target, *args, **kwargs: scheduled.append(
                            target["conversation_ref"]))
    monkeypatch.setattr(service, "semantic_processor", object(), raising=False)
    for text in ("you're too formal", "be more casual", "be less formal", "be more playful", "be more playful!",
                 "could you be more playful"):
        said(brain, text)
    proposals = {p["kind"]: p for p in listing(brain)["proposals"]}
    accept_proposal(service, principal, ident, proposals["less_formal"]["id"])
    reject_proposal(service, principal, ident, proposals["more_playful"]["id"])
    assert scheduled and set(scheduled) == {"chat"}  # The user's own messages learn; suggestions never do.
    monkeypatch.undo()
    status = service.memory_status(principal, ident)["recorded_messages"]
    assert status == 6
    service.work_once(principal, ident)
    roles = ("user", "assistant", "operator", "tool")
    assert "persona_proposal" not in str(service.timeline(principal, ident, roles=roles))
    # Only memBrain writes suggestions: observing into their conversation is refused.
    planted = say(brain, json.dumps({"persona_proposal": "more_emoji", "source_event_ids": ["a", "b", "c"],
                                     "language": "en", "proposed_at": "2026-11-03T00:00:00Z"}),
                  conversation=PROPOSALS_CONVERSATION)
    assert planted["outcome"] == "rejected" and planted["error"]["code"] == "invalid_evidence"
    # Feedback typed into the persona conversation is refused before it could count.
    assert say(brain, "be more casual", conversation=PERSONA_CONVERSATION)["outcome"] == "rejected"
    assert [p["kind"] for p in listing(brain)["proposals"]] == ["more_playful", "less_formal"]


def test_restored_archives_keep_proposals_and_decisions(brain):
    import httpx

    from membrain.client import MemoryClient

    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="host")
    for text in ("you're too formal", "be more casual", "be less formal", "your replies are too long",
                 "be shorter", "Keep it short, please", "be more playful", "be more playful!",
                 "could you be more playful"):
        said(brain, text)
    proposals = {p["kind"]: p for p in listing(brain)["proposals"]}
    now = later(0)
    accept_proposal(service, principal, ident, proposals["less_formal"]["id"], now=now)
    reject_proposal(service, principal, ident, proposals["shorter"]["id"], now=now)
    original = listing(brain, now=now)

    def handle(request):
        return httpx.Response(200, json=service.handle(principal, json.loads(request.content)))

    with MemoryClient("http://memory.test", "k", ident, transport=httpx.MockTransport(handle)) as client:
        archive = client.export()["result"]
        copy = service.create_brain(principal, "Restored growth")["id"]
        client.restore(archive["archive_id"], expected_manifest_sha256=archive["manifest_sha256"],
                       expected_scope_generation=1, mode="new_brain", brain_id=copy)
    restored = persona_proposals(service, principal, copy, now=now)
    def summary(result):
        return sorted((p["kind"], p["status"], p["paused_until"], p["version"], [s["text"] for s in p["sources"]])
                      for p in result["proposals"])

    assert summary(restored) == summary(original) and len(restored["proposals"]) == 3
    assert restored["pauses"] == original["pauses"]
    version = persona_versions(service, principal, copy)["versions"][0]
    assert (version["version"], version["made_by"], version["feedback"]["kind"]) == (2, "feedback", "less_formal")
    # The open one can still be accepted in the restored brain; the paused one stays paused.
    opened = next(p for p in restored["proposals"] if p["status"] == "open")
    assert accept_proposal(service, principal, copy, opened["id"], now=now)["persona"]["version"] == 3
    assert persona_proposals(service, principal, copy, now=now)["open"] == 0


def test_api_routes_check_keys_owners_and_decisions_and_erase_all_removes_everything(installation, brain):
    service, principal, ident = brain
    settings = replace(installation[2], api_keys={hashlib.sha256(b"growth-test-key").hexdigest(): principal})
    path = f"/v1/brains/{ident}/persona/proposals"
    foreign = service.create_brain(Principal(principal.tenant_id, uid()), "Foreign")["id"]
    for text in ("you're too formal", "be more casual", "be less formal"):
        said(brain, text)
    with TestClient(create_app(settings, service), base_url="http://127.0.0.1",
                    headers={"Authorization": "Bearer growth-test-key"}) as client:
        assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
        proposal = client.get(path).json()["proposals"][0]
        for method, suffix in (("GET", ""), ("POST", f"/{proposal['id']}/accept"), ("POST", f"/{proposal['id']}/reject")):
            denied = client.request(method, f"/v1/brains/{foreign}/persona/proposals{suffix}")
            assert denied.status_code == 404, (method, suffix)
            assert client.request(method, path + suffix, headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert client.post(path + "/no-such-proposal/accept").status_code == 404
        accepted = client.post(path + f"/{proposal['id']}/accept")
        assert accepted.status_code == 200 and accepted.json()["persona"]["made_by"] == "feedback"
        again = client.post(path + f"/{proposal['id']}/reject")
        assert again.status_code == 409 and again.json()["error"]["message"] == "That suggestion is no longer open."
        assert client.get(f"/v1/brains/{ident}/persona").json()["version"] == 1
        # Erasing all memory removes suggestions and decisions with everything else.
        generation = service.dashboard(principal, ident)["brain"]["scope_generation"]
        erased = service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "forget",
            "target": {"brain_ref": ident}, "payload": {
                "idempotency_key": uid(), "selector": {"kind": "all_authorized_scope", "ids": []},
                "mode": "erase_content", "expected_scope_generation": generation}})
        assert erased["outcome"] == "completed", erased
        assert client.get(path).json()["proposals"] == []
    with service.database.transaction(principal) as conn:
        left = conn.execute("SELECT count(*) AS value FROM memory_events WHERE brain_id=%s AND conversation_id=%s "
                            "AND NOT deleted", (ident, PROPOSALS_CONVERSATION)).fetchone()["value"]
    assert left == 0


# Contradictory feedback ------------------------------------------------------------------------------------------
# Kinds that edit the same card field in opposite directions. The user's latest direction decides: a suggestion
# never rests on feedback the user has since contradicted, and two contradictory suggestions are never open at once.

def _open(brain, **kwargs):
    return [p for p in listing(brain, **kwargs)["proposals"] if p["status"] == "open"]


def test_newer_opposite_feedback_withdraws_an_open_suggestion_and_never_leaves_two_open(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, {**CARD, "voice": {**CARD["voice"], "register": "neutral"}},
                made_by="user")
    for text in ("you're too formal", "be more casual please", "太正式了"):
        said(brain, text)
    assert [p["kind"] for p in _open(brain)] == ["less_formal"]
    # The user changes direction: one complaint the other way already contradicts the open suggestion.
    turn = said(brain, "you're too casual")
    listed = listing(brain)["proposals"]
    assert _open(brain) == []
    withdrawn = next(p for p in listed if p["kind"] == "less_formal")
    assert withdrawn["status"] == "withdrawn" and withdrawn["withdrawn_because"] == "contradicted"
    # Two more the new way make a suggestion from the new direction only, never two at once.
    later_two = [said(brain, text) for text in ("you are way too casual now", "be more formal please")]
    opened = _open(brain)
    assert [p["kind"] for p in opened] == ["more_formal"]
    assert [s["event_id"] for s in opened[0]["sources"]] == [turn, *later_two]


def test_feedback_before_the_latest_opposite_complaint_does_not_count(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, {**CARD, "voice": {**CARD["voice"], "length": "medium"}}, made_by="user")
    said(brain, "your replies are too long")
    said(brain, "Keep it short, please")
    said(brain, "your replies are too short")  # The other way: the two before it no longer count.
    said(brain, "回复太长了")
    assert _open(brain) == []
    said(brain, "be shorter")
    assert _open(brain) == []
    third = said(brain, "you write too much")
    opened = _open(brain)
    assert [p["kind"] for p in opened] == ["shorter"] and opened[0]["source_count"] == 3
    assert opened[0]["sources"][-1]["event_id"] == third


def test_an_accepted_change_uses_up_older_feedback_asking_the_opposite_way(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="user")
    # Two old complaints the other way, then three that make the suggestion, which is accepted.
    said(brain, "you're too casual")
    said(brain, "be more formal please")
    for text in ("you're too formal", "be more casual please", "太正式了"):
        said(brain, text)
    proposal = _open(brain)[0]
    assert proposal["kind"] == "less_formal"
    accept_proposal(service, principal, ident, proposal["id"])
    # The old complaints were about the card before the change: one new message cannot join them into a suggestion
    # to undo it. It takes three after the change.
    said(brain, "you are way too casual now")
    assert _open(brain) == []
    said(brain, "you're too casual")
    assert _open(brain) == []
    said(brain, "be more formal please")
    assert [p["kind"] for p in _open(brain)] == ["more_formal"]


def test_a_rejected_suggestion_does_not_hide_newer_opposite_feedback(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, {**CARD, "voice": {**CARD["voice"], "length": "medium"}}, made_by="user")
    start = later(0)
    for text in ("your replies are too long", "Keep it short, please", "回复太长了"):
        said(brain, text)
    reject_proposal(service, principal, ident, _open(brain, now=start)[0]["id"], now=start)
    for text in ("your replies are too short", "be more detailed", "回答详细一点"):
        said(brain, text)
    assert [p["kind"] for p in _open(brain, now=start)] == ["longer"]


def test_kinds_on_other_fields_are_not_contradictions(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, CARD, made_by="user")
    for text in ("you're too formal", "be more casual please", "太正式了"):
        said(brain, text)
    for text in ("your replies are too short", "be more detailed", "回答详细一点"):
        said(brain, text)
    assert {p["kind"] for p in _open(brain)} == {"less_formal", "longer"}


def test_opposite_kinds_edit_the_same_field_and_are_symmetric():
    from membrain.persona_growth import OPPOSITES

    for kind, opposite in OPPOSITES.items():
        assert OPPOSITES[opposite] == kind and KINDS[kind]["field"] == KINDS[opposite]["field"] != "traits"
    assert set(KINDS) - set(OPPOSITES) == {"more_playful"}


# A contradiction is never forgotten in a long history ------------------------------------------------------------

NEUTRAL = {**CARD, "voice": {**CARD["voice"], "register": "neutral"}}
FILLER = "the formal dinner was too long"  # Matches the feedback stems but is not feedback.


def _contradicted(brain):
    service, principal, ident = brain
    set_persona(service, principal, ident, NEUTRAL, made_by="user")
    for text in ("you're too formal", "be more casual please", "太正式了"):
        said(brain, text)
    against = said(brain, "you're too casual")
    statuses = {p["kind"]: (p["status"], p["withdrawn_because"]) for p in listing(brain)["proposals"]}
    assert statuses == {"less_formal": ("withdrawn", "contradicted")}
    return against


def _observe_many(brain, texts, size=1000):
    service, principal, ident = brain
    for start in range(0, len(texts), size):
        result = service.handle(principal, {
            "message_type": "request", "contract_version": "1.0.0-draft", "request_id": uid(), "action": "observe",
            "target": {"brain_ref": ident, "conversation_ref": "chat", "branch_ref": "main"},
            "payload": {"idempotency_key": uid(), "events": [{
                "source_event_key": uid(), "source_revision": 1, "producer_ref": "growth-test", "actor_ref": "user",
                "actor_role": "user", "event_kind": "message", "content": {"media_type": "text/plain", "text": text},
                "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
                "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": [],
            } for text in texts[start:start + size]]}})
        assert result["outcome"] == "completed", result


def test_a_contradiction_stays_after_many_later_stem_matching_messages(brain, monkeypatch):
    import membrain.persona_growth as growth

    _contradicted(brain)
    monkeypatch.setattr(growth, "SCAN_ROWS", 3)
    for _ in range(5):
        said(brain, FILLER)
    statuses = {p["kind"]: (p["status"], p["withdrawn_because"]) for p in listing(brain)["proposals"]}
    assert statuses == {"less_formal": ("withdrawn", "contradicted")}


def test_a_contradiction_stays_past_the_real_scan_limit(brain):
    import membrain.persona_growth as growth

    _contradicted(brain)
    _observe_many(brain, [FILLER] * (growth.SCAN_ROWS + 10))
    statuses = {p["kind"]: (p["status"], p["withdrawn_because"]) for p in listing(brain)["proposals"]}
    assert statuses == {"less_formal": ("withdrawn", "contradicted")}


def test_deleting_the_contradicting_message_reopens_the_suggestion(brain):
    against = _contradicted(brain)
    forget(brain, [against])
    opened = _open(brain)
    assert [p["kind"] for p in opened] == ["less_formal"]
    assert all(s["event_id"] != against for s in opened[0]["sources"])


def test_contradicting_feedback_before_the_persona_reset_never_blocks_new_feedback(brain):
    service, principal, ident = brain
    _contradicted(brain)
    delete_persona_history(service, principal, ident)
    assert listing(brain)["proposals"] == []
    set_persona(service, principal, ident, NEUTRAL, made_by="user")
    fresh = [said(brain, text) for text in ("you're too formal", "be more casual please", "太正式了")]
    opened = _open(brain)
    assert [p["kind"] for p in opened] == ["less_formal"]
    assert [s["event_id"] for s in opened[0]["sources"]] == fresh


def test_a_contradiction_survives_an_archive_restore(brain):
    service, principal, ident = brain
    _contradicted(brain)
    copy_brain = _restored(brain, "Restored contradiction")
    statuses = {p["kind"]: (p["status"], p["withdrawn_because"])
                for p in persona_proposals(service, principal, copy_brain)["proposals"]}
    assert statuses == {"less_formal": ("withdrawn", "contradicted")}
    # Restored "less formal" feedback before the contradiction still does not count toward a new suggestion.
    said((service, principal, copy_brain), "you're too formal")
    assert [p for p in persona_proposals(service, principal, copy_brain)["proposals"] if p["status"] == "open"] == []


def test_the_contradiction_check_reads_every_page_of_a_long_history(brain, monkeypatch):
    import membrain.persona_growth as growth

    service, principal, ident = brain
    set_persona(service, principal, ident, NEUTRAL, made_by="user")
    for text in ("you're too formal", "be more casual please", "太正式了"):
        said(brain, text)
    monkeypatch.setattr(growth, "SCAN_ROWS", 3)
    for _ in range(7):  # More than two pages between the suggestion and the contradiction, then more after it.
        said(brain, FILLER)
    said(brain, "you're too casual")
    for _ in range(4):
        said(brain, FILLER)
    statuses = {p["kind"]: (p["status"], p["withdrawn_because"]) for p in listing(brain)["proposals"]}
    assert statuses == {"less_formal": ("withdrawn", "contradicted")}
