"""What the removed runtime mode left behind, for tests of what still reads, erases and restores it.

memBrain had a bundled chat mode of its own (``membrain desktop chat``) and a Python session SDK (``BrainRuntime``,
``open_agent``) built on a public turn lifecycle API (``/v1/brains/{id}/runtime/turns``). They are removed: nothing
creates runtime turns, transitions, delivery receipts, answer reviews, prepared selections or chat sessions any
more. Databases, profiles, installation backups and archives from older runtimes still hold them, and the tables
stay.

``tests/fixtures/legacy_runtime/runtime_turns.json`` holds every row of one brain that the runtime at ba70e7cd
filled through ``BrainRuntime`` (the turns, their transitions, the events they recorded, working states, traces,
the feedback contribution and access state an attributed confirmation wrote, stored requests and jobs).
``load_runtime_brain`` writes those rows into a new brain with plain SQL, as that runtime left them.
``runtime_turns_archive.json`` is the local archive the same runtime exported from that brain.

``old_chat_files`` writes the chat configuration and a pending chat session the way the removed desktop chat saved
them beside a profile.
"""
import copy
import json
import os
from pathlib import Path

from psycopg.types.json import Jsonb

from membrain.helpers import Principal, digest, uid
from membrain.recovery_profile import write_document
from membrain.service import MemoryService

FIXTURES = Path(__file__).parent / "fixtures" / "legacy_runtime"
# Stored archives are loaded from the archive fixture instead (their manifest hashes cover the brain they came from).
SKIPPED = {"memory_archives"}


def fixture(name="runtime_turns"):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _order(conn, tables):
    """The tables in an order that inserts every row after the rows its foreign keys point to."""
    edges = {table: set() for table in tables}
    for row in conn.execute(
        "SELECT c.conrelid::regclass::text AS child,c.confrelid::regclass::text AS parent FROM pg_constraint c "
        "WHERE c.contype='f' AND c.conrelid::regclass::text=ANY(%s::text[])", (list(tables),),
    ):
        if row["parent"] in edges and row["parent"] != row["child"]:
            edges[row["child"]].add(row["parent"])
    ordered, seen = [], set()

    def visit(table):
        if table in seen:
            return
        seen.add(table)
        for parent in sorted(edges[table]):
            visit(parent)
        ordered.append(table)

    for table in sorted(edges):
        visit(table)
    return ordered


def _columns(conn, table):
    """Columns that take a stored value: not generated and not drawn from a sequence."""
    return [row["column_name"] for row in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s "
        "AND is_generated='NEVER' AND identity_generation IS NULL "
        "AND coalesce(column_default,'') NOT LIKE 'nextval(%%' ORDER BY ordinal_position", (table,),
    )]


class RuntimeBrain:
    """A principal's brain whose rows the runtime at ba70e7cd wrote through its runtime mode."""

    def __init__(self, database, name="runtime_turns", principal=None):
        self.database = database
        self.service = MemoryService(database)
        self.principal = principal or Principal(uid(), uid())
        self.brain_id = uid()
        data = fixture(name)
        self.data = data
        self.texts = data["texts"]
        self.turns = data["turns"]
        self.memory = data["memory"]
        replacements = {data["tenant_id"]: self.principal.tenant_id, data["owner_id"]: self.principal.principal_id,
                        data["brain_id"]: self.brain_id}

        def rebind(row):
            text = json.dumps(row, ensure_ascii=False)
            for old, new in replacements.items():
                text = text.replace(old, new)
            return json.loads(text)

        tables = {table: rows for table, rows in data["tables"].items() if table not in SKIPPED}
        with database.transaction(self.principal) as conn:
            for table in _order(conn, tables):
                columns = _columns(conn, table)
                names = ",".join(columns)
                for row in tables[table]:
                    conn.execute(f"INSERT INTO {table}({names}) SELECT {names} FROM jsonb_populate_record(NULL::{table},%s)",
                                 (Jsonb(rebind(row)),))

    @property
    def params(self):
        return self.service._params(self.principal, self.brain_id)

    def rows(self, table, where="", parameters=()):
        with self.database.transaction(self.principal) as conn:
            return conn.execute(
                "SELECT * FROM " + table + " WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s " + where,
                (*self.params, *parameters),
            ).fetchall()

    def turn(self, name):
        return self.rows("memory_runtime_turns", "AND turn_id=%s", (self.turns[name],))[0]

    def action(self, action, payload, *, conversation="chat", branch="main"):
        from membrain.contracts import CONTRACT_VERSION

        response = self.service.handle(self.principal, {
            "message_type": "request", "contract_version": CONTRACT_VERSION, "request_id": uid(),
            "action": action, "target": {"brain_ref": self.brain_id, "conversation_ref": conversation,
                                         "branch_ref": branch},
            "payload": payload,
        })
        assert response["outcome"] == "completed", response
        return response["result"]

    def scope_generation(self):
        return self.service.dashboard(self.principal, self.brain_id)["brain"]["scope_generation"]

    def forget(self, kind, ids, mode="erase_content"):
        return self.action("forget", {"selector": {"kind": kind, "ids": list(ids)}, "mode": mode,
                                      "expected_scope_generation": self.scope_generation(),
                                      "idempotency_key": uid()})

    def events(self, text):
        """Every stored event (any revision) whose observed text is ``text``."""
        return [row for row in self.rows("memory_events") if row["document"] is not None
                and row["document"]["observed"]["content"].get("text") == text]


def load_runtime_brain(database, name="runtime_turns", principal=None):
    """A new brain, of a new principal unless one is given, holding the fixture's rows."""
    return RuntimeBrain(database, name, principal)


def archive_document():
    data = fixture("runtime_turns_archive")
    assert data["document"]["archive_origin"] == "local_export"
    return copy.deepcopy(data["document"])


CHAT = {"base_url": "https://chat.example/v1", "model": "chat-model", "api_key": "private-chat-key",
        "thinking": None, "max_output_tokens": 4096, "timeout_seconds": 180, "max_response_bytes": 1048576,
        "version": 1}


def session_identity(profile, conversation_id="chat", branch_id="main"):
    return {name: getattr(profile, name) for name in ("installation_id", "brain_id", "tenant_id", "principal_id")} | {
        "conversation_id": conversation_id, "branch_id": branch_id}


def old_chat_files(profile, *, conversation_id="chat", branch_id="main", message_id="message-1", text="hello"):
    """chat.json and one pending chat session, in the formats the removed desktop chat wrote beside a profile.

    The chat configuration held the chat model's address, model and key; a pending session recorded the message a
    chat turn was answering until the turn finished. Returns the pending document.
    """
    write_document(profile.directory / "chat.json", CHAT)
    identity = session_identity(profile, conversation_id, branch_id)
    root = profile.directory / "sessions"
    root.mkdir(mode=0o700, exist_ok=True)
    directory = root / digest(identity)
    directory.mkdir(mode=0o700)
    pending = {
        "version": 1, "identity": identity, "message_id": message_id,
        "input_fingerprint": digest({"message_id": message_id, "text": text}),
        "turn_id": "turn-" + digest([identity["brain_id"], conversation_id, branch_id, message_id])[:40],
        "generator_fingerprint": digest("old-generator"), "runtime_fingerprint": digest("old-runtime"),
    }
    write_document(directory / "pending.json", pending)
    os.chmod(directory / "pending.json", 0o600)
    return pending
