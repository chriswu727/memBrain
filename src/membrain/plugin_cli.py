from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOOK_EVENTS = ("session-start", "user-prompt", "stop")
HOOK_HOSTS = ("claude-code", "codex", "openclaw", "workbuddy")


def add_commands(commands):
    plugin = commands.add_parser("plugin", help="Zero-configuration entry points for agent host plugins")
    actions = plugin.add_subparsers(dest="plugin_command", required=True)
    hook = actions.add_parser("hook", help="Handle one host lifecycle hook from JSON on stdin; never fails")
    hook.add_argument("event", choices=HOOK_EVENTS)
    hook.add_argument("--host", choices=HOOK_HOSTS, default="claude-code", help="Host whose hook format is read")
    tool = actions.add_parser("tool", help="Run one memory tool with JSON arguments on stdin (for hosts without MCP)")
    tool.add_argument("name", choices=("note", "search", "pause", "resume", "boundary"))
    imports = actions.add_parser("import", help="Import the memory files hosts keep (Claude Code, Hermes, OpenClaw, "
                                                "Codex) as notes; safe to repeat")
    imports.add_argument("--from", dest="hosts", action="append", choices=("claude-code", "hermes", "openclaw", "codex"),
                         help="Only this host (repeatable); default all")
    imports.add_argument("--all", action="store_true",
                         help="Also import project and environment memory, not only memory about the person")
    imports.add_argument("--dry-run", action="store_true", help="Report what would be imported without saving")
    actions.add_parser("start", help="Create the local installation if needed and start the service")
    setup = actions.add_parser("setup", help="Start memory and open a guided connection check; no model API key needed")
    setup.add_argument("--no-browser", action="store_true", help="Print the guided memory page link without opening it")
    actions.add_parser("mcp", help="Run the MCP stdio bridge, creating and starting the installation if needed")
    actions.add_parser("status", help="Show installation, service and pending-record state")
    actions.add_parser("fetch-model", help="Download the local multilingual embedding model for semantic recall")
    pause = actions.add_parser("pause", help="Stop recording messages (recall keeps working) until resumed")
    pause.add_argument("--hours", type=float, default=None, help="Resume automatically after this many hours")
    actions.add_parser("resume", help="Resume recording messages")
    for name, text in (("forget-user", "Erase everything one person's memory holds (for bot operators); cannot be undone"),
                       ("export-user", "Export one person's memory as an archive document (for bot operators)")):
        person = actions.add_parser(name, help=text)
        person.add_argument("--platform", help="Platform as the bot reports it (for example aiocqhttp, telegram, or a "
                                               "proxy namespace/platform such as qq/api)")
        person.add_argument("--user", help="The person's id on that platform")
        person.add_argument("--group", help="The group, for memory kept from a group chat")
        person.add_argument("--user-id", help="A memBrain user id exactly as stored, instead of the three above")
        person.add_argument("--yes", action="store_true", help="Do not ask for confirmation (forget-user)")
        person.add_argument("--out", type=Path, help="Write the export here instead of standard output (export-user)")
    ui = actions.add_parser("ui", help="Open the memory page in a browser (starts the service if needed)")
    ui.add_argument("--no-browser", action="store_true", help="Only print the single-use link")
    for parser in actions.choices.values():
        parser.add_argument("--directory", type=Path, default=None)


def _person(args, directory: Path) -> int:
    """Erase or export one bot user's memory; returns the exit status."""
    from . import host
    from .adapters.chatbot import ChatMemory, Speaker

    if args.user_id:
        user = args.user_id
    elif args.platform and args.user:
        user = ChatMemory(directory, group_memory="separate").user_id(Speaker(args.platform, args.user, args.group))
    else:
        print("Give --platform and --user (and --group for a group chat), or --user-id.", file=sys.stderr)
        return 2
    try:
        if args.plugin_command == "export-user":
            document = json.dumps(host.export_user(directory, user), ensure_ascii=False, indent=2)
            if args.out:
                # A new owner-only file replaces the target, so an existing readable file never gets the export.
                temporary = args.out.with_name(f".{args.out.name}.{os.getpid()}.tmp")
                descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(document)
                os.replace(temporary, args.out)
                print(f"Exported {user} to {args.out}. The file holds their original messages; store it securely.",
                      file=sys.stderr)
            else:
                print(document)
            return 0
        if not args.yes:
            answer = input(f"Erase everything memBrain holds for {user}? This cannot be undone. Type ERASE: ")
            if answer.strip() != "ERASE":
                print("Nothing was erased.", file=sys.stderr)
                return 1
        print(json.dumps({"user_id": user, **host.erase_user(directory, user)}, indent=2))
        return 0
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1


def dispatch(args) -> None:
    from . import plugin

    directory = plugin.profile_directory(args.directory)
    if args.plugin_command == "hook":
        raise SystemExit(plugin.run_hook(args.event, directory, host_name=args.host))
    if args.plugin_command in ("forget-user", "export-user"):
        raise SystemExit(_person(args, directory))
    if args.plugin_command == "import":
        from . import host, imports

        sources = imports.discover(tuple(args.hosts or imports.HOSTS), include_general=args.all)
        plugin.start(directory)
        with host.ready_client(directory) as client:
            result = imports.import_notes(client, sources, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.plugin_command == "tool":
        raise SystemExit(plugin.run_tool(args.name, directory))
    if args.plugin_command == "mcp":
        from .desktop_connection import run_mcp
        from .host import installed_tool_matches, installed_tool_python, running_from_uv_cache

        durable = installed_tool_python() if running_from_uv_cache() else None
        if durable is not None:
            if not installed_tool_matches(durable):
                print("The installed memBrain tool differs from this MCP runtime. Update the tool using the same package source as this MCP configuration, then reconnect. Existing data was preserved.", file=sys.stderr)
                raise SystemExit(1)
            # Serve MCP from the installed tool so the service it starts outlives uv cache cleanups.
            import subprocess

            raise SystemExit(subprocess.call([str(durable), "-m", "membrain.cli", "plugin", "mcp",
                                              "--directory", str(directory)]))

        plugin.ensure_installation(directory)
        run_mcp(directory, require_turn_capture=True)
        return
    from .desktop import DesktopError

    try:
        if args.plugin_command == "start":
            result = plugin.start(directory)
        elif args.plugin_command == "fetch-model":
            result = plugin.fetch_model(directory)
        elif args.plugin_command in ("setup", "ui"):
            from . import host
            from .local_profile import load_profile

            result = plugin.start(directory)
            url = f"{load_profile(directory).base_url}/memory?code={host.issue_ui_code(directory)}"
            if args.plugin_command == "setup":
                print("Local memory is running. No extra model API key is needed.")
                print(f"Recall: {result['semantic_recall']}. Recording: {result['recording']}.")
                print("Use the page below to check that your agent records messages, then try a new session.")
            if not args.no_browser:
                import webbrowser

                webbrowser.open(url)
            print(f"Memory page (single-use link, valid for {host.UI_CODE_SECONDS // 60} minutes):\n{url}")
            return
        elif args.plugin_command in ("pause", "resume"):
            from . import host

            result = host.pause(directory, args.hours) if args.plugin_command == "pause" else host.resume(directory)
        else:
            from . import host

            result = host.installation_status(directory)
    except DesktopError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:
        from .deletion_registry import RegistryError  # Imported only here: hooks must stay light.

        if not isinstance(error, RegistryError):
            raise
        # The installation was retired by activating a restored backup, or its recovery record is unreadable.
        print(f"{error.code}: {error} If you restored a backup into another directory, set MEMBRAIN_DIRECTORY "
              "to that directory; run membrain desktop recovery-status for details.", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, indent=2, ensure_ascii=False))
