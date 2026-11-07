"""The evaluation-only scenario clock (C5 harness): the service process reads it, normal profiles cannot use it, and
time never goes backwards."""
import datetime
import json
import time
from pathlib import Path

import pytest

from membrain import desktop, embedded_database, evaluation_clock, helpers, host
from membrain.evaluation_clock import CLOCK, ENV, MARKER, ClockRefused
from membrain.local_profile import ensure_profile
from membrain.notes import save_note

ROOT = Path(__file__).resolve().parents[1]
UTC = datetime.UTC


def at(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


@pytest.fixture(autouse=True)
def wall_clock_after(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    yield
    evaluation_clock.disable()


def profile(tmp_path, name="installation", *, database_engine="docker") -> Path:
    directory = tmp_path / name
    ensure_profile(directory, database_engine=database_engine)
    return directory


def evaluation_profile(tmp_path, monkeypatch, when="2026-03-03T21:00:00Z", *, database_engine="docker") -> Path:
    directory = profile(tmp_path, database_engine=database_engine)
    evaluation_clock.mark_disposable(directory)
    evaluation_clock.advance(directory, at(when))
    monkeypatch.setenv(ENV, str(directory / CLOCK))
    return directory


# Off by default, refused where it does not belong ----------------------------------------------------------------

def test_without_the_variable_the_wall_clock_is_used_even_beside_a_clock_file(tmp_path):
    directory = profile(tmp_path)
    evaluation_clock.mark_disposable(directory)
    evaluation_clock.advance(directory, at("2020-01-01T00:00:00Z"))
    assert evaluation_clock.enable(directory) is None
    assert helpers._scenario_clock is None
    assert abs(at(helpers.now()) - datetime.datetime.now(UTC)) < datetime.timedelta(seconds=5)
    assert helpers.today() == datetime.date.today()


def test_the_clock_moves_now_and_today_in_an_evaluation_profile(tmp_path, monkeypatch, capsys):
    directory = evaluation_profile(tmp_path, monkeypatch)
    assert evaluation_clock.enable(directory) is not None
    assert "EVALUATION CLOCK ENABLED" in capsys.readouterr().err
    assert at(helpers.now()) - at("2026-03-03T21:00:00Z") < datetime.timedelta(seconds=5)
    evaluation_clock.advance(directory, at("2026-03-06T09:00:00Z"))
    assert helpers.now().startswith("2026-03-06T09:00:0")


@pytest.mark.parametrize("damage", ["no marker", "other installation", "clock elsewhere", "relative path",
                                    "marker symlink", "no clock file"])
def test_a_profile_that_is_not_a_disposable_evaluation_profile_is_refused(tmp_path, monkeypatch, damage):
    directory = evaluation_profile(tmp_path, monkeypatch)
    if damage == "no marker":
        (directory / MARKER).unlink()
    elif damage == "other installation":
        other = profile(tmp_path, "other")
        (directory / MARKER).write_text((evaluation_clock.mark_disposable(other)).read_text())
    elif damage == "clock elsewhere":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / CLOCK).write_text((directory / CLOCK).read_text())
        monkeypatch.setenv(ENV, str(elsewhere / CLOCK))
    elif damage == "relative path":
        monkeypatch.setenv(ENV, CLOCK)
    elif damage == "marker symlink":
        real = tmp_path / "marker.json"
        real.write_text((directory / MARKER).read_text())
        (directory / MARKER).unlink()
        (directory / MARKER).symlink_to(real)
    else:
        (directory / CLOCK).unlink()
    with pytest.raises(ClockRefused):
        evaluation_clock.enable(directory)
    assert helpers._scenario_clock is None


def test_the_default_installation_is_never_an_evaluation_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from membrain.local_profile import default_profile_directory

    directory = default_profile_directory()
    ensure_profile(directory)
    with pytest.raises(ClockRefused):
        evaluation_clock.mark_disposable(directory)
    marker = {"purpose": evaluation_clock.PURPOSE,
              "installation_id": json.loads((directory / "profile.json").read_text())["installation_id"]}
    (directory / MARKER).write_text(json.dumps(marker))
    evaluation_clock.advance(directory, at("2026-03-03T21:00:00Z"))
    monkeypatch.setenv(ENV, str(directory / CLOCK))
    with pytest.raises(ClockRefused, match="default installation"):
        evaluation_clock.enable(directory)


def test_the_service_refuses_to_start_with_a_clock_on_a_normal_profile_and_logs_it(tmp_path, monkeypatch):
    directory = profile(tmp_path)
    evaluation_clock.advance(directory, at("2026-03-03T21:00:00Z"))
    monkeypatch.setenv(ENV, str(directory / CLOCK))
    monkeypatch.setattr(desktop, "_check_database", lambda *a, **k: pytest.fail("the database was opened"))
    with pytest.raises(desktop.DesktopError) as refused:
        desktop.run(directory)
    assert refused.value.code == "evaluation_clock_refused"
    events = [json.loads(line) for line in (directory / "service.log").read_text().splitlines()]
    assert [event["event"] for event in events] == ["evaluation_clock_refused"]
    assert helpers._scenario_clock is None


def test_no_launcher_plugin_or_adapter_sets_the_clock():
    allowed = {ROOT / "src" / "membrain" / "evaluation_clock.py"}
    places = [ROOT / "integrations", ROOT / "plugins", ROOT / "sdk", ROOT / "scripts", ROOT / "src"]
    found = [path for place in places if place.exists() for path in place.rglob("*")
             if path.is_file() and path not in allowed and path.suffix not in (".png", ".onnx", ".ico", ".pyc")
             and ENV in path.read_text(errors="ignore")]
    assert found == []


# Never backwards ----------------------------------------------------------------------------------------------------

def test_time_never_moves_backwards(tmp_path, monkeypatch):
    directory = evaluation_profile(tmp_path, monkeypatch, when="2026-03-05T12:00:00Z")
    with pytest.raises(ClockRefused, match="backwards"):
        evaluation_clock.advance(directory, at("2026-03-05T11:59:59Z"))
    # A time the running clock has already passed (but not before the last one set) leaves the clock running on.
    time.sleep(0.05)
    kept = evaluation_clock.advance(directory, at("2026-03-05T12:00:00Z"))
    assert kept > at("2026-03-05T12:00:00Z")
    clock = evaluation_clock.enable(directory)
    first = at(helpers.now())
    # Someone rewrites the file to an earlier time behind the writer's back: readers hold their last time.
    (directory / CLOCK).write_text(json.dumps({"time": "2026-03-01T00:00:00Z", "set_at": time.time()}))
    later = [at(helpers.now()) for _ in range(3)]
    assert all(value >= first for value in later) and later == sorted(later)
    assert clock.backwards >= 1


# On a real local service ----------------------------------------------------------------------------------------

@pytest.fixture
def service(tmp_path, monkeypatch):
    if not embedded_database.available():
        pytest.skip("embedded PostgreSQL binaries are not installed")
    monkeypatch.setenv("MEMBRAIN_SEMANTIC", "0")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    directory = evaluation_profile(tmp_path, monkeypatch, database_engine="embedded")
    try:
        yield directory
    finally:
        try:
            desktop.stop(directory)
        except Exception:
            pass


def _recorded(directory, text):
    with host.ready_client(directory) as client:
        items = client.timeline(roles=("user", "assistant"), limit=50)["items"]
    return next(at(item["recorded_at"]) for item in items if item["text"] == text)


def test_the_service_process_records_and_decays_on_the_scenario_clock(service, monkeypatch):
    directory = service
    host.start(directory)  # The harness's process does not enable the clock here: only the service reads it.
    assert helpers._scenario_clock is None
    log = (directory / "service.log").read_text()
    assert "evaluation_clock_enabled_time_is_simulated" in log
    host.prompt_context(directory, "day-1", "I got the job!", turn_id="t0")
    host.finish_turn(directory, "day-1", "Congratulations!", turn_id="t0")
    recorded = _recorded(directory, "I got the job!")
    assert at("2026-03-03T21:00:00Z") <= recorded < at("2026-03-03T21:05:00Z")
    with host.ready_client(directory) as client:
        save_note(client, "Got the job at the studio.", kind="milestone",
                  affect={"label": "happy", "valence": 2, "intensity": 2, "basis": "reported"})
        mood = client.mood()
        assert mood["label"] == "glad" and not mood["at_baseline"] and "Simulated mood" in mood["block"]
        assert mood["now"].startswith("2026-03-03T21:0")

    # The next morning: still glad, easing. Two days after the trigger: exactly the baseline, with no mood line.
    evaluation_clock.advance(directory, at("2026-03-04T09:00:00Z"))
    with host.ready_client(directory) as client:
        mood = client.mood()
        assert mood["label"] == "glad" and mood["easing"] and mood["block"]
    evaluation_clock.advance(directory, at("2026-03-05T21:10:00Z"))
    with host.ready_client(directory) as client:
        mood = client.mood()
        assert mood["at_baseline"] and mood["block"] is None
        assert mood["now"].startswith("2026-03-05T21:1")

    # Familiarity counts scenario days of conversation, and new events keep the clock's order.
    host.prompt_context(directory, "day-3", "Back again.", turn_id="t0")
    host.finish_turn(directory, "day-3", "Welcome back.", turn_id="t0")
    later = _recorded(directory, "Back again.")
    assert later > recorded and later.date() == datetime.date(2026, 3, 5)
    with host.ready_client(directory) as client:
        familiarity = client.relationship()["familiarity"]
    assert familiarity["days"] == 2 and familiarity["since"] == "2026-03-03"
    with pytest.raises(ClockRefused):
        evaluation_clock.advance(directory, at("2026-03-04T00:00:00Z"))

    # The same installation started without the variable runs on the wall clock again.
    desktop.stop(directory)
    monkeypatch.delenv(ENV)
    host.start(directory)
    assert (directory / "service.log").read_text().count("evaluation_clock_enabled") == 1
    host.prompt_context(directory, "today", "Wall clock now.", turn_id="t0")
    host.finish_turn(directory, "today", "Yes.", turn_id="t0")
    assert abs(_recorded(directory, "Wall clock now.") - datetime.datetime.now(UTC)) < datetime.timedelta(minutes=2)
