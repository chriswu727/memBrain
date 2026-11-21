"""The notes block tells a host with a shell how to show the user where a note came from.

In the real-host trial of 2026-11-18 (evaluations/host-trial-2026-11-18.md) the host was asked "Can you show me where I
said that?", answered from the note in words, and told the user it could not show the conversation. The command that
opens the memory page at a note (``membrain plugin ui --note <id>``) was named only in the skill, which the host never
opened. The notes block, which carries every note's id, now names it, for the hosts whose AI can run it on the user's
machine for the installation's own memory, in a form that runs whether or not ``membrain`` is on the PATH.
"""
import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host, notes, plugin

# Its last sentence was "Never say you cannot show the source.", which asked for a false claim when the command fails.
HINT = (" If the user asks to see where a note came from (where they said it) or to check it, run membrain plugin ui "
        "--note <id>: it opens their memory page at that note, what it replaced and its source messages. If it "
        "fails, say so; never claim there is no way to show the source.")
NOTE = "Prefers green tea in the afternoon."
NOTES_BLOCK = re.compile(r"<membrain-notes>.*?</membrain-notes>", re.DOTALL)
COMMAND = re.compile(r"run (.+?) --note <id>: it opens their memory page")


def entry_directory() -> str:
    return str(host._entry_point().parent)


def path_without_membrain() -> str:
    return os.pathsep.join(part for part in os.environ.get("PATH", "").split(os.pathsep)
                           if part and not (Path(part) / ("membrain.exe" if os.name == "nt" else "membrain")).exists())


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


# The sentence and the command, without a service ---------------------------------------------------------------------

def test_the_sentence_is_one_short_sentence_pair_that_costs_272_characters():
    assert notes.note_page_hint("membrain plugin ui") == HINT
    assert len(HINT) == 272
    assert "plugin ui" not in host.server_instructions() and len(host.server_instructions()) <= 1400


def test_the_notes_block_carries_it_after_the_replaces_sentence_only_when_given_a_command():
    saved = {"items": [{"event_id": "0b5c8f9e-1111-4222-8333-944455556666", "text": NOTE,
                        "recorded_at": "2026-11-02T10:00:00+00:00"}], "complete": True}
    block = notes.render_notes(saved, page="membrain plugin ui")
    assert f"pass the old note's id in replaces.{HINT}\n" in block
    assert block.count("plugin ui") == 1
    assert "plugin ui" not in notes.render_notes(saved)
    assert "plugin ui" not in notes.render_notes(saved, page="membrain plugin ui", real_life=True)


def test_membrain_is_named_alone_when_it_resolves_to_this_runtimes_own_program(monkeypatch):
    if not host._entry_point().is_file():
        pytest.skip("this environment has no membrain program")
    monkeypatch.setenv("PATH", entry_directory() + os.pathsep + path_without_membrain())
    assert host.page_command() == "membrain plugin ui"


def test_without_membrain_on_the_path_the_programs_own_path_is_given(monkeypatch):
    if not host._entry_point().is_file():
        pytest.skip("this environment has no membrain program")
    monkeypatch.setenv("PATH", path_without_membrain())
    command = host.page_command()
    assert command == host._shell_word(host._entry_point()) + " plugin ui"
    if os.name != "nt" and str(host._entry_point()).startswith(str(Path.home()) + "/"):
        assert command.startswith("~/") and str(Path.home()) not in command  # The user's name stays out.


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for another installation")
def test_another_installations_membrain_on_the_path_is_not_taken_for_this_one(tmp_path, monkeypatch):
    if not host._entry_point().is_file():
        pytest.skip("this environment has no membrain program")
    other = tmp_path / "bin" / "membrain"
    other.parent.mkdir()
    other.write_text("#!/bin/sh\necho another installation\n")
    other.chmod(0o755)
    monkeypatch.setenv("PATH", str(other.parent) + os.pathsep + path_without_membrain())
    assert host.page_command() == host._shell_word(host._entry_point()) + " plugin ui"


def test_a_runtime_in_uvs_cache_never_gives_its_own_path(monkeypatch):
    """A cache cleanup removes that environment, so its path could stop working at any time."""
    monkeypatch.setattr(host, "running_from_uv_cache", lambda: True)
    monkeypatch.setenv("PATH", path_without_membrain())
    assert host.page_command() == "membrain plugin ui"


def test_finding_the_command_runs_no_program(monkeypatch):
    """It runs in the session-start hook (a 10-second limit, every session): file lookups only."""
    def refuse(*args, **kwargs):
        raise AssertionError("page_command started a program")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    for path in (path_without_membrain(), entry_directory() + os.pathsep + path_without_membrain()):
        monkeypatch.setenv("PATH", path)
        assert host.page_command().endswith("membrain plugin ui")


def test_a_copied_program_counts_as_the_same_one_and_a_different_file_does_not(tmp_path):
    """On Windows uv copies a tool's programs into its bin directory; each copy names the environment's interpreter."""
    entry, copy, other = tmp_path / "entry", tmp_path / "copy", tmp_path / "other"
    entry.write_bytes(b"MZ trampoline for C:/tools/membrain-ai/Scripts/python.exe")
    copy.write_bytes(entry.read_bytes())
    other.write_bytes(b"MZ trampoline for C:/other/membrain-ai/Scripts/python.exe")
    assert host._same_program(copy, entry) and host._same_program(entry, entry)
    assert not host._same_program(other, entry) and not host._same_program(tmp_path / "missing", entry)


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell quoting")
def test_a_path_is_given_under_home_when_it_can_be_and_quoted_when_it_must_be(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    plain = tmp_path / ".local" / "share" / "uv" / "tools" / "membrain-ai" / "bin" / "membrain"
    assert host._shell_word(plain) == "~/.local/share/uv/tools/membrain-ai/bin/membrain"
    spaced = tmp_path / "My Tools" / "bin" / "membrain"
    assert host._shell_word(spaced) == shlex.quote(str(spaced))
    outside = Path("/opt/membrain/bin/membrain")
    assert host._shell_word(outside) == "/opt/membrain/bin/membrain"


# Which hosts get it, on a real service ---------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def installation(tmp_path_factory):
    """One installation: a session start before any note, then a note in the installation's own memory, in one
    person's memory of a multi-user host, in a chat bot user's memory and in a role-play's memory."""
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    from membrain.adapters.chatbot import Speaker, speaker_user_id

    patch = pytest.MonkeyPatch()
    patch.setenv("MEMBRAIN_SEMANTIC", "0")
    patch.setenv("PATH", entry_directory() + os.pathsep + path_without_membrain())
    directory = tmp_path_factory.mktemp("note-page") / "brain"
    try:
        host.start(directory)
        empty = plugin.session_start({"session_id": "before-any-note"}, directory)
        speaker = Speaker("telegram", "42")
        ids = {}
        for key, user in (("own", None), ("alice", "alice"), ("bot", speaker_user_id(speaker)),
                          ("roleplay", host.roleplay_user(None, "Merlin"))):
            with host.ready_client(directory, user) as client:
                ids[key] = notes.save_note(client, NOTE, kind="preference")["note_id"]
        yield {"directory": directory, "empty": empty, "ids": ids, "speaker": speaker}
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
        patch.undo()


def notes_block(text):
    found = NOTES_BLOCK.search(text or "")
    return found.group(0) if found else ""


def test_a_session_without_notes_is_not_told(installation):
    assert "plugin ui" not in (installation["empty"] or "")
    assert "<membrain-notes>" not in (installation["empty"] or "")


@pytest.mark.parametrize("producer", ["membrain-plugin", "membrain-codex", "membrain-workbuddy"])
def test_claude_code_codex_and_workbuddy_sessions_with_notes_are_told_with_the_exact_sentence(installation, producer,
                                                                                            monkeypatch):
    monkeypatch.setenv("PATH", entry_directory() + os.pathsep + path_without_membrain())
    opening = plugin.session_start({"session_id": f"told-{producer}"}, installation["directory"], producer)
    block = notes_block(opening)
    assert f"pass the old note's id in replaces.{HINT}\n" in block
    assert f"(id: {installation['ids']['own']})" in block and opening.count("plugin ui") == 1


def test_a_refreshed_notes_block_in_a_session_is_told_too(installation, monkeypatch):
    monkeypatch.setenv("PATH", entry_directory() + os.pathsep + path_without_membrain())
    directory = installation["directory"]
    plugin.session_start({"session_id": "refreshed"}, directory)
    with host.ready_client(directory) as client:
        added = notes.save_note(client, "Works from Lisbon on Fridays.", kind="routine")["note_id"]
    context = plugin.user_prompt({"session_id": "refreshed", "prompt": "Morning!", "prompt_id": "t1"}, directory)
    block = notes_block(context)
    assert "<membrain-updates>" in context and HINT in block and f"(id: {added})" in block


@pytest.mark.parametrize("excluded", ["openclaw", "multi-user", "hermes", "chat bot", "proxy", "role-play"])
def test_hosts_that_cannot_open_this_memorys_page_are_not_told(installation, excluded, monkeypatch):
    """OpenClaw's AI talks to people other than the owner; Hermes, chat bots and the proxy run no command for the user;
    a multi-user host's person and a role-play have a memory the installation's page does not show."""
    from membrain.adapters import hermes
    from membrain.adapters.chatbot import ChatMemory

    monkeypatch.setenv("PATH", entry_directory() + os.pathsep + path_without_membrain())
    directory = installation["directory"]
    if excluded == "openclaw":
        opening = plugin.session_start({"session_id": "excluded-openclaw"}, directory, "membrain-openclaw")
    elif excluded == "multi-user":
        opening = plugin.session_start({"session_id": "excluded-alice", "membrain_user": "alice"}, directory)
    elif excluded == "hermes":  # The owner's own session, as HermesMemoryProvider.system_prompt_block builds it.
        opening = host.session_context(directory, "excluded-hermes", tools=hermes.TOOLS, skip_imports_from=("hermes",))
    elif excluded == "chat bot":
        memory = ChatMemory(directory)
        speaker = installation["speaker"]
        opening = memory.context(speaker, "hello", session=memory.session(speaker))
    elif excluded == "proxy":
        opening = host.session_context(directory, "excluded-proxy", tools=None)
    else:
        opening = host.session_context(directory, "excluded-roleplay", tools=plugin.HOST_TOOLS["claude-code"],
                                       roleplay="Merlin")
    block = notes_block(opening)
    assert NOTE in block  # The session has notes, with their ids, and still no sentence.
    assert "plugin ui" not in opening


# The command it prints runs --------------------------------------------------------------------------------------------

@pytest.mark.skipif(os.name == "nt", reason="the printed command is run by a POSIX shell here")
@pytest.mark.parametrize("on_path", [True, False], ids=["membrain-on-path", "membrain-not-on-path"])
def test_the_printed_command_opens_the_page_at_that_note(installation, on_path, monkeypatch):
    """Built and run in the same environment, as the hook and the host's shell share the host's. The link's code is
    neither asserted nor shown; it is used up afterwards."""
    from membrain.local_profile import load_profile

    if not host._entry_point().is_file():
        pytest.skip("this environment has no membrain program")
    directory = installation["directory"]
    path = (entry_directory() + os.pathsep if on_path else "") + path_without_membrain()
    monkeypatch.setenv("PATH", path)
    opening = plugin.session_start({"session_id": f"runnable-{on_path}"}, directory)
    command = COMMAND.search(notes_block(opening)).group(1)
    assert (command == "membrain plugin ui") is on_path
    note = installation["ids"]["own"]
    environment = {**os.environ, "PATH": path, "MEMBRAIN_DIRECTORY": str(directory)}
    finished = subprocess.run(f"{command} --note {note} --no-browser", shell=True, env=environment,
                              capture_output=True, text=True, timeout=120, check=False)
    printed = finished.stdout.strip().splitlines()
    link = printed[-1] if printed else ""
    prefix = f"{load_profile(directory).base_url}/memory?code="
    opened = finished.returncode == 0 and link.startswith(prefix) and link.endswith(f"#note={note}")
    assert opened, f"exit {finished.returncode}; {len(printed)} lines printed"
    assert host.consume_ui_code(directory, link[len(prefix):].split("#", 1)[0])
