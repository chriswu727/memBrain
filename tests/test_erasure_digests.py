"""Erasing a message leaves nothing stored that could confirm a guess of it: no text and no digest, anywhere.

Before the erasure the test collects every digest-shaped value (64 lowercase hex digits) that appeared in any row of
the brain while the message was recorded and processed: its event row, the reply that depends on it, the claims,
cues, notes, requests, traces and stored archive derived from them. After the erasure none of them may appear in any
column of any table, except the values in ``ALLOWED``, each with the reason it cannot be derived from the content.
Hiding a message (``suppress_recall``) is not erasure and keeps everything.
"""
import re

import pytest
from service_harness import harness as harness

from membrain.client import default_budget, default_read_fence, integration_capabilities
from membrain.helpers import digest, uid

pytestmark = pytest.mark.integration
HEX = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
ZERO = "0" * 64
SECRET = "My passport number ends in 7741 and it lives in the blue drawer."
REPLY = "Noted: the passport ending 7741 is in the blue drawer."
CONTROL = "I water the fig tree on Sundays."


def tables(harness):
    with harness.database.transaction(harness.principal) as conn:
        return [row["table_name"] for row in conn.execute(
            "SELECT c.table_name FROM information_schema.columns c JOIN information_schema.tables t "
            "ON t.table_name=c.table_name AND t.table_schema=c.table_schema WHERE c.table_schema=current_schema() "
            "AND c.column_name='tenant_id' AND t.table_type='BASE TABLE' AND c.table_name LIKE 'memory\\_%%' "
            "ESCAPE '\\' ORDER BY c.table_name")]


def rows(harness):
    """Every row of every table that belongs to this principal, as text, by table."""
    found = {}
    with harness.database.transaction(harness.principal) as conn:
        for table in tables(harness):
            owner = conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
                                 "AND table_name=%s AND column_name='owner_id'", (table,)).fetchone()
            condition = "tenant_id=%s" + (" AND owner_id=%s" if owner else "")
            values = (harness.principal.tenant_id,) + ((harness.principal.principal_id,) if owner else ())
            found[table] = [row["value"] for row in conn.execute(
                f"SELECT t::text AS value FROM {table} t WHERE {condition}", values)]
    return found


def digests(harness):
    """Each digest-shaped value stored for this principal, with the tables it is in."""
    found = {}
    for table, values in rows(harness).items():
        for value in values:
            for item in HEX.findall(value):
                found.setdefault(item, set()).add(table)
    return found


def drain(harness):
    for _ in range(100):
        if not harness.service.work_once(harness.principal, harness.brain):
            return
    pytest.fail("The worker did not become idle")


def record(harness):
    """The control message first; then the secret, its reply, a cue, a note and a recall and prepare about it, and
    an export. Returns the digests stored before the secret, those after, and the secret's event id."""
    harness.observe(CONTROL, source_key="control")
    drain(harness)
    before = digests(harness)
    secret = harness.observe(SECRET, source_key="secret")["accepted_event_ids"][0]
    harness.memory.observe(REPLY, role="assistant", delivery_state="delivered", conversation_id="chat",
                           branch_id="main", source_event_key="secret-reply", producer_ref="service-test",
                           parent_source_event_keys=["secret"])
    drain(harness)
    harness.memory.write_message_cues([{"event_id": secret, "cues": ["passport location"]}])
    harness.memory.write_note("The passport is in the blue drawer.", source_event_ids=[secret])
    harness.memory.recall(SECRET, conversation_id="chat", branch_id="main")
    harness.memory.prepare("turn-" + uid(), conversation_id="chat", branch_id="main",
                           latest_input_event_ids=[secret], read_fence=default_read_fence(),
                           budget=default_budget(4000), capabilities=integration_capabilities())
    harness.memory.export(conversation_id="chat", branch_id="main")
    return before, digests(harness), secret


def forget(harness, event_id, mode="erase_content"):
    generation = harness.memory.dashboard()["brain"]["scope_generation"]
    return harness.memory.forget([event_id], kind="events", mode=mode, expected_scope_generation=generation)


# Values a row keeps after the erasure that are provably not derived from the erased content.
ALLOWED = {
    ZERO: "the redaction marker itself",
}


@pytest.mark.parametrize("embedded", [False, True])
def test_erasing_a_message_leaves_no_digest_of_it_or_of_anything_derived_from_it(harness, embedded):
    if embedded:  # Vectors and passages of the claims, embedded as the local model would.
        from test_semantic_shared_reads import fake_embeddings

        harness.service.embedding_provider = fake_embeddings([])
    before, recorded, secret = record(harness)
    if embedded:
        with harness.database.transaction(harness.principal) as conn:
            assert conn.execute("SELECT count(*) AS n FROM memory_embeddings WHERE tenant_id=%s",
                                (harness.principal.tenant_id,)).fetchone()["n"]
    captured = set(recorded) - set(before)
    assert captured, "recording the message must have stored digests"
    forget(harness, secret)
    after = digests(harness)
    with harness.database.transaction(harness.principal) as conn:
        # An embedding job's id is "embed:" and a digest of the memory's id and revision and the model's space
        # (vector_jobs.embedding_job_id): identity, not content.
        job_ids = {row["id"].split(":", 1)[1] for row in conn.execute(
            "SELECT id FROM memory_jobs WHERE tenant_id=%s AND kind='embed' AND id LIKE 'embed:%%'",
            (harness.principal.tenant_id,))}
    left = {value: sorted(after[value]) for value in captured & set(after) if value not in set(ALLOWED) | job_ids}
    assert left == {}
    text = rows(harness)
    assert not [table for table, values in text.items() for value in values
                if "7741" in value or "blue drawer" in value]
    # The control message keeps its own digests.
    assert digest({"media_type": "text/plain", "text": CONTROL}) in after


def test_hiding_a_message_keeps_its_digests(harness):
    before, recorded, secret = record(harness)
    content = digest({"media_type": "text/plain", "text": SECRET})
    assert content in recorded
    forget(harness, secret, mode="suppress_recall")
    assert content in digests(harness)


def test_an_older_archive_restored_after_the_erasure_keeps_the_message_erased(harness):
    """The archive still holds the message; restoring it locally or by upload excludes it, without an error."""
    harness.observe(CONTROL, source_key="control")
    secret = harness.observe(SECRET, source_key="secret")["accepted_event_ids"][0]
    drain(harness)
    exported = harness.memory.export(conversation_id="chat", branch_id="main")["result"]
    with harness.database.transaction(harness.principal) as conn:
        saved = conn.execute("SELECT manifest_hash,document FROM memory_archives WHERE tenant_id=%s AND id=%s",
                             (harness.principal.tenant_id, exported["archive_id"])).fetchone()
    document = saved["document"]
    assert any(event["event_id"] == secret for event in document["events"])
    forget(harness, secret)
    # Locally: the export the server holds, which the erasure rewrote. By upload: the copy taken before the erasure.
    with harness.database.transaction(harness.principal) as conn:
        current = conn.execute("SELECT manifest_hash,document FROM memory_archives WHERE tenant_id=%s AND id=%s",
                               (harness.principal.tenant_id, exported["archive_id"])).fetchone()
    assert current["manifest_hash"] != saved["manifest_hash"]
    assert secret in current["document"]["excluded_deleted_event_ids"]
    stored = [{"archive_id": exported["archive_id"], "manifest_sha256": current["manifest_hash"]},
              harness.memory.upload_archive(document)]
    for item in stored:
        harness.memory.brain_id = harness.memory.create_brain("Restored")["id"]
        result = harness.memory.restore(
            item["archive_id"], expected_manifest_sha256=item["manifest_sha256"], mode="new_brain",
            expected_scope_generation=harness.memory.dashboard()["brain"]["scope_generation"])
        assert result["outcome"] == "completed", result
        counts = result["result"]
        assert counts["excluded_deleted_count"] >= 1 and counts["quarantined_event_count"] == 0
        timeline = harness.memory.timeline(roles=("user", "assistant"), conversation_id="chat")["items"]
        assert [item["text"] for item in timeline] == [CONTROL]
    assert not [table for table, values in rows(harness).items() for value in values if "7741" in value]
