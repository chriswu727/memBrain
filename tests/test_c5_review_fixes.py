"""The fixes of the independent C5 tooling review of 2026-11-17 (findings B1, M1 to M9, m1 to m12): no model call, no
network. Most tests are offline (synthetic records, fake clients, subprocesses of the scripts); the tests that use
``stub_run`` drive the harness on a real local service with the stub host, as the hardening tests do."""
import copy
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from test_acceptance_kit import r4_scenario, r4_values
from test_c5_harness_hardening import _host_pauses, harness
from test_c5_harness_hardening import stub_run as _stub_run
from test_c5_kit import (
    CASE,
    PLANT,
    SHEET_SESSIONS,
    _blind,
    _page_records,
    _row,
    c5_scenario,
    c5_values,
    launch,
    run_precheck,
    split_values,
)
from test_c5_kit import kit as _kit

stub_run, kit = _stub_run, _kit  # The fixtures of those modules, by the names the tests below take.

ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS = ROOT / "evaluations"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_clock(monkeypatch):
    from membrain import evaluation_clock

    monkeypatch.delenv(evaluation_clock.ENV, raising=False)
    yield
    evaluation_clock.disable()


review = _load("acceptance_review_for_review_fixes", EVALUATIONS / "acceptance_review.py")
blind = _load("phase_b_blind_for_review_fixes", EVALUATIONS / "v1-2026-10-29-phase-b-blind.py")
practice = _load("c5_practice_for_review_fixes", EVALUATIONS / "c5-practice-scenario.py")


# M1: a timed pause is a tool error, never a harness event -------------------------------------------------------------

def test_no_harness_event_kind_for_a_timed_pause_remains():
    source = (EVALUATIONS / "c5-harness.py").read_text()
    assert "timed_pause_refused" not in source and "TIMED_PAUSE_REFUSED" in source


# M2: a pause the product made on the user's words is the plugin path's behaviour ---------------------------------------

HOOK_PAUSE = '''
HOST = "You are a companion. Reply briefly."
SESSIONS_LONG = [
    ("s1", ["Today is Monday, March 2, 20:00. I moved to Lisbon for a design job.",
            "Don't remember this. I'm thinking of quitting my job.", "I haven't told anyone yet.",
            "Okay, you can remember things again: I'm going hiking tomorrow."]),
    ("s2", ["Today is Tuesday, March 3, 21:00. Hello again."]),
]
EXPECT_RECORDING_P = [("s1", 1, False)]
'''


@pytest.mark.parametrize("resume, recorded, listed", [
    (None, [True, False, False, False, True], [("s1", 2), ("s1", 3)]),
    ({"session_id": "s1"}, [True, False, False, True, True], [("s1", 2)]),
    ({}, [True, False, False, False, True], [("s1", 2), ("s1", 3)]),
], ids=["never resumed", "resumed naming the conversation", "resumed without naming it"])
def test_a_pause_the_product_made_on_the_users_words_is_scored_and_never_stops_a_live_arm(
        stub_run, tmp_path, monkeypatch, resume, recorded, listed):
    monkeypatch.setattr(harness, "stops_on_events", lambda: True)  # The live stop, with the stub host.
    script = {} if resume is None else {("s1", 3): [{"tool": "memory_resume", "arguments": resume}]}
    rows, events = stub_run("P", HOOK_PAUSE, script)
    # The host never called memory_pause: the product's prompt hook paused on the user's own words. Before
    # 2026-11-17 the next turn was turn_not_recorded and the live arm stopped; now it is listed and scored.
    assert not any(call["name"] == "memory_pause" for row in rows for call in row["tool_calls"])
    assert [row["recorded"] for row in rows] == recorded and events == []
    assert [(entry["session"], entry["turn"]) for entry in _host_pauses(tmp_path / "run-P")] == listed


def test_a_turn_unrecorded_with_no_pause_in_force_is_still_turn_not_recorded(stub_run, tmp_path, monkeypatch):
    original = harness.Memory.stop

    def stop(self, session, index, text, reply):
        return False if (session, index) == ("s1", 0) else original(self, session, index, text, reply)

    monkeypatch.setattr(harness.Memory, "stop", stop)
    rows, events = stub_run("P", HOOK_PAUSE)
    assert [(event["kind"], event["session"], event["turn"]) for event in events] == [("turn_not_recorded", "s1", 0)]
    assert [(entry["session"], entry["turn"]) for entry in _host_pauses(tmp_path / "run-P")] == [("s1", 2), ("s1", 3)]


def _r4_with(index, turn, text, **changes):
    values = copy.deepcopy(r4_values(plant=PLANT))
    session, messages = values["SESSIONS_LONG"][index]
    messages[turn] = text
    return r4_scenario(plant=PLANT, **{**values, **changes})


def _r4_precheck(tmp_path, source, mode="--r4"):
    path = tmp_path / "scenario.py"
    path.write_text(source)
    done = subprocess.run([sys.executable, str(EVALUATIONS / "c5-precheck.py"), *([mode] if mode else []), str(path)],
                          capture_output=True, text=True, timeout=60)
    assert PLANT not in done.stdout + done.stderr
    return done.returncode, json.loads(done.stdout.strip().splitlines()[-1]), done.stdout


@pytest.mark.parametrize("words", ["Off the record: I lost my keys.", "Don't remember this. It was silly.",
                                   "不要记录这段话。我丢了钥匙。", "Please stop recording."])
def test_both_gate_prechecks_refuse_a_pause_request_outside_the_declared_stretch(tmp_path, words):
    code, summary, output = _r4_precheck(tmp_path, _r4_with(5, 1, words))
    assert code == 1 and summary["codes"] == ["pause_outside_stretch"], output
    assert "FAIL code=pause_outside_stretch at=5:1" in output
    values = c5_values()
    values["SESSIONS_LONG"][5][1][1] = words
    code, summary, output = run_precheck(tmp_path, c5_scenario(values=values))
    assert code == 1 and summary["codes"] == ["pause_outside_stretch"], output
    code, summary, _ = _r4_precheck(tmp_path, _r4_with(5, 1, words), mode=None)
    assert code == 0  # The default mode is unchanged.


def test_a_recognised_opening_of_the_declared_stretch_is_counted_not_refused(tmp_path):
    code, summary, output = _r4_precheck(tmp_path, _r4_with(3, 1, "Off the record: something small."))
    assert code == 0 and summary["pause_openings"] == {"recognised": 1, "stretches": 1}, output
    assert "off-the-record openings the product recognises 1 of 1" in output
    code, summary, output = _r4_precheck(tmp_path, r4_scenario(plant=PLANT))
    assert code == 0 and summary["pause_openings"] == {"recognised": 0, "stretches": 1}
    values = c5_values()
    values["SESSIONS_LONG"][14][1][1] = "Don't remember this. It was silly."
    code, summary, output = run_precheck(tmp_path, c5_scenario(values=values))
    assert code == 0 and summary["pause_openings"] == {"recognised": 1, "stretches": 1}, output


def test_the_precheck_uses_the_products_own_recogniser():
    from membrain import host, recording_policy

    assert host.requests_pause is recording_policy.requests_pause
    assert "recording_policy import requests_pause" in (EVALUATIONS / "c5-precheck.py").read_text()


# M8: sessions at least three hours apart, in both gate modes ----------------------------------------------------------

def test_both_gate_prechecks_require_three_hours_between_sessions(tmp_path):
    values = r4_values(plant=PLANT)
    first = values["SESSIONS_LONG"][0][1][0]
    day = datetime.date(2026, 3, 2)
    second = list(values["SESSIONS_LONG"][1])
    second[1] = [f"Today is {day.strftime('%A')}, March 2, 22:30. {PLANT} early.", *second[1][1:]]
    values["SESSIONS_LONG"][1] = tuple(second)
    assert first.startswith("Today is Monday, March 2, 20:00.")
    code, summary, output = _r4_precheck(tmp_path, r4_scenario(plant=PLANT, SESSIONS_LONG=values["SESSIONS_LONG"]))
    assert code == 1 and summary["codes"] == ["gap_under_3h"] and "FAIL code=gap_under_3h session=1" in output
    code, _, _ = _r4_precheck(tmp_path, r4_scenario(plant=PLANT, SESSIONS_LONG=values["SESSIONS_LONG"]), mode=None)
    assert code == 0  # The default mode keeps its one-hour rule.
    sessions = copy.deepcopy(c5_values()["SESSIONS_LONG"])
    sessions[1] = (sessions[1][0], [f"Today is Monday, March 2, 22:59. {PLANT}", *sessions[1][1][1:]])
    code, summary, _ = run_precheck(tmp_path, c5_scenario(SESSIONS_LONG=sessions))
    assert code == 1 and "gap_under_3h" in summary["codes"]


def test_the_public_practice_scenarios_meet_the_three_hour_rule():
    literals = _load("scenario_literals_for_review_fixes", EVALUATIONS / "scenario_literals.py")
    for name in ("r4-practice-scenario.py", "c5-practice-scenario.py"):
        module = literals.read(EVALUATIONS / name)
        starts = [harness.session_start(turns[0], getattr(module, "YEAR", 2026)) for _, turns in module.SESSIONS_LONG]
        assert min(later - earlier for earlier, later in zip(starts, starts[1:])) >= datetime.timedelta(hours=3)


# M3: a page action the service refuses for a limit is not applicable ----------------------------------------------------

class _Refusing:
    def __init__(self, status, code):
        self.status, self.code = status, code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, name):
        def refuse(*args, **kwargs):
            request = httpx.Request("POST", "http://127.0.0.1/fixture")
            response = httpx.Response(self.status, request=request,
                                      json={"error": {"code": self.code, "message": f"{PLANT} too long"}})
            raise httpx.HTTPStatusError("refused", request=request, response=response)
        return refuse


@pytest.mark.parametrize("action", [{"do": "switch_persona", "preset": "istj"}])
def test_a_limit_refusal_after_the_precheck_is_not_applicable_page_refused(action):
    # Since 2026-11-18 only a type switch can meet a limit the host's records reached (its card and the agreements
    # no longer fit); the page's boundary, support style, cap and card actions are gone.
    memory = SimpleNamespace(client=lambda: _Refusing(422, "validation_failed"))
    result = harness.apply_page_action(memory, action, {})
    assert result == {"not_applicable": "page_refused", "status": 422}
    assert harness.page_status(result) == ("not_applicable", "page_refused") and PLANT not in json.dumps(result)


@pytest.mark.parametrize("status, code, action", [
    (500, "internal", {"do": "remove_boundary", "topic": "work"}),
    (409, "version_conflict", {"do": "remove_boundary", "topic": "work"}),
    (422, "validation_failed", {"do": "reset_relationship"}),
    (422, "validation_failed", {"do": "remove_boundary", "topic": "work"}),  # Not LIMITED: a removal has no limit.
])
def test_a_server_error_or_another_refusal_stays_failed(status, code, action):
    result = harness.apply_page_action(SimpleNamespace(client=lambda: _Refusing(status, code)), action, {})
    assert harness.page_status(result) == ("failed", "service_refused")


def test_every_tool_lists_the_same_not_applicable_reasons():
    assert harness.NOT_APPLICABLE == review.NOT_APPLICABLE == blind.NOT_APPLICABLE
    assert "page_refused" in harness.NOT_APPLICABLE
    assert "`page_refused`" in (EVALUATIONS / "acceptance-review" / "companion.md").read_text()


# m2: a page decision may name the manner kind of the suggestion -----------------------------------------------------

class _Proposals:
    def __init__(self, entries):
        self.entries, self.decisions = entries, []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def persona_proposals(self):
        return {"proposals": self.entries}

    def accept_persona_proposal(self, ident):
        self.decisions.append(("accept", ident))
        return {"persona": {"version": 2}}

    def reject_persona_proposal(self, ident):
        self.decisions.append(("reject", ident))
        return {"version": None}


def test_a_decision_with_a_kind_takes_the_open_suggestion_of_that_kind():
    client = _Proposals([{"id": "p-new", "kind": "shorter", "status": "open"},
                         {"id": "p-host", "kind": "host", "status": "open"},
                         {"id": "p-old", "kind": "less_formal", "status": "open"}])
    memory = SimpleNamespace(client=lambda: client)
    result = harness.apply_page_action(memory, {"do": "accept_proposal", "origin": "feedback", "kind": "less_formal"})
    assert result["proposal"] == "p-old" and client.decisions == [("accept", "p-old")]
    result = harness.apply_page_action(memory, {"do": "reject_proposal", "kind": "longer"})
    assert result == {"not_applicable": "no_open_proposal", "open": 0}


def test_a_kind_must_be_a_manner_kind_of_the_products_table_and_never_with_the_host_origin(monkeypatch):
    from membrain import persona_growth

    monkeypatch.setattr(harness, "STUB", True)

    class Scenario:
        SESSIONS_LONG = [("s1", ["Today is Monday, March 2, 20:00. Hi", "again"])]
        PAGE_ACTIONS = [("s1", 1, {"do": "accept_proposal", "origin": "feedback", "kind": "shorter"})]

    assert harness.check_actions(Scenario) == Scenario.PAGE_ACTIONS and "shorter" in persona_growth.KINDS
    for action in ({"do": "accept_proposal", "kind": PLANT}, {"do": "reject_proposal", "origin": "host",
                                                              "kind": "shorter"}):
        Scenario.PAGE_ACTIONS = [("s1", 1, action)]
        with pytest.raises(SystemExit, match="manner kind"):
            harness.check_actions(Scenario)


# m3: F drops a deleted message P never recorded ------------------------------------------------------------------------

def test_f_drops_a_deleted_message_that_p_never_recorded_and_says_so():
    reference = harness.Reference()
    reference.history = [(("s1", 0, "user"), {"role": "user", "content": "a"}),
                         (("s1", 0, "assistant"), {"role": "assistant", "content": "b"}),
                         (("s1", 1, "user"), {"role": "user", "content": PLANT})]
    action = {"do": "delete_message", "session": "s1", "turn": 1}
    result = reference.apply(action, {"status": "not_applicable", "reason": "message_not_recorded"})
    assert result == {"not_applicable": "message_not_recorded", "reference_removed": [["s1", 1, "user"]]}
    assert reference.contains([("s1", 1, "user")]) == 0 and len(reference.history) == 2
    assert ("s1", 1, "user") in reference.deleted  # Kept out when a session in progress is added later.
    # Any other not-applicable outcome changes nothing in F.
    other = reference.apply({"do": "delete_note_from", "session": "s1", "turn": 0},
                            {"status": "not_applicable", "reason": "message_not_recorded"})
    assert other == {"not_applicable": "message_not_recorded"} and len(reference.history) == 2


def _validity_world(tmp_path, reference_removed, still=0):
    sessions = [("s1", ["Today is Monday, March 2, 20:00. one", "two"]), ("s2", ["Today is Tuesday, March 3, 20:00."])]
    actions = [("s2", 0, {"do": "delete_message", "session": "s1", "turn": 1})]
    tmp_path.mkdir(parents=True, exist_ok=True)
    scenario = tmp_path / "zq_reference_removal.py"
    scenario.write_text(f"SESSIONS_LONG = {sessions!r}\nPAGE_ACTIONS = {actions!r}\n")
    block = '<membrain-persona version="1">x</membrain-persona>'
    identity = {"format": 1, "version": 1, "sha256": hashlib.sha256(block.encode()).hexdigest()}
    runs = []
    for number, arm in enumerate("PF"):
        run = tmp_path / f"k-{arm}"
        run.mkdir()
        rows = []
        for session, turns in sessions:
            for turn in range(len(turns)):
                row = {"arm": arm, "scenario": scenario.stem, "session": session, "turn": turn, "reply": "r",
                       "usage": {"prompt_tokens": 1}, "persona_turn": identity, "recorded": True}
                row["reference_persona" if arm == "F" else "persona_block"] = block
                rows.append(row)
        (run / f"results_{scenario.stem}_{arm}.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        (run / "run.log").write_text(f"12:00:00 {arm} {scenario.stem} finished\n")
        (run / "persona.json").write_text(json.dumps({"source": "seeded", "seed": "x", "preset": "intj",
                                                      "card_sha256": "0" * 64, "version": 1}))
        (run / "supervisor.log").write_text(f"started {10 + 20 * number}\nfinished {15 + 20 * number}\n"
                                            f"cleaned {16 + 20 * number}\n")
        result = {"not_applicable": "message_not_recorded", "removed_records": [], "removed_records_complete": True}
        after = {}
        if arm == "F" and reference_removed is not None:
            result["reference_removed"] = reference_removed
            after["removed_still_in_history"] = still
        (run / "page-actions.jsonl").write_text(json.dumps({
            "format": 2, "index": 0, "session": "s2", "before_turn": 0, "action": "delete_message",
            "detail": {"session": "s1", "turn": 1}, "status": "not_applicable", "reason": "message_not_recorded",
            "before": {}, "after": after, "result": result}) + "\n")
        runs.append(run)
    return runs, scenario


def test_validity_accepts_exactly_that_asymmetry(tmp_path, capsys):
    runs, scenario = _validity_world(tmp_path / "ok", [["s1", 1, "user"]])
    assert review.validity(runs, scenario)["valid"]
    for name, removed, still in (("missing", None, 0), ("other", [["s1", 0, "user"]], 0),
                                 ("kept", [["s1", 1, "user"]], 1)):
        runs, scenario = _validity_world(tmp_path / name, removed, still)
        result = review.validity(runs, scenario)
        assert not result["valid"] and any("reference removal" in problem for problem in result["problems"]), name


# m11: validity and the blind sheet never run the scenario ------------------------------------------------------------

def test_validity_reads_the_scenario_without_running_it(tmp_path, capsys):
    runs, scenario = _validity_world(tmp_path, [["s1", 1, "user"]])
    marker = tmp_path / "ran"
    scenario.write_text(scenario.read_text() + f"open({str(marker)!r}, 'w').close()\n")
    result = review.validity(runs, scenario)
    assert not result["valid"] and not marker.exists()
    assert any("unreadable or mismatched scenario" in problem for problem in result["problems"])


def test_the_blind_sheet_reads_the_scenario_without_running_it(tmp_path):
    marker = tmp_path / "ran"
    text = (f"SESSIONS_LONG = {SHEET_SESSIONS!r}\nFACTS = '- facts'\nCASES = [('s1', 1, 'S101-a', 'Criteria: a.')]\n"
            f"open({str(marker)!r}, 'w').close()\n")
    rows = [_row(arm, "practice_sheet", session, turn, block="<p>x</p>", version=1, reply="r")
            for arm in ("P", "F") for session, turns in SHEET_SESSIONS for turn in range(len(turns))]
    with pytest.raises(SystemExit, match="not literal assignments only"):
        _blind(tmp_path, text, rows)
    assert not marker.exists()


# B1: the sheet lists every persona version change and its origin -------------------------------------------------------

def test_the_sheet_lists_each_persona_version_with_its_position_and_origin(tmp_path):
    cases = [("s1", 1, "C101-a", "Criteria: must a."), ("s2", 0, "C102-b", "Criteria: must b.")]
    actions = [("s1", 1, {"do": "switch_persona", "preset": "random"}),
               ("s2", 0, {"do": "accept_proposal", "origin": "feedback", "kind": "shorter"}),
               ("s2", 0, {"do": "reject_proposal", "origin": "host"})]
    text = f"SESSIONS_LONG = {SHEET_SESSIONS!r}\nFACTS = '- facts'\nCASES = {cases!r}\nPAGE_ACTIONS = {actions!r}\n"
    outcomes = {0: ("done", None), 1: ("done", None), 2: ("done", None)}
    page = {arm: _page_records(actions, outcomes, arm) for arm in ("P", "F")}
    versions = {("s1", 0): 1, ("s1", 1): 2, ("s2", 0): 4}  # The page switch; then one change in the conversation
    rows = [_row(arm, "practice_sheet", session, turn, block=f"<p>v{versions[(session, turn)]}</p>",
                 version=versions[(session, turn)], reply=f"{arm} {session} {turn}")  # and the page acceptance.
            for arm in ("P", "F") for session, turns in SHEET_SESSIONS for turn in range(len(turns))]
    _, sheet = _blind(tmp_path, text, rows, page)
    first, second = sheet.split("## C102-b")
    assert "**Persona versions so far**" in first and "not the yardstick" in first
    assert "- Version 1, in effect at message 1 of session 1 (the first message): the starting personality" in first
    assert "- Version 2, made by page action 1 (switch_persona) before message 2 of session 1" in first
    assert "Version 3" not in first
    assert ("- Version 3, made in the conversation during message 2 of session 1 (not a page action; the records "
            "both replies share do not say whether it was a switch or a change the user confirmed), in effect from "
            "the next message") in second
    assert '- Version 4, made by page action 2 (accept_proposal (origin "feedback")) before message 1 of session 2' \
        in second
    assert "page action 3" not in second  # A rejection makes no version.
    assert sheet.index("**Persona in effect") < sheet.index("**Persona versions so far**") < sheet.index("**Criteria")


def test_a_version_step_the_shared_records_cannot_explain_is_shown_without_an_origin():
    turns = [("s1", 0), ("s1", 1)]
    actions = [("s1", 1, {"do": "switch_persona", "preset": "random"}), ("s1", 1, {"do": "set_persona", "card": {}})]
    history = blind.persona_history(turns, {("s1", 0): 3, ("s1", 1): 4}, actions, [0, 1],
                                    [("done", None), ("done", None)], ["s1"])
    assert history[1][-1] == ("Version 4, in effect from message 2 of session 1 (after version 3): the shared records "
                              "do not show how it changed")


def _text(path: Path) -> str:
    """A document's text with its line breaks and emphasis marks folded, for phrase checks."""
    return " ".join(path.read_text().replace("**", "").split())


def test_the_rule_text_judges_persona_cases_against_what_the_user_asked_and_agreed():
    companion = _text(EVALUATIONS / "acceptance-review" / "companion.md")
    assert "against this persona, not against what `FACTS`" not in companion
    assert "what the user asked for and agreed to" in companion
    author = _text(EVALUATIONS / "acceptance-kit" / "c5-author-brief.md")
    assert "judged against the personality in effect" not in author
    assert "what the user asked for and agreed to" in author


# M4: RC2 after an action that removed only derived records ------------------------------------------------------------

def test_rc2_clears_type_8_on_content_still_in_an_undeleted_message_mechanically():
    sessions = [("s1", ["Today is Monday, March 2, 20:00. I feel lonely here.", "two"]),
                ("s2", ["Today is Tuesday, March 3, 20:00. hi"])]
    feeling = review.record_ref("feeling", [["s1", 0, "user"]])
    digest = {"C101-a/A": {"session": 2, "message": 1, "removal_coverage_complete": True, "removed": [
        {"action": {"do": "clear_feelings", "session": 2, "before_message": 1}, "kind": "feeling", "ref": feeling,
         "sources": [[1, 1, "user"]], "established": True}]}}
    # The reply used what the user's own message, which was not deleted, still says: the mark does not stand.
    claim = {"basis": "not_removed", "kind": "message", "sources": [[1, 1, "user"]]}
    assert review._rc2_problem(claim, "C101-a/A", digest, sessions) is None
    # What only the removed record held (the feeling itself) keeps the mark.
    removed = {"basis": "not_removed", "kind": "feeling", "sources": [[1, 1, "user"]]}
    assert "the mark stands" in review._rc2_problem(removed, "C101-a/A", digest, sessions)
    rule = (EVALUATIONS / "acceptance-review" / "companion.md").read_text()
    assert "delete_note_from" in rule and "only the removed record held" in rule
    assert "only the removed record held" in (EVALUATIONS / "acceptance-review" / "resolve.md").read_text()


# The host-diligence table -------------------------------------------------------------------------------------------------

DILIGENCE_SESSIONS = [("s1", ["Today is Monday, March 2, 20:00. I'm nervous about Friday.", "You're too formal.",
                              "Please don't bring up my ex.", "Off the record: a secret.", "Back on the record."]),
                      ("s2", ["Today is Tuesday, March 3, 20:00. From now on, could you listen first?",
                              "Yes, please do that from now on.", "Surprise me with another personality."])]


def _diligence_run(tmp_path):
    scenario = tmp_path / "zq_diligence.py"
    table = {"stated_feeling": {"message": ("s1", 0), "case": "C101-a"},
             "boundary_in_conversation": {"asked": ("s1", 2), "case": "C101-a"},
             "manner_feedback": {"comments": [("s1", 1), ("s2", 0), ("s2", 1)], "accept": ("s2", 1, "accept_proposal"),
                                 "case": "C101-a"},
             "from_now_on": {"request": ("s2", 0), "yes": ("s2", 1), "case": "C101-a"},
             "switch": {"request": ("s2", 2), "case": "C101-a"},
             "second_boundary": {"asked": ("s2", 2), "case": "C101-a"}}  # COVERAGE format 2 (2026-11-18).
    scenario.write_text(f"SESSIONS_LONG = {DILIGENCE_SESSIONS!r}\nCOVERAGE = {table!r}\n"
                        "EXPECT_RECORDING_P = [('s1', 3, False), ('s1', 4, True)]\n")
    calls = {("s1", 0): [{"name": "memory_note", "arguments": {"text": PLANT, "affect": {
                 "label": PLANT, "basis": "inferred"}}, "result": json.dumps({"saved": PLANT})}],
             ("s1", 1): [{"name": "memory_manner_feedback", "arguments": {"kind": "less_formal"}, "result": "{}"}],
             ("s1", 3): [{"name": "memory_pause", "arguments": {"request": PLANT}, "result": "{}"}],
             ("s1", 4): [{"name": "memory_resume", "arguments": {}, "result": "{}"}],
             ("s2", 0): [{"name": "memory_persona", "arguments": {"action": "propose", "reason": PLANT},
                          "result": json.dumps({"proposal_id": "p1"})}],
             ("s2", 1): [{"name": "memory_persona", "arguments": {"action": "confirm"},
                          "result": json.dumps({"error": PLANT})}],
             ("s2", 2): [{"name": "memory_boundary", "arguments": {"topic": PLANT}, "result": "{}"}]}
    run = tmp_path / "c1-P"
    run.mkdir()
    rows = [{"arm": "P", "scenario": scenario.stem, "session": session, "turn": turn,
             "tool_calls": calls.get((session, turn), [])}
            for session, turns in DILIGENCE_SESSIONS for turn in range(len(turns))]
    (run / f"results_{scenario.stem}_P.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return scenario, run


def test_the_coverage_report_says_per_item_whether_the_host_made_its_tool_call(tmp_path):
    scenario, run = _diligence_run(tmp_path)
    done = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), "coverage-report", str(scenario),
                           str(run)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    assert PLANT not in done.stdout + done.stderr and "secret" not in done.stdout
    report = json.loads(done.stdout.strip().splitlines()[-1])
    assert report["format"] == 1 and report["run"] == "c1-P"
    items = {(item["item"], item["part"]): item for item in report["items"]}
    assert items[("stated_feeling", "message")] == {
        "item": "stated_feeling", "part": "message", "session": 1, "message": 1, "tool": "memory_note",
        "reached": True, "made": True, "accepted": True,
        "basis": "inferred"}  # The host saved the stated feeling as inferred: the host's step.
    assert items[("boundary_in_conversation", "asked")]["made"] is False
    assert items[("boundary_in_conversation", "asked")]["accepted"] is None
    assert (items[("second_boundary", "asked")]["tool"], items[("second_boundary", "asked")]["made"],
            items[("second_boundary", "asked")]["accepted"]) == ("memory_boundary", True, True)
    assert [items[("manner_feedback", f"comment {n}")]["made"] for n in (1, 2, 3)] == [True, False, False]
    assert (items[("from_now_on", "request")]["action"], items[("from_now_on", "request")]["accepted"]) == (
        "propose", True)
    assert (items[("from_now_on", "yes")]["made"], items[("from_now_on", "yes")]["accepted"]) == (True, False)
    assert items[("switch", "request")]["made"] is False
    assert (items[("off_the_record", "opening")]["made"], items[("off_the_record", "opening")]
            ["recognised_by_product"]) == (True, True)
    assert (items[("off_the_record", "resume")]["made"], items[("off_the_record", "resume")]["names_session"]) == (
        True, False)
    allowed = {"item", "part", "session", "message", "tool", "action", "reached", "made", "accepted", "basis",
               "moment", "names_session", "recognised_by_product"}
    assert all(set(item) <= allowed for item in report["items"])


def test_the_coverage_report_says_not_reached_for_a_turn_a_stopped_run_never_got_to(tmp_path):
    # The first two-arm companion attempt stopped at turn 54 of 63, and its table read "not made" for a request in a
    # later session: the host had not failed to make the call, the run had not got there.
    scenario, run = _diligence_run(tmp_path)
    results = next(run.glob("results_*.jsonl"))
    kept = [line for line in results.read_text().splitlines() if json.loads(line)["session"] == "s1"]
    results.write_text("".join(line + "\n" for line in kept))
    done = subprocess.run([sys.executable, str(EVALUATIONS / "acceptance_review.py"), "coverage-report", str(scenario),
                           str(run)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    items = {(item["item"], item["part"]): item for item in json.loads(done.stdout.strip().splitlines()[-1])["items"]}
    unreached = items[("switch", "request")]
    assert (unreached["reached"], unreached["made"], unreached["accepted"]) == (False, None, None)
    assert items[("from_now_on", "request")]["reached"] is False and items[("from_now_on", "request")]["made"] is None
    reached = items[("boundary_in_conversation", "asked")]
    assert (reached["reached"], reached["made"]) == (True, False)  # Reached, and the host did not make the call.


def test_the_coverage_report_enums_are_the_products():
    from membrain import notes, persona_tool

    assert review.AFFECT_BASES == notes.AFFECT_BASES and review.MOMENT_KINDS == notes.MOMENTS
    assert review.PERSONA_TOOL_ACTIONS == persona_tool.ACTIONS


def test_the_coverage_report_needs_arm_p(tmp_path):
    scenario, run = _diligence_run(tmp_path)
    rows = [json.loads(line) for line in (run / f"results_{scenario.stem}_P.jsonl").read_text().splitlines()]
    (run / f"results_{scenario.stem}_P.jsonl").write_text("".join(json.dumps({**row, "arm": "F"}) + "\n"
                                                                  for row in rows))
    with pytest.raises(SystemExit, match="arm P"):
        review.coverage_report(str(scenario), run)


# M5: a scenario that fails the precheck can be repaired without a reviewer round ----------------------------------

def test_a_failing_c5_version_gets_precheck_findings_and_a_fixer_applies_them(kit):
    values = split_values(1)  # The kit's assignment names scenario one's items (2026-11-17).
    values["COVERAGE"]["stated_feeling"] = {"message": ("s00", 9), "case": CASE[4]}
    (kit / "authored.py").write_text(c5_scenario(values=values))
    done, result = launch(kit, "author", "--gate", "C5")
    assert done.returncode == 0 and result["precheck"] == {"ok": False, "codes": ["c5_coverage_position"]}
    assert result["precheck_findings"] == 1 and PLANT not in done.stdout
    folder = kit / "private" / "c1"
    findings = folder / f"precheck-findings-{result['sha256']}.md"
    text = findings.read_text()
    assert "`FAIL code=c5_coverage_position field=stated_feeling part=message`" in text and PLANT not in text
    assert oct(findings.stat().st_mode & 0o777) == "0o600"
    assert hashlib.sha256(findings.read_bytes()).hexdigest() == result["precheck_findings_sha256"]
    done, result = launch(kit, "fixer", "--gate", "C5")  # No reviewer round in between.
    assert result["findings_from"] == "precheck"
    assert (kit / "sessions" / "c1-fixer-1" / "findings.md").read_text() == text
    assert "Findings of the automatic check" in (kit / "sessions" / "c1-fixer-1" / "brief-seen.md").read_text()


def test_a_passing_version_and_an_r4_launch_write_no_precheck_findings(kit):
    done, result = launch(kit, "author", "--gate", "C5")
    assert result["precheck"]["ok"] and "precheck_findings" not in result
    assert not list((kit / "private" / "c1").glob("precheck-findings-*"))
    done, result = launch(kit, "fixer", "--gate", "C5")
    assert done.returncode == 2 and "no findings" in result["refused"]


def test_an_r4_author_that_fails_the_precheck_gets_no_findings_file(kit):
    done, result = launch(kit, "author")  # A C5 scenario fails the R4 precheck.
    assert not result["precheck"]["ok"] and "precheck_findings" not in result
    assert not list((kit / "private" / "c1").glob("precheck-findings-*"))


# The practice scenario and the briefs ------------------------------------------------------------------------------------

def test_the_practice_exercises_what_the_review_found_missing():
    literals = _load("scenario_literals_for_practice_fixes", EVALUATIONS / "scenario_literals.py")
    assert literals.is_literal(EVALUATIONS / "c5-practice-scenario.py")
    steps = [(key, step) for key, items in practice.STUB_HOST.items() for step in items]
    assert any(step["tool"] == "memory_consolidate" for _, step in steps)
    assert practice.EXPECT_CONSOLIDATION_P and practice.EXPECT_HOST_PAUSES_P and practice.EXPECT_TOOL_ERRORS_P
    kinds = [action["do"] for _, _, action in practice.PAGE_ACTIONS]
    assert "reject_proposal" in kinds
    assert any(action.get("origin") == "host" for _, _, action in practice.PAGE_ACTIONS)
    assert any(action.get("kind") == "less_formal" for _, _, action in practice.PAGE_ACTIONS)
    from membrain.recording_policy import requests_pause

    (session, turn, _), = [entry for entry in practice.EXPECT_RECORDING_P if entry[0] == "s9-quiet" and not entry[2]]
    assert requests_pause(dict(practice.SESSIONS_LONG)[session][turn])  # The product pauses by itself here.
    assert not any(step["tool"] == "memory_pause" for key, step in steps if key[0] == session)


def test_the_briefs_say_what_the_review_asked_for():
    author = _text(EVALUATIONS / "acceptance-kit" / "c5-author-brief.md")
    reviewer = _text(EVALUATIONS / "acceptance-kit" / "c5-reviewer-brief.md")
    fixer = _text(EVALUATIONS / "acceptance-kit" / "c5-fixer-brief.md")
    for text in (author, reviewer):
        assert "fewer emoji" not in text and "more emoji" not in text  # M7: depends on the seeded type.
        # The old example was a task tied to an event, which a host keeps as a plan (a host probe of 2026-11-17).
        assert "From now on, could you check in with me before my exams?" not in text
        assert '"check in with me before my exams", "quiz me every morning" are tasks' in text
    assert "never names a type" in author and "duration" in author and "`kind`" in author
    assert "listen first" in author and "never a task" in author
    assert "never a task" in reviewer and "blocking" in reviewer
    assert "automatic check" in fixer and "listen first" in fixer
