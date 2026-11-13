"""Memory for chat bots that serve many people on messaging platforms (QQ, WeChat, Telegram, Discord, Feishu...).

Bot frameworks call ``context`` before each model request and ``record`` after the reply. Each person gets their own
memory (``membrain.host`` user brains), so notes, history and recall never cross between users. By default what
someone says in a group is kept apart from their private chats with the bot, so a group reply cannot reveal a private
conversation; ``group_memory="shared"`` joins them.

Bots keep one conversation per chat for months, while memBrain leaves the current conversation out of recall because
the host already shows it. Sessions are therefore one calendar day of a chat (and restart when the bot framework
starts a new conversation): today's messages are in the framework's own context, earlier days come from memory.
"""
from __future__ import annotations

import datetime as _datetime
import hashlib
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from .. import host, host_outcomes, host_receipts, host_recording

TOOLS = {"note": "membrain_note", "recall": "membrain_search", "pause": "membrain_pause", "resume": "membrain_resume"}
GROUP_MEMORY = ("separate", "shared")
PREVIOUS_EXCHANGES = 2000


@dataclass(frozen=True)
class Speaker:
    """Who is talking: the platform (adapter type or instance), their ID there, and the group if not a private chat."""

    platform: str
    user: str
    group: str | None = None

    def usable(self) -> bool:
        return bool(str(self.platform).strip() and str(self.user).strip())


def _identity(kind: str, parts: list) -> str:
    return f"%{kind}:" + hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def speaker_user_id(speaker: Speaker, group_memory: str = "separate") -> str:
    """The memBrain user a speaker's memory is kept under (``ChatMemory.user_id``), without opening an installation."""
    platform, user = str(speaker.platform), str(speaker.user)
    group = str(speaker.group) if speaker.group and group_memory == "separate" else None
    parts = [(platform, 40), (user, 80)]
    if group is not None:
        parts.append((group, 60))
    if any(len(value) > limit or any(char in value for char in ":%|") for value, limit in parts):
        return _identity("chat-v2", [platform, user, group])
    return f"{platform}:group:{group}:{user}" if group is not None else f"{platform}:{user}"


class ChatMemory:
    """One memBrain installation serving every user of a bot. Methods block; async hosts run them in a thread.

    ``block_seconds`` is retained for constructor compatibility; personal context is always refreshed.
    """

    def __init__(self, directory: Path, *, group_memory: str = "separate", record_groups: bool = True,
                 producer: str = "membrain-chatbot", tools: dict | None = TOOLS,
                 block_seconds: float = 0, roleplay: str | None = None, share_real_life: bool = False,
                 extractor=None):
        if group_memory not in GROUP_MEMORY:
            raise ValueError(f"group_memory must be one of {', '.join(GROUP_MEMORY)}.")
        self.directory = Path(directory).expanduser()
        self.group_memory, self.record_groups, self.producer, self.tools = group_memory, record_groups, producer, tools
        # A bot that plays a character keeps that story's memory apart from each person's real-life memory.
        self.roleplay, self.share_real_life = roleplay or None, share_real_life
        # Optional: a model that saves notes from each turn, for bots whose own model cannot call the note tool.
        self.extractor = extractor
        # Exact references let short follow-ups use their context without caching erased message text.
        self._previous: OrderedDict[tuple[str, str], tuple[dict, ...]] = OrderedDict()
        # The consolidation batch handed out last to each memory user in each session (``consolidate``).
        self._batches: OrderedDict[tuple[str, str | None], dict] = OrderedDict()
        self._lock = threading.Lock()
        host.state_directory(self.directory)

    def start(self) -> None:
        """Start the local service in the background if it is not running; returns at once."""
        client = host.ready_client(self.directory)
        if client is None:
            host.start_in_background(self.directory)
        else:
            client.close()

    def user_id(self, speaker: Speaker) -> str:
        return speaker_user_id(speaker, self.group_memory)

    def session(self, speaker: Speaker, conversation: str | None = None, *, today: _datetime.date | None = None) -> str:
        """The memBrain session for this speaker today in this chat (or framework conversation)."""
        day = (today or _datetime.date.today()).isoformat()
        return _identity("session-v2", [self.user_id(speaker), speaker.group, conversation, day])

    def memory_user(self, speaker: Speaker, roleplay: str | None = None) -> str:
        """The memory this speaker's messages go to: their own, or their role-play with a character."""
        return host.roleplay_user(self.user_id(speaker), roleplay or self.roleplay)

    def bound_session(self, speaker: Speaker, conversation: str, *, roleplay: str | None = None) -> str:
        return _identity("session-v3", [self.memory_user(speaker, roleplay), speaker.group, conversation])

    def _recording(self, speaker: Speaker) -> bool:
        return speaker.usable() and (self.record_groups or not speaker.group)

    def context(self, speaker: Speaker, text: str, *, session: str, turn_id: str | None = None,
                roleplay: str | None = None, share_real_life: bool | None = None) -> str | None:
        """Memory to add to the system prompt for this message: notice, notes, history and related messages.

        The message is staged and stored with the reply by ``record``. Returns ``None`` when nothing applies.
        ``roleplay`` (or the bot's own character) selects that story's separate memory.
        """
        if not self._recording(speaker):
            return None
        roleplay = roleplay or self.roleplay
        share = self.share_real_life if share_real_life is None else share_real_life
        block = host.session_context(self.directory, session, tools=self.tools, user_id=self.user_id(speaker),
                                     roleplay=roleplay, share_real_life=share)
        recalled = host.prompt_context(self.directory, session, text, turn_id=turn_id, producer=self.producer,
                                       user_id=self.user_id(speaker), roleplay=roleplay,
                                       include_source=bool(self.tools), tools=self.tools)  # The source hint is for the note tool.
        return "\n\n".join(part for part in (block, recalled) if part) or None

    def record(self, speaker: Speaker, reply: str | None, *, session: str, turn_id: str | None = None,
               prompt: str | None = None, roleplay: str | None = None) -> dict | None:
        """Store the staged message (or ``prompt``) and the reply, unless this user paused recording.

        Returns the exchange's recording receipt (``membrain.host_receipts``): per message, server-confirmed,
        locally queued, excluded with the policy's reason and scope, failed, or unknown. It does not report
        whether the platform delivered the reply. ``None`` means no receipt was available.
        """
        if not self._recording(speaker):
            reason = "speaker_unidentified" if not speaker.usable() else "group_recording_disabled"
            roles = ["user"] + (["assistant"] if isinstance(reply, str) and reply.strip() else [])
            return host_receipts.turn([host_receipts.message(role, None, "excluded", reason, scope="adapter")
                                       for role in roles])
        receipt = {}
        records = host.finish_turn(self.directory, session, reply, turn_id=turn_id, producer=self.producer,
                                   prompt=prompt, user_id=self.user_id(speaker), roleplay=roleplay or self.roleplay,
                                   receipt=receipt)
        # Only a turn that was actually recorded or queued is read, and its notes are linked to its messages, so
        # forgetting those messages forgets the notes too.
        message = next((record for record in records if record["role"] == "user"), None)
        if self.extractor is not None and message is not None:
            sources = [{"producer_ref": record["producer_ref"], "source_event_key": record["source_event_key"],
                        "source_revision": 1} for record in records]
            user = self.memory_user(speaker, roleplay)
            with self._lock:
                previous = self._previous.pop((user, session), ())
                self._previous[(user, session)] = tuple(sources)
                while len(self._previous) > PREVIOUS_EXCHANGES:
                    self._previous.popitem(last=False)
            recording = message.get("_recording", {"revision": 0, "target": None})
            self._extract(user, sources, previous, session=session,
                          recording=dict(recording) if isinstance(recording, dict) else recording)
        return receipt or None

    def exchange(self, speaker: Speaker, *, session: str, turn_id: str, roleplay: str | None = None) -> str | None:
        """The stable handle of one exchange, for ``outcome``; ``None`` when this speaker is not recorded. It can
        be computed before the exchange is recorded and addresses only this speaker's own turn."""
        if not self._recording(speaker) or not isinstance(turn_id, str) or not 1 <= len(turn_id) <= 120:
            return None
        return host_outcomes.exchange_id(session, turn_id, producer=self.producer, user_id=self.user_id(speaker),
                                         roleplay=roleplay or self.roleplay)

    def outcome(self, speaker: Speaker, *, exchange: str | None = None, session: str | None = None,
                turn_id: str | None = None, roleplay: str | None = None) -> dict:
        """The retained recording outcome of one of this speaker's exchanges (``membrain.host_outcomes``): the last
        observation of each message with its age, or an explicit ``awaiting_completion``, ``erased``, ``not_found``
        or ``unavailable``. Another person's exchange is ``not_found``. A local read: it never stores, replays or
        sends anything, and does not report whether the platform delivered the reply."""
        return host_outcomes.lookup(self.directory, exchange=exchange, session=session, turn_id=turn_id,
                                    producer=self.producer, user_id=self.user_id(speaker),
                                    roleplay=roleplay or self.roleplay)

    def recent_outcomes(self, speaker: Speaker, *, session: str, roleplay: str | None = None,
                        limit: int = 10) -> dict:
        """This speaker's most recently observed exchanges in one session, newest first."""
        return host_outcomes.recent(self.directory, session=session, producer=self.producer,
                                    user_id=self.user_id(speaker), roleplay=roleplay or self.roleplay, limit=limit)

    def _extract(self, user: str, sources: list[dict], previous_sources: tuple[dict, ...] = (), *, recording,
                 session: str | None = None) -> None:
        from ..extraction import extract_turn

        def task():
            extract_turn(self.directory, self.extractor, user, sources=sources, previous_sources=previous_sources,
                         recording=recording, session=session)

        if not self.extractor.submit(task):
            from ..extraction import record_outcome

            record_outcome(self.directory, skipped=True)

    def note(self, speaker: Speaker, text: str, replaces=(), *, roleplay: str | None = None, source_event_ids=(), source_messages=(),
             recording_capture: str | None = None, **fields) -> dict:
        from ..host_recording import save_note
        from ..notes import note_fields

        if not self._recording(speaker):
            return {"error": "Memory tools are not available in this conversation."}
        user = self.memory_user(speaker, roleplay)
        from ..host_recording import capture_marker

        if host.paused(self.directory, user, marker=capture_marker(recording_capture)):
            return {"error": "Recording is paused. Resume before saving agent notes."}
        client = self._client(user)
        if client is None:
            return {"error": "memBrain is starting; try again in a few seconds."}
        with client:
            result = save_note(self.directory, client, host.scrub(str(text or "")), replaces=tuple(replaces or ()), source_event_ids=source_event_ids, source_messages=source_messages,
                               recording_capture=recording_capture, user_id=user,
                               **note_fields(fields))
        return result

    def boundary(self, speaker: Speaker, topic: str, aliases=(), *, roleplay: str | None = None) -> dict:
        if not self._recording(speaker):
            return {"error": "Memory tools are not available in this conversation."}
        user = self.memory_user(speaker, roleplay)
        client = self._client(user)
        if client is None:
            return {"error": "memBrain is starting; try again in a few seconds."}
        with client:
            result = client.add_boundary(topic, aliases)
        return {"boundaries": result.get("boundaries", [])}

    def search(self, speaker: Speaker, query: str, *, session: str | None = None, roleplay: str | None = None,
               replies: bool = False) -> dict:
        """Recall for the search tool. ``replies`` adds the bot's own earlier replies, which automatic recall leaves
        out: the bot's AI sets it when the user asks about something it said."""
        client = self._client(self.memory_user(speaker, roleplay))
        if client is None:
            return {"error": "memBrain is starting; try again in a few seconds."}
        with client:
            found = host.recall_context(client, host.scrub(str(query or "")), current_conversation=session,
                                        replies=bool(replies))
        return {"context": found or "No matching records."}

    def consolidate(self, speaker: Speaker, cues=None, reviewed_through=None, *, session: str | None = None,
                    roleplay: str | None = None) -> dict:
        """The consolidation tool (``host.consolidate``): without arguments, a batch of this speaker's earlier
        messages to write retrieval cues for; then the cues. The batch handed out last in this ``session`` is
        remembered, so the second call need not repeat its number, unless the bot restarted in between."""
        if not self._recording(speaker):
            return {"error": "Memory tools are not available in this conversation."}
        user = self.memory_user(speaker, roleplay)
        if host.paused(self.directory, user):
            return {"error": host.CONSOLIDATION_PAUSED}
        client = self._client(user)
        if client is None:
            return {"error": "memBrain is starting; try again in a few seconds."}
        with self._lock:
            handed_out = self._batches.pop((user, session), {})
            self._batches[(user, session)] = handed_out
            while len(self._batches) > PREVIOUS_EXCHANGES:
                self._batches.popitem(last=False)
        with client:
            return host.consolidate(client, cues, reviewed_through, handed_out=handed_out)

    def pause(self, speaker: Speaker, hours: float | None = None, until_resumed: bool = False) -> dict:
        """Pause recording for this speaker: for the rest of the conversation unless ``hours`` or
        ``until_resumed`` (the person asked to stop being remembered until they say so)."""
        user = self.user_id(speaker)
        result = host_recording.pause(self.directory, hours, user_id=user, conversation=not until_resumed,
                                      roleplay=self.roleplay)
        return result

    def forget(self, speaker: Speaker) -> dict:
        """Erase everything this speaker's memory holds here, and their memory of the bot's role-play character."""
        users = [self.user_id(speaker)]
        if self.roleplay:
            users.append(self.memory_user(speaker))
        results = [host.erase_user(self.directory, user) for user in dict.fromkeys(users)]
        with self._lock:
            for key in [key for key in self._previous if key[0] in users or host.real_life_user(key[0]) in users]:
                del self._previous[key]
            for key in [key for key in self._batches if key[0] in users or host.real_life_user(key[0]) in users]:
                del self._batches[key]
        return {"erased": all(result["erased"] in ("accepted", "completed") for result in results),
                "queued_records_dropped": sum(result["queued_records_dropped"] for result in results)}

    def export(self, speaker: Speaker) -> dict:
        """This speaker's memory here as an archive document."""
        return host.export_user(self.directory, self.user_id(speaker))

    def resume(self, speaker: Speaker, *, current_turn: bool = True, session: str | None = None) -> dict:
        """Resume recording for this speaker. Pass the conversation's ``session`` to include its current message
        when it asked to resume; without a session only future messages are recorded."""
        user = self.user_id(speaker)
        result = host_recording.resume(self.directory, user_id=user, current_turn=current_turn, session=session,
                                       roleplay=self.roleplay)
        return result

    def _client(self, user: str):
        client = host.ready_client(self.directory, user)
        if client is None:
            host.start_in_background(self.directory)
        return client
