"""Scenario clock for evaluation runs only (C5 harness). Normal installations never use it.

An evaluation scenario spans days or weeks in minutes. So that the local service records events, decays the
simulated mood, counts familiarity days and pauses proposals on the scenario's timeline, ``helpers.now()`` and
``helpers.today()`` can read a clock file that the harness advances, in the service process and in the harness's own
process alike.

Safety:
- Off unless ``MEMBRAIN_EVALUATION_CLOCK`` is set. No launcher, plugin or adapter sets it.
- When it is set, the profile must be a disposable evaluation profile: a marker file written by the harness for
  this installation's id, the clock file inside the profile directory, and never the default installation
  directory. Anything else is refused: the service does not start (``DesktopError``), so a stray variable fails
  loudly instead of faking time on a real profile.
- Enabling it is logged in the service log and on standard error.
- Time never moves backwards: the writer refuses an earlier time than the last one set, and each reading process
  never returns a time earlier than one it already returned. Events therefore keep recorded times in the same
  order as their sequence numbers.

The clock runs: it reads ``time`` plus the wall-clock seconds elapsed since the harness set it, so events within a
turn keep their real spacing.
"""
from __future__ import annotations

import datetime as _datetime
import json
import os
import sys
import threading
import time
from pathlib import Path

ENV = "MEMBRAIN_EVALUATION_CLOCK"
MARKER = "evaluation-profile.json"
CLOCK = "evaluation-clock.json"
PURPOSE = "disposable evaluation profile: the scenario clock replaces the wall clock"
WARNING = ("memBrain EVALUATION CLOCK ENABLED: time is simulated from {path}. This must never happen outside a "
           "disposable evaluation profile.")


class ClockRefused(RuntimeError):
    """The scenario clock was requested where it is not allowed, or would move backwards."""


def _parse(value: str) -> _datetime.datetime:
    moment = _datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ClockRefused("Clock times must carry a time zone.")
    return moment.astimezone(_datetime.UTC)


def _iso(moment: _datetime.datetime) -> str:
    return moment.astimezone(_datetime.UTC).isoformat().replace("+00:00", "Z")


def _read(path: Path) -> tuple[_datetime.datetime, float]:
    if path.is_symlink() or not path.is_file():
        raise ClockRefused(f"The evaluation clock file {path} is missing.")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        return _parse(document["time"]), float(document["set_at"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ClockRefused(f"The evaluation clock file {path} cannot be read.") from error


class ScenarioClock:
    """Reads the clock file (re-parsed only when it changes) and never returns an earlier time than before."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._seen: tuple | None = None
        self._value: tuple[_datetime.datetime, float] | None = None
        self._last: _datetime.datetime | None = None
        self.backwards = 0  # Times the file was moved back and the reading was held (should stay 0).

    def now(self) -> _datetime.datetime:
        with self._lock:
            try:
                stat = self.path.stat()
                seen = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
            except OSError:
                seen = None
            if seen is None or seen != self._seen or self._value is None:
                self._value, self._seen = _read(self.path), seen
            base, set_at = self._value
            moment = base + _datetime.timedelta(seconds=max(0.0, time.time() - set_at))
            if self._last is not None and moment < self._last:
                if self.backwards == 0:
                    print(f"memBrain evaluation clock: {self.path} moved backwards; holding {_iso(self._last)}",
                          file=sys.stderr, flush=True)
                self.backwards += 1
                moment = self._last
            self._last = moment
            return moment


def requested() -> str | None:
    return os.environ.get(ENV) or None


def _installation_id(directory: Path) -> str | None:
    try:
        value = json.loads((directory / "profile.json").read_text(encoding="utf-8")).get("installation_id")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value else None


def mark_disposable(directory: Path) -> Path:
    """Mark an installation the harness just created as a disposable evaluation profile (harness only)."""
    from .local_profile import default_profile_directory

    directory = Path(os.path.abspath(directory))
    if directory == Path(os.path.abspath(default_profile_directory())):
        raise ClockRefused("The default installation is never an evaluation profile.")
    installation = _installation_id(directory)
    if installation is None:
        raise ClockRefused("Create the evaluation profile before marking it.")
    marker = directory / MARKER
    marker.write_text(json.dumps({"purpose": PURPOSE, "installation_id": installation}) + "\n", encoding="utf-8")
    return marker


def check(directory: Path) -> Path:
    """The clock file to use for this profile, or ClockRefused when the profile may not use one."""
    from .local_profile import default_profile_directory

    raw = requested()
    if raw is None:
        raise ClockRefused(f"{ENV} is not set.")
    directory = Path(os.path.abspath(directory))
    path = Path(raw)
    if not path.is_absolute() or Path(os.path.abspath(path)) != directory / CLOCK:
        raise ClockRefused(f"{ENV} must name {CLOCK} inside the evaluation profile directory.")
    if directory == Path(os.path.abspath(default_profile_directory())):
        raise ClockRefused("The default installation never uses the evaluation clock.")
    marker = directory / MARKER
    try:
        if marker.is_symlink() or not marker.is_file():
            raise ValueError
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ClockRefused("This profile is not a disposable evaluation profile.") from None
    installation = _installation_id(directory)
    if (not isinstance(document, dict) or document.get("purpose") != PURPOSE or installation is None
            or document.get("installation_id") != installation):
        raise ClockRefused("This profile is not a disposable evaluation profile.")
    _read(path)
    return path


def enable(directory: Path) -> ScenarioClock | None:
    """Use the scenario clock in this process when ``MEMBRAIN_EVALUATION_CLOCK`` is set; None when it is not.

    Raises ClockRefused when it is set for a profile that may not use it.
    """
    from . import helpers

    if requested() is None:
        return None
    clock = ScenarioClock(check(directory))
    helpers._scenario_clock = clock.now
    print(WARNING.format(path=clock.path), file=sys.stderr, flush=True)
    return clock


def disable() -> None:
    """Back to the wall clock in this process (tests and the harness's own clean-up)."""
    from . import helpers

    helpers._scenario_clock = None


def advance(directory: Path, moment: _datetime.datetime, *, run: str = "") -> _datetime.datetime:
    """Set the scenario time (harness only). Refuses a time earlier than the last one set; a time the running clock
    has already passed leaves the clock as it is. Returns the scenario time now in force."""
    if moment.tzinfo is None:
        raise ClockRefused("Clock times must carry a time zone.")
    moment = moment.astimezone(_datetime.UTC)
    path = Path(os.path.abspath(directory)) / CLOCK
    if path.exists():
        base, set_at = _read(path)
        if moment < base:
            raise ClockRefused(f"The scenario clock never moves backwards ({_iso(moment)} is before {_iso(base)}).")
        current = base + _datetime.timedelta(seconds=max(0.0, time.time() - set_at))
        if moment <= current:
            return current
    temporary = path.with_name(CLOCK + ".tmp")
    temporary.write_text(json.dumps({"time": _iso(moment), "set_at": time.time(), "run": run}) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)
    return moment


def current(directory: Path) -> _datetime.datetime:
    """The scenario time in force for a profile's clock file (harness and tests)."""
    base, set_at = _read(Path(os.path.abspath(directory)) / CLOCK)
    return base + _datetime.timedelta(seconds=max(0.0, time.time() - set_at))
