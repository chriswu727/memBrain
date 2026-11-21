"""Speaker-attribution test for agent memory: cases, the adapter contract and model-free scoring.

A memory system is given scripted conversations in which the assistant proposes something and the user accepts,
rejects, corrects or ignores it. Later, in a new conversation, it is asked for the memory context of a question
such as "what did I decide about X?". The scorer reads that context, line by line, and checks two things:

1. whether the user's actual statement is there, attributed to the user;
2. whether a suggestion the user did not accept is there presented as something the user said, or with no
   speaker at all.

No model is called. The rules are stated exactly in ``SCORING_RULES`` below and in the report; their blind spots
are listed there too. Nothing in this file depends on memBrain: adapters live in their own modules.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

HERE = Path(__file__).resolve().parent
KINDS = ("rejected", "corrected", "adopted", "ignored")
ASKS = ("user_decision", "assistant_suggestion")
WINDOW = 20  # Characters kept on each side of a phrase when checking that a line copies a stored turn.


# Data ---------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Turn:
    role: str  # "user" or "assistant"
    text: str


@dataclass(frozen=True)
class Session:
    id: str  # Unique across the whole kit; adapters may use it as the conversation identifier.
    date: str  # ISO date the conversation is set on. Systems that record wall-clock time may ignore it.
    turns: tuple[Turn, ...]


@dataclass(frozen=True)
class Question:
    case: str
    id: str
    kind: str  # The case's kind: how the user answered the assistant.
    asks: str  # "user_decision" or "assistant_suggestion"
    text: str
    user_statement: tuple[str, ...] = ()
    adopted: tuple[str, ...] = ()
    assistant_statement: tuple[str, ...] = ()
    unaccepted: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.case}/{self.id}"


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    sessions: tuple[Session, ...]
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class Line:
    """One line of a context, with the speaker a reader of the context would take it to be from.

    ``speaker`` is "user", "assistant" or None. None means the context does not say who said it (or names some
    other source, such as a note or a tool).
    """
    speaker: str | None
    text: str


def load(path: Path = HERE / "cases.json", distractors: Path | None = HERE / "distractors.json"
         ) -> tuple[list[Case], list[Session]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = []
    for item in data["cases"]:
        sessions = tuple(Session(f"{item['id']}-s{number}", session["date"],
                                 tuple(Turn(turn["role"], turn["text"]) for turn in session["turns"]))
                         for number, session in enumerate(item["sessions"], 1))
        questions = tuple(Question(item["id"], question["id"], item["kind"], question["asks"], question["text"],
                                   tuple(question.get("user_statement", ())), tuple(question.get("adopted", ())),
                                   tuple(question.get("assistant_statement", ())),
                                   tuple(question.get("unaccepted", ())))
                          for question in item["questions"])
        cases.append(Case(item["id"], item["kind"], sessions, questions))
    filler = []
    if distractors is not None:
        for item in json.loads(Path(distractors).read_text(encoding="utf-8"))["sessions"]:
            filler.append(Session(f"filler-{item['id']}", item["date"],
                                  tuple(Turn(turn["role"], turn["text"]) for turn in item["turns"])))
    validate(cases, filler)
    return cases, filler


# Matching -----------------------------------------------------------------------------------------------------------

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                         " ": " "})


def normalize(text: str) -> str:
    """Lower case, Unicode NFKC, straight quotes and dashes, single spaces."""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_QUOTES).lower().split())


def _pattern(phrase: str) -> re.Pattern:
    return re.compile(r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)")


def contains(text: str, phrase: str) -> bool:
    """``phrase`` occurs in ``text`` as whole words, after both are normalized."""
    return bool(_pattern(phrase).search(normalize(text)))


def windows(turn_text: str, phrase: str) -> list[str]:
    """The phrase with up to ``WINDOW`` characters of its turn on each side, for every occurrence in the turn."""
    flat = normalize(turn_text)
    return [flat[max(0, match.start() - WINDOW):match.end() + WINDOW] for match in _pattern(phrase).finditer(flat)]


def copies(line: str, turn_text: str, phrase: str) -> bool:
    """The line reproduces the stored turn around the phrase: the line is that turn's words, not a rewrite."""
    flat = normalize(line)
    return any(window in flat for window in windows(turn_text, phrase))


# Validation ---------------------------------------------------------------------------------------------------------

def validate(cases: list[Case], filler: list[Session]) -> None:
    """Refuse a case file whose phrases could not be scored unambiguously. Raises ValueError listing every problem.

    - every scored phrase occurs where it is supposed to come from: a user statement in a user turn of its case,
      an adopted, assistant or unaccepted phrase in an assistant turn of its case;
    - a user statement does not also occur in an assistant turn of its case, unless the case is "adopted" (where
      the user repeats the assistant's words on purpose);
    - no scored phrase occurs in another case or in a filler session, so a shared memory stays unambiguous.
    """
    problems, ids = [], set()
    for case in cases:
        if case.id in ids:
            problems.append(f"{case.id}: duplicate case id")
        ids.add(case.id)
        if case.kind not in KINDS:
            problems.append(f"{case.id}: unknown kind {case.kind!r}")
        users = [turn.text for session in case.sessions for turn in session.turns if turn.role == "user"]
        assistants = [turn.text for session in case.sessions for turn in session.turns if turn.role == "assistant"]
        roles = {turn.role for session in case.sessions for turn in session.turns}
        if not roles <= {"user", "assistant"}:
            problems.append(f"{case.id}: roles must be user or assistant")
        others = [turn.text for other in cases if other.id != case.id for session in other.sessions
                  for turn in session.turns] + [turn.text for session in filler for turn in session.turns]
        for question in case.questions:
            where = question.key
            if question.asks not in ASKS:
                problems.append(f"{where}: unknown asks {question.asks!r}")
            if question.asks == "assistant_suggestion" and not question.assistant_statement:
                problems.append(f"{where}: an assistant_suggestion question needs assistant_statement")
            for phrase in question.user_statement:
                if not any(contains(text, phrase) for text in users):
                    problems.append(f"{where}: user statement {phrase!r} is in no user turn")
                if case.kind != "adopted" and any(contains(text, phrase) for text in assistants):
                    problems.append(f"{where}: user statement {phrase!r} is also in an assistant turn")
            for name in ("adopted", "assistant_statement", "unaccepted"):
                for phrase in getattr(question, name):
                    if not any(contains(text, phrase) for text in assistants):
                        problems.append(f"{where}: {name} phrase {phrase!r} is in no assistant turn")
            for phrase in (*question.user_statement, *question.adopted, *question.assistant_statement,
                           *question.unaccepted):
                if any(contains(text, phrase) for text in others):
                    problems.append(f"{where}: phrase {phrase!r} also occurs outside its case")
    if problems:
        raise ValueError("Invalid cases:\n" + "\n".join(problems))


# The adapter contract -----------------------------------------------------------------------------------------------

class Adapter(Protocol):
    """What a memory system must implement to be tested. See README.md for the full contract."""

    name: str

    def reset(self, workdir: Path) -> None:
        """Start a new, empty memory. Anything it writes to disk goes under ``workdir``, a directory the runner
        created for this run and may delete afterwards."""

    def ingest(self, session: Session) -> None:
        """Record one conversation, turn by turn in order, the way the system records a live conversation."""

    def ready(self) -> None:
        """Called once after the last session is ingested. Finish any indexing or background processing so that
        the contexts that follow are stable. Questions must not be stored as new memories."""

    def context(self, question: str, *, budget: int) -> str:
        """The memory text a host model would be given for ``question`` at the start of a new conversation, at most
        ``budget`` characters. The runner cuts anything longer before scoring."""

    def attribute(self, context: str) -> list[Line]:
        """Split ``context`` into lines and give, for each, the speaker the text itself shows. A speaker counts only
        if a reader of the context could see it, on the line or in the header of the block that holds the line."""

    def close(self) -> None:
        """Stop anything ``reset`` started."""


# Scoring ------------------------------------------------------------------------------------------------------------

SCORING_RULES = """\
Each question is scored against the lines the adapter's attribute() returns for the context, after the runner has
cut the context to the budget. A line whose text is not in the context is ignored. All matching is on normalized
text (lower case, NFKC, straight quotes, single spaces) and on whole words.

R1  user statement found: every user_statement phrase occurs in a line attributed to the user.
R2  adopted content found: every adopted phrase occurs in a line attributed to the user or to the assistant.
R3  suggestion recalled (assistant_suggestion questions): every assistant_statement phrase occurs in a line
    attributed to the assistant.
For each unaccepted phrase in each line that contains it:
R4  the line copies a user turn around the phrase (the user's own words, such as "not Strasbourg"): no finding.
R5  otherwise, attributed to the user, copying an assistant turn around the phrase: misattributed (verbatim).
R6  otherwise, attributed to the user: misattributed (rewritten); listed for review, see blind spots.
R7  otherwise, with no speaker: unattributed.
R8  otherwise, attributed to the assistant: shown as the assistant's; not an error, counted as exposure.
A question passes when R1 and R2 hold (user_decision) or R3 holds (assistant_suggestion), and no line is
misattributed or unattributed. A user_decision question with no user_statement or adopted phrase (the user never
said anything on the topic) passes on R5 to R7 alone.
"""


def score(question: Question, lines: list[Line], turns: list[Turn]) -> dict:
    """Apply ``SCORING_RULES`` to one question. ``turns`` are every stored turn, used for R4 and R5."""
    users = [turn.text for turn in turns if turn.role == "user"]
    assistants = [turn.text for turn in turns if turn.role == "assistant"]

    def found(phrase: str, speakers: set) -> bool:
        return any(line.speaker in speakers and contains(line.text, phrase) for line in lines)

    missing_user = [phrase for phrase in question.user_statement if not found(phrase, {"user"})]
    missing_adopted = [phrase for phrase in question.adopted if not found(phrase, {"user", "assistant"})]
    missing_assistant = [phrase for phrase in question.assistant_statement if not found(phrase, {"assistant"})]
    findings = []
    for line in lines:
        for phrase in question.unaccepted:
            if not contains(line.text, phrase):
                continue
            if any(copies(line.text, text, phrase) for text in users if contains(text, phrase)):
                continue  # R4
            if line.speaker == "user":
                verbatim = any(copies(line.text, text, phrase) for text in assistants if contains(text, phrase))
                kind = "misattributed_verbatim" if verbatim else "misattributed_rewritten"  # R5, R6
            elif line.speaker is None:
                kind = "unattributed"  # R7
            else:
                kind = "attributed_to_assistant"  # R8
            findings.append({"phrase": phrase, "kind": kind, "line": line.text})
    decision = None
    if question.asks == "user_decision" and (question.user_statement or question.adopted):
        decision = not missing_user and not missing_adopted
    suggestion = (not missing_assistant) if question.asks == "assistant_suggestion" else None
    bad = [item for item in findings if item["kind"] != "attributed_to_assistant"]
    return {
        "decision_found": decision,
        "suggestion_found": suggestion,
        "missing_user_statement": missing_user,
        "missing_adopted": missing_adopted,
        "missing_assistant_statement": missing_assistant,
        "misattributed": sum(item["kind"].startswith("misattributed") for item in findings),
        "unattributed": sum(item["kind"] == "unattributed" for item in findings),
        "exposed": sum(item["kind"] == "attributed_to_assistant" for item in findings),
        "findings": findings,
        "passed": decision is not False and suggestion is not False and not bad,
    }


def verified_lines(adapter: Adapter, context: str) -> tuple[list[Line], int]:
    """The adapter's lines that really occur in the context, and how many it returned that do not."""
    flat = normalize(context)
    lines = [line for line in adapter.attribute(context) if normalize(line.text)]  # Blank lines say nothing.
    kept = [line for line in lines if normalize(line.text) in flat]
    return kept, len(lines) - len(kept)


# Grouping questions for a run -------------------------------------------------------------------------------------

def all_turns(cases: list[Case], filler: list[Session]) -> list[Turn]:
    return [turn for case in cases for session in case.sessions for turn in session.turns] + [
        turn for session in filler for turn in session.turns]


def shared_sessions(cases: list[Case], filler: list[Session]) -> list[Session]:
    """Every case and filler session in date order (ties keep file order), as one person's history."""
    sessions = [session for case in cases for session in case.sessions] + list(filler)
    return sorted(sessions, key=lambda session: session.date)


@dataclass
class Summary:
    rows: list[dict] = field(default_factory=list)

    def table(self) -> str:
        """Markdown table: one column per (mode, arm) in the rows, in the order first seen."""
        columns = []
        for row in self.rows:
            if (row["mode"], row["arm"]) not in columns:
                columns.append((row["mode"], row["arm"]))

        def pick(column, keep):
            return [row for row in self.rows if (row["mode"], row["arm"]) == column and keep(row)]

        def share(items, test):
            return f"{sum(map(test, items))}/{len(items)}" if items else "-"

        decision = lambda row: row["asks"] == "user_decision" and row["decision_found"] is not None  # noqa: E731
        measures = [
            ("Questions passed", lambda row: True, lambda row: row["passed"]),
            ("User decision found (R1, R2)", decision, lambda row: row["decision_found"]),
            *[(f"  {kind}", lambda row, kind=kind: decision(row) and row["kind"] == kind,
               lambda row: row["decision_found"]) for kind in KINDS],
            ("Assistant suggestion recalled when asked (R3)", lambda row: row["asks"] == "assistant_suggestion",
             lambda row: row["suggestion_found"]),
            ("Questions with a suggestion attributed to the user (R5, R6)", lambda row: True,
             lambda row: row["misattributed"] > 0),
            ("Questions with a suggestion shown without a speaker (R7)", lambda row: True,
             lambda row: row["unattributed"] > 0),
            ("Questions with a suggestion shown as the assistant's (R8)", lambda row: True,
             lambda row: row["exposed"] > 0),
        ]
        header = "| | " + " | ".join(f"{mode}: {arm}" for mode, arm in columns) + " |"
        out = [header, "| --- |" + " --- |" * len(columns)]
        for label, keep, test in measures:
            out.append(f"| {label} | " + " | ".join(share(pick(column, keep), test) for column in columns) + " |")
        sizes = []
        for column in columns:
            items = pick(column, lambda row: True)
            sizes.append(str(round(sum(row["characters"] for row in items) / len(items))) if items else "-")
        out.append("| Mean context characters | " + " | ".join(sizes) + " |")
        return "\n".join(out)
