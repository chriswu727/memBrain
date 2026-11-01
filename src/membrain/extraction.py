"""Optional note extraction for hosts whose model cannot save notes itself (the proxy, simple bots).

Notes are memBrain's durable facts. Agent hosts write them with the note tool; a bot behind the proxy has no tools,
so its people would only ever get raw-message recall. With an extraction model configured, each finished turn is
read once, after the reply has been sent, together with the person's current notes, and the lasting facts in it
are saved as typed notes (plans and whether they are done, people and their aliases, constraints, preferences),
replacing notes they update. Extraction never runs while recording is paused and never delays a reply.
"""
from __future__ import annotations

import datetime as _datetime
import json
import logging
import os
import queue
import re
import threading

import httpx

from .notes import KINDS, STATUSES, note_fields

PRODUCER = "membrain-extract"
MAX_NOTES = 5
_logger = logging.getLogger("membrain.extraction")
_WORDS = re.compile(r"\w+", re.UNICODE)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")

INSTRUCTIONS = f"""You maintain long-term memory notes about one person who talks to an assistant. Read the latest
exchange and the person's current notes, and decide which lasting facts about the person or their life to save.

Save: health conditions and limits, allergies and diet, people in their life and how they relate (with names and
nicknames that are easy to confuse), dates and places of plans, budgets and numbers that will matter, preferences
about how the assistant should help, decisions, and changes to earlier plans. Write each note as one short sentence
in the person's language, with dates as YYYY-MM-DD when timing matters and the name of who it is about.

Do not save small talk, one-off requests, facts already in a note, things the assistant said unless the person
agreed, or anything the person asked not to keep. A plan stays "intended" until the person says it is scheduled
or done; never mark something done because it was planned. When a fact changes (a date moves, a plan is cancelled
or done), save the updated note and put the old note's id in "replaces". Most exchanges need no note.

Answer with JSON only: {{"notes": [ ... ]}} with at most {MAX_NOTES} items, each
{{"text": "...", "kind": one of {list(KINDS)}, "about": "name or empty", "aliases": [],
"status": one of {list(STATUSES)} or empty (plans and the assistant's promises only), "due": "YYYY-MM-DD or empty",
"occurs_at": "YYYY-MM-DD or empty", "sensitive": true or false, "replaces": ["old note id", ...]}}.
Return {{"notes": []}} when nothing lasting was said."""


def worth_reading(prompt: str) -> bool:
    """Skip greetings and one-word messages, which never hold a lasting fact, to save a model call."""
    text = prompt or ""
    return len(_WORDS.findall(text)) >= 4 or len(_CJK.findall(text)) >= 6


class Extractor:
    """Reads finished turns with an OpenAI-compatible chat model and saves the lasting facts as notes."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, *, thinking: bool = False,
                 transport: httpx.BaseTransport | None = None):
        self.base_url, self.model, self.api_key, self.thinking = base_url.rstrip("/"), model, api_key, thinking
        self._http = httpx.Client(timeout=httpx.Timeout(120, connect=15), transport=transport)
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_environment(cls, *, base_url: str | None = None, api_key: str | None = None) -> Extractor | None:
        """``MEMBRAIN_EXTRACT_MODEL`` turns extraction on; base URL and key default to the given ones."""
        model = os.environ.get("MEMBRAIN_EXTRACT_MODEL")
        if not model:
            return None
        url = os.environ.get("MEMBRAIN_EXTRACT_BASE_URL") or base_url
        key = os.environ.get("MEMBRAIN_EXTRACT_KEY") or api_key
        if not url:
            raise ValueError("Set MEMBRAIN_EXTRACT_BASE_URL for note extraction.")
        return cls(url, model, key)

    def propose(self, prompt: str, reply: str, notes: str, today: _datetime.date | None = None) -> list[dict]:
        """The notes to save for one exchange, as checked note fields plus ``text`` and ``replaces``."""
        today = today or _datetime.date.today()
        body = {"model": self.model, "temperature": 0, "max_tokens": 1200, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": (
                    f"Today is {today.isoformat()}.\n\nCurrent notes:\n{notes or '(none)'}\n\n"
                    f"Latest exchange:\nPerson: {prompt}\nAssistant: {reply}")}]}
        if not self.thinking:
            body["thinking"] = {"type": "disabled"}  # Ignored by providers that do not know it.
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = self._http.post(self.base_url + "/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"].get("content") or "{}"
        try:
            proposed = json.loads(content).get("notes") or []
        except (ValueError, AttributeError):
            return []
        notes_out = []
        for item in proposed[:MAX_NOTES] if isinstance(proposed, list) else []:
            if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                continue
            fields = {key: value for key, value in item.items() if value not in (None, "", [], False)
                      and key in ("kind", "about", "aliases", "status", "due", "occurs_at", "sensitive")}
            if fields.get("kind") not in KINDS:
                fields.pop("kind", None)
            if fields.get("status") not in STATUSES or fields.get("kind") not in ("plan", "agent_commitment"):
                fields.pop("status", None)
            try:
                checked = note_fields(fields)
            except ValueError:
                checked = {}
            replaces = [value for value in item.get("replaces") or () if isinstance(value, str)]
            notes_out.append({"text": str(item["text"]).strip(), "replaces": replaces, **checked})
        return notes_out

    def submit(self, task) -> None:
        """Run ``task`` on the background worker; drops it when the queue is full rather than slowing replies."""
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="membrain-extract", daemon=True)
                self._worker.start()
        try:
            self._queue.put_nowait(task)
        except queue.Full:
            _logger.warning("note extraction queue full; turn skipped")

    def _run(self) -> None:
        while True:
            task = self._queue.get()
            try:
                task()
            except Exception as error:  # Extraction is best effort; it must never affect the bot.
                _logger.warning("note extraction failed: %s", type(error).__name__)
            finally:
                self._queue.task_done()

    def wait(self, timeout: float = 60) -> None:
        """Wait until queued extractions finish (tests and orderly shutdown)."""
        deadline = threading.Event()
        timer = threading.Timer(timeout, deadline.set)
        timer.start()
        try:
            while self._queue.unfinished_tasks and not deadline.is_set():
                deadline.wait(0.05)
        finally:
            timer.cancel()


def extract_turn(directory, extractor: Extractor, user_id: str | None, prompt: str, reply: str) -> list[dict]:
    """Save the lasting facts of one recorded turn as notes in this person's memory; returns what was saved."""
    from . import host
    from .notes import list_notes, render_notes, save_note

    if host.paused(directory, user_id) or not worth_reading(prompt):
        return []
    client = host.ready_client(directory, user_id)
    if client is None:
        return []
    with client:
        current = render_notes(list_notes(client), tool=None) or ""
        saved = []
        for note in extractor.propose(host.scrub(prompt), host.scrub(reply or ""), current):
            text, replaces = note.pop("text"), note.pop("replaces")
            try:
                result = save_note(client, host.scrub(text), replaces=tuple(replaces), producer=PRODUCER, **note)
            except Exception as error:  # One bad proposal must not lose the others.
                _logger.warning("note not saved: %s", type(error).__name__)
                continue
            saved.append({"text": text, **note, **result})
        return saved
