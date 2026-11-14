# Scenario reviewer brief

You review one test scenario written for an evaluation of AI assistants that talk with the same person over several
weeks. The scenario is `scenario.py` in this directory; `brief.md` is this file. The author worked from a brief whose
rules are restated below. You do not fix the scenario: you list what must change. Another session applies your
findings, and you or another reviewer may check the result.

Work only in this directory. Read only `brief.md` and `scenario.py`. Do not open, list or search anything else on
this machine, do not use the web, and do not run the scenario file. Write two files in this directory:
`findings.md` and `review.json`. Your final message should say only that they are written. Do not repeat the
scenario's content anywhere else.

## The rules the scenario must meet

**Form.** A Python module defining only `YEAR`, `HOST`, `SESSIONS_LONG`, `FACTS`, `CASES` and, when the scenario
has an off-the-record stretch, `EXPECT_RECORDING_P`. No imports, no functions, no `PERSONA`, no `PAGE_ACTIONS`, no
name starting with `STUB_`.
- `HOST` is one short paragraph saying who the assistant talks to and to reply briefly and naturally. It names no
  memory system, tool or product and gives the assistant no name, personality or character.
- `SESSIONS_LONG`: `(session_id, [user messages])` in time order, 15 to 22 sessions, 60 to 66 user messages in all.
  The first message of every session states the weekday, date and a 24-hour time in one of these forms, and the
  weekday is right for the date in `YEAR`: `Today is Tuesday, March 3, 21:00.`, `Hoy es martes, 3 de marzo, 21:00.`,
  `Heute ist Dienstag, der 3. März, 21:00.`, `今天是3月3日，星期二，21:00。`. Start times strictly increase and are
  at least one hour apart. A role-play session's id starts with `roleplay-`.
- `CASES`: exactly 11 `(session_id, turn_index, case_id, "Criteria: ...")`, each pointing at a real user message
  (0-based turn index), with unique ids `<PREFIX>01-<slug>` to `<PREFIX>11-<slug>`.
- `EXPECT_RECORDING_P`: every off-the-record turn (the request itself included) as `False`, then the resume request
  as `True`, all in the same session.
- Language: mainly English with one session in Spanish or German, or mainly Chinese with one session in English.

**Persona-agnostic script.** No user message depends on an assistant's earlier reply, name, style or personality;
the user never asks about the assistant's personality or comments on how it talks.

**Coverage across the 11 cases** (one case may cover two): a follow-up on a dated plan; a corrected fact; a
cancelled or withdrawn plan; an intention never confirmed as done; two confusable people; a confidential fact
whose disclosure would be wrong in a later case; an off-the-record stretch in one session followed by an explicit
request to remember again, with later cases depending on facts said after the resume and one case checking that an
off-the-record fact is not presented as remembered; a date given only as a day of the month; recall across a long
gap. Optionally one role-play session and a case checking that an invented role-play fact is not treated as real.

**Fair cases.** For each case check that:
- it is answerable from what the user said before that message, on the record and in real life, so that someone
  who had read every earlier user message could pass it;
- the case's own message does not give the answer away but makes it natural to use;
- the criteria use "must", "must not", "should" and "bonus" as defined: "must" for the point of the case, "must not"
  for the specific error, "should" for a lesser element, "bonus" never changes the score; they require no wording,
  length or style;
- it depends only on what the user said, never on what an assistant said earlier;
- it has one clear correct answer that `FACTS` states, and `FACTS` agrees with the messages (dates, names, numbers,
  corrections, what was off the record and what was asked to be kept private);
- it tests what is right for this person, not how an assistant is built.

**Content.** Fictional; no real public figures or real employers; nothing harmful; nothing about assistants'
memory, tools, notes or any product in any field.

## What you write

`findings.md`: a numbered list. Each finding names the place (session id and turn, case id, or field), what is wrong,
the rule it breaks, and exactly what to change. Mark a finding **blocking** when the scenario cannot be used without
it (a broken rule above, an unfair case, a contradiction between `FACTS` and the messages); otherwise **minor**.
Write "No findings." when there are none.

`review.json`: `{"approved": true | false, "findings": <number of findings>, "blocking": <number of blocking
findings>}`. Approve only when there is no blocking finding. Count every finding you wrote.
