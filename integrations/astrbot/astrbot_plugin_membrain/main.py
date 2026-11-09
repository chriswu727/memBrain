"""memBrain for AstrBot: per-user long-term memory on QQ, WeChat, Telegram, Feishu, Discord and every other platform."""
import asyncio
import json
from pathlib import Path

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.core.utils.astrbot_path import get_astrbot_plugin_data_path

from membrain.adapters.chatbot import ChatMemory, Speaker

_STATE = "membrain"


def _speaker(event: AstrMessageEvent) -> Speaker:
    return Speaker(str(event.get_platform_name() or ""), str(event.get_sender_id() or ""),
                   str(event.get_group_id() or "") or None)


class MembrainPlugin(star.Star):
    """Long-term memory for each user: notes and earlier conversations before replies, tools to note, search and pause."""

    def __init__(self, context: star.Context, config: dict | None = None):
        super().__init__(context, config)
        config = config or {}
        directory = config.get("directory") or str(Path(get_astrbot_plugin_data_path()) / "membrain")
        extractor = None
        if config.get("extract_model") and config.get("extract_base_url"):
            from membrain.extraction import Extractor

            extractor = Extractor(config["extract_base_url"], config["extract_model"], config.get("extract_key") or None)
        self.memory = ChatMemory(Path(directory), group_memory=config.get("group_memory") or "separate",
                                 record_groups=config.get("record_groups", True), producer="membrain-astrbot",
                                 roleplay=config.get("roleplay_character") or None,
                                 share_real_life=bool(config.get("share_real_life")), extractor=extractor)
        self.memory.start()

    @filter.on_llm_request()
    async def add_memory(self, event: AstrMessageEvent, req: ProviderRequest):
        speaker, text = _speaker(event), event.get_message_str() or req.prompt or ""
        if not speaker.usable() or not text.strip():
            return
        conversation = getattr(getattr(req, "conversation", None), "cid", None)
        session = self.memory.session(speaker, conversation)
        turn = str(getattr(event.message_obj, "message_id", "") or "")[:120] or None
        event.set_extra(_STATE, {"session": session, "turn": turn, "prompt": text})
        try:
            block = await asyncio.to_thread(self.memory.context, speaker, text, session=session, turn_id=turn)
        except Exception as error:  # Memory must never stop the bot from answering.
            self.logger.warning(f"memBrain recall failed: {type(error).__name__}: {error}")
            return
        if block:
            req.system_prompt = f"{req.system_prompt or ''}\n\n{block}".strip()

    @filter.on_llm_response()
    async def store_turn(self, event: AstrMessageEvent, response: LLMResponse):
        state = event.get_extra(_STATE)
        if not state or getattr(response, "role", "assistant") != "assistant":
            return
        try:
            await asyncio.to_thread(self.memory.record, _speaker(event), response.completion_text,
                                    session=state["session"], turn_id=state["turn"], prompt=state["prompt"])
        except Exception as error:
            self.logger.warning(f"memBrain recording failed: {type(error).__name__}: {error}")

    @filter.llm_tool(name="membrain_note")
    async def membrain_note(self, event: AstrMessageEvent, text: str, replaces: list | None = None,
                            kind: str | None = None, about: str | None = None, aliases: list | None = None,
                            status: str | None = None, due: str | None = None, occurs_at: str | None = None,
                            pinned: bool = False, sensitive: bool = False, source_event_ids: list | None = None,
                            source_messages: list | None = None, affect: dict | None = None, shared: bool = False,
                            recording_capture: str | None = None):
        """Save one short, lasting fact about the user you are talking to (health, people, dates, places, preferences, decisions, plans and their changes) so it is shown in every later conversation. One fact per note, under 300 characters. Set kind when it is clear; a plan stays intended until the user confirms it is scheduled or done, and done means everything in the note has happened (paid but not yet delivered is scheduled). When a fact changes, save the new note and pass the old note's id in replaces. When the user expresses a feeling about it, add affect: reported only if they said it, inferred (with source_event_ids or source_messages) if clearly evident but unsaid; never invent one. Do not save routine requests or anything the user asked you not to keep.

        Args:
            text(string): The fact, in one sentence, with dates when they matter.
            replaces(array[string]): IDs of earlier notes this one replaces, when a fact changed.
            kind(string): person, constraint, preference, plan, routine, milestone, relationship, agent_commitment or other.
            about(string): Who the fact is about, by name, if not the user.
            aliases(array[string]): Other names for that person, such as a nickname.
            status(string): For plans and promises: intended, scheduled, done, cancelled or superseded.
            due(string): YYYY-MM-DD by which a plan or promise should happen.
            occurs_at(string): YYYY-MM-DD on which an event happens.
            pinned(boolean): Always show this note.
            sensitive(boolean): Health, money or other private matters.
            source_event_ids(array[string]): Original recorded message IDs, when available.
            source_messages(array[object]): Exact source references from the current membrain-source block.
            recording_capture(string): Copy recording_capture from this turn's membrain-source block; never substitute another turn's value.
            affect(object): A feeling the user expressed about this: label (their own word), valence -2 to 2, intensity 0 to 3, basis reported or inferred, optional topic and felt_at YYYY-MM-DD.
            shared(boolean): With kind milestone: a moment you and the user shared, such as a goal reached together or a shared joke.
        """
        fields = {"kind": kind, "about": about, "aliases": aliases, "status": status, "due": due,
                  "occurs_at": occurs_at, "pinned": pinned, "sensitive": sensitive,
                  "source_event_ids": source_event_ids or [], "source_messages": source_messages or [],
                  "affect": affect, "shared": shared, "recording_capture": recording_capture}
        try:
            result = await asyncio.to_thread(self.memory.note, _speaker(event), text, replaces or (), **fields)
        except ValueError as error:
            result = {"error": str(error)}
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="membrain_search")
    async def membrain_search(self, event: AstrMessageEvent, query: str):
        """Search this user's earlier conversations and notes when a request depends on personal context that is not already shown.

        Args:
            query(string): A few concrete keywords: names, places, activities, dates.
        """
        state = event.get_extra(_STATE) or {}
        result = await asyncio.to_thread(self.memory.search, _speaker(event), query, session=state.get("session"))
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="membrain_boundary")
    async def membrain_boundary(self, event: AstrMessageEvent, topic: str, aliases: list | None = None):
        """Save a topic the user asked you not to bring up. It stays out of recalled memory unless they raise it.
        This is not a pause or deletion: the conversation is still remembered. The memory page can remove it.

        Args:
            topic(string): The topic in a few words, only when the user asked not to bring it up.
            aliases(array[string]): Other names the user uses for this topic, in any language.
        """
        result = await asyncio.to_thread(self.memory.boundary, _speaker(event), topic, aliases or ())
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="membrain_pause")
    async def membrain_pause(self, event: AstrMessageEvent, hours: float | None = None, until_resumed: bool = False):
        """Stop recording only when the user asks you not to remember or store something ("off the record", "don't remember this"), not when they ask you to keep something private or between you: save that as a sensitive note instead. Without arguments the pause lasts for the rest of this conversation; pass hours when they name a duration, or until_resumed only when they ask you to stop remembering until they say so. The current exchange is not stored either.

        Args:
            hours(number): Optional number of hours after which recording resumes.
            until_resumed(boolean): Only when the user asks to stop being remembered until they say so.
        """
        return json.dumps(await asyncio.to_thread(self.memory.pause, _speaker(event), hours, until_resumed))

    @filter.command("membrain_forget")
    async def membrain_forget(self, event: AstrMessageEvent, confirm: str = ""):
        """Erase what the bot remembers about you in this chat. Send /membrain_forget confirm."""
        if confirm.strip().lower() != "confirm":
            yield event.plain_result("This erases everything I remember about you in this chat and cannot be undone. "
                                     "Send /membrain_forget confirm to go ahead.")
            return
        try:
            result = await asyncio.to_thread(self.memory.forget, _speaker(event))
        except Exception as error:
            self.logger.warning(f"memBrain erase failed: {type(error).__name__}: {error}")
            yield event.plain_result("I could not erase your memory just now; please try again shortly.")
            return
        yield event.plain_result("Done: everything I remembered about you in this chat is erased."
                                 if result["erased"] else "Part of your memory could not be erased; please try again.")

    @filter.llm_tool(name="membrain_resume")
    async def membrain_resume(self, event: AstrMessageEvent):
        """Resume this local capture control when the user asks. Check the returned recording state and scopes; other controls may still block capture. This does not confirm message storage."""
        state = event.get_extra(_STATE) or {}
        return json.dumps(await asyncio.to_thread(self.memory.resume, _speaker(event), session=state.get("session")))
