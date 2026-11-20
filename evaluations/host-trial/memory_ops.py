"""The trial memory's own operations, run by the FROZEN runtime's interpreter (``runtime/.venv/bin/python -I``).

The preparer copies this file into the trial directory and the runner calls that copy, so that a trial's memory is
created, started, read and stopped by the runtime under trial, never by the checkout that launched it. Every command
prints one JSON object. It never reads anything outside the directories it is given.

  memory_ops.py create BRAIN --model-from INSTALLATION   a new memory with free ports and the local embedding model
  memory_ops.py start BRAIN                              as the plugin's start hook does (``host.start``)
  memory_ops.py stop BRAIN
  memory_ops.py status BRAIN
  memory_ops.py state BRAIN [--erased ID ...]            notes, boundaries and every stored record, read through the
                                                         service; with --erased, which of those ids are still there
  memory_ops.py clone SOURCE_BRAIN TARGET_BRAIN          a stopped memory copied to a new directory (see ``clone``)
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import sys
from pathlib import Path

PAGE = 200
PAGES = 20
RECORD_CHARACTERS = 4000


def _free_port(taken: set[int]) -> int:
    while True:
        with socket.socket() as stream:
            stream.bind(("127.0.0.1", 0))
            port = stream.getsockname()[1]
        if port not in taken and 20000 < port < 60000:
            taken.add(port)
            return port


def create(brain: Path, model_from: Path) -> dict:
    from membrain.local_embeddings import installed, model_directory
    from membrain.local_profile import ensure_profile

    if brain.exists():
        raise SystemExit(f"{brain} exists: a trial memory is always new")
    source = installed(model_from)
    if source is None:
        raise SystemExit("the model cache holds no complete local embedding model (give --model-from an installation "
                         "directory that has one)")
    brain.mkdir(mode=0o700, parents=True)
    taken: set[int] = set()
    profile = ensure_profile(brain, database_engine="embedded", api_port=_free_port(taken),
                             database_port=_free_port(taken))
    shutil.copytree(source, model_directory(brain))
    return {"created": True, "api_port": profile.api_port, "database_port": profile.database_port,
            "model": bool(installed(brain))}


def start(brain: Path) -> dict:
    from membrain import host

    result = host.start(brain)
    return {key: result.get(key) for key in ("state", "ready", "semantic_recall", "spool_replayed")}


def stop(brain: Path) -> dict:
    from membrain import desktop

    result = desktop.stop(brain)
    return {key: result.get(key) for key in ("state", "ready", "database", "data_preserved")}


def status(brain: Path) -> dict:
    from membrain import desktop

    if not (brain / "profile.json").exists():
        return {"state": "not_installed", "ready": False}
    result = desktop.status(brain)
    return {key: result.get(key) for key in ("state", "ready", "database")}


def _records(client) -> tuple[list[dict], bool]:
    items, cursor, complete = [], None, True
    for _ in range(PAGES):
        response = client.timeline(roles=("user", "assistant"), max_characters=200_000,
                                   max_item_characters=RECORD_CHARACTERS, limit=PAGE, before_sequence=cursor)
        items += response.get("items") or []
        cursor = response.get("next_before_sequence")
        complete = bool(response.get("complete", True))
        if complete or type(cursor) is not int:
            break
    keep = ("event_id", "conversation_id", "text", "recorded_at", "producer")
    # The timeline names the speaker ``actor_role``; a record without one is refused, so that a role filter can never
    # pass by matching nothing.
    records = []
    for item in items:
        role = item.get("actor_role") or item.get("role")
        if role not in ("user", "assistant"):
            raise SystemExit(f"a stored record has no user or assistant role: {sorted(item)}")
        records.append({"role": role, **{key: item.get(key) for key in keep if key in item}})
    return records, complete


def state(brain: Path, erased: list[str]) -> dict:
    from membrain import host
    from membrain.notes import list_notes

    client = host.ready_client(brain)
    if client is None:
        raise SystemExit("the trial memory's service is not ready")
    with client:
        notes = []
        for item in list_notes(client).get("items") or []:
            notes.append({"event_id": item.get("event_id"), "text": item.get("text"),
                          "recorded_at": item.get("recorded_at"), "producer": item.get("producer"),
                          "replaced": [{key: entry.get(key) for key in ("event_id", "depth", "erased", "recorded_at")}
                                       for entry in item.get("replaced") or () if isinstance(entry, dict)]})
        boundaries = (client.relationship_boundaries() or {}).get("boundaries") or []
        records, complete = _records(client)
        result = {"notes": notes,
                  "boundaries": [{key: entry.get(key) for key in ("id", "topic", "aliases")} for entry in boundaries],
                  "records": records, "records_complete": complete}
        if erased:
            found = client.timeline(roles=("user", "assistant"), event_ids=erased, limit=PAGE,
                                    max_characters=200_000, max_item_characters=RECORD_CHARACTERS)
            present = {item.get("event_id") for item in found.get("items") or [] if (item.get("text") or "").strip()}
            result["still_present"] = sorted(set(erased) & present)
    return result


def _rewrite(value, old: str, new: str, ports: dict[int, int]):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in ("api_port", "database_port") and type(item) is int and item in ports:
                out[key] = ports[item]
            else:
                out[key] = _rewrite(item, old, new, ports)
        return out
    if isinstance(value, list):
        return [_rewrite(item, old, new, ports) for item in value]
    if isinstance(value, str) and (value == old or value.startswith(old + "/")):
        return new + value[len(old):]
    return value


def clone(source: Path, target: Path) -> dict:
    """Copy a STOPPED trial memory to a new directory and point the copy at itself: its own ports and its own copy of
    the deletion registry. Nothing in the source is written. An installation never does this: the copy keeps the
    source's installation, brain and owner identities. It exists so that a scenario can continue an earlier trial's
    memory while that trial's scene stays exactly as it was."""
    from membrain import desktop, embedded_database
    from membrain.local_profile import load_profile

    source, target = source.resolve(), target.resolve()
    if target.exists():
        raise SystemExit(f"{target} exists: a clone is always new")
    profile = load_profile(source)
    if desktop.status(source).get("ready") or embedded_database.running(profile):
        raise SystemExit("the earlier memory's service is running: stop it first (trial.py service stop)")
    old_root, new_root = str(source.parent), str(target.parent)
    binding_path = source / "recovery.json"
    binding = json.loads(binding_path.read_text()) if binding_path.exists() else None
    registry = Path(binding["registry_path"]) if binding else None
    if registry is not None and source.parent not in registry.parents:
        raise SystemExit("the earlier memory's deletion registry is outside its trial directory; not cloned")
    target.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("postmaster.pid", "ui-codes.json", ".profile-*.tmp")
    shutil.copytree(source, target, symlinks=True, ignore=ignore)
    if registry is not None:
        shutil.copytree(registry, Path(new_root) / registry.relative_to(old_root), symlinks=True)
    taken: set[int] = set()
    ports = {profile.api_port: _free_port(taken), profile.database_port: _free_port(taken)}
    rewritten = []
    for path in sorted(target.rglob("*.json")):
        relative = path.relative_to(target)
        if relative.parts[0] in ("postgres", "models", "native-engines") or path.is_symlink():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            continue
        changed = _rewrite(document, old_root, new_root, ports)
        if changed != document:
            mode = path.stat().st_mode
            path.write_text(json.dumps(changed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            path.chmod(mode)
            rewritten.append(str(relative))
    # The database's own configuration names its port (the engine writes it once, at initialisation).
    configuration = target / "postgres" / "postgresql.conf"
    if configuration.is_file():
        text = configuration.read_text(encoding="utf-8")
        changed = re.sub(rf"(?m)^port = {profile.database_port}$", f"port = {ports[profile.database_port]}", text)
        if changed == text:
            raise SystemExit("the earlier memory's database configuration does not name its port as expected")
        configuration.write_text(changed, encoding="utf-8")
        rewritten.append("postgres/postgresql.conf")
    return {"cloned": True, "rewritten": rewritten, "api_port": ports[profile.api_port],
            "database_port": ports[profile.database_port]}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    command, brain = argv[0], Path(argv[1])
    if command == "create":
        if argv[2:3] != ["--model-from"] or len(argv) != 4:
            raise SystemExit("create BRAIN --model-from INSTALLATION")
        result = create(brain, Path(argv[3]))
    elif command in ("start", "stop", "status"):
        result = {"start": start, "stop": stop, "status": status}[command](brain)
    elif command == "state":
        erased = argv[3:] if argv[2:3] == ["--erased"] else []
        result = state(brain, erased)
    elif command == "clone":
        result = clone(brain, Path(argv[2]))
    else:
        raise SystemExit(f"unknown command {command}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
