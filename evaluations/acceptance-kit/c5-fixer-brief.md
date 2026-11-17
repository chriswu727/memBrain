# Companion scenario fixer brief

You apply a reviewer's findings to one test scenario for an evaluation of AI companions. `scenario.py` is the
scenario, `findings.md` the reviewer's numbered findings, and `brief.md` this file.

Work only in this directory. Read only these three files. Do not open, list or search anything else on this machine,
do not use the web, and do not run the scenario file.

Apply every finding, blocking and minor, exactly as it asks, and change nothing else: keep every other message,
fact, case, criterion, page action and `COVERAGE` entry word for word. When a finding asks for a change that would
break another rule it quotes, apply the change in the way that keeps that rule. Keep the file a Python module that
only defines `YEAR`, `HOST`, `SESSIONS_LONG`, `FACTS`, `CASES`, `PAGE_ACTIONS`, `COVERAGE` and, if present,
`EXPECT_RECORDING_P`, with plain literal values; keep the 11 cases, the 60 to 66 user messages and the case ids'
prefix and numbering.

Positions refer to messages: a page action is `(session_id, before_turn, {...})` and acts before that user message; a
deletion names its message by `"session"` and `"turn"`; `COVERAGE` names messages as `(session_id, turn_index)`,
cases by id, and page actions as `(session_id, before_turn, kind)`. When you add, remove or move a message, update
every case, page action, `COVERAGE` entry and `EXPECT_RECORDING_P` entry whose turn index it shifts, and keep
`FACTS` in agreement. Keep a "from now on" request and the user's yes in the same session, and keep each session's
first message stating its weekday, date and time in the form it already uses.

Write the corrected file as `scenario.py` in this directory (replacing it), and `fixes.json` as
`{"applied": <number of findings applied>}`. Your final message should say only that both are written. Do not repeat
the scenario's content anywhere else.
