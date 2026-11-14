"""Reconcile host-owned files with confirmed server erasures, without replaying queued messages.

The lock order is replay, session, journal writer (the same as erase_user). No plaintext or content digest is sent
to the read endpoint. A missing source is not an erasure: old content-derived source keys whose server copy was
redacted cannot be resolved without an event receipt, and must retain the ordinary recording-fence replay path.
"""
import json
import re
import time
from pathlib import Path

from . import host_outcomes, host_queue, host_recording, host_turns
from .helpers import digest
from .local_profile import profile_lock


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _identity(record):
    return (record.get("producer_ref", "sdk"), record.get("source_event_key"))


def _path(directory, owner, target):
    return Path(directory) / "plugin" / "erasures" / (digest([owner, target]) + ".json")


def _belongs(record, owner, target):
    capture = record.get("_recording")
    return (record.get("_user") == owner and isinstance(capture, dict) and capture.get("target") == target)


def blocked(directory, record):
    """Called under the journal write or session lock. Only explicit, target-bound erasures exclude a write."""
    if not isinstance(record, dict):
        return False
    capture = record.get("_recording")
    if not isinstance(capture, dict) or not capture.get("target"):
        return False
    state = _read(_path(directory, record.get("_user"), capture["target"]))
    return list(_identity(record)) in state.get("sources", [])


def _lines(path):
    if not path.exists():
        return []
    return path.read_bytes().splitlines(keepends=True)


def _record(line):
    try:
        value = json.loads(line)
        return value if isinstance(value, dict) else None
    except (ValueError, UnicodeError):
        return None


def reconcile(directory, client, owner=None, *, revision=None):
    """A successful contact clears confirmed erased copies. Offline/older services never imply deletion."""
    reader = getattr(client, "recording_erasures", None)
    if not callable(reader):
        return False
    from . import host

    target = host_recording._target(client)
    marker = _path(directory, owner, target)
    root = host.state_directory(directory)
    with profile_lock(root / "spool-lock", timeout=5):
        saved = _read(marker)
        if revision is not None and saved.get("revision") == revision:
            return True
        # Snapshot and rewrite while holding both writers out. A concurrent append either precedes the snapshot
        # or sees the erasure markers in blocked(); unrelated admissions are never replaced by an old snapshot.
        with (profile_lock(root / "session-state-lock", timeout=5),
              profile_lock(root / "spool-write-lock", timeout=5)):
            sessions = [(path, _read(path)) for path in (root / "sessions").glob("*.json")]
            spool = root / "spool.jsonl"
            rejected = root / "spool-rejected.jsonl"
            queued = list(host_queue.unacknowledged(spool)) if spool.exists() else []
            refused = _lines(rejected)
            references, locations = [], []
            event_ids = {}

            def add(identity, event_id=None):
                producer, source = identity
                if (not isinstance(producer, str) or not 1 <= len(producer) <= 256
                        or not isinstance(source, str) or not 1 <= len(source) <= 256):
                    return  # A malformed refused record must not prevent other sources' cleanup.
                if not isinstance(event_id, str) or not 1 <= len(event_id) <= 256:
                    event_id = None
                if re.search(r"[0-9a-f]{32}", source) and not event_id:
                    return  # Erasure has removed that digest from the server; absence cannot identify a deletion.
                references.append({"producer_ref": producer, "source_event_key": "event-reference" if event_id else source,
                                   **({"event_id": event_id} if event_id else {})})
                locations.append(identity)

            for _, state in sessions:
                for entry in host_turns.entries(state).values():
                    if entry.get("owner") != owner or host_outcomes.bound(entry) != target:
                        continue
                    identity = (entry.get("producer"), entry.get("source"))
                    messages = entry.get("outcome", {}).get("messages", [])
                    event = next((item.get("event_id") for item in messages if item.get("role") == "user"), None)
                    event_ids[identity] = event
                    add(identity, event)
                    for item in messages:
                        if item.get("role") == "assistant" and item.get("event_id") and identity[1]:
                            assistant = (identity[0], identity[1].rsplit(":", 1)[0] + ":assistant")
                            event_ids[assistant] = item["event_id"]
                            add(assistant, item["event_id"])
            for line in [*queued, *refused]:
                record = _record(line)
                if record is not None and _belongs(record, owner, target):
                    identity = _identity(record)
                    add(identity, event_ids.get(identity))

            erased = {tuple(value) for value in saved.get("sources", [])}
            has_erasures = False
            observed_revision = None
            for start in range(0, max(1, len(references)), 128):
                batch = references[start:start + 128]
                response = reader(batch)
                indices = response.get("erased")
                current = response.get("revision")
                if (not isinstance(indices, list) or any(type(i) is not int or not 0 <= i < len(batch) for i in indices)
                        or type(current) is not int or current < 0 or type(response.get("has_erasures")) is not bool):
                    raise ValueError("Invalid erasure confirmation.")
                if observed_revision is not None and current != observed_revision:
                    raise ValueError("Erasure state changed during reconciliation; retry on the next contact.")
                observed_revision = current
                has_erasures |= response["has_erasures"]
                erased.update(locations[start + index] for index in indices)

            if not has_erasures and not erased:
                marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                host._write_state(marker, {"sources": [], "revision": observed_revision})
                return True

            # Never retain content-derived identities as deletion markers. Their local copies can still be
            # removed in this pass when an event receipt identifies them, but cannot become a permanent digest.
            durable = sorted(item for item in erased if not re.search(r"[0-9a-f]{32}", item[1]))
            marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Install the guards before rewriting, but advance the checkpoint only after every rewrite succeeds.
            host._write_state(marker, {"sources": durable})

            def keep(line):
                record = _record(line)
                return not (record is not None and _belongs(record, owner, target) and _identity(record) in erased)

            if spool.exists():
                # Even an acknowledged prefix can contain a deleted message and its checksum.
                host_queue.replace_queue(spool, b"".join(line for line in queued if keep(line)))
            if rejected.exists():
                host_queue._write(rejected, b"".join(line for line in refused if keep(line)))
            for path, state in sessions:
                changed = False
                for key, entry in list(host_turns.entries(state).items()):
                    if entry.get("owner") != owner or host_outcomes.bound(entry) != target:
                        continue
                    identity = (entry.get("producer"), entry.get("source"))
                    legacy_finished = (has_erasures and entry.get("done") and not entry.get("record")
                                       and isinstance(identity[1], str) and re.search(r"[0-9a-f]{32}", identity[1])
                                       and not event_ids.get(identity))
                    if identity in erased or legacy_finished:
                        bound = host_outcomes.bound(entry)
                        if identity not in durable:
                            del state["turns"][key]
                        else:
                            entry.clear()
                            entry.update(owner=owner, producer=identity[0], source=identity[1], done=True,
                                         bound=bound, exclusion={"reason": "erased", "scope": "brain"})
                        state["turns_require_staging"] = True
                        if state.get("last_prompt_key") == key:
                            for name in ("last_prompt", "last_prompt_key", "last_prompt_recording"):
                                state.pop(name, None)
                        changed = True
                    elif identity[1] and (identity[0], identity[1].rsplit(":", 1)[0] + ":assistant") in erased:
                        for item in entry.get("outcome", {}).get("messages", []):
                            if item.get("role") == "assistant":
                                item.clear()
                                item.update(role="assistant", state="excluded", reason="erased", scope="brain",
                                            at=round(time.time(), 3), by="recovery")
                                changed = True
                # Context fingerprints can depend on any erased note, persona or message. They carry no
                # per-source provenance, so discard that disposable cache for this owner after an erasure.
                if has_erasures and state.get("user_id") == owner:
                    context = state.get("memory_context")
                    if isinstance(context, dict) and context.get("brain_id") == client.brain_id:
                        # Keep content-free version/visibility/options metadata: it tells the host to announce
                        # a removed persona or mood, and preserves the user's context-sharing settings.
                        if "fingerprint" in context:
                            context.pop("fingerprint")
                            changed = True
                callbacks = state.get("callbacks", [])
                kept = [item for item in callbacks if not (
                    item.get("owner") == owner and item.get("target") == target
                    and (item.get("producer"), item.get("source")) in erased)]
                if kept != callbacks:
                    state["callbacks"] = kept
                    changed = True
                if changed:
                    host._write_session_marker(path, state)
            if has_erasures and host_recording.local_target(directory, owner) == target:
                _redact_legacy(directory, client.brain_id)
            host._write_state(marker, {"sources": durable, "revision": observed_revision})
    return True


def _redact_legacy(directory, brain_id):
    """Retired desktop session digests are disposable evidence, never live queues or input to recall."""
    from . import host
    from .legacy_erasure import REDACTED_DIGEST
    from .local_profile import load_profile

    profile = load_profile(directory)

    def redact(document):
        identity = document.get("identity", {})
        if (identity.get("brain_id") == brain_id and identity.get("tenant_id") == profile.tenant_id
                and identity.get("principal_id") == profile.principal_id and "input_fingerprint" in document):
            return {**document, "input_fingerprint": REDACTED_DIGEST}
        return document

    with profile_lock(Path(directory), timeout=5):
        for path in (Path(directory) / "sessions").glob("*/pending.json"):
            original = _read(path)
            cleaned = redact(original)
            if cleaned != original:
                host._write_state(path, cleaned)
        evidence = Path(directory) / "recovery-sessions.jsonl"
        if evidence.exists():
            original = _lines(evidence)
            documents = [json.loads(line) for line in original if line.strip()]
            cleaned = [redact(document) for document in documents]
            if cleaned != documents:
                host_queue._write(evidence, "".join(json.dumps(document) + "\n" for document in cleaned).encode())
