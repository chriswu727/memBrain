"""Read-only installation diagnostics and concrete recovery commands."""
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

from . import embedded_database, host

# What each semantic-recall state means for recall, and what to do about it (None: nothing to do).
SEMANTIC = {
    "ready": ("ready", None),
    "downloading": ("downloading in the background; recall matches words until it finishes.", None),
    "download_failed": ("download_failed; recall matches words only.",
                        "Run membrain plugin fetch-model when network access is available; set HF_ENDPOINT to "
                        "download from a Hugging Face mirror."),
    "unavailable": ("unavailable: this runtime was installed without the semantic extra; recall matches words only.",
                    "Reinstall membrain-ai with its embedded and semantic extras."),
}
NOT_DOWNLOADED = ("{state}; recall matches words only.", "Run membrain plugin fetch-model when network access is available.")
STARTING = "A start or stop is in progress. Run membrain doctor again in a minute."


def _lifecycle_busy(directory: Path) -> bool:
    """Whether a start, stop or restart of this installation's service is running now (it holds the lifecycle lock)."""
    from .local_profile import LocalProfileBusy, profile_lock

    path = Path(directory) / "lifecycle"
    if not path.is_dir():
        return False
    try:
        with profile_lock(path, timeout=0):
            return False
    except LocalProfileBusy:
        return True


def _service(status: dict, directory: Path) -> tuple[str, str, str | None]:
    state = status["state"]
    if status.get("ready"):
        return "pass", state, None
    if state == "not_installed":
        return "error", state, "Run membrain plugin start."
    if state in ("stopped", "starting_or_stopping") and _lifecycle_busy(directory):
        # The first start prepares the database before the service runs; until then the service reads as stopped.
        return "warning", "starting_or_stopping", STARTING
    if state == "port_conflict":
        port = urlsplit(status.get("base_url") or "").port
        return "error", state, (f"Another program is listening on port {port}, the port this installation's service "
                                "uses. Close that program, then run membrain plugin start; no process was stopped.")
    return "error", state, ("Run membrain desktop status and membrain desktop logs; restart only after inspecting the "
                            "reported cause.")


def diagnose(directory: Path) -> dict:
    checks = []
    def add(name, state, detail, fix=None):
        checks.append({"name": name, "state": state, "detail": detail, "fix": fix})

    add("python", "pass" if sys.version_info >= (3, 12) else "error", ".".join(map(str, sys.version_info[:3])),
        None if sys.version_info >= (3, 12) else "Install Python 3.12 or later.")
    add("uv", "pass" if shutil.which("uv") else "warning", "Available" if shutil.which("uv") else "Not on PATH",
        None if shutil.which("uv") else "Install uv for automatic plugin startup and updates.")
    from .local_profile import LocalProfileBusy

    try:
        status = host.installation_status(directory)
    except LocalProfileBusy:
        # A start that prepares the database holds the profile for longer than the doctor waits for it.
        add("service", "warning", "starting_or_stopping", STARTING)
        return {"ok": True, "checks": checks}
    except Exception:
        add("installation", "error", "Configuration could not be read.", "Inspect profile.json and run membrain desktop status.")
        return {"ok": False, "checks": checks}
    add("service", *_service(status, directory))
    engine = None
    if (Path(directory) / "profile.json").exists():
        from .local_profile import load_profile

        try:
            engine = load_profile(directory).database_engine
        except Exception:
            engine = None  # Reported by the service check; the engine check needs a readable profile.
    if engine == "embedded":
        add("database_engine", "pass" if embedded_database.available() else "error", "Embedded PostgreSQL",
            None if embedded_database.available() else "Install membrain-ai[embedded] with Python 3.12.")
    elif engine == "docker":
        add("database_engine", "pass" if shutil.which("docker") else "error", "Docker",
            None if shutil.which("docker") else "Install and start Docker, then run membrain plugin start.")
    semantic = status["semantic_recall"]
    detail, fix = SEMANTIC.get(semantic, NOT_DOWNLOADED)
    add("semantic_recall", "pass" if semantic == "ready" else "warning", detail.format(state=semantic), fix)
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
