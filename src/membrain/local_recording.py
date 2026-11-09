import hashlib
import json
import math

from .helpers import DomainError
from .local_profile import profile_lock


def local_status(directory):
    from . import host

    with profile_lock(host.state_directory(directory) / "session-state-lock", timeout=5):
        try:
            content = host._pause_file(directory).read_bytes()
        except FileNotFoundError:
            content = None
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
        return {"paused": paused, "revision": hashlib.sha256(content).hexdigest()}


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
