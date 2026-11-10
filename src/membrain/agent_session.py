from __future__ import annotations

import json
import os
import re
import secrets
import threading
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from pathlib import Path

import httpx

from . import desktop_connection
from .delivery_receipts import confirmed_delivery_receipt
from .helpers import digest
from .local_profile import (
    LocalProfileBusy,
    LocalProfileError,
    _open_private,
    _private,
    load_profile,
    profile_lock,
)
from .recording_policy import requests_pause
from .runtime import (
    MEMORY_CONSUMPTION_VERSION,
    BrainRuntime,
    RuntimeBlocked,
    RuntimePolicy,
    TemporaryCause,
    TurnResult,
    _scope_conflict,
)
from .turns import FAILURE_CODES, STAGES

_MAX_PENDING_BYTES = 8192
_SESSION_TOKEN = object()
_ACTIVE_SCOPES: set[str] = set()
_ACTIVE_GUARD = threading.Lock()
_ERROR_CODES = {
    "acknowledgement_required", "delivery_already_recorded", "invalid_turn_id", "message_identity_conflict",
    "commit_recovery_required",
    "configuration_changed", "invalid_configuration", "invalid_message", "invalid_runtime_result",
    "invalid_scope", "no_pending_turn", "pending_turn", "pending_turn_recording_excluded",
    "profile_identity_changed",
    "profile_unavailable", "session_busy", "session_closed", "session_state_invalid",
    "session_state_unavailable",
}


def _reset_after_fork():
    global _ACTIVE_SCOPES, _ACTIVE_GUARD
    _ACTIVE_SCOPES, _ACTIVE_GUARD = set(), threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_after_fork)


class SessionError(RuntimeError):
    def __init__(self, code: str, turn_id: str | None = None):
        if (not isinstance(code, str) or code not in _ERROR_CODES or (turn_id is not None and (
                not isinstance(turn_id, str) or not re.fullmatch(r"turn-[0-9a-f]{40}", turn_id)))):
            raise ValueError("Invalid session error metadata")
        self.code, self.turn_id = code, turn_id
        super().__init__(code + (f": turn {turn_id}" if turn_id else ""))


def _identifier(value):
    return (isinstance(value, str) and 1 <= len(value) <= 256 and not any(
        character.isspace() or unicodedata.category(character).startswith("C")
        for character in value
    ))


def _identity(profile, conversation_id, branch_id):
    return {name: getattr(profile, name) for name in (
        "installation_id", "brain_id", "tenant_id", "principal_id",
    )} | {"conversation_id": conversation_id, "branch_id": branch_id}


def _turn_id(identity, message_id):
    return "turn-" + digest([
        identity["brain_id"], identity["conversation_id"], identity["branch_id"], message_id,
    ])[:40]


def _unique_pairs(pairs):
    document = {}
    for key, value in pairs:
        if key in document:
            raise ValueError
        document[key] = value
    return document


def _read_pending(path, identity):
    try:
        descriptor = _open_private(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(_MAX_PENDING_BYTES + 1)
        if len(raw) > _MAX_PENDING_BYTES:
            raise ValueError
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
        if not isinstance(value, dict) or set(value) != {
            "version", "identity", "message_id", "input_fingerprint", "turn_id",
            "generator_fingerprint", "runtime_fingerprint",
        }:
            raise ValueError
        if type(value["version"]) is not int or value["version"] != 1:
            raise ValueError
        if value["identity"] != identity or not _identifier(value["message_id"]):
            raise ValueError
        if any(not isinstance(value[name], str) or not re.fullmatch(r"[0-9a-f]{64}", value[name])
               for name in ("input_fingerprint", "generator_fingerprint", "runtime_fingerprint")):
            raise ValueError
        if value["turn_id"] != _turn_id(identity, value["message_id"]):
            raise ValueError
        return value
    except FileNotFoundError:
        return None
    except (ValueError, UnicodeError, RecursionError):
        raise SessionError("session_state_invalid") from None
    except (OSError, LocalProfileError):
        raise SessionError("session_state_unavailable") from None


def _sync_directory(path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _save_pending(path, document):
    temporary = path.parent / (".pending-" + secrets.token_hex(16) + ".tmp")
    try:
        data = (json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        if len(data) > _MAX_PENDING_BYTES:
            raise SessionError("session_state_invalid")
        if path.exists() or path.is_symlink():
            _private(path)
        descriptor = _open_private(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    except (OSError, LocalProfileError):
        raise SessionError("session_state_unavailable") from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _read_choice(path, identity):
    """This conversation branch's stored recording choice: ``on`` only when no file exists, ``paused`` for a valid
    off-record choice bound to this exact identity, and ``unknown`` for anything else."""
    try:
        descriptor = _open_private(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(_MAX_PENDING_BYTES + 1)
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except FileNotFoundError:
        return "on"
    except (ValueError, UnicodeError, RecursionError, OSError, LocalProfileError):
        return "unknown"
    return "paused" if value == {"version": 1, "identity": identity, "recording": "off"} else "unknown"


class AgentSession:
    """A locked synchronous conversation created by ``open_agent``.

    The session binds this machine's recording controls to its turns: installation-scoped device capture and this
    conversation branch's own off-record choice. Either one, or a server pause, makes a new message temporary. The
    three controls stay independent; changing one never changes another.

    Local controls are read when a new message starts and when a pending turn is explicitly recovered. They are
    not a fence around a recorded turn already running: a device pause set while its model or delivery callback is
    executing does not cancel that call or remove what the turn captures. Only the server switch fences that.
    """

    def __init__(self, *, profile, identity, runtime, path, generator_fingerprint,
                 runtime_fingerprint, _token=None):
        if _token is not _SESSION_TOKEN:
            raise SessionError("invalid_configuration")
        self._profile, self._identity, self._runtime, self._path = profile, identity, runtime, path
        # Bodyless, and keyed like the pending sidecar: installation, brain, user, conversation and branch.
        self._recording_path = path.with_name("recording.json")
        # The local policy the temporary context was built under; a different one starts an empty context.
        self._local_stamp = None
        self._generator_fingerprint = generator_fingerprint
        self._runtime_fingerprint = runtime_fingerprint
        self._closed = False
        self._operation_lock = threading.Lock()

    @contextmanager
    def _operation(self):
        if not self._operation_lock.acquire(blocking=False):
            raise SessionError("session_busy")
        try:
            if self._closed:
                raise SessionError("session_closed")
            try:
                current = load_profile(self._profile.directory)
            except (OSError, LocalProfileError):
                raise SessionError("profile_unavailable") from None
            if _identity(current, self._identity["conversation_id"], self._identity["branch_id"]) != self._identity:
                raise SessionError("profile_identity_changed")
            yield
        finally:
            self._operation_lock.release()

    @property
    def pending(self) -> dict | None:
        with self._operation():
            value = _read_pending(self._path, self._identity)
            return {key: value[key] for key in ("turn_id", "message_id")} if value else None

    def _configuration(self, pending):
        if (pending["generator_fingerprint"] != self._generator_fingerprint
                or pending["runtime_fingerprint"] != self._runtime_fingerprint):
            raise SessionError("configuration_changed", pending["turn_id"])

    def _recovery_configuration(self, pending, row):
        if row is not None and row.get("stage") == "committed":
            raise SessionError("commit_recovery_required", pending["turn_id"])
        if row is None or (row.get("stage") not in ("delivered", "completed")
                           and not confirmed_delivery_receipt(row)):
            self._configuration(pending)

    def _binding(self, row, pending, *, code="session_state_invalid"):
        expected = {name: pending["identity"][name] for name in (
            "brain_id", "conversation_id", "branch_id",
        )} | {name: pending[name] for name in ("turn_id", "input_fingerprint")}
        if not isinstance(row, dict) or any(row.get(key) != value for key, value in expected.items()):
            raise SessionError(code, pending["turn_id"])

    def _existing_turn(self, pending, *, allow_missing=False, code="session_state_invalid"):
        try:
            row = self._runtime.journal.get(pending["turn_id"])
        except httpx.HTTPStatusError as error:
            if allow_missing and error.response.status_code == 404:
                return None
            raise
        self._binding(row, pending, code=code)
        return row

    def _clear(self, pending):
        if pending.get("ephemeral"):
            self._runtime.temporary.clear()
            return
        try:
            self._path.unlink()
            _sync_directory(self._path.parent)
        except OSError:
            raise SessionError("session_state_unavailable", pending["turn_id"]) from None

    def _clear_confirmed_failure(self, pending, error):
        if error.turn_id != pending["turn_id"]:
            return
        try:
            row = self._existing_turn(pending)
        except httpx.HTTPError:
            return
        if confirmed_delivery_receipt(row):
            self._clear(pending)

    def _result(self, result, pending):
        if not isinstance(result, TurnResult) or result.turn_id != pending["turn_id"]:
            raise SessionError("invalid_runtime_result", pending["turn_id"])
        if result.stage == "committed":
            raise SessionError("commit_recovery_required", pending["turn_id"])
        if result.stage == "completed":
            self._clear(pending)
        return result

    def _local_controls(self):
        from .local_recording import device_capture

        try:
            device = device_capture(self._profile.directory)
        except Exception:
            device = {"scope": "installation", "state": "unknown", "reason": "local_state_unreadable"}
        conversation = {"scope": "conversation_branch", "state": _read_choice(self._recording_path, self._identity)}
        if conversation["state"] == "unknown":
            conversation["reason"] = "local_state_unreadable"
        return device, conversation

    def _local_policy(self):
        """Every local control that keeps a new message out of memory, and the identity of that local policy.

        A control that cannot be read counts as a cause, as a precaution, under its own reason: its state is
        unknown, not confirmed off. The identity changes whenever an applicable control does, including a device
        pause that was lifted and set again between two messages.
        """
        device, conversation = self._local_controls()
        causes = []
        if device["state"] == "paused":
            causes.append(TemporaryCause("local_pause", "installation", device.get("until")))
        elif device["state"] != "on":
            causes.append(TemporaryCause("local_state_unreadable", "installation"))
        if conversation["state"] == "paused":
            causes.append(TemporaryCause("off_record", "conversation_branch"))
        elif conversation["state"] != "on":
            causes.append(TemporaryCause("local_state_unreadable", "conversation_branch"))
        return tuple(causes), (device["state"], device.get("revision"), conversation["state"])

    def _recording_state(self):
        device, conversation = self._local_controls()
        server = {"scope": "brain", "state": "unknown", "revision": None}
        try:
            status = self._runtime.recording_status()
            if type(status["paused"]) is bool and type(status["revision"]) is int:
                server = {"scope": "brain", "state": "paused" if status["paused"] else "on",
                          "revision": status["revision"]}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass  # Unreachable or invalid: the server state stays unknown instead of a guessed on or off.
        states = [server["state"], device["state"], conversation["state"]]
        effective = "paused" if "paused" in states else "unknown" if "unknown" in states else "on"
        # A turn of either kind starts with the service: without its answer nothing can be reserved or generated.
        handling = "unavailable" if server["state"] == "unknown" else "record" if effective == "on" else "temporary"
        return {"recording": effective, "new_message": handling,
                "controls": {"server": server, "device": device, "conversation": conversation}}

    def recording_state(self) -> dict:
        """The three controls that decide whether a new message here is recorded, each read separately.

        ``recording`` is ``paused`` when a control is known to exclude new messages, ``unknown`` when none is but
        one could not be confirmed, and otherwise ``on``. ``new_message`` says what sending one would do now:
        ``record`` it; handle it as ``temporary``, which always needs the service to confirm a temporary
        reservation and otherwise stops before generation; or ``unavailable`` when the service did not answer, so
        that no turn, recorded or temporary, can start. An unreadable local control leads to ``temporary`` as a
        precaution; it is not confirmation that recording is off. These are snapshots, not a transaction across
        stores, and say nothing about an earlier message, a turn already in progress or its delivery.
        """
        with self._operation():
            return self._recording_state()

    def _store_choice(self, off_record):
        if _read_choice(self._recording_path, self._identity) == ("paused" if off_record else "on"):
            return
        if off_record:
            _save_pending(self._recording_path, {"version": 1, "identity": self._identity, "recording": "off"})
        else:
            try:
                self._recording_path.unlink(missing_ok=True)
                _sync_directory(self._recording_path.parent)
            except OSError:
                raise SessionError("session_state_unavailable") from None
        # Temporary context ends with the choice that created it; it is never carried into a later one.
        self._runtime.temporary.clear()

    def set_off_record(self, off_record: bool) -> dict:
        """Keep new messages of this conversation branch off the record, or record them again.

        Only a bodyless choice is stored, for this installation, brain, user, conversation and branch. It changes
        no other control: not the brain's server recording switch, device capture or another conversation. It
        decides how the next new message is handled. A recorded turn that is still pending is neither converted
        nor resumed by it, and nothing already sent to a model or a recipient is recalled. Returns
        ``recording_state()``.
        """
        if type(off_record) is not bool:
            raise SessionError("invalid_configuration")
        with self._operation():
            self._store_choice(off_record)
            return self._recording_state()

    def _require_recording(self, pending, row, causes):
        """A recorded turn in progress never becomes temporary, and is not continued while a local control
        excludes recording or cannot be read. Bookkeeping for a reply already delivered captures nothing new."""
        if causes and (row is None or (row.get("stage") not in ("delivered", "committed", "completed")
                                       and not confirmed_delivery_receipt(row))):
            raise SessionError("pending_turn_recording_excluded", pending["turn_id"])

    def respond(self, text: str, *, message_id: str) -> TurnResult:
        if not isinstance(text, str) or not text.strip() or not _identifier(message_id):
            raise SessionError("invalid_message")
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise SessionError("invalid_message") from None
        with self._operation():
            pending = _read_pending(self._path, self._identity)
            fingerprint = digest({"message_id": message_id, "text": text})
            if pending and (pending["message_id"] != message_id or pending["input_fingerprint"] != fingerprint):
                row = self._existing_turn(pending, allow_missing=True)
                if row is None or row.get("stage") != "failed" or row.get("failure_code") != "cancelled":
                    raise SessionError("pending_turn", pending["turn_id"])
                # The turn was explicitly cancelled, so no answer exists or can be delivered for it; a new
                # message may start instead of every later message failing on the closed turn.
                self._clear(pending)
                pending = None
            if requests_pause(text):
                # A direct opening control ("Off the record: ...") takes effect before anything can be captured,
                # and stays in effect for this conversation branch until it is explicitly recorded again.
                self._store_choice(True)
            local, stamp = self._local_policy()
            if stamp != self._local_stamp:
                # Temporary context ends with the local policy it was built under. A timed pause that expired is
                # such a change by this machine's own clock. An unreachable service is not: it stops the turn
                # below without touching the context, and its own revision decides once it answers.
                self._runtime.temporary.clear()
                self._local_stamp = stamp
            if pending is None:
                status = self._runtime.recording_status()
                causes = ((TemporaryCause("server_paused", "brain"),) if status["paused"] else ()) + local
                if causes:
                    return self._runtime.respond_temporary(
                        text, message_id=message_id, conversation_id=self._identity["conversation_id"],
                        branch_id=self._identity["branch_id"], revision=status["revision"], causes=causes,
                    )
                self._runtime.temporary.clear()
            new_pending = pending is None
            if pending:
                row = self._existing_turn(pending, allow_missing=True)
                self._require_recording(pending, row, local)
                self._recovery_configuration(pending, row)
            else:
                pending = {
                    "version": 1, "identity": self._identity, "message_id": message_id,
                    "input_fingerprint": fingerprint, "turn_id": _turn_id(self._identity, message_id),
                    "generator_fingerprint": self._generator_fingerprint,
                    "runtime_fingerprint": self._runtime_fingerprint,
                }
                self._existing_turn(pending, allow_missing=True, code="message_identity_conflict")
                _save_pending(self._path, pending)
            try:
                result = self._runtime.respond(
                    text, message_id=message_id, conversation_id=self._identity["conversation_id"],
                    branch_id=self._identity["branch_id"], allow_temporary=False,
                )
            except RuntimeBlocked as error:
                if (new_pending and error.code in ("scope_conflict", "recording_paused") and error.turn_id == pending["turn_id"]
                        and self._existing_turn(pending, allow_missing=True) is None):
                    self._clear(pending)
                elif error.code != "scope_conflict":
                    self._clear_confirmed_failure(pending, error)
                raise
            return self._result(result, pending)

    def resume(self) -> TurnResult:
        with self._operation():
            pending = _read_pending(self._path, self._identity)
            if pending is None:
                raise SessionError("no_pending_turn")
            try:
                row = self._existing_turn(pending)
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    self._configuration(pending)
                raise
            self._require_recording(pending, row, self._local_policy()[0])
            self._recovery_configuration(pending, row)
            try:
                result = self._runtime.resume(pending["turn_id"])
            except RuntimeBlocked as error:
                self._clear_confirmed_failure(pending, error)
                raise
            return self._result(result, pending)

    def cancel(self, *, turn_id: str, acknowledge_uncertain: bool = False) -> dict:
        """Close a pending turn without undoing captured memory or external effects."""
        if not isinstance(turn_id, str) or not re.fullmatch(r"turn-[0-9a-f]{40}", turn_id):
            raise SessionError("invalid_turn_id")
        if type(acknowledge_uncertain) is not bool:
            raise SessionError("invalid_configuration")
        with self._operation():
            pending = _read_pending(self._path, self._identity)
            if pending is None:
                try:
                    row = self._runtime.journal.get(turn_id)
                except httpx.HTTPStatusError as error:
                    if error.response.status_code == 404:
                        raise SessionError("no_pending_turn") from None
                    raise
                if not row.get("ephemeral") or any(row.get(key) != self._identity[key] for key in (
                        "brain_id", "conversation_id", "branch_id")):
                    raise SessionError("no_pending_turn")
                pending = {"identity": self._identity, "turn_id": turn_id,
                           "input_fingerprint": "0" * 64, "ephemeral": True}
            if pending["turn_id"] != turn_id:
                raise SessionError("pending_turn", pending["turn_id"])
            row = self._existing_turn(pending, allow_missing=True)
            if row is None:
                try:
                    row = self._runtime.journal.begin(
                        turn_id=turn_id, conversation_id=self._identity["conversation_id"],
                        branch_id=self._identity["branch_id"], input_fingerprint=pending["input_fingerprint"],
                    )
                except httpx.HTTPStatusError as error:
                    if _scope_conflict(error) and self._existing_turn(pending, allow_missing=True) is None:
                        self._clear(pending)
                        return {"turn_id": turn_id, "stage": "not_started", "failure_code": "scope_conflict"}
                    raise
                self._binding(row, pending)
            if row.get("stage") in ("delivered", "committed"):
                raise SessionError("delivery_already_recorded", turn_id)
            if row.get("stage") not in (*STAGES, "failed"):
                raise SessionError("invalid_runtime_result", turn_id)
            if row["stage"] not in ("completed", "failed"):
                failure_code = {"generating": "generation_uncertain", "delivering": "delivery_uncertain"}.get(
                    row["stage"], "cancelled",
                )
                if row.get("ephemeral") and row["stage"] == "generated" and row.get("response_review_calls"):
                    failure_code = "generation_uncertain"
                if failure_code != "cancelled" and not acknowledge_uncertain:
                    raise SessionError("acknowledgement_required", turn_id)
                row = self._runtime.journal.claim(
                    turn_id, worker_id=self._runtime.worker_id,
                    lease_seconds=RuntimePolicy().lease_seconds, expected_revision=row["revision"],
                )
                self._binding(row, pending)
                row = self._runtime.journal.fail(
                    turn_id, lease_token=row["lease_token"], expected_revision=row["revision"],
                    failure_code=failure_code,
                )
                self._binding(row, pending)
            if (row.get("stage") not in ("completed", "failed") or (
                    row["stage"] == "failed" and (not isinstance(row.get("failure_code"), str)
                                                  or row["failure_code"] not in FAILURE_CODES))):
                raise SessionError("invalid_runtime_result", turn_id)
            result = {"turn_id": turn_id, "stage": row["stage"],
                      "failure_code": row["failure_code"] if row["stage"] == "failed" else None}
            self._clear(pending)
            return result


@contextmanager
def open_agent(
    directory: Path | None = None, *, conversation_id: str, branch_id: str = "main",
    deliver=None, instructions: str = "", policy: RuntimePolicy | None = None,
    start_service: bool = True, generate=None, generator_fingerprint: str | None = None,
):
    """Hold a local conversation lock and own its memory connection and default generator."""
    if not _identifier(conversation_id) or not _identifier(branch_id):
        raise SessionError("invalid_scope")
    if (not isinstance(instructions, str) or (policy is not None and not isinstance(policy, RuntimePolicy))
            or (deliver is not None and not callable(deliver)) or type(start_service) is not bool
            or (generate is not None and (not callable(generate) or not _identifier(generator_fingerprint)))
            or (generate is None and generator_fingerprint is not None)):
        raise SessionError("invalid_configuration")
    try:
        instructions.encode("utf-8")
    except UnicodeError:
        raise SessionError("invalid_configuration") from None
    policy = policy or RuntimePolicy()
    runtime_fingerprint = digest({
        "version": "agent-session-v1", "memory_protocol": MEMORY_CONSUMPTION_VERSION,
        "instructions": instructions, "policy": asdict(policy),
    })
    try:
        profile = load_profile(directory)
        from .recovery_profile import check_start_allowed

        check_start_allowed(profile)
        identity = _identity(profile, conversation_id, branch_id)
        root = profile.directory / "sessions"
        root.mkdir(mode=0o700, exist_ok=True)
        _private(root, directory=True)
    except (OSError, LocalProfileError):
        raise SessionError("profile_unavailable") from None
    session_directory = root / digest(identity)
    key = str(session_directory)
    with _ACTIVE_GUARD:
        if key in _ACTIVE_SCOPES:
            raise SessionError("session_busy")
        _ACTIVE_SCOPES.add(key)
    try:
        with ExitStack() as stack:
            try:
                stack.enter_context(profile_lock(session_directory, timeout=0))
            except LocalProfileBusy:
                raise SessionError("session_busy") from None
            except (OSError, LocalProfileError):
                raise SessionError("session_state_unavailable") from None
            pending_path = session_directory / "pending.json"
            _read_pending(pending_path, identity)
            if generate is None:
                from .chat_config import load_chat_configuration

                configuration = load_chat_configuration(profile.directory)
                generator_fingerprint = configuration.fingerprint
                generate = configuration.generator()
                stack.callback(generate.close)
            generator_fingerprint = digest(generator_fingerprint)
            client = stack.enter_context(desktop_connection.open_client(
                profile.directory, start_service=start_service,
            ))
            try:
                current = load_profile(profile.directory)
            except (OSError, LocalProfileError):
                raise SessionError("profile_unavailable") from None
            if _identity(current, conversation_id, branch_id) != identity or client.brain_id != profile.brain_id:
                raise SessionError("profile_identity_changed")
            session = AgentSession(
                profile=profile, identity=identity,
                runtime=BrainRuntime(client, generate, deliver=deliver, instructions=instructions, policy=policy),
                path=pending_path, generator_fingerprint=generator_fingerprint,
                runtime_fingerprint=runtime_fingerprint, _token=_SESSION_TOKEN,
            )
            try:
                yield session
            finally:
                with session._operation_lock:
                    session._closed = True
                    session._runtime.temporary.clear()
    finally:
        with _ACTIVE_GUARD:
            _ACTIVE_SCOPES.discard(key)
