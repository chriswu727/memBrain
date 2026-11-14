from __future__ import annotations

import getpass
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx

from .desktop_chat_monitor import _notice
from .runtime import DeliveryReceipt, RuntimeBlocked, RuntimePolicy


def add_commands(actions):
    configure = actions.add_parser("configure-chat", help="Configure the model that answers messages")
    configure.add_argument("--directory", type=Path)
    configure.add_argument("--base-url", help="Chat Completions-compatible provider URL")
    configure.add_argument("--model")
    configure.add_argument("--api-key-env", help="Environment variable name containing the provider key")
    configure.add_argument("--thinking", choices=("enabled", "disabled"))
    configure.add_argument("--use-cognition", action="store_true", help="Explicitly copy the memory learning provider")
    configure.add_argument("--max-output-tokens", type=int, default=4096)
    configure.add_argument("--timeout-seconds", type=float, default=180)
    configure.add_argument("--max-response-bytes", type=int, default=1048576)
    configure.add_argument("--non-interactive", action="store_true")

    chat = actions.add_parser("chat", help="Chat using the local persistent brain")
    chat.add_argument("--directory", type=Path)
    chat.add_argument("--conversation", default="desktop-chat")
    chat.add_argument("--branch", default="main")
    chat.add_argument("--instructions-file", type=Path)
    chat.add_argument("--orientation", choices=("always", "on_demand"), default="always")
    mode = chat.add_mutually_exclusive_group()
    mode.add_argument("--message", help="Send one message; requires a stable --message-id")
    mode.add_argument("--resume", action="store_true", help="Resume the pending turn once without resending input")
    mode.add_argument("--cancel", metavar="TURN_ID", help="Close the specified pending turn without retrying it")
    mode.add_argument("--off-record", action="store_true",
                      help="Keep new messages of this conversation branch off the record; sends no message")
    mode.add_argument("--on-record", action="store_true",
                      help="Record new messages of this conversation branch again; other controls are unchanged")
    mode.add_argument("--recording-status", action="store_true",
                      help="Show the server, device and conversation recording controls without changing them")
    chat.add_argument("--acknowledge-uncertain", action="store_true", help="Acknowledge unknown model or delivery outcomes when cancelling")
    chat.add_argument("--message-id", help="Keep this identity unchanged when retrying the same message")


def configure(args):
    from .chat_config import (
        ChatConfiguration,
        save_chat_configuration,
        use_cognition_configuration,
    )
    from .local_profile import ensure_profile

    explicit = (args.base_url, args.model, args.api_key_env, args.thinking)
    if args.use_cognition and any(explicit):
        raise ValueError("--use-cognition cannot be combined with explicit provider settings.")
    if args.use_cognition:
        configuration = use_cognition_configuration(args.directory)
        configuration = replace(configuration, max_output_tokens=args.max_output_tokens,
                                timeout_seconds=args.timeout_seconds,
                                max_response_bytes=args.max_response_bytes)
    else:
        base_url, model, key_variable = explicit[:3]
        if any(explicit):
            if not all(explicit[:3]):
                raise ValueError("Provide --base-url, --model and --api-key-env together.")
            api_key = os.environ.get(key_variable)
            if not api_key:
                raise ValueError("The selected provider key environment variable is empty.")
        elif sys.stdin.isatty() and not args.non_interactive:
            print("Configure the model that answers messages. Memory learning settings stay separate.", file=sys.stderr)
            print("Provider base URL: ", end="", file=sys.stderr, flush=True)
            base_url = input().strip()
            print("Model name: ", end="", file=sys.stderr, flush=True)
            model = input().strip()
            api_key = getpass.getpass("Provider API key (hidden): ")
        else:
            raise ValueError("Provide provider settings or --use-cognition, or run interactively.")
        configuration = ChatConfiguration(
            base_url=base_url, model=model, api_key=api_key, thinking=args.thinking,
            max_output_tokens=args.max_output_tokens, timeout_seconds=args.timeout_seconds,
            max_response_bytes=args.max_response_bytes,
        )
    profile = ensure_profile(args.directory)
    save_chat_configuration(configuration, profile.directory)
    return {"chat": "configured", "cognition": "configured" if profile.cognition else "not_configured",
            "service_restart_required": False}


def _deliver(request):
    text = request.text + "\n"
    try:
        if sys.stdout.write(text) != len(text):
            raise OSError
        sys.stdout.flush()
    except (OSError, UnicodeError):
        raise RuntimeBlocked("delivery_uncertain", request.turn_id) from None
    return DeliveryReceipt("delivered")


def _recovery_notice(error, agent, args):
    try:
        pending = agent.pending
        if pending is not None:
            turn_id = pending.get("turn_id") if isinstance(pending, dict) else None
            if not isinstance(turn_id, str) or not re.fullmatch(r"turn-[0-9a-f]{40}", turn_id):
                raise ValueError
            _notice(f"Local pending turn: {turn_id}. Keep this ID for explicit recovery. "
                    "Use desktop turn-status with the same conversation and branch to inspect remote state.")
    except Exception:
        _notice("Local pending state could not be inspected; it was not changed.")
    if getattr(error, "code", None) == "scope_conflict":
        from .desktop_turns import inspect_scope

        try:
            row = inspect_scope(args.directory, args.conversation, args.branch)["turn"]
            if row is None:
                _notice("No unfinished turn was found; the scope may have changed since rejection. No input was retried.")
            else:
                _notice(f"Unfinished turn in this scope: {row['turn_id']} ({row['stage']}). "
                        "Resolve it through the host that owns it; this command did not resume or cancel it.")
        except Exception:
            _notice("Scope inspection unavailable; use desktop turn-status with the same conversation and branch. "
                    "The conflicting turn is unknown.")


_TEMPORARY_CAUSES = {
    ("server_paused", "brain"): "memory recording is paused for this brain",
    ("local_pause", "installation"): "chat capture is paused on this device",
    ("off_record", "conversation_branch"): "this conversation branch is off the record (/on-record records new messages again)",
    ("caller_opt_out", "turn"): "this turn was sent as not recorded",
    ("local_state_unreadable", "installation"):
        "the device capture control could not be read, so its state is unknown (a precaution, not confirmation that capture is off)",
    ("local_state_unreadable", "conversation_branch"):
        "this conversation's recording choice could not be read, so its state is unknown (a precaution, not confirmation that it is off the record)",
}
_BLOCKED_ADVICE = {
    "off_record_reservation_rejected": (
        "The memory service did not accept an off-record reservation; a service older than this client does not "
        "support it. Upgrade and restart the service. Nothing was generated, sent or saved, and the message was "
        "not recorded instead."),
    "pending_turn_recording_excluded": (
        "A recorded turn is still pending while local recording is off or unconfirmed here. It was not converted "
        "to a temporary turn or resumed. Cancel it with its turn ID, or turn recording back on and then resume it."),
}


def _until(value):
    if value is None:
        return "until resumed"
    try:
        return "until " + time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(value))
    except (OverflowError, OSError, ValueError):
        return "until a time that cannot be shown"


def _temporary_notice(result):
    causes = [_TEMPORARY_CAUSES.get((cause.reason, cause.scope), cause.reason)
              + (f" ({_until(cause.until)})" if cause.reason == "local_pause" else "")
              for cause in getattr(result, "temporary_causes", ())]
    if [cause.reason for cause in getattr(result, "temporary_causes", ())] == ["server_paused"]:
        return "Temporary conversation: memBrain recording is paused. This turn was not saved or queued for learning."
    if not causes:
        return ("Temporary conversation: this turn was not saved or queued for learning. "
                "The reason is not stored with a replayed temporary turn.")
    return "Temporary conversation: " + "; ".join(causes) + ". This turn was not saved or queued for learning."


def _recording_report(state):
    """Readable lines for the three independently read controls. Each keeps its own known state: unknown is never
    shown as off, and temporary handling is never promised while the service that must reserve it is silent."""
    controls = state["controls"]
    server, device, conversation = controls["server"], controls["device"], controls["conversation"]
    local = (device["state"], conversation["state"])
    if state["new_message"] == "unavailable":
        lines = ["The memory service did not confirm its state. No message can be answered until it responds: "
                 "neither a recorded nor a temporary turn can start, and nothing is generated or saved meanwhile."]
        if "paused" in local:
            lines.append("A local control keeps new messages of this conversation branch out of memory. Temporary "
                         "handling still needs the service's reservation, which is unconfirmed while it is silent.")
        elif "unknown" in local:
            lines.append("A local recording control could not be read either, so recording is unconfirmed.")
        else:
            lines.append("Local controls are on. Whether a new message would be recorded is unconfirmed until "
                         "the service answers.")
    elif state["new_message"] == "record":
        lines = ["Recording is on for new messages in this conversation branch."]
    elif state["recording"] == "paused":
        lines = ["New messages in this conversation branch are handled as temporary: not saved or queued for learning."]
    else:
        lines = ["A local recording control could not be read, so recording is unconfirmed. As a precaution a new "
                 "message is handled as temporary, and only after the memory service confirms a temporary "
                 "reservation; otherwise it stops before generation."]
    device_text = {"on": "on", "paused": "paused " + _until(device.get("until"))}.get(
        device["state"], "unknown (the control file could not be read; inspect it before resuming device capture)")
    if device.get("host_conversations") == "paused":
        device_text += ("; a separate local pause covers the host conversations that were active when it was set "
                        "and does not apply to this direct conversation")
    return lines + [
        "Memory recording for the whole brain (server): " + {"on": "on", "paused": "paused"}.get(
            server["state"], "unknown (the service did not confirm it)") + ".",
        "Chat capture on this device (installation): " + device_text + ".",
        "This conversation branch: " + {"on": "on the record", "paused": "off the record"}.get(
            conversation["state"], "unknown (the stored choice could not be read; /on-record or /off-record replaces it)")
        + ".",
        "Each control is separate; changing one leaves the others unchanged. The two local controls apply to new "
        "messages and do not cancel a turn already running; pausing the server switch also stops recorded turns "
        "in progress.",
    ]


def _recording_command(agent, off_record=None):
    """Show the recording controls, after optionally changing this conversation branch's own choice."""
    from .agent_session import SessionError

    try:
        state = agent.recording_state() if off_record is None else agent.set_off_record(off_record)
        pending = agent.pending
    except SessionError as error:
        _notice(f"{error.code}: The recording choice or its state could not be confirmed; no message was sent.")
        return None
    if off_record is not None:
        _notice("This conversation branch is now " + ("off the record." if off_record else "on the record.")
                + " This command and its text were not sent or stored as a message.")
    for line in _recording_report(state):
        _notice(line)
    if pending and state["recording"] != "on":
        _notice(f"Recorded turn {pending['turn_id']} is still pending and was not changed. It cannot continue "
                "while recording is off or unconfirmed here; cancel it, or turn recording back on and resume it.")
    return state


def _call(operation, recovery=None):
    from .agent_session import SessionError
    from .chat_provider import ChatProviderError

    try:
        return operation()
    except (SessionError, RuntimeBlocked, ChatProviderError) as error:
        _notice(error.code)
        if error.code in _BLOCKED_ADVICE:
            _notice(_BLOCKED_ADVICE[error.code])
        elif isinstance(error, ChatProviderError) and error.status_code is not None:
            advice = {
                401: "Check the reply provider API key with desktop configure-chat.",
                403: "Check the reply provider permissions and model access.",
                404: "Check the reply provider endpoint and model in desktop configure-chat.",
                429: "The provider reported a rate or quota limit; check its limits before another attempt.",
            }.get(error.status_code, "Check the reply provider configuration and availability.")
            _notice(f"Model provider HTTP {error.status_code}. {advice}")
        elif isinstance(error, ChatProviderError) and error.code in {"timeout", "transport_error"}:
            _notice("The provider outcome may be unknown; a timeout does not prove the request was not processed.")
        if error.code != "no_pending_turn":
            if error.code not in _BLOCKED_ADVICE:
                _notice("Check the turn state before retrying. Unknown generation or delivery is not retried automatically.")
            if recovery is not None:
                try:
                    recovery(error)
                except Exception:
                    _notice("Recovery diagnostics unavailable; the original operation was not retried.")
        return None
    except httpx.HTTPError as error:
        _notice("memory_service_unavailable: Check desktop status and the turn state before retrying.")
        if recovery is not None:
            try:
                recovery(error)
            except Exception:
                _notice("Recovery diagnostics unavailable; the original operation was not retried.")
        return None


def _perform(operation, monitor=None, recovery=None):
    result = _call(operation, recovery)
    if result is None:
        return False
    if result.replayed:
        print(f"Turn {result.turn_id} was already completed; its answer was not sent again.", file=sys.stderr)
    elif result.stage != "completed":
        print(f"Turn {result.turn_id} remains at {result.stage}.", file=sys.stderr)
    if result.ephemeral:
        _notice(_temporary_notice(result))
    if result.stage == "completed" and monitor is not None and not result.ephemeral:
        monitor.completed(result.turn_id)
    return result.stage == "completed"


def _cancel(agent, turn_id, acknowledge_uncertain, recovery=None):
    result = _call(lambda: agent.cancel(turn_id=turn_id, acknowledge_uncertain=acknowledge_uncertain), recovery)
    if result is None:
        return False
    print(f"Turn {result['turn_id']} is {result['stage']}; no answer was generated or sent by cancellation.", file=sys.stderr)
    if result.get("failure_code") in ("generation_uncertain", "delivery_uncertain"):
        print("The original external outcome remains unknown; cancellation cannot undo a charge or a send.", file=sys.stderr)
    return True


def run(args):
    from .agent_session import open_agent

    if (args.message is None) != (args.message_id is None):
        raise ValueError("--message and --message-id must be supplied together.")
    if args.acknowledge_uncertain and args.cancel is None:
        raise ValueError("--acknowledge-uncertain requires --cancel with an exact turn ID.")
    if args.cancel is not None and not re.fullmatch(r"turn-[0-9a-f]{40}", args.cancel):
        raise ValueError("--cancel requires an exact pending turn ID.")
    if args.message is not None:
        if not args.message.strip() or not 1 <= len(args.message_id) <= 256 or any(
            character.isspace() or unicodedata.category(character).startswith("C")
            for character in args.message_id
        ):
            raise ValueError("Provide a nonempty message and a stable message ID without whitespace or control characters.")
        try:
            args.message.encode("utf-8")
        except UnicodeError:
            raise ValueError("The message must contain valid UTF-8 text.") from None
    control = (True if args.off_record else False if args.on_record else None, args.recording_status)
    interactive = args.message is None and not args.resume and args.cancel is None and control == (None, False)
    if interactive and not sys.stdin.isatty():
        raise ValueError("Use --message with --message-id, --resume, or --cancel outside an interactive terminal.")
    instructions = ""
    if args.instructions_file is not None:
        with args.instructions_file.open("rb") as stream:
            contents = stream.read(64001)
        if len(contents) > 64000:
            raise ValueError("The instructions file exceeds 64,000 bytes.")
        try:
            instructions = contents.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("The instructions file must contain UTF-8 text.") from None
    # Background learning was removed, so there is no learning monitor: replies report only their own outcome.
    monitor = None
    with open_agent(args.directory, conversation_id=args.conversation, branch_id=args.branch,
                    deliver=_deliver, instructions=instructions,
                    policy=RuntimePolicy(orientation_policy=args.orientation)) as agent:
        def recovery(error):
            _recovery_notice(error, agent, args)

        if control != (None, False):
            # A recording control sends no message. The machine-readable state goes to standard output.
            state = _recording_command(agent, control[0])
            if state is None:
                raise SystemExit(1)
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return
        if not interactive:
            if args.cancel is not None:
                if not _cancel(agent, args.cancel, args.acknowledge_uncertain, recovery):
                    raise SystemExit(1)
                return
            operation = agent.resume if args.resume else lambda: agent.respond(args.message, message_id=args.message_id)
            if not _perform(operation, monitor, recovery):
                raise SystemExit(1)
            return
        print("Local memory chat. Commands: /quit, /resume, /retry <original input>, /cancel <turn-id>.", file=sys.stderr)
        print("Recording: /off-record keeps this conversation branch out of memory, /on-record records new messages "
              "again, /recording shows the current controls. /resume only recovers a pending turn.", file=sys.stderr)
        print("Use /cancel-uncertain <turn-id> only to explicitly close a turn whose model or delivery outcome is unknown.", file=sys.stderr)
        if agent.pending:
            print(f"Pending turn {agent.pending['turn_id']}; resolve it before sending a new message.", file=sys.stderr)
        while True:
            print("You: ", end="", file=sys.stderr, flush=True)
            try:
                text = input()
            except EOFError:
                return
            command = text.strip()
            command_name = command.split(maxsplit=1)[0] if command else ""
            if command == "/quit":
                return
            if command == "/resume":
                _perform(agent.resume, monitor, recovery)
            elif command in ("/off-record", "/on-record", "/recording"):
                _recording_command(agent, {"/off-record": True, "/on-record": False}.get(command))
            elif command == "/retry":
                print("Specify the exact original input after /retry followed by a space.", file=sys.stderr)
            elif command in ("/cancel", "/cancel-uncertain"):
                print("Specify the exact pending turn ID after the command.", file=sys.stderr)
            elif command.startswith("/cancel ") or command.startswith("/cancel-uncertain "):
                name, turn_id = command.split(" ", 1)
                _cancel(agent, turn_id, name == "/cancel-uncertain", recovery)
            elif text.lstrip().startswith("/retry "):
                pending = agent.pending
                if not pending:
                    print("no_pending_turn", file=sys.stderr)
                    continue
                _perform(lambda: agent.respond(text.lstrip()[len("/retry "):], message_id=pending["message_id"]), monitor, recovery)
            elif command_name in (
                "/quit", "/resume", "/retry", "/cancel", "/cancel-uncertain",
            ) or command.startswith(("/off-record", "/on-record", "/recording")):
                # A mistyped recording command, such as "/off-record: ...", must not be sent as a message.
                print("Invalid command arguments; no message was sent.", file=sys.stderr)
            elif text.strip():
                _perform(lambda: agent.respond(text, message_id=str(uuid4())), monitor, recovery)
