"""One life of a memory through the plugin path: kept, recalled, corrected, deleted, and not brought back.

The scenario the project uses to check that the parts hold together, on a real local service:

1. The user says where they live and who they run with; the message is stored and the host saves two notes from it.
2. Recalling it repeatedly adds no memory and changes none.
3. The user corrects where they live; later sessions are told the corrected fact, the superseded note is gone from
   the notes, and what remains of the earlier statement is shown before the correction, as history.
4. The user has the memory of their running partner deleted; the message, the reply to it and every note drawn
   from it are gone from notes, history, recall and the memory map.
5. An archive exported before the deletion is restored; nothing deleted comes back.

Not covered here, because the default path has no step that produces them: an inferred statement kept apart from
what the user said, and the effect of a deletion on personality, mood or relationship state.
"""
import asyncio
import copy
import json

import pytest

from membrain import desktop, embedded_database, host
from membrain.mcp_server import create_server
from membrain.notes import list_notes

pytestmark = pytest.mark.skipif(not embedded_database.available(),
                                reason="embedded PostgreSQL binaries are not installed")

FIRST = "I live in Shanghai, and most mornings I go running with Xiao Lin along the river."
REPLY = "Running along the river with Xiao Lin sounds like a good start to the day."
CORRECTION = "I told you the wrong city earlier. I live in Hangzhou, not Shanghai."


def _turn(directory, session, text, reply, turn_id="1"):
    """One exchange as a hook host reports it; returns the note references and the recording capture."""
    context = host.prompt_context(directory, session, text, turn_id=turn_id, include_source=True)
    references, _ = json.JSONDecoder().raw_decode(context.split("source_messages=", 1)[1])
    capture, _ = json.JSONDecoder().raw_decode(context.split("recording_capture=", 1)[1])
    host.finish_turn(directory, session, reply, turn_id=turn_id)
    return references, capture


def _call(server, name, arguments):
    _, result = asyncio.run(server.call_tool(name, arguments))
    return result


def _notes(client):
    return [item["text"] for item in list_notes(client)["items"]]


def _everything_a_host_sees(directory, session, question):
    return host.session_context(directory, session) + "\n" + (host.prompt_context(directory, session, question) or "")


def test_a_memory_is_kept_recalled_corrected_deleted_and_not_brought_back(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        with host.ready_client(directory) as client:
            server = create_server(client, directory=directory)

            # 1. Kept: the message, and two notes the host draws from it.
            references, capture = _turn(directory, "monday", FIRST, REPLY)
            home = _call(server, "memory_note", {"text": "Lives in Shanghai.", "kind": "other",
                                                 "source_messages": references, "recording_capture": capture})
            partner = _call(server, "memory_note", {"text": "Runs most mornings with Xiao Lin.", "kind": "person",
                                                    "about": "Xiao Lin", "source_messages": references,
                                                    "recording_capture": capture})
            assert home["note_id"] and partner["note_id"]
            seen = _everything_a_host_sees(directory, "tuesday", "Who do I go running with?")
            assert "Xiao Lin" in seen and "Shanghai" in seen

            # 2. Recalled repeatedly: nothing is added and nothing changes.
            before = (client.timeline(roles=("user", "assistant"), max_characters=200_000), _notes(client))
            for _ in range(3):
                found = _call(server, "memory_recall", {"query": "running partner Xiao Lin", "with_ids": True})
                assert any("Xiao Lin" in record["text"] for record in found["records"])
            after = (client.timeline(roles=("user", "assistant"), max_characters=200_000), _notes(client))
            assert after == before

            # 3. Corrected: the new fact replaces the note; the earlier statement stays only as earlier history.
            references, capture = _turn(directory, "wednesday", CORRECTION, "Thanks, Hangzhou it is.")
            corrected = _call(server, "memory_note", {"text": "Lives in Hangzhou.", "kind": "other",
                                                      "replaces": [home["note_id"]], "source_messages": references,
                                                      "recording_capture": capture})
            assert corrected["note_id"]
            notes = _notes(client)
            assert any("Hangzhou" in note for note in notes) and not any("Lives in Shanghai" in note for note in notes)
            opening = host.session_context(directory, "thursday")
            block = opening.split("<membrain-notes>", 1)[1].split("</membrain-notes>", 1)[0]
            assert "Hangzhou" in block and "Shanghai" not in block
            # With so short a history the opening holds all of it and per-message recall adds nothing; either way
            # the host must be shown the correction, and after anything that remains of the earlier statement.
            shown = opening + "\n" + (host.prompt_context(directory, "thursday", "Which city do I live in?") or "")
            assert CORRECTION in shown
            assert shown.index(FIRST) < shown.index(CORRECTION) if FIRST in shown else True

            # An archive from before the deletion, for step 5.
            exported = client.export()["result"]
            archive = copy.deepcopy(client.download_archive((exported.get("archive") or exported)["archive_id"])["document"])
            assert "Xiao Lin" in json.dumps(archive, ensure_ascii=False)

            # 4. Deleted: the message about the running partner, and everything drawn from it.
            found = _call(server, "memory_recall", {"query": "running with Xiao Lin", "with_ids": True})
            targets = [record["event_id"] for record in found["records"] if record["text"] == FIRST]
            assert len(targets) == 1
            result = _call(server, "memory_forget", {"ids": targets, "kind": "events", "mode": "erase_content",
                                                     "expected_scope_generation": found["scope_generation"]})
            assert result.get("outcome") not in ("rejected", "conflict", "failed"), result

            def nothing_left(stage):
                everything = json.dumps({
                    "notes": _notes(client),
                    "timeline": client.timeline(roles=("user", "assistant"), max_characters=200_000),
                    "recall": _call(server, "memory_recall", {"query": "running partner Xiao Lin river", "with_ids": True}),
                    "said": _call(server, "memory_recall", {"query": "what did you say about my running partner"}),
                    "map": client.memory_map(include_sensitive=True),
                    "context": _everything_a_host_sees(directory, f"after-{stage}", "Who do I go running with?"),
                }, ensure_ascii=False)
                assert "Xiao Lin" not in everything and "along the river" not in everything, stage
                return everything

            remaining = nothing_left("deletion")
            assert "Hangzhou" in remaining  # The correction came from another message and is untouched.

            # 5. Not brought back: restoring the earlier archive leaves the deleted memory deleted.
            uploaded = client.upload_archive(archive)
            generation = client.dashboard()["brain"]["scope_generation"]
            restored = client.restore(uploaded["archive_id"], expected_manifest_sha256=uploaded["manifest_sha256"],
                                      expected_scope_generation=generation)
            assert restored.get("outcome") not in ("rejected", "conflict", "failed"), restored
            assert "Hangzhou" in nothing_left("restore")
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
