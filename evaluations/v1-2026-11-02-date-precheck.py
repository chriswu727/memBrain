"""Free pre-check for the final acceptance plan: every session's parsed date matches the weekday its text states.

Usage: python evaluations/v1-2026-11-02-date-precheck.py SCENARIO_FILE...
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("harness", HERE / "v1-2026-10-29-phase-b-harness.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

WEEKDAYS = [("monday", "lunes", "montag", "一"), ("tuesday", "martes", "dienstag", "二"),
            ("wednesday", "miércoles", "mittwoch", "三"), ("thursday", "jueves", "donnerstag", "四"),
            ("friday", "viernes", "freitag", "五"), ("saturday", "sábado", "samstag", "六"),
            ("sunday", "domingo", "sonntag", "日")]
STATED = re.compile(r"(?:Today is|Hoy es|Heute ist) (\w+),|今天是\d+月\d+日[，,]?\s*(?:星期|周)([一二三四五六日天])", re.IGNORECASE)

failures = 0
for path in sys.argv[1:]:
    module = harness.load(path)
    year, today = getattr(module, "YEAR", harness.YEAR), None
    for session, turns in module.SESSIONS_LONG:
        today = harness.session_date(turns[0], today, year)
        match = STATED.search(turns[0])
        stated = (match[1] or match[2] or "").lower().replace("天", "日") if match else None
        expected = WEEKDAYS[today.weekday()]
        ok = stated is None or stated in expected
        failures += not ok
        print(f"{'ok ' if ok else 'BAD'} {Path(path).stem} {session}: {today.isoformat()} {today.strftime('%A')}"
              f" (stated: {stated or 'no weekday'})")
print("failures:", failures)
sys.exit(1 if failures else 0)
