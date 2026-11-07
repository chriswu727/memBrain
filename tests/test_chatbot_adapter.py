import asyncio
import datetime
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, host
from membrain.adapters.chatbot import ChatMemory, Speaker

PLUGIN = Path(__file__).parents[1] / "integrations" / "astrbot" / "astrbot_plugin_membrain"


@pytest.fixture(autouse=True)
def no_model_download(monkeypatch):
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")


def test_people_get_their_own_memory_and_groups_stay_apart_from_private_chats(tmp_path):
    memory = ChatMemory(tmp_path)
    alice, bob = Speaker("aiocqhttp", "1001"), Speaker("aiocqhttp", "2002")
    in_group = Speaker("aiocqhttp", "1001", group="777")
    assert len({memory.user_id(alice), memory.user_id(bob), memory.user_id(in_group)}) == 3
    assert ChatMemory(tmp_path, group_memory="shared").user_id(in_group) == memory.user_id(alice)
    day = datetime.date(2026, 10, 28)
    assert memory.session(alice, today=day) != memory.session(alice, today=day + datetime.timedelta(days=1))
    assert memory.session(in_group, today=day) != memory.session(Speaker("aiocqhttp", "2002", "777"), today=day)
    assert all(len(value) <= 200 for value in (memory.session(Speaker("x" * 500, "y" * 500, "z" * 500)),
                                               memory.user_id(Speaker("x" * 500, "y" * 500, "z" * 500))))
    with pytest.raises(ValueError):
        ChatMemory(tmp_path, group_memory="everyone")


def test_groups_can_be_left_unrecorded_and_unknown_senders_are_ignored(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(host, "prompt_context", lambda *args, **kwargs: calls.append(kwargs) or None)
    monkeypatch.setattr(host, "session_context", lambda *args, **kwargs: calls.append(kwargs) or "")
    monkeypatch.setattr(host, "finish_turn", lambda *args, **kwargs: calls.append(kwargs))
    memory = ChatMemory(tmp_path, record_groups=False)
    for speaker in (Speaker("telegram", "5", group="9"), Speaker("telegram", "")):
        assert memory.context(speaker, "hello", session="s") is None
        memory.record(speaker, "hi", session="s", prompt="hello")
    assert calls == []


def test_outside_edits_are_reflected_on_the_next_request_in_the_same_session(tmp_path, monkeypatch):
    text = ["Jordan and the user hiked together."]
    monkeypatch.setattr(host, "session_context", lambda *args, **kwargs: text[0])
    monkeypatch.setattr(host, "prompt_context", lambda *args, **kwargs: None)
    memory, speaker = ChatMemory(tmp_path), Speaker("discord", "mei")
    assert "Jordan" in memory.context(speaker, "hello", session="same")
    text[0] = "The earlier memory was removed in the memory page."
    assert "Jordan" not in memory.context(speaker, "hello again", session="same")


def test_session_block_is_refreshed_on_each_turn_including_recording_changes(tmp_path, monkeypatch):
    blocks = []
    monkeypatch.setattr(host, "session_context", lambda directory, session, **kwargs: blocks.append(session) or
                        f"notes v{len(blocks)}")
    monkeypatch.setattr(host, "prompt_context", lambda *args, **kwargs: "related")
    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: None)
    monkeypatch.setattr(host, "start_in_background", lambda directory: None)
    memory, mei = ChatMemory(tmp_path), Speaker("discord", "mei")
    assert memory.context(mei, "hi", session="s") == "notes v1\n\nrelated"
    assert memory.context(mei, "again", session="s") == "notes v2\n\nrelated"
    assert memory.note(mei, "Allergic to sesame.") == {"error": "memBrain is starting; try again in a few seconds."}
    memory.pause(mei)
    assert memory.context(mei, "later", session="s") == "notes v3\n\nrelated"
    assert host.paused(tmp_path, memory.user_id(mei)) and not host.paused(tmp_path)


def _load_astrbot_plugin(monkeypatch, tmp_path):
    """Load the AstrBot plugin against minimal stand-ins for the AstrBot modules it imports."""
    registered = {}

    def decorator(kind):
        def factory(*names, **options):
            def wrap(function):
                registered[(names[0] if names else None) or options.get("name") or kind] = function
                return function
            return wrap
        return factory

    class Star:
        def __init__(self, context, config=None):
            self.context, self.logger = context, types.SimpleNamespace(warning=print)

    modules = {
        "astrbot": types.ModuleType("astrbot"),
        "astrbot.api": types.SimpleNamespace(star=types.SimpleNamespace(Star=Star, Context=object)),
        "astrbot.api.event": types.SimpleNamespace(AstrMessageEvent=object, filter=types.SimpleNamespace(
            on_llm_request=decorator("request"), on_llm_response=decorator("response"),
            llm_tool=decorator("tool"), command=decorator("command"))),
        "astrbot.api.provider": types.SimpleNamespace(LLMResponse=object, ProviderRequest=object),
        "astrbot.core.utils.astrbot_path": types.SimpleNamespace(
            get_astrbot_plugin_data_path=lambda: str(tmp_path / "plugin_data")),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("astrbot_plugin_membrain_main", PLUGIN / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, registered


def test_boundaries_use_the_speakers_roleplay_and_never_an_unrecorded_group(tmp_path, monkeypatch):
    users, saved = [], []

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def add_boundary(self, topic, aliases):
            saved.append((topic, aliases))
            return {"boundaries": [{"topic": topic, "aliases": aliases}]}

    monkeypatch.setattr(host, "ready_client", lambda directory, user_id=None: users.append(user_id) or Client())
    memory = ChatMemory(tmp_path, roleplay="Mira", record_groups=False)
    private = Speaker("telegram", "42")
    assert memory.boundary(private, "my ex", ["前任"])["boundaries"][0]["topic"] == "my ex"
    assert users == [memory.memory_user(private)]
    assert saved == [("my ex", ["前任"])]
    assert "error" in memory.boundary(Speaker("telegram", "42", "group"), "my ex")
    assert "error" in memory.boundary(Speaker("telegram", ""), "my ex")
    assert len(users) == 1


class Event:
    def __init__(self, sender, text, group="", message_id="m1"):
        self.sender, self.text, self.group, self.extra = sender, text, group, {}
        self.message_obj = types.SimpleNamespace(message_id=message_id)

    def get_platform_name(self):
        return "aiocqhttp"

    def get_sender_id(self):
        return self.sender

    def get_group_id(self):
        return self.group

    def get_message_str(self):
        return self.text

    def set_extra(self, key, value):
        self.extra[key] = value

    def get_extra(self, key=None, default=None):
        return self.extra.get(key, default)

    def plain_result(self, text):
        return text


def test_astrbot_plugin_files_are_complete():
    for name in ("main.py", "metadata.yaml", "requirements.txt", "_conf_schema.json"):
        assert (PLUGIN / name).is_file()
    schema = json.loads((PLUGIN / "_conf_schema.json").read_text())
    assert schema["group_memory"]["default"] == "separate" and schema["record_groups"]["default"] is True
    assert "membrain-ai" in (PLUGIN / "requirements.txt").read_text()
    assert "name: astrbot_plugin_membrain" in (PLUGIN / "metadata.yaml").read_text()


@pytest.mark.parametrize("has_session", [False, True])
def test_astrbot_resume_uses_the_request_event_session(tmp_path, monkeypatch, has_session):
    from test_host import Client

    module, _ = _load_astrbot_plugin(monkeypatch, tmp_path)
    client = Client()
    monkeypatch.setattr(host, "ready_client", lambda *args: client)
    instance = module.MembrainPlugin.__new__(module.MembrainPlugin)
    instance.memory = ChatMemory(tmp_path)
    event = Event("1001", "Resume recording please.")
    if has_session:
        event.set_extra("membrain", {"session": "requester"})
    user = instance.memory.user_id(module._speaker(event))
    host.pause(tmp_path, user_id=user)
    host.prompt_context(tmp_path, "requester", event.text, user_id=user)
    host.prompt_context(tmp_path, "private", "Unrelated private synthetic detail.", user_id=user)
    asyncio.run(instance.membrain_resume(event))
    assert host.turn_resumed(tmp_path, "requester") == has_session
    assert not host.turn_resumed(tmp_path, "private")
    assert host.finish_turn(tmp_path, "private", "Private reply", prompt="Unrelated private synthetic detail.",
                            user_id=user) == []


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_astrbot_plugin_remembers_each_qq_user_separately_through_a_real_service(tmp_path, monkeypatch):
    module, handlers = _load_astrbot_plugin(monkeypatch, tmp_path)
    directory = tmp_path / "plugin_data" / "membrain"
    assert set(handlers) == {"request", "response", "membrain_note", "membrain_search", "membrain_pause",
                             "membrain_resume", "membrain_forget", "membrain_boundary"}
    try:
        # AstrBot constructs the plugin before any installation exists; its background start must still succeed.
        plugin = module.MembrainPlugin(context=None, config={})
        assert plugin.memory.directory == directory
        host.start(directory)

        async def turn(event, reply, conversation="c1"):
            request = types.SimpleNamespace(system_prompt="You are a friendly bot.", prompt=event.text,
                                            conversation=types.SimpleNamespace(cid=conversation))
            await plugin.add_memory(event, request)
            await plugin.store_turn(event, types.SimpleNamespace(role="assistant", completion_text=reply))
            return request.system_prompt

        async def scenario():
            await turn(Event("1001", "My cat Biscuit is allergic to chicken."), "Got it, no chicken.")
            await turn(Event("2002", "I'm training for the Shanghai marathon."), "Good luck!")
            note = json.loads(await plugin.membrain_note(Event("1001", ""), "Cat Biscuit: chicken allergy."))
            assert "note_id" in note
            group = await turn(Event("1001", "Hi everyone", group="777"), "Hello!", conversation="g1")
            assert "Biscuit" not in group  # A group never sees a private conversation by default.
            paused = Event("2002", "Off the record: I'm changing jobs.", message_id="m9")
            await plugin.membrain_pause(paused)
            await turn(paused, "Understood.")
            await plugin.membrain_resume(paused)
            alice = await turn(Event("1001", "What treats can I buy for my cat?", message_id="m2"), "Fish.",
                               conversation="c2")
            bob = await turn(Event("2002", "Any advice for my race?", message_id="m3"), "Taper.", conversation="c3")
            return alice, bob

        alice, bob = asyncio.run(scenario())
        assert alice.startswith("You are a friendly bot.")
        assert "Cat Biscuit: chicken allergy." in alice and "marathon" not in alice
        assert "marathon" in bob and "Biscuit" not in bob
        shared = json.loads(asyncio.run(plugin.membrain_note(Event("1001", ""),
            "We planned Biscuit's meals together.", kind="milestone", shared=True)))
        assert "note_id" in shared
        boundary = json.loads(asyncio.run(plugin.membrain_boundary(Event("1001", ""), "my cat", ["Biscuit", "小饼干"])))
        assert boundary["boundaries"][0]["aliases"] == ["Biscuit", "小饼干"]
        with host.ready_client(directory, plugin.memory.user_id(module.Speaker("aiocqhttp", "1001"))) as client:
            assert client.relationship()["shared_moments"][0]["id"] == shared["note_id"]
        with host.ready_client(directory, plugin.memory.user_id(module.Speaker("aiocqhttp", "2002"))) as client:
            assert client.relationship()["boundaries"] == []
        hidden = plugin.memory.context(module.Speaker("aiocqhttp", "1001"), "Hello again", session="after-boundary")
        assert "Cat Biscuit: chicken allergy." not in hidden and "allergic to chicken" not in hidden
        raised = plugin.memory.search(module.Speaker("aiocqhttp", "1001"), "Biscuit chicken allergy")
        assert "allergic to chicken" in raised["context"]
        with host.ready_client(directory, plugin.memory.user_id(module.Speaker("aiocqhttp", "2002"))) as client:
            stored = json.dumps(client.timeline(roles=("user", "assistant"), max_characters=200_000))
        assert "marathon" in stored and "changing jobs" not in stored

        async def command(event, *args):
            return [reply async for reply in plugin.membrain_forget(event, *args)]

        # A person erases their own memory with a command they send themselves; others keep theirs.
        assert "confirm" in asyncio.run(command(Event("1001", "/membrain_forget")))[0]
        assert asyncio.run(command(Event("1001", "/membrain_forget confirm"), "confirm"))[0].startswith("Done")
        async def both():
            return (await turn(Event("1001", "What treats can I buy for my cat?", message_id="m4"), "Ask me.",
                               conversation="c4"),
                    await turn(Event("2002", "Any advice for my race?", message_id="m5"), "Rest.", conversation="c5"))

        alice, bob = asyncio.run(both())
        assert "Biscuit" not in alice and "marathon" in bob
        # An operator can export or erase one person from the command line.
        from membrain import plugin_cli

        exported = tmp_path / "bob.json"
        args = types.SimpleNamespace(plugin_command="export-user", platform="aiocqhttp", user="2002", group=None,
                                     user_id=None, yes=True, out=exported)
        assert plugin_cli._person(args, directory) == 0
        assert "marathon" in exported.read_text() and oct(exported.stat().st_mode & 0o777) == "0o600"
        args.plugin_command = "forget-user"
        assert plugin_cli._person(args, directory) == 0
        with host.ready_client(directory, plugin.memory.user_id(module.Speaker("aiocqhttp", "2002"))) as client:
            assert "marathon" not in json.dumps(client.timeline(roles=("user", "assistant"), max_characters=200_000))
    finally:
        try:
            desktop.stop(directory)
        except desktop.DesktopError:
            pass


def test_astrbot_tool_docstrings_follow_astrbots_parameter_format(monkeypatch, tmp_path):
    """AstrBot builds tool schemas only from ``name(type): description`` lines in the docstring's Args block."""
    import inspect
    import re

    module, handlers = _load_astrbot_plugin(monkeypatch, tmp_path)
    supported = {"string", "number", "object", "array", "boolean"}
    for name in ("membrain_note", "membrain_search", "membrain_boundary", "membrain_pause", "membrain_resume"):
        function = handlers[name]
        parameters = [p for p in inspect.signature(function).parameters if p not in ("self", "event")]
        doc = inspect.getdoc(function)
        documented = dict(re.findall(r"^\s+(\w+)\((\w+(?:\[\w+\])?)\): \S", doc, re.MULTILINE))
        assert sorted(documented) == sorted(parameters), name
        for kind in documented.values():
            outer, _, inner = kind.rstrip("]").partition("[")
            assert outer in supported and (not inner or inner in supported), (name, kind)


@pytest.mark.parametrize("first,second", [
    (Speaker("api", "group:123:alice"), Speaker("api", "alice", "123")),
    (Speaker("api:one", "alice"), Speaker("api", "one:alice")),
    (Speaker("api", "x" * 81), Speaker("api", hashlib.sha256(b"x" * 81).hexdigest())),
])
def test_ambiguous_speaker_ids_cannot_share_memory(tmp_path, first, second):
    memory = ChatMemory(tmp_path)
    assert memory.user_id(first) != memory.user_id(second)
    assert memory.session(first, "same") != memory.session(second, "same")
    assert memory.user_id(Speaker("telegram", "123")) == "telegram:123"


def test_groups_cannot_share_session_state_even_with_the_same_conversation_id(tmp_path):
    memory = ChatMemory(tmp_path)
    assert memory.session(Speaker("api", "alice", "one"), "c") != memory.session(
        Speaker("api", "alice", "two"), "c")


def test_turning_off_real_life_sharing_invalidates_cached_context(tmp_path, monkeypatch):
    monkeypatch.setattr(host, "session_context", lambda *args, **kwargs:
                        "personal note" if kwargs["share_real_life"] else "story only")
    monkeypatch.setattr(host, "prompt_context", lambda *args, **kwargs: None)
    memory, speaker = ChatMemory(tmp_path), Speaker("api", "alice")
    assert memory.context(speaker, "hi", session="s", roleplay="Ada", share_real_life=True) == "personal note"
    assert memory.context(speaker, "hi", session="s", roleplay="Ada", share_real_life=False) == "story only"


@pytest.mark.skipif(not embedded_database.available(), reason="embedded PostgreSQL binaries are not installed")
def test_colliding_legacy_speakers_cannot_read_each_others_notes(tmp_path):
    memory = ChatMemory(tmp_path)
    private, group = Speaker("api", "group:123:alice"), Speaker("api", "alice", "123")
    try:
        host.start(tmp_path)
        assert "error" not in memory.note(private, "Private appointment with Dr Juniper.")
        own = memory.context(private, "hello", session=memory.session(private))
        other = memory.context(group, "hello", session=memory.session(group))
        assert "Dr Juniper" in own and "Dr Juniper" not in other
    finally:
        try:
            desktop.stop(tmp_path)
        except desktop.DesktopError:
            pass
