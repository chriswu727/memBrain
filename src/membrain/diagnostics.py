"""Read-only installation diagnostics and concrete recovery commands."""
import shutil
import sys
from pathlib import Path

from . import embedded_database, host


def diagnose(directory: Path) -> dict:
    checks = []
    def add(name, state, detail, fix=None):
        checks.append({"name": name, "state": state, "detail": detail, "fix": fix})

    add("python", "pass" if sys.version_info >= (3, 12) else "error", ".".join(map(str, sys.version_info[:3])),
        None if sys.version_info >= (3, 12) else "Install Python 3.12 or later.")
    add("uv", "pass" if shutil.which("uv") else "warning", "Available" if shutil.which("uv") else "Not on PATH",
        None if shutil.which("uv") else "Install uv for automatic plugin startup and updates.")
    try:
        status = host.installation_status(directory)
    except Exception:
        add("installation", "error", "Configuration could not be read.", "Inspect profile.json and run membrain desktop status.")
        return {"ok": False, "checks": checks}
    state = status["state"]
    add("service", "pass" if status.get("ready") else "error", state,
        None if status.get("ready") else "Run membrain plugin start." if state == "not_installed" else
        "Run membrain desktop status and membrain desktop logs; restart only after inspecting the reported cause.")
    engine = status.get("database_engine")
    if engine == "embedded":
        add("database_engine", "pass" if embedded_database.available() else "error", "Embedded PostgreSQL",
            None if embedded_database.available() else "Install membrain-ai[embedded] with Python 3.12.")
    elif engine == "docker":
        add("database_engine", "pass" if shutil.which("docker") else "error", "Docker",
            None if shutil.which("docker") else "Install and start Docker, then run membrain plugin start.")
    semantic = status["semantic_recall"]
    add("semantic_recall", "pass" if semantic == "ready" else "warning", semantic + "; keyword recall remains available once the service is ready.",
        None if semantic == "ready" else "Run membrain plugin fetch-model when network access is available.")
    extraction = status.get("note_extraction")
    if extraction is not None:
        failing = int(extraction.get("failed_since_success") or 0)
        add("note_extraction", "warning" if failing else "pass",
            f"{failing} turns with incomplete note extraction since {extraction.get('last_success_at') or 'the start'} "
            f"(last error: {extraction.get('last_error')}); messages are still recorded and recalled." if failing
            else f"{extraction.get('turns_read', 0)} turns read; {extraction.get('notes_saved', 0)} notes saved.",
            "Check the memory service and MEMBRAIN_EXTRACT_MODEL, its base URL, key and provider status." if failing else None)
    pending = status["pending_records"]
    add("queue", "warning" if pending else "pass", f"{pending} records waiting for delivery.",
        "Run membrain plugin start to replay filtered records." if pending else None)
    parent = Path(directory).absolute()
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free
    add("disk", "warning" if free < 1024**3 else "pass", f"{free // 1024**2} MiB free.",
        "Free disk space before importing more history or downloading the model." if free < 1024**3 else None)
    if status.get("ready"):
        try:
            with host.ready_client(directory) as client:
                brain = client.memory_status()
            add("index", "warning" if brain["index_lag"] or brain["failed_jobs"] else "pass",
                f"{brain['index_lag']} messages awaiting indexing; {brain['failed_jobs']} failed jobs.",
                "Inspect the local service logs if indexing stops advancing." if brain["failed_jobs"] else None)
        except Exception:
            add("index", "error", "Index status could not be read.", "Run membrain plugin status and inspect service logs.")
    return {"ok": not any(check["state"] == "error" for check in checks), "checks": checks}
