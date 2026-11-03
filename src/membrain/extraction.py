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
import time

import httpx

from .notes import KINDS, STATUSES, note_fields

PRODUCER = "membrain-extract"
MAX_NOTES = 5
STATUS_FILE = "extraction.json"
RETRY_DELAYS = (2, 8)  # Seconds before the second and third attempt at a turn the provider failed on for now.
_logger = logging.getLogger("membrain.extraction")
# Messages that never carry a lasting fact. Anything else is read, however short: "cancelled it", "改到周五", "ok"
# (agreeing to what the assistant proposed) and "I'm vegan now" can all be updates.
_SMALL_TALK = re.compile(
    r"(hi|hiya|hello|hey|yo|thanks?|thank you|thx|ty|cheers|bye|goodbye|good (morning|night|evening)|gm|gn|"
    r"night|lol|lmao|ha(ha)+|he(he)+|你好|您好|嗨|哈喽|谢谢|谢谢你|多谢|感谢|晚安|早安|早上好|早|拜拜|再见|哈{2,}|呵呵|嘿嘿)"
    r"[呀啊哦哈~]*", re.IGNORECASE)
_FILLER = {"ok", "okay", "so", "much", "a", "lot", "very", "you", "again", "all", "everyone", "there"}
_MEANINGFUL = re.compile(r"[^\W_]", re.UNICODE)

INSTRUCTIONS = f"""You maintain long-term memory notes about one person who talks to an assistant. Read the latest
exchange and the person's current notes, and decide which lasting facts about the person or their life to save.

Save: health conditions and limits, allergies and diet, people in their life and how they relate (with names and
nicknames that are easy to confuse), dates and places of plans, budgets and numbers that will matter, preferences
about how the assistant should help, decisions, and changes to earlier plans. Write each note as one short sentence
in the language the person wrote the latest exchange in, with dates as YYYY-MM-DD when timing matters and the name
of who it is about.

Save only what the person said. Do not save small talk, one-off requests, facts already in a note, anything the
person asked not to keep, or what the assistant said, assumed or asked about (a question such as "is Leila still
dog-sitting?" is not a fact) unless the person confirmed it. A plan stays "intended" until the person says it is scheduled
or done; never mark something done because it was planned, and "done" means everything in the note has happened (paid
for but not yet delivered is "scheduled", with the delivery date). Anything the person must do by a date (send
documents, pay, register) is a "plan" with that "due" date, whoever it involves. When a fact changes (a date moves, a plan is cancelled
or done), save the updated note and put the old note's id in "replaces". Most exchanges need no note.

Resolve dates against today's date and the calendar given with the exchange: a day of the month without a month
("the 16th", "16号") is the next such day from today, and when a weekday is named with it the two must agree on the
calendar. If they cannot be reconciled, leave the date out rather than guess.

Answer with JSON only: {{"notes": [ ... ]}} with at most {MAX_NOTES} items, each
{{"text": "...", "kind": one of {list(KINDS)}, "about": "name or empty", "aliases": [],
"status": one of {list(STATUSES)} or empty (plans and the assistant's promises only), "due": "YYYY-MM-DD or empty",
"occurs_at": "YYYY-MM-DD or empty", "sensitive": true or false, "replaces": ["old note id", ...]}}.
Return {{"notes": []}} when nothing lasting was said."""


def worth_reading(prompt: str) -> bool:
    """Skip greetings, thanks and emoji-only messages, which never hold a lasting fact, to save a model call."""
    text = re.sub(r"[\s\W_]+", " ", prompt or "", flags=re.UNICODE).strip()
    if not _MEANINGFUL.search(text):
        return False
    if _SMALL_TALK.fullmatch(text):
        return False
    # "ok thanks", "thanks so much", "hi there": small talk with filler words around it.
    words = text.lower().split()
    rest = [word for word in words if word not in _FILLER]
    return not (rest and len(rest) < len(words) and _SMALL_TALK.fullmatch(" ".join(rest)))


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

    def propose(self, prompt: str, reply: str, notes: str, today: _datetime.date | None = None,
                previous: tuple[str, str] | None = None) -> list[dict]:
        """The notes to save for one exchange, as checked note fields plus ``text`` and ``replaces``.

        ``previous`` is the exchange before it in the same conversation, shown so a short reply can be understood.
        """
        today = today or _datetime.date.today()
        earlier = ""
        if previous:
            earlier = ("Previous exchange (context only; its facts were already considered):\n"
                       f"Person: {_clip(previous[0])}\nAssistant: {_clip(previous[1])}\n\n")
        body = {"model": self.model, "temperature": 0, "max_tokens": 1200, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": INSTRUCTIONS}, {"role": "user", "content": (
                    f"Today is {today.isoformat()} ({today.strftime('%A')}).\n{_calendar(today)}\n\n"
                    f"Current notes:\n{notes or '(none)'}\n\n{earlier}"
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

    def submit(self, task) -> bool:
        """Run ``task`` on the background worker; drops it when the queue is full rather than slowing replies.

        Returns whether the task was queued.
        """
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="membrain-extract", daemon=True)
                self._worker.start()
        try:
            self._queue.put_nowait(task)
            return True
        except queue.Full:
            _logger.warning("note extraction queue full; turn skipped")
            return False

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


def _retryable(error: Exception) -> bool:
    if isinstance(error, httpx.TransportError):
        return True
    return isinstance(error, httpx.HTTPStatusError) and (error.response.status_code == 429
                                                          or error.response.status_code >= 500)


def _error_name(error: Exception | str) -> str:
    if isinstance(error, str):
        return error
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    return type(error).__name__


_status_lock = threading.Lock()


def record_outcome(directory, *, saved: int | None = None, error: Exception | str | None = None,
                   skipped: bool = False) -> None:
    """Count one turn's extraction outcome in the installation's state, so a failing provider is visible.

    Messages are recorded either way; only the notes drawn from them are missing while extraction fails.
    """
    from . import host

    now = _datetime.datetime.now(_datetime.timezone.utc).isoformat(timespec="seconds")
    with _status_lock:
        path = host.state_directory(directory) / STATUS_FILE
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if not isinstance(state, dict):
            state = {}
        for key in ("turns_read", "notes_saved", "turns_failed", "turns_skipped", "failed_since_success"):
            state[key] = int(state.get(key) or 0)
        if skipped:
            state["turns_skipped"] += 1
            state["failed_since_success"] += 1
            state["last_failure_at"], state["last_error"] = now, "queue full"
        elif error is not None:
            state["turns_failed"] += 1
            state["failed_since_success"] += 1
            state["last_failure_at"], state["last_error"] = now, _error_name(error)
        else:
            state["turns_read"] += 1
            state["notes_saved"] += saved or 0
            state["failed_since_success"] = 0
            state["last_success_at"] = now
        temporary = path.with_name(f".{STATUS_FILE}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temporary, path)


def extraction_status(directory) -> dict | None:
    """The installation's extraction outcomes, or ``None`` when extraction has never run here.

    ``state`` is ``degraded`` when the turns since the last successful read all failed or were skipped.
    """
    from pathlib import Path

    try:
        state = json.loads((Path(directory) / "plugin" / STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict):
        return None
    return {**state, "state": "degraded" if int(state.get("failed_since_success") or 0) else "ok"}


def _calendar(today: _datetime.date, days: int = 35) -> str:
    """The coming weeks with their weekdays, so "Saturday the 16th" resolves to the right month."""
    dates = (today + _datetime.timedelta(days=offset) for offset in range(1, days + 1))
    return "Calendar: " + ", ".join(f"{day.isoformat()} {day.strftime('%a')}" for day in dates)


def _clip(text: str, limit: int = 2000) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + " …"


def extract_turn(directory, extractor: Extractor, user_id: str | None, prompt: str, reply: str, *,
                 sources=(), previous: tuple[str, str] | None = None) -> list[dict]:
    """Save the lasting facts of one recorded turn as notes in this person's memory; returns what was saved.

    ``sources`` are the turn's message references (``producer_ref``, ``source_event_key``, ``source_revision``);
    each note is linked to them, so forgetting the messages forgets the notes drawn from them.
    """
    from . import host
    from .notes import list_notes, render_notes, save_note

    if host.paused(directory, user_id) or not worth_reading(prompt):
        return []
    client = host.ready_client(directory, user_id)
    if client is None:
        record_outcome(directory, error="memory service not ready")
        return []
    with client:
        current = render_notes(list_notes(client), tool=None) or ""
        saved = []
        earlier = (host.scrub(previous[0] or ""), host.scrub(previous[1] or "")) if previous else None
        delays = getattr(extractor, "retry_delays", RETRY_DELAYS)
        for attempt in range(len(delays) + 1):
            try:
                proposed = extractor.propose(host.scrub(prompt), host.scrub(reply or ""), current, previous=earlier)
                break
            except Exception as error:
                if attempt < len(delays) and _retryable(error):
                    time.sleep(delays[attempt])
                    continue
                record_outcome(directory, error=error)
                raise
        for note in proposed:
            text, replaces = note.pop("text"), note.pop("replaces")
            try:
                result = save_note(client, host.scrub(text), replaces=tuple(replaces), producer=PRODUCER,
                                   source_messages=list(sources), **note)
            except Exception as error:  # One bad proposal must not lose the others.
                _logger.warning("note not saved: %s", type(error).__name__)
                continue
            saved.append({"text": text, **note, **result})
    record_outcome(directory, saved=len(saved))
    return saved
