"""The companion switch: the persona, simulated mood and familiarity can be turned off, and on again, per person.

Off leaves out exactly the persona block, the mood block and the familiarity part of the relationship block. The
boundaries (and their recall filter), feelings on note lines, commitments and their one-time reminder, notes,
history and recall keep working. Nothing in memory changes, so turning it on again shows the same state.
"""
import argparse
import asyncio
import io
import json
import os
import re
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from test_relationship import EX, TODAY, state

from membrain import companion_switch, desktop, embedded_database, host, notes, plugin, plugin_cli
from membrain.host_context import COMPANION_OFF, snapshot, update
from membrain.local_profile import load_profile
from membrain.mcp_server import create_server
from membrain.notes import format_note
from membrain.persona import normalize_card
from membrain.relationship import familiarity

WEB = Path(__file__).parents[1] / "src" / "membrain" / "web"
CARD = {"name": "Mira", "traits": ["warm", "teasing but kind"], "values": ["honesty over flattery"],
        "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}
JOB = {"label": "thrilled", "valence": 2, "intensity": 3, "basis": "reported", "topic": "the new job"}
MOOD = {"label": "glad", "at_baseline": False, "pinned": False, "easing": False, "since": "2027-03-29T10:00:00Z",
        "reason": "the user said they felt thrilled"}


def block(text, tag):
    found = re.search(rf"<{tag}[ >].*?</{tag}>", text or "", re.DOTALL)
    return found.group(0) if found else None


# Without a database ---------------------------------------------------------------------------------------------

def test_the_switch_is_on_by_default_kept_per_person_and_followed_by_their_role_play(tmp_path):
    assert companion_switch.enabled(tmp_path) and companion_switch.enabled(tmp_path, "qq:1")
    off = companion_switch.set_enabled(tmp_path, False, "qq:1")
    assert (off["companion"], off["enabled"], off["applies_to"]) == ("off", False, "this user")
    assert not companion_switch.enabled(tmp_path, "qq:1")
    assert companion_switch.enabled(tmp_path) and companion_switch.enabled(tmp_path, "qq:2")  # Nobody else.
    assert not companion_switch.enabled(tmp_path, host.roleplay_user("qq:1", "Mira"))  # Their role-play too.
    assert (tmp_path / "plugin" / "companion-users" / (host.user_brain_id("qq:1") + ".json")).is_file()
    owner = companion_switch.set_enabled(tmp_path, False)
    assert owner["applies_to"] == "the installation's owner" and not companion_switch.enabled(tmp_path)
    assert not companion_switch.enabled(tmp_path, host.roleplay_user(None, "Mira"))
    assert companion_switch.enabled(tmp_path, "qq:2")  # The owner's switch is the owner's only.
    assert companion_switch.set_enabled(tmp_path, True, "qq:1")["companion"] == "on"
    assert companion_switch.enabled(tmp_path, "qq:1") and not companion_switch.enabled(tmp_path)
    assert not (tmp_path / "plugin" / "companion-users" / (host.user_brain_id("qq:1") + ".json")).exists()
    # Only turning it off writes the file, so one that cannot be read counts as off.
    (tmp_path / "plugin" / "companion.json").write_text("{torn")
    assert companion_switch.status(tmp_path)["companion"] == "off"
    with pytest.raises(ValueError):
        companion_switch.set_enabled(tmp_path, "off")
    companion_switch.forget(tmp_path, None)
    assert companion_switch.enabled(tmp_path)


def _saved():
    item = lambda ident, text: {"event_id": ident, "text": text, "actor_role": "assistant",  # noqa: E731
                                "recorded_at": "2027-03-01T09:00:00Z", "sequence": 5}
    return {"items": [item("n1", format_note("Got the job at Acme.", kind="milestone")),
                      item("n2", format_note("Broke up with Jordan in January.", kind="relationship")),
                      item("n3", format_note("Our first chat.", kind="milestone", shared=True)),
                      item("n4", format_note("Send the recipe.", kind="agent_commitment", status="intended",
                                             due="2027-03-10")),
                      item("n5", "Prefers short replies.")],
            "affect": [{"note_id": "n1", **JOB, "felt_at": "2027-03-01"}]}


def _bond():
    return state(familiarity=familiarity([f"2027-03-0{n}" for n in range(1, 5)], 1, None, TODAY),
                 support_style={"text": "listen first, advice only when asked"}, boundaries=[EX],
                 shared_moments=[{"id": "n3", "text": "Our first chat.", "occurs_at": "2027-03-02"}],
                 commitments={"missed": [{"note_id": "n4", "text": "Send the recipe.", "due": "2027-03-10",
                                          "acknowledged": False}]})


def test_off_leaves_out_exactly_the_persona_the_mood_and_the_familiarity():
    persona = {"version": 3, "card": normalize_card(CARD)}
    tools = {"note": "memory_note", "recall": "memory_recall"}
    arguments = dict(brain_id="b", tools=tools, persona=persona, mood=MOOD, relationship=_bond())
    on, off = snapshot(_saved(), **arguments), snapshot(_saved(), **arguments, companion=False)
    assert on == snapshot(_saved(), **arguments, companion=True)  # The default is on, unchanged.
    for tag in ("membrain-persona", "membrain-companion-mood", "membrain-relationship"):
        assert block(on["text"], tag) and not block(off["text"], tag), tag
    assert (on["persona_version"], on["mood_shown"], on["companion"]) == (3, True, True)
    assert (off["persona_version"], off["mood_shown"], off["companion"]) == (None, False, False)
    # The boundaries and the one-time missed promise stay, in their own block, without the companionship.
    kept = block(off["text"], "membrain-boundaries")
    assert "my ex (also: 前任, Jordan)" in kept and "Send the recipe. (due 2027-03-10, id: n4)" in kept
    assert "Familiarity" not in kept and "listen first" not in kept and "Our first chat." not in kept
    assert (off["boundaries"], off["acknowledge"]) == (on["boundaries"], on["acknowledge"]) == ([EX], ["n4"])
    # Feelings on note lines, the boundary filter on notes and the coming-up reminder are the same.
    for text in (on["text"], off["text"]):
        assert "(the user said they felt thrilled" in text and "Jordan in January" not in text
    assert block(on["text"], "membrain-coming-up") == block(off["text"], "membrain-coming-up")
    # The notes differ only by the shared moment, which is an ordinary note when the relationship block is off.
    assert "Our first chat." not in block(on["text"], "membrain-notes")
    assert "Our first chat." in block(off["text"], "membrain-notes")
    plain = {"items": [entry for entry in _saved()["items"] if entry["event_id"] != "n3"], "affect": _saved()["affect"]}
    assert (block(snapshot(plain, **arguments)["text"], "membrain-notes")
            == block(snapshot(plain, **arguments, companion=False)["text"], "membrain-notes"))
    # With nothing companion-related to show, off still differs by its fingerprint, so a session is told at once.
    empty_on = snapshot({"items": []}, brain_id="b", tools=None)
    empty_off = snapshot({"items": []}, brain_id="b", tools=None, companion=False)
    assert empty_on["text"] == empty_off["text"] == "" and empty_on["fingerprint"] != empty_off["fingerprint"]


def test_turning_it_off_and_on_mid_session_is_announced_once():
    persona = {"version": 3, "card": normalize_card(CARD)}
    arguments = dict(brain_id="b", tools=None, persona=persona, mood=MOOD, relationship=_bond())
    on, off = snapshot(_saved(), **arguments), snapshot(_saved(), **arguments, companion=False)
    turned_off = update(off, on["fingerprint"], 3, True, True)
    assert "companion layer was turned off" in turned_off and COMPANION_OFF in turned_off
    assert "reset or removed" not in turned_off and "back at its baseline" not in turned_off
    assert "<membrain-persona " not in turned_off and "<membrain-boundaries>" in turned_off
    assert update(off, off["fingerprint"], None, False, False) is None
    again = update(snapshot(_saved(), **{**arguments, "persona": None}, companion=False), off["fingerprint"],
                   None, False, False)
    assert again is None or "turned off" not in again
    back = update(on, off["fingerprint"], None, False, False)
    assert "companion layer is on again" in back and block(back, "membrain-persona") == block(on["text"],
                                                                                              "membrain-persona")
    assert block(back, "membrain-companion-mood") == block(on["text"], "membrain-companion-mood")


class Client:
    brain_id = "brain"


def test_the_tool_the_cli_and_the_tool_command_report_and_change_the_state(tmp_path, capsys):
    server = create_server(Client(), directory=tmp_path)
    assert "memory_companion" in {tool.name for tool in asyncio.run(server.list_tools())}
    assert "memory_companion" not in {tool.name for tool in asyncio.run(create_server(Client()).list_tools())}

    def call(arguments):
        return asyncio.run(server.call_tool("memory_companion", arguments))[1]

    assert call({})["companion"] == "on"
    assert call({"enabled": False})["companion"] == "off" and not companion_switch.enabled(tmp_path)
    assert call({})["companion"] == "off"
    assert call({"enabled": True})["enabled"] is True and companion_switch.enabled(tmp_path)

    parser = argparse.ArgumentParser()
    plugin_cli.add_commands(parser.add_subparsers(dest="command"))

    def cli(*words):
        with pytest.raises(SystemExit) as stopped:
            plugin_cli.dispatch(parser.parse_args(["plugin", "companion", *words, "--directory", str(tmp_path)]))
        return stopped.value.code, json.loads(capsys.readouterr().out)

    assert cli() == (0, companion_switch.status(tmp_path))
    code, result = cli("off", "--platform", "aiocqhttp", "--user", "12345")
    assert (code, result["companion"], result["applies_to"]) == (0, "off", "this user")
    assert not companion_switch.enabled(tmp_path, "aiocqhttp:12345") and companion_switch.enabled(tmp_path)
    assert cli("status", "--user-id", "aiocqhttp:12345")[1]["companion"] == "off"
    assert cli("on", "--user-id", "aiocqhttp:12345")[1]["companion"] == "on"
    assert cli("off")[1]["applies_to"] == "the installation's owner" and not companion_switch.enabled(tmp_path)
    cli("on")

    def tool(arguments):
        plugin.run_tool("companion", tmp_path, stream=io.BytesIO(json.dumps(arguments).encode()))
        return json.loads(capsys.readouterr().out)

    assert tool({"enabled": False, "membrain_user": "qq:7"})["companion"] == "off"
    assert not companion_switch.enabled(tmp_path, "qq:7") and companion_switch.enabled(tmp_path)
    assert tool({"membrain_user": "qq:7"})["companion"] == "off"
    assert "error" in tool({"enabled": "no"})


def test_the_command_skill_and_page_describe_the_switch():
    root = Path(__file__).parents[1] / "plugins" / "membrain"
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["commands"] == ["./commands/"]
    command = (root / "commands" / "companion.md").read_text()
    assert command.startswith("---\ndescription: ") and "$ARGUMENTS" in command
    assert "mcp__plugin_membrain_membrain__memory_companion" in command and "membrain plugin companion" in command
    skill = (root / "skills" / "membrain" / "SKILL.md").read_text()
    assert "## Companion layer" in skill and "memory_companion" in skill and "/membrain:companion" in skill
    page, script = (WEB / "memory.html").read_text(), (WEB / "memory.js").read_text()
    assert 'id="companion-off"' in page and "/v1/local/companion?brain_id=" in script


# On a real service ----------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    directory = tmp_path_factory.mktemp("companion") / "installation"
    with patch.dict(os.environ, {"MEMBRAIN_SEMANTIC": "0", "PYTHON_DOTENV_DISABLED": "1"}):
        try:
            host.start(directory)
            yield directory
        finally:
            desktop.stop(directory)


def test_off_and_on_again_across_sessions_keeps_privacy_and_restores_the_same_companion(installation):
    directory = installation
    user, other = "companion-" + uuid4().hex, "companion-other-" + uuid4().hex

    def turn(session, text, reply="Okay."):
        context = host.prompt_context(directory, session, text, turn_id=uuid4().hex, user_id=user) or ""
        host.finish_turn(directory, session, reply, user_id=user)
        return context

    host.session_context(directory, "s0", user_id=user)
    turn("s0", "My ex Jordan and I used to go hiking at Mount Tam every Sunday.")
    turn("s0", "I also love hiking near Mount Tam on my own.")
    with host.ready_client(directory, user) as client:
        client.set_persona(CARD, made_by="host")
        notes.save_note(client, "Got the job at Acme.", kind="milestone", affect=JOB)
        notes.save_note(client, "We finished the 10k plan together.", kind="milestone", shared=True,
                        occurs_at="2026-01-12")
        client.set_support_style("listen first, advice only when asked")
        client.add_boundary("my ex", ["Jordan"])
        notes.save_note(client, "Send the lasagne recipe.", kind="agent_commitment", status="intended",
                        due="2020-01-10")
    on = host.session_context(directory, "s1", user_id=user)
    for tag in ("membrain-persona", "membrain-companion-mood", "membrain-relationship"):
        assert block(on, tag), tag
    assert "Send the lasagne recipe." in block(on, "membrain-relationship") and COMPANION_OFF not in on

    assert companion_switch.set_enabled(directory, False, user)["companion"] == "off"
    assert companion_switch.enabled(directory) and companion_switch.enabled(directory, other)
    # The session in progress is told on its next prompt, and the companion blocks no longer come.
    told = turn("s1", "Anything new?")
    assert "companion layer was turned off" in told and COMPANION_OFF in told
    assert not block(told, "membrain-persona") and not block(told, "membrain-relationship")
    assert "<membrain-boundaries>" in told and "(the user said they felt thrilled" in told

    with host.ready_client(directory, user) as client:
        notes.save_note(client, "Book the vet.", kind="agent_commitment", status="intended", due="2020-02-01")
    off = host.session_context(directory, "s2", user_id=user)
    for tag in ("membrain-persona", "membrain-companion-mood", "membrain-relationship"):
        assert not block(off, tag), tag
    assert COMPANION_OFF in off
    kept = block(off, "membrain-boundaries")
    assert "my ex (also: Jordan)" in kept and "Book the vet." in kept and "shown once" in kept
    assert "Familiarity" not in kept and "listen first" not in kept
    assert "(the user said they felt thrilled" in off and "Book the vet." in block(off, "membrain-coming-up")
    assert "10k plan together" in block(off, "membrain-notes")  # The shared moment is an ordinary note.
    assert "Mount Tam every Sunday" not in off and "hiking near Mount Tam on my own" in off
    # Recall still keeps the boundary topic out unless the user raises it.
    assert "Mount Tam every Sunday" not in turn("s2", "Any hiking ideas near Mount Tam this weekend?")
    assert "Mount Tam every Sunday" in turn("s2", "I ran into Jordan at Mount Tam today, it was awkward.")
    # The other person's companion layer is untouched.
    with host.ready_client(directory, other) as client:
        client.set_persona(CARD, made_by="host")
    assert block(host.session_context(directory, "o1", user_id=other), "membrain-persona")

    # Nothing was deleted, and turning it on again shows the same persona, mood and relationship.
    with host.ready_client(directory, user) as client:
        assert client.persona()["version"] == 1
        assert client.relationship()["support_style"]["text"] == "listen first, advice only when asked"
    companion_switch.set_enabled(directory, True, user)
    back = turn("s2", "And now?")
    assert "companion layer is on again" in back
    assert block(back, "membrain-persona") == block(on, "membrain-persona")
    assert block(back, "membrain-companion-mood") == block(on, "membrain-companion-mood")
    again = host.session_context(directory, "s3", user_id=user)
    assert block(again, "membrain-persona") == block(on, "membrain-persona")
    assert block(again, "membrain-companion-mood") == block(on, "membrain-companion-mood")
    relationship_block = block(again, "membrain-relationship")
    assert "listen first, advice only when asked" in relationship_block and "my ex (also: Jordan)" in relationship_block
    assert COMPANION_OFF not in again and "<membrain-boundaries>" not in again


def test_the_host_ai_turns_the_owners_layer_off_and_the_page_reads_it(installation):
    directory = installation
    with host.ready_client(directory) as client:
        client.set_persona(CARD, made_by="host")
        server = create_server(client, directory=directory)
        assert block(host.session_context(directory, "owner-1"), "membrain-persona")
        assert asyncio.run(server.call_tool("memory_companion", {"enabled": False}))[1]["companion"] == "off"
        off = host.session_context(directory, "owner-2")
        assert not block(off, "membrain-persona") and COMPANION_OFF in off
        profile = load_profile(directory)
        headers = {"Authorization": "Bearer " + profile.api_key}
        page = httpx.get(profile.base_url + "/v1/local/companion", headers=headers, timeout=10).json()
        assert page["enabled"] is False
        assert httpx.get(profile.base_url + "/v1/local/companion?brain_id=user-other", headers=headers,
                         timeout=10).json() == {"enabled": None}
        assert httpx.get(profile.base_url + "/v1/local/companion", timeout=10).status_code == 401
        assert asyncio.run(server.call_tool("memory_companion", {"enabled": True}))[1]["companion"] == "on"
        assert block(host.session_context(directory, "owner-3"), "membrain-persona")
