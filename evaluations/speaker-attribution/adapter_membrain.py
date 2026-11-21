"""memBrain arm: the plugin path through the public host API (``membrain.host``), on a fresh disposable profile.

Ingestion is what the plugin's hooks do for a live conversation: each message is delivered as a record, a reply
sharing its exchange with the message it answers (``host.message_record`` plus ``host.deliver``). No note is
written, because in an installation only the host AI writes notes and no model runs here. Recording is then
paused, so the questions never become memories, and the run waits until every stored message is embedded.

The context for a question is what a host is given at the start of a new conversation: the session opening
(``host.session_context``) followed by the related earlier messages for the first message (``host.prompt_context``).
This is the approach of ``evaluations/longmemeval/evidence_recall.py``.

The optional variant ``membrain+recall-tool`` adds what the recall tool returns when the host AI asks for its own
earlier replies too (``my_replies``), as the plugin calls it. Whether a host makes that call is the host model's
decision, which this test does not measure.

The profile, its database and its ports are created under the run's working directory and nowhere else. The
runner passes ``LOCALAPPDATA`` pointing inside that directory as well, so the embedded database binaries are
prepared there rather than in the user's own cache.
"""
from __future__ import annotations

import re
import socket
import time
from pathlib import Path

from kit import Line, Session

PRODUCER = "speaker-attribution-ingest"
_ITEM = re.compile(r"^- \[(?P<meta>[^\]]*)\] ")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def install_model(directory: Path, cache: Path) -> None:
    """Give an installation the pinned local embedding model, downloaded once into ``cache`` and checksum-verified
    (as ``evaluations/locomo/run_locomo.py`` does)."""
    import shutil

    from membrain.local_embeddings import download, installed, model_directory

    if installed(directory):
        return
    if not installed(cache):
        download(cache)
    shutil.copytree(model_directory(cache), model_directory(directory), dirs_exist_ok=True)


def start(directory: Path, timeout: float = 600) -> None:
    """Start the installation and leave it without a persona, as the other harnesses do: a new memory is otherwise
    given a preset persona picked at random, which would put a different block in each run's context."""
    from membrain import desktop, host

    try:
        host.start(directory)
    except desktop.DesktopError as error:
        if error.code != "service_start_timeout":
            raise
        deadline = time.monotonic() + timeout
        while not desktop.status(directory).get("ready"):
            if time.monotonic() > deadline:
                raise
            time.sleep(5)
        host.start(directory)
    marker = Path(directory) / "evaluation-no-persona"
    if not marker.exists():
        with host.ready_client(directory) as client:
            if not client.persona().get("version"):
                client.delete_persona_history()  # Leaves the marker after which no first persona is assigned.
        marker.write_text("The harness left this memory without a persona.\n", encoding="utf-8")


def wait_for_embeddings(directory: Path, timeout: float = 1800) -> dict:
    from membrain import host

    deadline, status = time.monotonic() + timeout, {}
    while time.monotonic() < deadline:
        with host.ready_client(directory) as client:
            status = client.dashboard()["status"]
        if status.get("pending_jobs") == 0 and status.get("index_lag", 0) == 0:
            return status
        time.sleep(2)
    raise RuntimeError(f"embeddings did not finish: {status}")


class MemBrain:
    name = "membrain"

    def __init__(self, model_cache: Path, *, recall_tool: bool = True):
        self.model_cache = Path(model_cache)
        self.recall_tool = recall_tool
        self.directory: Path | None = None
        self.asked = 0
        self._variants: dict[str, str] = {}
        self.timings: dict[str, float] = {}

    def reset(self, workdir: Path) -> None:
        from membrain import host
        from membrain.local_profile import ensure_profile

        self.directory = Path(workdir) / "membrain-profile"
        began = time.monotonic()
        ensure_profile(self.directory, api_port=free_port(), database_port=free_port(), database_engine="embedded")
        host.ensure_installation(self.directory)
        install_model(self.directory, self.model_cache)
        start(self.directory)
        self.timings["start_seconds"] = round(time.monotonic() - began, 1)
        self.asked = 0

    def ingest(self, session: Session) -> None:
        from membrain import host

        with host.ready_client(self.directory) as client:
            exchange, previous = 0, None
            for turn in session.turns:
                # A reply shares its exchange with the message it answers; anything else starts a new one.
                if turn.role != "assistant" or previous != "user":
                    exchange += 1
                previous = turn.role
                record = host.message_record(session.id, turn.role, turn.text, turn_id=f"x{exchange}",
                                             producer=PRODUCER)
                if not host.deliver(self.directory, client, record):
                    raise RuntimeError(f"memBrain refused to store a turn of {session.id}")

    def ready(self) -> None:
        from membrain import host

        host.pause(self.directory)  # The questions must never become memories.
        began = time.monotonic()
        wait_for_embeddings(self.directory)
        self.timings["embed_seconds"] = round(time.monotonic() - began, 1)

    def context(self, question: str, *, budget: int) -> str:
        from membrain import host

        self.asked += 1
        session = f"speaker-attribution-question-{self.asked}"
        opening = host.session_context(self.directory, session)
        recalled = host.prompt_context(self.directory, session, question) or ""
        text = opening + ("\n\n" + recalled if recalled else "")
        self._variants = {}
        if self.recall_tool:
            # What the memory_recall tool returns with my_replies=true (membrain.plugin calls it this way).
            with host.ready_client(self.directory) as client:
                tool = host.recall_context(client, host.scrub(question), current_conversation=session, replies=True,
                                           deliberate=True, notes=True) or ""
            self._variants["membrain+recall-tool"] = text + ("\n\n" + tool if tool else "")
        return text

    def variants(self) -> dict[str, str]:
        """Further contexts computed by the last ``context`` call, scored as arms of their own."""
        return dict(self._variants)

    def attribute(self, context: str) -> list[Line]:
        """memBrain marks speakers in two ways.

        - ``<membrain-history>``: the block header says the lines are what "this user wrote" ("Everything this user
          wrote in earlier sessions" or "The N most recent messages this user wrote"), so its items are the user's.
        - ``<membrain-memory>``: each item says it on its own line, "- [2026-11-21 · user said] ..." or
          "- [2026-11-21 · assistant said] ...". Items marked "note" or anything else have no speaker here.
        Every other line (notices, headers) has no speaker.
        """
        lines, block, block_speaker = [], None, None
        for raw in context.splitlines():
            stripped = raw.strip()
            if stripped.startswith("<membrain-") and not stripped.startswith("</"):
                block, block_speaker = stripped[1:].split(">")[0], None
                rest = stripped.split(">", 1)[1].strip() if ">" in stripped else ""
                if rest:
                    lines.append(Line(None, rest))
                continue
            if stripped.startswith("</membrain-"):
                block, block_speaker = None, None
                continue
            item = _ITEM.match(stripped)
            speaker = None
            if block == "membrain-history":
                if item is None and "this user wrote" in stripped:
                    block_speaker = "user"
                elif item is not None:
                    speaker = block_speaker
            elif block == "membrain-memory" and item is not None:
                label = item["meta"].split("·", 1)[1].strip() if "·" in item["meta"] else ""
                speaker = ("user" if label.startswith("user said") else
                           "assistant" if label.startswith("assistant said") else None)
            lines.append(Line(speaker, stripped))
        return lines

    def details(self, context: str) -> dict:
        """Which memBrain path supplied the context: a complete history, or recent history plus recall."""
        return {"history_complete": "Everything this user wrote in earlier sessions" in context,
                "has_recall_block": "<membrain-memory>" in context}

    def close(self) -> None:
        from membrain import desktop

        if self.directory is None:
            return
        if not (self.directory / "profile.json").exists():
            return
        try:
            desktop.stop(self.directory)
        except desktop.DesktopError:
            pass
