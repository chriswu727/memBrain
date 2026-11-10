import hashlib
import json
import math

from .helpers import DomainError
from .local_profile import profile_lock


def _pause_scope(value):
    """Whose capture a readable pause covers. A pause a host conversation asked for lists the host conversations
    that were active on this installation when it was set, whichever adapter they belong to. It does not cover a
    host conversation outside that list and ends once the listed ones are over (``host.end_conversation_pause``);
    it is not a pause of the whole device. Any other pause, timed or until resumed, covers the installation."""
    return "conversations" if isinstance(value.get("conversations"), list) else "installation"


def local_status(directory):
    from . import host

    with profile_lock(host.state_directory(directory) / "session-state-lock", timeout=5):
        try:
            content = host._pause_file(directory).read_bytes()
        except FileNotFoundError:
            content = None
        value = None
        if content is not None:
            try:
                value = json.loads(content)
                until = value.get("until")
                if not isinstance(value, dict) or (until is not None and (
                        type(until) not in (int, float) or not math.isfinite(until))):
                    raise ValueError("Invalid device capture state.")
            except (ValueError, AttributeError, OverflowError):
                raise DomainError("dependency_unavailable", "Device capture state is unreadable. Run membrain doctor.") from None
        paused = host.paused(directory)
        if not host._pause_file(directory).exists():
            content = b""
        # ``paused`` keeps its meaning: some local capture is blocked. ``scope`` says how much.
        return {"paused": paused, "revision": hashlib.sha256(content).hexdigest(),
                **({"scope": _pause_scope(value)} if paused and isinstance(value, dict) else {})}


def device_capture(directory):
    """Installation-scoped device capture as one read-only snapshot, for direct chat sessions.

    It creates nothing, takes no lock and leaves an expired pause in place: pause files are replaced atomically and
    expiry cleanup belongs to the host paths that hold the state lock. Only a pause of the whole installation, timed
    or until resumed, pauses a direct conversation. A pause a host conversation asked for covers the host
    conversations it lists: a direct conversation is not one of them, so it stays ``on`` here, reports that pause
    separately and never ends it. ``revision`` identifies one exact pause, so a pause that was lifted and set again
    is a different policy even with the same duration. Unreadable metadata is ``unknown``: the host blocks capture
    on it, and a caller must not report it as recording on or off.
    """
    from . import host

    state, value = host._pause_state(host._pause_file(directory, create=False))
    if state == "paused" and _pause_scope(value) == "conversations":
        return {"scope": "installation", "state": "on", "host_conversations": "paused"}
    if state == "paused":
        # Hashing the parsed pause (its nonce, start and expiry) needs no second read of the file.
        identity = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        return {"scope": "installation", "state": "paused", "until": value.get("until"), "revision": identity}
    if state == "unreadable":
        return {"scope": "installation", "state": "unknown", "reason": "local_state_unreadable"}
    return {"scope": "installation", "state": "on"}


def status(directory, service, principal, brain_id):
    from .recording_control import recording_status

    server = recording_status(service, principal, brain_id)
    local = local_status(directory)
    return {"recording": "paused" if server["paused"] or local["paused"] else "on",
            "brain_id": brain_id, "local": local, "server": server}


def change(directory, *, paused, hours=None, expected_revision=None):
    from . import host

    if type(paused) is not bool or (hours is not None and (type(hours) not in (int, float) or not paused)):
        raise DomainError("validation_failed", "Use a boolean pause and an optional numeric pause duration.")
    if expected_revision is not None and (not isinstance(expected_revision, str)
                                         or len(expected_revision) != 64):
        raise DomainError("validation_failed", "Use the local recording revision from the displayed state.")
    with profile_lock(host.state_directory(directory) / "session-state-lock", timeout=5):
        current = local_status(directory)
        if expected_revision is not None and expected_revision != current["revision"]:
            raise DomainError("version_conflict", "Device capture changed. Refresh before changing it again.")
        if paused:
            try:
                host.pause(directory, hours)
            except ValueError as error:
                raise DomainError("validation_failed", str(error)) from None
        else:
            host.resume(directory)
