# Companion scenario reviewer brief

You review one test scenario written for an evaluation of AI companions: assistants that talk with the same person
over several weeks, remember what they were told, have a personality, keep a simulated mood and build a relationship.
The scenario is `scenario.py` in this directory. The author wrote it from `author-brief.md` and `assignment.md`, both
here; `brief.md` is this file. **Yours is the one full review of this scenario.** Later rounds are verifications: a
verifier checks only that each of your blocking findings was resolved exactly as you instructed and that no fatal
class (below) fails; it may not reopen or reword what you decided. So find everything now, and say exactly what to
change. You do not fix the scenario: a fixer applies your findings word for word.

Work only in this directory. Read only `brief.md`, `author-brief.md`, `assignment.md` and `scenario.py`. Do not open,
list or search anything else on this machine, do not use the web, and do not run the scenario file. Write two files
in this directory: `findings.md` and `review.json`. Your final message should say only that they are written. Do not
repeat the scenario's content anywhere else.

## The rules

`author-brief.md` is the standard: the format, the size, the items (the scenario covers only the items its
assignment names on the line `- Coverage items: ...`, one case each, two for `mood`; the other cases are ordinary
memory cases), what `FACTS` records, what makes a case fair, and the **criteria templates** for the coverage cases.
An automatic check has already passed the file: the format, the counts, the dates and weekdays at the session
starts, the page actions, the `COVERAGE` positions, cases, order and timing, one case per item, and messages that
are too short or open with a common reaction. **You check what it cannot: what the words say.**

The templates are the standard. A coverage case's "must" and "must not" are the template's, with the facts filled
in. Flag a **deviation** from its template (a "must" or "must not" added, dropped or changed in substance, or facts
filled in wrongly), never the template itself: do not ask for a different wording of a template clause, a stricter
or looser test, or a style requirement the template does not have. "Should" and "bonus" clauses are the author's;
flag one only when it is wrong on the facts or demands removed content (F4).

What the words decide, item by item (for the items the assignment names; the item names of `COVERAGE` are
`"stated_feeling"`, `"inferred_feeling"`, `"mood"`, `"feelings_question"`, `"boundary_in_conversation"`,
`"second_boundary"`, `"page_deletion"`, `"reset"`, `"manner_feedback"`, `"from_now_on"`, `"switch"`,
`"shared_moments"` and `"absence"`):
- the stated feeling is stated by the user, and the inferred one is never said;
- no message between the mood news and the later mood case carries news or a feeling;
- the feelings question is sincere and asks about what the user told the companion, not about what it answered;
- each boundary case's own message makes the topic relevant without raising it;
- the deleted message carries emotional or relationship content, which no other message before the case repeats;
- the three manner comments are of the accepted `kind`, never about emoji, none of the opposite kind between them;
- the "from now on" request is about the companion's manner of responding: it is never a task, a reminder, a
  check-in or anything tied to a time or an event ("check in with me before my exams", "quiz me every morning" are
  tasks), and never one of the manner-comment kinds (length, formality, jokes); its case's message is a situation
  that calls for the agreed behaviour;
- the switch names no type; the shared moments are mentioned by the user as shared, one playful and one hard;
- no message names a duration for the off-the-record stretch, and none outside it asks not to be remembered.

## What is blocking: exactly the fatal classes

A finding is **blocking** when, and only when, it is an instance of one of these classes. Everything else is
**minor**, however much you would prefer it changed.

<!-- FATAL-LIST-START -->
- **F1 Reply dependence.** A user message that only makes sense after some reply: it reacts to, thanks for, agrees with,
  laughs at or answers something the companion said, or assumes what it said or did. The one exception is the declared
  "yes" to the "from now on" request.
- **F2 Unjudgeable case.** A case whose criteria cannot be judged from the reply, `FACTS`, the page actions and the
  persona shown: a clause needs a fact `FACTS` does not state, rests on a style word with no visible test, or concerns
  something the case's message gives no occasion for; or `FACTS` contradicts a message or page action the case relies
  on.
- **F3 Wrong coverage.** A `COVERAGE` entry whose message, page action or case is not what its item requires: a stated
  feeling that is not stated, an inferred one the user does say, news or a feeling between the mood news and the later
  mood case, a case that does not test its item or whose own message states the answer.
- **F4 Removed content demanded.** A criteria clause that requires recalling or using what the user deleted, reset,
  cleared or said off the record.
- **F5 Wrong "from now on" kind.** A `from_now_on` request that is a task, a reminder, a check-in or anything tied to a
  time or an event, or a manner-comment kind (length, formality, jokes).
- **F6 Named type or duration.** A user message that names or describes a personality type, or names a duration for a
  pause or for the off-the-record stretch.
- **F7 Date contradiction.** A weekday, date, day count or relative day ("yesterday", "last week", "three days ago") in
  a message, `FACTS` or criteria that contradicts the session dates.
- **F8 Template departure.** A coverage case whose "must" or "must not" differs in substance from its item's criteria
  template (a clause added, dropped or changed in what it requires).
- **F9 Boundary or deletion leak.** A boundary case whose own message raises the boundary topic; what a deleted message
  said appearing in another message before its case, or in the case's own message.
- **F10 A "never" of the author brief.** A user message or `HOST` that mentions the memory page, notes, tools or how the
  companion remembers; a `HOST` that names the companion or gives it a personality; a manner comment about emoji; a
  message outside the off-the-record stretch that asks not to be remembered; crisis or self-harm content; a real public
  figure or a real employer.
<!-- FATAL-LIST-END -->

## How to review: every message, in order

1. **Scan every user message.** Go through `SESSIONS_LONG` in order, session by session, every message, and decide
   for each one whether it is an instance of F1, F6, F7, F9 or F10. Reply dependence (F1) above all: read each
   message as if the reply before it had been one word; if the message then reads oddly (it reacts to, thanks for,
   agrees with, laughs at or answers a reply, or assumes what the companion said, suggested or did), it is F1.
   Thanking the companion for being there ("thank you for staying with me") is not F1; thanking it for advice is.
   List **every** instance, never examples: two messages of the same kind are two findings, or one finding that
   names both with a change for each.
2. **Check every case**, in `CASES` order: its message (F3, F9), its criteria against its item's template (F8) or,
   for an ordinary case, against the general form; that every clause can be judged from `FACTS`, the page actions
   and the persona shown (F2); that no clause demands removed content (F4); that dates and day counts agree (F7).
3. **Check every `COVERAGE` entry** of the assignment's items: its messages, page actions and cases really are what
   the item requires (F3); the `from_now_on` request's kind (F5).
4. **Check `FACTS`** against the messages and page actions (F2, F7), and `HOST` (F10).

## What you write

`findings.md`, in exactly this shape:

```
# Findings

## Message scan
- s01-arrival t0: ok
- s01-arrival t1: F1 (blocking B1)
- ... one line per user message, every message of SESSIONS_LONG in order

## Blocking
B1. [F1] s01-arrival turn 1: "<the words at fault, at most 12>"
    Change: replace the message with: "<the complete new message>"
    Also: <every other place the change touches: a FACTS line (its complete new text), a COVERAGE entry, turn
    indexes; or "nothing else">
B2. ...

## Minor
M1. <place>: <what is wrong>. Change: <what to change>
```

Rules for the findings:
- Number blocking findings B1, B2, ... and minor ones M1, M2, .... Give each blocking finding its fatal class.
- **Every blocking finding states the exact change** so that a fixer can apply it and a verifier can check it
  mechanically: the complete new text of each message, criteria string or `FACTS` line it changes (never "reword it
  so that ..."), or exactly which words to delete, and every other place the change touches. A new message must
  itself pass every rule (no reply dependence, at least 16 characters, no reaction opening); new criteria for a
  coverage case are its template with the facts filled in.
- One change per place: never offer alternatives ("either ... or ...") in a blocking finding.
- Write "None." under a heading with no findings.

`review.json`: `{"approved": true | false, "findings": <number of B and M findings>, "blocking": <number of B
findings>}`. Approve only when there is no blocking finding. Count every finding you wrote.
