# Scenario fixer brief

You apply a reviewer's findings to one test scenario for an evaluation of AI assistants. `scenario.py` is the
scenario, `findings.md` the reviewer's numbered findings, and `brief.md` this file.

Work only in this directory. Read only these three files. Do not open, list or search anything else on this machine,
do not use the web, and do not run the scenario file.

Apply every finding, blocking and minor, exactly as it asks, and change nothing else: keep every other message,
fact, case and criterion word for word. When a finding asks for a change that would break another rule it quotes,
apply the change in the way that keeps that rule. Keep the file a Python module that only defines `YEAR`, `HOST`,
`SESSIONS_LONG`, `FACTS`, `CASES` and, if present, `EXPECT_RECORDING_P`; keep the 11 cases, the 60 to 66 user
messages and the case ids' prefix.

Write the corrected file as `scenario.py` in this directory (replacing it), and `fixes.json` as
`{"applied": <number of findings applied>}`. Your final message should say only that both are written. Do not repeat
the scenario's content anywhere else.
