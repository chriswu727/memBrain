import json
import sys
from pathlib import Path


def add_commands(commands):
    desktop = commands.add_parser("desktop", help="Set up and manage the local memory service")
    actions = desktop.add_subparsers(dest="desktop_command", required=True)
    for name in ("setup", "start", "status", "stop", "restart", "mcp-config", "mcp", "logs", "_run"):
        parser = actions.add_parser(name)
        parser.add_argument("--directory", type=Path, default=None)
        if name == "setup":
            parser.add_argument("--api-port", type=int)
            parser.add_argument("--database-port", type=int)
            parser.add_argument("--database", choices=("auto", "docker", "embedded"), default="auto",
                                help="Database engine for a new installation; auto uses the embedded engine when installed")
            parser.add_argument("--no-start", action="store_true", help="Save configuration without starting services")
            parser.add_argument("--non-interactive", action="store_true",
                                help="Accepted for compatibility; setup never prompts")
        elif name == "logs":
            parser.add_argument("--lines", type=int, default=30)
    from .desktop_chat import add_commands as add_chat_commands
    from .desktop_recovery import add_commands as add_recovery_commands
    from .desktop_turns import add_commands as add_turn_commands

    add_chat_commands(actions)
    add_recovery_commands(actions)
    add_turn_commands(actions)


def _setup(args):
    from . import desktop
    from .desktop_connection import mcp_config
    from .local_profile import ensure_profile, profile_lock

    engine = getattr(args, "database", "docker")
    if engine == "auto":
        from .embedded_database import default_engine

        engine = default_engine()
    # memBrain asks for no model of its own: the host's AI does every model task.
    profile = ensure_profile(args.directory, api_port=args.api_port, database_port=args.database_port,
                             database_engine=engine)
    with profile_lock(profile.directory):
        configuration = mcp_config(profile.directory)
        path = profile.directory / "mcp.json"
        desktop._private_write(path, json.dumps(configuration, indent=2) + "\n")
    current = desktop.status(profile.directory)
    if args.no_start:
        result = current
    elif current["state"] == "restart_required":
        result = desktop.restart(profile.directory)
    else:
        result = desktop.start(profile.directory)
    result.update(mcp_config=configuration, mcp_config_file=str(path))
    return result


def _logs(directory, lines):
    from .local_profile import load_profile

    if not 1 <= lines <= 100:
        raise ValueError("--lines must be between 1 and 100.")
    path = load_profile(directory).directory / "service.log"
    if path.is_symlink():
        raise ValueError("The log path is a symbolic link.")
    if not path.exists():
        return {"events": []}
    events = []
    for line in path.read_text(encoding="utf-8").splitlines()[-lines:]:
        try:
            entry = json.loads(line)
            if isinstance(entry, dict) and set(entry) == {"time", "event", "instance_id"}:
                events.append(entry)
        except ValueError:
            continue
    return {"events": events}


def dispatch(args):
    import psycopg

    from . import desktop
    from .agent_session import SessionError
    from .backup_transport import BackupError
    from .chat_config import ChatConfigurationError
    from .deletion_registry import RegistryError
    from .desktop_chat import configure, run
    from .desktop_connection import mcp_config, run_mcp
    from .storage import SchemaCompatibilityError

    try:
        action = args.desktop_command
        if action == "setup":
            result = _setup(args)
        elif action == "configure-chat":
            result = configure(args)
        elif action == "chat":
            run(args)
            return
        elif action == "mcp-config":
            result = mcp_config(args.directory)
        elif action == "mcp":
            run_mcp(args.directory)
            return
        elif action == "_run":
            desktop.run(args.directory)
            return
        elif action == "logs":
            result = _logs(args.directory, args.lines)
        elif action in {"backup", "restore-backup", "activate-recovery", "recovery-status", "cancel-backup"}:
            from .desktop_recovery import run as run_recovery

            result = run_recovery(args)
        elif action == "turn-status":
            from .desktop_turns import run as run_turns

            result = run_turns(args)
        else:
            result = getattr(desktop, action)(args.directory)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (desktop.DesktopError, SessionError, ChatConfigurationError, BackupError, RegistryError,
            SchemaCompatibilityError, ValueError) as error:
        print(f"{getattr(error, 'code', 'configuration_error')}: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except psycopg.Error:
        print("database_unavailable: The database operation did not complete. Existing data was preserved; retry the same recovery request.", file=sys.stderr)
        raise SystemExit(1) from None
    except OSError:
        print("local_io_error: Local files or processes were unavailable. Existing data was preserved.", file=sys.stderr)
        raise SystemExit(1) from None
    except (KeyboardInterrupt, EOFError):
        message = ("Chat interrupted; check the pending turn before retrying. An interrupted send may have an unknown outcome."
                   if args.desktop_command == "chat" else "Setup cancelled; saved configuration was preserved.")
        print(message, file=sys.stderr)
        raise SystemExit(130) from None
