"""The assistant's own earlier replies are recalled when the host AI asks for them, and not otherwise.

Shown unasked, a suggestion the assistant once made has been restated as a fact about the user. So automatic recall
leaves its replies out, and the host AI, which can tell that the user is asking about something it said, asks for
them through the recall tool.
"""
import asyncio

import pytest

from membrain import desktop, embedded_database, host
from membrain.mcp_server import create_server

pytestmark = pytest.mark.skipif(not embedded_database.available(),
                                reason="embedded PostgreSQL binaries are not installed")

ASKED = "We are in Rome next month. Where can we get a good sandwich near the Vatican?"
REPLY = "Try Forno Feliziani on Via Candia: it is a short walk from the Vatican and known for its porchetta rolls."


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def test_the_recall_tool_returns_the_assistant_s_replies_only_when_asked_for(tmp_path):
    directory = tmp_path / "brain"
    try:
        host.start(directory)
        host.prompt_context(directory, "rome", ASKED, turn_id="1", include_source=True)
        host.finish_turn(directory, "rome", REPLY, turn_id="1")
        with host.ready_client(directory) as client:
            # How a user actually asks: none of the phrasings automatic recall recognises.
            question = "Remind me of the name of that deli near the Vatican you mentioned."
            assert not host.ASKS_ABOUT_ASSISTANT.search(question)
            unasked = host.recall_context(client, question, current_conversation="later") or ""
            assert "Forno Feliziani" not in unasked
            asked = host.recall_context(client, "deli near the Vatican porchetta", current_conversation="later",
                                        replies=True) or ""
            assert "assistant said] " in asked and "Forno Feliziani" in asked

            server = create_server(client, directory=directory)

            def tool(arguments):
                return asyncio.run(server.call_tool("memory_recall", arguments))[1]["context"]

            assert "Forno Feliziani" not in tool({"query": "deli near the Vatican"})
            assert "Forno Feliziani" in tool({"query": "deli near the Vatican", "my_replies": True})

        opening = host.session_context(directory, "later")
        if "Related messages from earlier conversations" in opening:  # Not shown when the whole history fits.
            assert "my_replies" in opening
        assert "my_replies" not in host._session_notice(False, {key: value for key, value in host.TOOL_NAMES.items()
                                                                if key != "replies"}, False, None)
        assert "my_replies" in host._session_notice(False, host.TOOL_NAMES, False, None)
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass
