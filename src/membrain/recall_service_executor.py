import time
from dataclasses import replace
from datetime import datetime, timedelta
from multiprocessing.util import Finalize
from types import SimpleNamespace

from . import helpers, recall_deadline
from .config import configured_service
from .contracts import validator
from .helpers import DomainError
from .recall_executor import RecallExecutor

_SERVICE = None


def _initialize_service(settings, principals, barrier):
    global _SERVICE
    manager = configured_service(settings, principals=principals)
    _SERVICE = manager.__enter__()
    Finalize(None, manager.__exit__, args=(None, None, None), exitpriority=10)
    validator("ActionRequest")
    validator("ActionResponse")
    barrier.wait()


def _respond(principal, request, embedding, space, started, deadline, clock, access_at=None):
    previous_clock = helpers._scenario_clock
    previous_provider = _SERVICE.embedding_provider
    previous_access_time = _SERVICE.access_time_provider
    try:
        if request.get("action") not in {"recall", "prepare"}:
            raise DomainError("unsupported_capability", "This worker only handles recall and preparation.")
        if clock is not None:
            moment, sent = clock
            origin = datetime.fromisoformat(moment.replace("Z", "+00:00"))
            helpers._scenario_clock = lambda: origin + timedelta(seconds=time.monotonic() - sent)
        # Only the provider's identity crosses processes; model sessions and paid transports stay in the API.
        _SERVICE.embedding_provider = SimpleNamespace(space=space) if space is not None else None
        _SERVICE.access_time_provider = (lambda: access_at) if access_at is not None else None
        with recall_deadline.window(started, deadline):
            return {"response": _SERVICE._respond(principal, request, embedding=embedding)}
    except DomainError as error:
        return {"error": error.as_dict()}
    except Exception:
        return {"error": {"code": "internal_error", "message": "Recall transaction failed.", "retryable": False}}
    finally:
        _SERVICE.embedding_provider = previous_provider
        _SERVICE.access_time_provider = previous_access_time
        helpers._scenario_clock = previous_clock


class RecallServiceExecutor(RecallExecutor):
    def __init__(self, workers, settings):
        super().__init__(workers)
        self._principals = tuple(set(settings.principals().values()))
        self._settings = replace(
            settings, recall_processes=0, api_keys={}, api_keys_file=None, migration_database_url=None,
            cognition_base_url=None, cognition_api_key=None, cognition_model=None,
            cognition_thinking=None, cognition_reasoning_effort=None,
            embedding_base_url=None, embedding_api_key=None, embedding_model=None,
            embedding_model_version=None, embedding_dimensions=None, embedding_local_directory=None,
        )

    def _initialization(self, context):
        return _initialize_service, (self._settings, self._principals, context.Barrier(self.workers, timeout=20))

    def respond(self, principal, request, embedding, space, *, access_at=None):
        started = time.monotonic()
        deadline = started + request["payload"]["budget"]["max_wall_time_ms"] / 1000
        clock = (helpers.now(), time.monotonic()) if helpers._scenario_clock is not None else None
        value = self._run(_respond, (principal, request, embedding, space, started, deadline, clock, access_at), deadline)
        if "error" in value:
            raise DomainError(**value["error"])
        return value["response"]
