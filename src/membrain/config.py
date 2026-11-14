import json
import logging
import os
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .helpers import Principal


@dataclass
class Settings:
    database_url: str = field(repr=False)
    migration_database_url: str | None = field(default=None, repr=False)
    api_keys_file: Path | None = None
    api_keys: dict[str, Principal] = field(default_factory=dict, repr=False)
    max_request_bytes: int = 2_000_000
    recall_processes: int = field(default_factory=lambda: _environment_integer("MEMBRAIN_RECALL_PROCESSES", 4))
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    embedding_local_directory: str | None = None
    recovery_registry_path: Path | None = None
    recovery_registry_id: str | None = None
    recovery_installation_id: str | None = None

    def __post_init__(self):
        if type(self.recall_processes) is not int or not 0 <= self.recall_processes <= 4:
            raise ValueError("MEMBRAIN_RECALL_PROCESSES must be an integer from 0 to 4")
        recovery = (self.recovery_registry_path, self.recovery_registry_id, self.recovery_installation_id)
        if any(value is not None for value in recovery) and any(value is None for value in recovery):
            raise ValueError("Recovery authority requires its path, registry identity and installation identity.")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        database_url = os.environ.get("MEMORY_DATABASE_URL")
        if not database_url:
            raise ValueError("MEMORY_DATABASE_URL is required; run membrain init")
        key_file = os.environ.get("MEMORY_API_KEYS_FILE")
        removed = [name for name in REMOVED_EMBEDDING_SETTINGS if os.environ.get(name) is not None]
        if removed:
            # The metered remote embedding provider was removed. Its settings are ignored rather than refused, so a
            # deployment that still sets them starts; only the names are logged, never their values.
            logging.getLogger("membrain.config").warning(
                "Ignoring %s: the remote embedding provider was removed. Set MEMORY_EMBEDDING_LOCAL_DIRECTORY to "
                "use the local embedding model.", ", ".join(removed))
        removed = sorted(name for name in os.environ if name.startswith(REMOVED_COGNITION_PREFIX))
        if removed:
            # Background learning with a cognition model of memBrain's own was removed: the host's AI does every
            # model task. Its settings are ignored rather than refused, so a deployment that still sets them starts
            # (also with a partial or malformed configuration); only the names are logged, never their values.
            logging.getLogger("membrain.config").warning(
                "Ignoring %s: background learning with a cognition model was removed; memBrain calls no model of "
                "its own.", ", ".join(removed))
        return cls(
            database_url=database_url,
            migration_database_url=os.environ.get("MEMORY_MIGRATION_DATABASE_URL"),
            api_keys_file=Path(key_file) if key_file else None,
            allowed_hosts=tuple(os.environ.get(
                "MEMORY_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
            ).split(",")),
            embedding_local_directory=os.environ.get("MEMORY_EMBEDDING_LOCAL_DIRECTORY"),
        )

    def principals(self) -> dict[str, Principal]:
        if self.api_keys_file:
            document = json.loads(self.api_keys_file.read_text(encoding="utf-8"))
            return {key: Principal(**value) for key, value in document.items()}
        return self.api_keys


# Settings of the metered remote embedding provider, which was removed; still set, they are ignored with a warning.
REMOVED_EMBEDDING_SETTINGS = ("MEMORY_EMBEDDING_BASE_URL", "MEMORY_EMBEDDING_API_KEY", "MEMORY_EMBEDDING_MODEL",
                              "MEMORY_EMBEDDING_MODEL_VERSION", "MEMORY_EMBEDDING_DIMENSIONS")
# Settings of the removed cognition model (MEMORY_COGNITION_BASE_URL, _API_KEY, _MODEL, _THINKING, _REASONING_EFFORT
# and the _MAX_* limits); still set, they are ignored with a warning.
REMOVED_COGNITION_PREFIX = "MEMORY_COGNITION_"


def _environment_integer(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise ValueError(f"{name} must be a bounded positive integer")
    return int(value)


@contextmanager
def configured_service(settings: Settings, *, principals=None):
    from .service import MemoryService
    from .storage import Database

    database = Database(settings.database_url, pool=True)
    try:
        database.check_compatibility(require_current=True)
    except Exception:
        database.close()
        raise
    from .recovery_authority import configure_authority

    with ExitStack() as resources:
        resources.callback(database.close)
        if principals is None:
            configure_authority(database, settings)
        else:
            configure_authority(database, settings, principals=principals)
        embedding = None
        if settings.embedding_local_directory is not None:
            from .local_embeddings import LocalEmbeddingProvider

            embedding = resources.enter_context(LocalEmbeddingProvider(Path(settings.embedding_local_directory)))
        yield MemoryService(database, embedding_provider=embedding)
