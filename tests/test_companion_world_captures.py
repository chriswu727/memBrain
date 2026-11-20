"""The companion worlds (``companion_world``) played end to end on a real service: every session gets a context and
every scripted tool call succeeds. With ``COMPANION_WORLD_DUMP`` set, the captures are written for the report."""
import pytest
from companion_world import WORLDS, built_world


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_each_world_plays_to_its_end_with_every_tool_call_answered(tmp_path_factory, name):
    with built_world(tmp_path_factory, name) as world:
        sessions = world.captures["sessions"]
        assert list(sessions) == [session for session, _day, _turns in WORLDS[name]]
        for record in sessions.values():
            # A chat bot has no session start: the whole context comes with each message.
            assert "memBrain memory is active" in (record["session_start"] or record["prompts"][0]["user_prompt"])
        assert all(not (isinstance(call["result"], dict) and call["result"].get("error"))
                   for call in world.tool_calls), world.tool_calls
