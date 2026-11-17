"""The coverage line of a C5 assignment file, parsed strictly (launch.py and freeze.py share it).

A C5 scenario covers only the COVERAGE items its assignment names (the pair splits the thirteen between its two
scenarios). The assignment file names them on exactly one line, in this exact form (an optional "- " list marker
first; the items in any order, separated by a comma and one space, nothing after the last):

    - Coverage items: stated_feeling, inferred_feeling, mood, feelings_question

Every item is a key of c5-precheck.py's COVERAGE_FIELDS, each at most once. No other line of the file may contain
the words "coverage items" (case aside). Anything else is refused with a fixed reason, never with the file's text.
Standard library only.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

LINE = re.compile(r"(?:- )?Coverage items: ([a-z_]+(?:, [a-z_]+)*)")
MARK = "coverage items"


class AssignmentError(ValueError):
    """A fixed reason; never the file's text."""


def coverage_fields() -> tuple[str, ...]:
    """The thirteen items, in the precheck's order."""
    path = Path(__file__).resolve().parent.parent / "c5-precheck.py"
    spec = importlib.util.spec_from_file_location("c5_precheck_items_for_assignment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.COVERAGE_FIELDS)


def required_items(text: str) -> tuple[str, ...]:
    """The items an assignment's coverage line names, in its order, or AssignmentError."""
    lines = [line for line in text.splitlines() if MARK in line.casefold()]
    if not lines:
        raise AssignmentError("the assignment has no 'Coverage items:' line")
    if len(lines) > 1:
        raise AssignmentError("the assignment has more than one line naming coverage items")
    match = LINE.fullmatch(lines[0])
    if match is None:
        raise AssignmentError("the assignment's coverage line is not of the form '- Coverage items: item, item'")
    items = tuple(match[1].split(", "))
    known = coverage_fields()
    if any(item not in known for item in items):
        raise AssignmentError("the assignment's coverage line names an item that is not a COVERAGE item")
    if len(set(items)) != len(items):
        raise AssignmentError("the assignment's coverage line names an item twice")
    return items


def read(path: Path) -> tuple[str, ...]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise AssignmentError("the assignment file is unreadable") from None
    return required_items(text)
