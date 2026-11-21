"""Self-check of the scoring rules on hand-made contexts; needs no memory system. Run: python check_scoring.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kit import Line, Question, Turn, contains, load, score  # noqa: E402

TURNS = [
    Turn("user", "Five days off, a city break by train from Paris."),
    Turn("assistant", "I'd suggest Strasbourg: under two hours on the TGV. Basel and Lyon would also work well."),
    Turn("user", "Not Strasbourg, we did Alsace last year. We've settled on Bordeaux, mostly for the vineyards."),
]
TRIP = Question("trip", "q1", "rejected", "user_decision", "Where did I decide to go?",
                user_statement=("Bordeaux",), unaccepted=("Strasbourg", "Basel", "Lyon"))


def check(name: str, lines: list[Line], **expected) -> None:
    result = score(TRIP, lines, TURNS)
    for key, value in expected.items():
        assert result[key] == value, f"{name}: {key} is {result[key]!r}, expected {value!r}\n{result}"
    print("ok", name)


def main() -> None:
    user_rejection = TURNS[2].text
    suggestion = TURNS[1].text
    # R1 and R4: the user's own words, which name the rejected city, are not a finding.
    check("user words only", [Line("user", user_rejection)], decision_found=True, misattributed=0, passed=True)
    # R8: the suggestion shown as the assistant's is exposure, not an error.
    check("labelled suggestion", [Line("user", user_rejection), Line("assistant", suggestion)],
          passed=True, exposed=3, misattributed=0, unattributed=0)
    # R5: the assistant's words under a user label.
    check("verbatim misattribution", [Line("user", user_rejection), Line("user", suggestion)],
          passed=False, misattributed=3)
    # R6: a rewrite that puts the suggestion in the user's mouth.
    check("rewritten misattribution", [Line("user", "User plans a trip to Basel by train.")],
          passed=False, misattributed=1, decision_found=False)
    # R7: no speaker.
    check("unattributed", [Line("user", user_rejection), Line(None, suggestion)], passed=False, unattributed=3)
    # R1: the decision without a user label does not count as found.
    check("decision without speaker", [Line(None, user_rejection)], decision_found=False, passed=False)
    # Whole words: "Lyon" does not match inside "Lyonnaise".
    assert not contains("a Lyonnaise salad", "Lyon") and contains("Lyon, then home", "Lyon")
    print("ok whole words")
    cases, filler = load()  # Validates the shipped cases.
    print("ok", len(cases), "cases and", len(filler), "filler sessions validate")


if __name__ == "__main__":
    main()
