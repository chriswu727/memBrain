"""A brain the removed runtime mode filled still starts, recalls, shows, pauses, exports, restores and erases.

The rows come from tests/fixtures/legacy_runtime, exported by the runtime at ba70e7cd after its ``BrainRuntime``
ran turns to every stage it could leave a turn in (tests/legacy_runtime.py). They are written into a new brain with
plain SQL, as that runtime left them; nothing in the package can create them any more.
"""
import hashlib
import json
import os

import pytest
from legacy_runtime import archive_document, load_runtime_brain
from psycopg.types.json import Jsonb

from membrain.client import default_budget, default_read_fence, integration_capabilities
from membrain.config import Settings
from membrain.helpers import digest, uid
from membrain.memory_map import memory_map
from membrain.recording_control import recording_status, set_recording
from membrain.storage import Database
from membrain.structure_map import structure_map

pytestmark = pytest.mark.integration


@pytest.fixture
def database():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("A dedicated PostgreSQL database is required")
    value = Database(os.environ.get("MEMORY_TEST_DATABASE_URL", settings.database_url), settings.migration_database_url)
    value.migrate()
    return value


@pytest.fixture
def old(database):
    return load_runtime_brain(database)


def brain_tables(old):
    with old.database.transaction(old.principal) as conn:
        return [row["table_name"] for row in conn.execute(
            "SELECT c.table_name FROM information_schema.columns c JOIN information_schema.tables t "
            "ON t.table_name=c.table_name AND t.table_schema=c.table_schema WHERE c.table_schema=current_schema() "
            "AND c.column_name='brain_id' AND t.table_type='BASE TABLE' AND c.table_name LIKE 'memory\\_%%' ESCAPE '\\' "
            "ORDER BY c.table_name")]


def everything(old, table):
    """Every column of every row of one of this brain's tables, as text."""
    with old.database.transaction(old.principal) as conn:
        owner = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
                             "AND table_name=%s AND column_name='owner_id'", (table,)).fetchone()
        condition = "tenant_id=%s AND brain_id=%s" + (" AND owner_id=%s" if owner else "")
        values = (old.principal.tenant_id, old.brain_id) + ((old.principal.principal_id,) if owner else ())
        return [row["value"] for row in conn.execute(f"SELECT t::text AS value FROM {table} t WHERE {condition}", values)]


def recall(old, query, conversation="chat"):
    return old.action("recall", {"query": query, "intent": "explore", "cue_event_ids": [], "additional_cues": [],
                                 "read_fence": default_read_fence(), "budget": default_budget(16000)},
                      conversation=conversation)


def test_the_rows_load_as_that_runtime_left_them(old):
    stages = {row["turn_id"]: row["stage"] for row in old.rows("memory_runtime_turns")}
    assert {name: stages[turn] for name, turn in old.turns.items()} == old.data["stages"]
    assert {"completed", "generated", "captured", "started", "failed"} <= set(stages.values())
    assert old.rows("memory_runtime_turn_transitions")
    assert old.turn("remembered")["prepared_memory_selection"]["state"] == "complete"
    assert old.turn("reviewed")["response_review"]["status"] == "approved"
    assert old.turn("rejected")["response_review"]["status"] == "rejected"
    assert old.turn("ephemeral")["ephemeral"]
    assert old.rows("memory_feedback_contributions") and old.rows("memory_access_state")
    assert old.rows("memory_working_states")


def test_an_old_brain_serves_recall_status_and_the_memory_page(old):
    found = recall(old, "松木香味")
    assert any(item["memory"]["statement"] == old.memory["statement"] for item in found["items"])
    status = old.service.memory_status(old.principal, old.brain_id)
    assert status
    old.service.dashboard(old.principal, old.brain_id)
    old.service.timeline(old.principal, old.brain_id, roles=("user", "assistant"))
    assert memory_map(old.service, old.principal, old.brain_id)
    assert structure_map(old.service, old.principal, old.brain_id)
    for _ in range(200):
        if not old.service.work_once(old.principal, old.brain_id):
            break
    else:
        pytest.fail("The worker did not become idle")
    assert {row["turn_id"]: row["stage"] for row in old.rows("memory_runtime_turns")} == {
        old.turns[name]: stage for name, stage in old.data["stages"].items()}


def test_prepare_commit_and_checkpoint_still_work_beside_old_turns(old):
    """The public actions stay; they need no runtime turn, and an old turn's id is just an identifier to them."""
    question = old.events("我喜欢哪种香味，松木吗？")[0]
    for turn_id in ("turn-" + uid(), old.turns["remembered"]):
        packet = old.action("prepare", {
            "turn_id": turn_id, "latest_input_event_ids": [question["id"]], "read_fence": default_read_fence(),
            "budget": default_budget(4000), "capabilities": integration_capabilities()})
        assert packet["turn_id"] == turn_id and "松木" in json.dumps(packet, ensure_ascii=False)
    working = old.rows("memory_working_states", "AND conversation_id='chat' AND branch_id='main'")[0]
    committed = old.action("commit", {
        "turn_id": "turn-" + uid(), "idempotency_key": uid(), "expected_working_revision": working["revision"],
        "delivered_event_ids": [], "proposed_items": [], "proposed_open_loops": [], "assertion_proposals": [],
        "recall_feedback": []})
    assert committed["working_state"]["revision"] == working["revision"] + 1
    checkpoint = old.action("checkpoint", {"expected_working_revision": working["revision"] + 1,
                                           "through_sequence": 1, "reason": "manual"})
    assert checkpoint["compaction_safe"]


def test_pausing_recording_still_stops_every_unfinished_old_turn(old):
    unfinished = {row["turn_id"] for row in old.rows("memory_runtime_turns")
                  if row["stage"] not in ("delivered", "committed", "completed", "failed")
                  and not (row["ephemeral"] and row["stage"] == "delivering")}
    assert unfinished
    before = {row["turn_id"]: row for row in old.rows("memory_runtime_turns")}
    revision = recording_status(old.service, old.principal, old.brain_id)["revision"]
    assert set_recording(old.service, old.principal, old.brain_id, paused=True, expected_revision=revision)["paused"]
    after = {row["turn_id"]: row for row in old.rows("memory_runtime_turns")}
    assert all(after[turn]["stage"] == "failed" and not after[turn]["scope_reserved"] for turn in unfinished)
    assert {turn: row for turn, row in after.items() if turn not in unfinished} == {
        turn: row for turn, row in before.items() if turn not in unfinished}
    assert {row["turn_id"] for row in old.rows("memory_runtime_turn_transitions", "AND operation='fail'")} >= unfinished


ERASED = ["reviewed", "draft", "unknown", "cancelled", "partial", "failed", "captured"]


@pytest.mark.parametrize("name", ERASED)
def test_erasing_a_turns_message_leaves_its_text_in_no_row_of_the_brain(old, name):
    """The finding asked for: erase a message an old turn recorded, then look for its text in every column."""
    text = old.texts[name + "_input"]
    events = old.events(text)
    assert events
    turn = old.turn(name)
    assert {ref["event_id"] for ref in turn["input_event_refs"]} == {event["id"] for event in events}
    before = [table for table in brain_tables(old) if any(text in value for value in everything(old, table))]
    assert "memory_events" in before
    old.forget("events", [event["id"] for event in events])
    survivors = {table: [value for value in everything(old, table) if text in value] for table in brain_tables(old)}
    assert {table: values for table, values in survivors.items() if values} == {}
    assert all(not any(text in value for value in everything(old, table))
               for table in ("memory_runtime_turns", "memory_runtime_turn_transitions"))


# A word or phrase only the input and answer of one turn contain.
TOKENS = {"reviewed": "amber-417", "rejected": "quarry garden", "draft": "copper kettle", "unknown": "Tromso",
          "cancelled": "behind the calendar", "partial": "saffron crocus", "failed": "violin lesson",
          "captured": "library card number", "ephemeral": "orchard barn"}


@pytest.mark.parametrize("name", sorted(TOKENS))
def test_erasing_every_message_of_a_turn_leaves_none_of_its_words_in_the_brain(old, name):
    """Inputs and answers, drafts and delivered revisions alike; an off-record turn stored none."""
    token = TOKENS[name]
    events = sorted({row["id"] for row in old.rows("memory_events") if row["document"] is not None
                     and token in json.dumps(row["document"]["observed"]["content"], ensure_ascii=False)})
    assert bool(events) is (name != "ephemeral")
    if events:
        old.forget("events", events)
    survivors = {table: [value for value in everything(old, table) if token in value] for table in brain_tables(old)}
    assert {table: values for table, values in survivors.items() if values} == {}


QUESTION = "我喜欢哪种香味，松木吗？"
SEED = "我喜欢松木香味。"


def digests(*texts):
    """Every digest an older runtime stored of a text: SHA-256 of the text (delivery receipts, answer reviews,
    prepared selections), of the message, its id and text (turn input fingerprints), and of the text alone (the
    input fingerprint a host gave a captured turn)."""
    found = set()
    for text in texts:
        found.update((hashlib.sha256(text.encode()).hexdigest(), digest(text)))
        found.update(digest({"message_id": message_id, "text": text}) for message_id in ("m", "question", "reply"))
    return found


def turn_texts(old, name):
    """The input and answer texts of one fixture turn (a partial delivery also recorded its delivered part)."""
    if name == "remembered":
        # The question, the answer (the remembered statement) and the message the statement was captured from.
        return {QUESTION, old.memory["statement"], SEED}
    texts = {old.texts[name + "_input"]}
    if name + "_output" in old.texts:
        texts.add(old.texts[name + "_output"])
    if name == "partial":
        texts.add(old.texts["partial_output"][:30])
    return texts


def text_events(old, texts):
    return sorted({row["id"] for row in old.rows("memory_events") if row["document"] is not None
                   and row["document"]["observed"]["content"].get("text") in texts})


def holding(old, needles):
    """Each of the brain's tables with the rows (as text) that contain one of ``needles``."""
    found = {table: [value for value in everything(old, table) if any(needle in value for needle in needles)]
             for table in brain_tables(old)}
    return {table: values for table, values in found.items() if values}


REDACTED = ["remembered", "reviewed", "rejected", "draft", "unknown", "cancelled", "partial", "failed", "captured"]


@pytest.mark.parametrize("name", REDACTED)
def test_erasing_a_turns_messages_leaves_no_digest_of_them_in_any_row(old, name):
    """Erasure replaces every digest of an erased input, reply or memory statement on old turn rows with the
    redaction marker (64 zeros); each turn row and its ids stay. An untouched turn keeps its digests."""
    texts = turn_texts(old, name)
    hashes = digests(*texts)
    assert "memory_runtime_turns" in holding(old, hashes)
    untouched = old.turn("phase_completed")
    events = text_events(old, texts)
    old.forget("events", events)
    assert holding(old, hashes) == {}
    assert holding(old, texts) == {}
    turn = old.turn(name)
    assert {ref["event_id"] for ref in turn["input_event_refs"]} <= set(events)
    if name != "remembered" or turn["input_event_refs"]:
        assert turn["input_fingerprint"] == "0" * 64
    assert old.turn("phase_completed") == untouched
    assert len(old.rows("memory_runtime_turns")) == len(old.data["tables"]["memory_runtime_turns"])


def test_hiding_a_message_keeps_its_turns_digests(old):
    """Only content erasure removes digests; suppressing recall hides the message and keeps them."""
    before = old.turn("reviewed")
    old.forget("events", text_events(old, turn_texts(old, "reviewed")), mode="suppress_recall")
    after = old.turn("reviewed")
    assert {key: after[key] for key in ("input_fingerprint", "delivery_receipt", "response_review")} == {
        key: before[key] for key in ("input_fingerprint", "delivery_receipt", "response_review")}


def test_an_archive_stored_before_erasure_keeps_no_text_or_digest_of_the_erased_messages(old):
    """Erasure rewrites the archives the server holds: the erased events leave them with their content digests."""
    exported = old.action("export", {
        "include_events": True, "include_assertions": True, "include_working_states": True,
        "include_provenance": True, "include_tombstones": True, "budget": default_budget(64000)})
    texts = turn_texts(old, "reviewed")
    content = {digest({"media_type": "text/plain", "text": text}) for text in texts}
    stored = old.service.download_archive(old.principal, exported["archive_id"])["document"]
    assert any(text in json.dumps(stored, ensure_ascii=False) for text in texts)
    assert any(item in json.dumps(stored) for item in content)
    old.forget("events", text_events(old, texts))
    rows = everything(old, "memory_archives")
    assert rows and not [value for value in rows if any(n in value for n in texts | digests(*texts) | content)]


def test_erasing_the_confirmation_withdraws_the_feedback_and_access_it_wrote(old):
    assert old.rows("memory_access_state", "AND memory_id=%s", (old.memory["memory_id"],))
    confirmation = old.events("yes")
    old.forget("events", [event["id"] for event in confirmation])
    assert all(row["invalidated_at"] is not None for row in old.rows("memory_feedback_contributions"))
    assert not old.rows("memory_access_state", "AND memory_id=%s AND external_uses>0", (old.memory["memory_id"],))


def test_forgetting_a_whole_old_conversation_erases_its_turns_messages(old):
    texts = [old.texts["reviewed_input"], old.texts["reviewed_output"]]
    old.forget("conversation", ["reviewed"])
    assert not any(text in value for table in brain_tables(old) for value in everything(old, table) for text in texts)
    assert not recall(old, "lantern code amber-417", conversation="reviewed")["items"]


def stored(old, document):
    archive_id, manifest = uid(), digest(document)
    with old.database.transaction(old.principal) as conn:
        conn.execute(
            "INSERT INTO memory_archives(tenant_id,owner_id,brain_id,id,manifest_hash,document) VALUES(%s,%s,%s,%s,%s,%s)",
            (*old.params, archive_id, manifest, Jsonb(document)))
    return {"archive_id": archive_id, "manifest_sha256": manifest, "document": document}


@pytest.mark.parametrize("upload", [False, True])
def test_an_export_of_an_old_runtime_brain_restores_and_is_then_erasable(old, upload):
    archive = stored(old, archive_document())
    old.brain_id = old.service.create_brain(old.principal, "Restored runtime archive")["id"]
    if upload:
        archive = old.service.upload_archive(old.principal, old.brain_id, archive["document"])
    old.action("restore", {
        "uploaded_archive_ref": archive["archive_id"], "expected_manifest_sha256": archive["manifest_sha256"],
        "mode": "new_brain", "apply_current_tombstones": True, "expected_scope_generation": old.scope_generation(),
        "budget": default_budget(64000)})
    found = recall(old, "松木香味")
    assert any(item["memory"]["statement"] == old.memory["statement"] for item in found["items"])
    text = old.texts["reviewed_input"]
    events = old.events(text)
    assert events
    old.forget("events", [event["id"] for event in events])
    assert not any(text in value for table in brain_tables(old) for value in everything(old, table))
