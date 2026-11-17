# Companion scenario verifier brief

You verify one test scenario written for an evaluation of AI companions: assistants that talk with the same person
over several weeks, remember what they were told, have a personality, keep a simulated mood and build a
relationship. The scenario is `scenario.py` in this directory. The author wrote it from `author-brief.md` and
`assignment.md`, both here; `brief.md` is this file. It has had **one full review** (`findings-1.md`), then fixes,
and possibly earlier verifications (`findings-2.md`, ...); `fixes-N.json` are the fixers' records and `rounds.md`
lists every step in order. **You do not review the scenario again.** You do three things only, and approve when the
first two find nothing.

Work only in this directory. Read only `brief.md`, `author-brief.md`, `assignment.md`, `scenario.py`, `rounds.md` and
the `findings-*.md` and `fixes-*.json` files. Do not open, list or search anything else on this machine, do not use
the web, and do not run the scenario file. Write two files in this directory: `findings.md` and `review.json`. Your
final message should say only that they are written. Do not repeat the scenario's content anywhere else.

## 1. Every earlier blocking finding: resolved as instructed?

For each blocking finding (B1, B2, ...) of every earlier `findings-*.md`, check the current `scenario.py`:
- **Resolved** when the change the finding gave is in the file: the new text it gave, word for word (punctuation,
  a turn index the change shifted, or the facts of a template aside), and the other places it named.
- **Not resolved** when the change is missing or the file has something else in its place. Then write a blocking
  finding that repeats the earlier instruction exactly ("findings-1.md B3, not resolved: ...").
- **The earlier instruction stands.** You may not reopen it, prefer another wording, ask for more, or judge whether
  it was a good decision. A change that is in the file is resolved even if you would have written it differently.
- If a later finding replaced the same place, the earlier one is resolved when the place no longer has the fault it
  named.
- If an instructed change itself fails a fatal class below, report that under 2 (blocking) with the smallest change
  that removes the fault and keeps the rest of the instruction.

Minor findings (M1, ...) and earlier advisory notes are not checked.

## 2. The fatal classes, over the whole file

Fixes can break what was fine before, so check the **whole** file, every round, for these classes, and only these.
The criteria templates of `author-brief.md` are the standard: a coverage case's "must" and "must not" are its
template's with the facts filled in (F8 flags a departure from the template, never the template itself).

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

Go through `SESSIONS_LONG` in order and decide for **every** user message whether it is an instance of F1, F6, F7,
F9 or F10 (read each as if the reply before it had been one word: if it then reads oddly, it is F1); then every case
(F2, F3, F4, F7, F8, F9), every `COVERAGE` entry (F3, F5), `FACTS` (F2, F7) and `HOST` (F10). List every instance, not
examples. An instance that an earlier round's reviewer saw and did not mark blocking is still blocking here if it is
one of these classes.

## 3. Anything else: advisory

Anything else you notice (a better wording, a weak "should", a minor gap in `FACTS`) goes under **Advisory**. An
advisory note never blocks and is not applied by the fixer.

## What you write

`findings.md`, in exactly this shape:

```
# Verification

## Earlier blocking findings
- findings-1.md B1: resolved
- findings-1.md B2: not resolved (blocking B1 below)
- ... one line for each blocking finding of every earlier findings file

## Message scan
- s01-arrival t0: ok
- ... one line per user message, every message of SESSIONS_LONG in order

## Blocking
B1. [findings-1.md B2, not resolved] <place>: <the earlier instruction, repeated exactly>
B2. [F1] s04-straight-question turn 2: "<the words at fault, at most 12>"
    Change: replace the message with: "<the complete new message>"
    Also: <every other place the change touches, or "nothing else">

## Advisory
A1. <place>: <note>
```

Every blocking finding states the exact change, as a reviewer's does: the complete new text of each message,
criteria string or `FACTS` line it changes, or exactly which words to delete, and every other place it touches; one
change per place, no alternatives. A new message must itself pass every rule; new criteria for a coverage case are
its template with the facts filled in. Write "None." under a heading with nothing in it.

`review.json`: `{"approved": true | false, "findings": <number of B and A findings>, "blocking": <number of B
findings>}`. **Approve exactly when** no earlier blocking finding is unresolved and no fatal class fails: then
`blocking` is 0 and `approved` is true, whatever the advisory notes say.
