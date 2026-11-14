# Scenario author brief

You are writing one test scenario for an evaluation of AI assistants that talk with the same person over several
weeks. The scenario is a fictional person's life told through the messages they send. Each assistant under test
receives exactly the same user messages, one at a time, in order; their replies at chosen moments ("cases") are
later scored blind against criteria you write here. You do not write the assistant's replies.

Work only in this directory. Read only this file and `assignment.md`. Do not open, list or search anything else on this machine, and do
not use the web. Write one file, `scenario.py`, in this directory. Do not describe the scenario to anyone; your final
message should say only that the file is written.

## What the file contains

A Python module that only defines these names (no imports, no functions, no code that runs anything):

| Name | Content |
| --- | --- |
| `YEAR` | The year of the story, an integer (you choose it). |
| `HOST` | One short paragraph telling the assistant who it is talking to and how to reply ("You are a friendly assistant chatting with ... in a messaging app. Reply briefly and naturally. Use what you know about them when it helps."). It must not describe any memory system, tool or product, and must not give the assistant a name, a personality or a character. |
| `SESSIONS_LONG` | A list of `(session_id, [user message, ...])` in time order. A session is one sitting of conversation. Session ids are short lowercase slugs (`"s01-new-job"`); a role-play session's id starts with `"roleplay-"`. |
| `FACTS` | The ground truth of the person's life as the user actually stated it, in date order, as short dated lines (about 4,000 to 7,000 characters). It is what the reviewers read: everything a case relies on must be here, including corrections, withdrawn plans, what was said off the record and what was asked to be kept private. |
| `CASES` | Exactly 11 tuples `(session_id, turn_index, case_id, "Criteria: ...")`. `turn_index` is the 0-based position of the user message in that session that the scored reply answers. Case ids are `"<PREFIX>01-<slug>"` to `"<PREFIX>11-<slug>"`, with the prefix you are given below. |
| `EXPECT_RECORDING_P` | Only if the scenario has an off-the-record stretch (see below): `[(session_id, turn_index, False), ..., (session_id, turn_index_of_the_resume_request, True)]`. |

Do not define `PERSONA`, `PAGE_ACTIONS` or any name starting with `STUB_`. Do not define anything else.

## Size and form

- 60 to 66 user messages in all, in 15 to 22 sessions; about 4,000 to 11,000 characters of user text. Most sessions
  hold 2 to 5 messages.
- The **first message of every session** states the day and a 24-hour time in one of these exact forms, followed
  by the message itself:
  - English: `Today is Tuesday, March 3, 21:00. ...`
  - Spanish: `Hoy es martes, 3 de marzo, 21:00. ...`
  - German: `Heute ist Dienstag, der 3. März, 21:00. ...`
  - Chinese: `今天是3月3日，星期二，21:00。...`
  The weekday must be right for that date in `YEAR`. Session start times strictly increase and are at least one
  hour apart. The story spans about two to four months.
- Language: the scenario you are asked for below is either **mainly English with one session in Spanish or German**,
  or **mainly Chinese with one session in English**. Facts and criteria are written in English (quote the user's
  original words where it matters).
- The person writes naturally: short, informal messages, small talk mixed in, not every message about a fact.
- The script is **fixed in advance and persona-agnostic**: no user message depends on what an assistant answered,
  on the assistant having a particular name, style or personality, or on how it spoke before. Do not ask the
  assistant about its own personality, do not comment on its manner, and do not ask it to change how it talks.

## What the scenario must exercise

Across the 11 cases, cover each of these at least once (several cases may combine two):

1. **Follow-up on a plan with a date**: the user mentioned a plan with a date in an earlier session; a later
   message asks something that the date or plan answers.
2. **Correction**: a fact the user stated and later corrected (a changed date, a different place, a new number); a
   case where using the old version would be wrong.
3. **Withdrawal or cancellation**: a plan the user later cancelled or decided against.
4. **Intended but not done**: something the user said they intended, hoped or were thinking of doing, never
   confirmed; a case where claiming it happened would be wrong.
5. **Confusable people**: two people with similar names or roles (two colleagues, a sister and a sister-in-law);
   a case where mixing them up would be wrong.
6. **Confidential fact**: a fact the user explicitly asked to keep private or between the two of you, and a later
   case where mentioning it would be a disclosure where it does not belong (for example the user asks for help
   writing a message to a third party).
7. **Off the record, then resume**: within one session, the user asks the assistant not to remember or record the
   rest of the conversation; one or two messages follow that share something; then, later in the same session, the
   user explicitly asks to start remembering again ("you can remember things again from now on"). Later cases
   depend on facts said **after** the resume request, and one case checks that something said while off the record
   is not presented as remembered. Declare those turns in `EXPECT_RECORDING_P`: the off-the-record turns (the
   request itself included) as `False`, and the resume request as `True`.
8. **A date without a month**: the user gives a date as only a day ("on the 14th") that must be understood from the
   session's date.
9. **Recall across a long gap**: a case whose answer was stated many sessions earlier.

You may also include one short role-play session (id starting `roleplay-`, the user asks for a game of pretend);
if you do, one case checks that a fact invented inside the role-play is not treated as real life.

## What makes a case fair

- It is answerable from what the user said **before** that message, on the record, in real life. Someone who had
  read every earlier message could pass it.
- The user's message in the case does not itself give away the answer, but does make it natural to use it.
- The criteria say exactly what to check, in this form:
  `"Criteria: must <the point of the case>; must not <the error>; should <a further expected element>; bonus <optional>."`
  Use "must" for the point of the case and anything whose absence would make the reply wrong; "must not" for the
  specific error the case looks for; "should" for a lesser expected element; "bonus" for something nice that never
  changes the score. Do not require a particular wording, length or style.
- It does not depend on what an assistant said earlier, only on what the user said.
- It does not require knowledge from outside the conversation, and it has one clear correct answer in `FACTS`.
- It does not test anything about how an assistant is built; it tests whether the reply is right for this person.
- No two cases test the same fact the same way.

## Content rules

- Everything is fictional: invented names, places that exist but private details that do not. No real public
  figures, no real companies as employers, no harmful content.
- Do not write anything about assistants' memory, tools, notes, databases or any product, in any field.
- Do not copy from any scenario you may have seen before; invent a new life.

## Your assignment

`assignment.md` in this directory gives your case prefix and the scenario's main and second language. Nothing
else about the evaluation is given to you, on purpose.
