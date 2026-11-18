# A real host on the resume-after-correction scenario: seven turns on Claude Code

The owner approved one trial on Claude Code with its subscription: Sonnet, at most 12 short turns, a synthetic project, messages as a user would write them, nothing that reminds the host to take notes or names a tool, and no rerun after a failure. Claude Code 2.1.322, headless (`claude -p`, sessions resumed with `--resume`), `claude-sonnet-5-5`, on WSL2, against a frozen copy of runtime `f69d4cda`. Seven turns were used. It closes no release gate.

The questions: was the old decision replaced correctly; which database does a new session go on with; and, asked why, can the host open the source of the correction.

| | Result |
| --- | --- |
| The decision saved, then replaced when corrected | **Yes.** Day 1: a note, citing the user's message. Day 3: a new note with `replaces` naming the old one; the tool answered that it replaced it. |
| The new session goes on with | **SQLite**, against project files that still said PostgreSQL. |
| Asked why, opens the source of the correction | **No.** It answered correctly in words, twice, quoting the user's message and saying it had replaced the earlier decision; it never opened the memory page. |

## What happened, turn by turn

Per-turn summaries with ids, capture tokens and paths removed are in [evidence](evidence/host-trial-2026-11-18/), with the [messages](evidence/host-trial-2026-11-18/messages.txt) as sent.

1. **"Let's get the Tidepool backend going. Decision: we'll use PostgreSQL as the database for the project."** The host looked the note tool up, saved "Tidepool project: decided (2026-11-18) to use PostgreSQL as the database for the backend." with the user's message as its source, and wrote PostgreSQL into the project's README, `.env.example` and requirements. It said it had saved the decision.
2. **"For the frontend packages I prefer pnpm over npm."** A preference note; the README updated.
3. New session. **"Quick correction on the database: only the server uses PostgreSQL; local stays SQLite."** One note: "…PostgreSQL is used only on the server; the local database stays SQLite (corrected 2026-11-18, refines earlier all-PostgreSQL decision)", with `replaces` holding the first note's id. Reply: "I updated the earlier note, which said PostgreSQL for the whole project." It did not touch the project files, which went on saying PostgreSQL.
4. **"Let's sketch the migration for the projects table next."** Two versions unasked, PostgreSQL for the server and SQLite for local.
5. New session. **"finish the local install"**. The session's context held the note with "(replaces your note of 2026-11-18)" and the day-1 message marked "superseded by your note of 2026-11-18". The host read the README and `.env.example`, then said: "The README still says Postgres, but your decision is that local uses SQLite. So I'll skip `createdb`, point `DATABASE_URL` at SQLite, and use pnpm for the frontend." It wrote `backend/.env` with `DATABASE_URL=sqlite:///tidepool.db`. The install commands themselves needed an approval a headless session cannot give, and it said so.
6. **"Why do you think local is SQLite?"** "You told me in an earlier session. Memory has your message from 2026-11-18: 'Quick correction on the database: only the server uses PostgreSQL; local stays SQLite.' That corrected your first decision to use PostgreSQL for the whole project. The project files don't back it up… So the SQLite choice rests only on your word." No page opened.
7. **"Can you show me where I said that?"** It listed the user's four earlier messages from the history block, named the third as the one it relied on, and added: "Memory gives me only the text and the date. It doesn't give me a time of day or a session transcript, so I can't show you the surrounding conversation." No page opened.

## The failure, and its likely cause

The way to open the page at a note (`membrain plugin ui --note <id>`, [added on the same day](basis-link-2026-11-18.md)) is described in one sentence of the plugin's skill. **The host never opened the skill in seven turns**, and the command appears in none of the seven logs: it could not have known. The [trial of 2026-11-13](host-trial-2026-11-13.md) found the same thing about the skill and moved three instructions out of it; this one was put back into it. Turn 7 shows the cost: the host told the user it could not show the conversation, when the page can.

The page itself works on what the real host recorded. Opened by the lead with that command and the corrected note's id, it showed the note, "Replaced an earlier note on 2026-11-18.", the earlier sentence, "Said on 2026-11-18:" with the correction and "The earlier note was based on:" with the decision, each with its conversation link.

Nothing was changed and no further turn was run after turn 7.

## What else it showed

- **Memory against stale project files.** After turn 1 the project said PostgreSQL in three files, and nothing in the project was corrected on day 3. In the new session the host read those files and still followed the user's correction, saying which it was following and why. Asked why, it pointed out that the files do not back the choice and offered to switch back.
- **The host dated its own note text** ("decided (2026-11-18)", "corrected 2026-11-18"), so the note line carried the date three times with the lineage clause.
- **It announces saves** in a clause ("I saved the decision to memory"), as on 2026-11-13.
- **Consolidation ran inside turn 6**, before the answer, and the answer was written once.
- **All three days fell on one calendar day**, so every date in the context was the same and the clause read "replaces your note of 2026-11-18" under a note of 2026-11-18.

## Cost on the host

By the host's own accounting: 0.43 USD for seven turns and 36 model calls (0.16, 0.11 and 0.16 USD for the three sessions). The session context at the start of the third session was 3,734 characters.

## How it was run, and how it differs from an installation

- A copy of the plugin whose hooks and tool server run the frozen runtime copy directly ([difference](evidence/host-trial-2026-11-18/plugin-diff.txt)), loaded with `--plugin-dir`; a new, empty memory with ports of its own, its service started beforehand as on a machine where memBrain is already installed; a synthetic project directory.
- The host's login was the owner's own; nothing else of the owner's configuration or memory was read or written by memBrain. The trial's session records are in the host's own project history for the trial directory.
- Allowed without asking: the plugin's tools, reading and editing files in the project, and `membrain plugin ui`. A `membrain` command was put on the path, as `uv tool install` does in an installation.
- **Found while preparing:** this machine has `uv` but no `uvx`, and every launcher of the plugin begins with "if `uvx` is found" and otherwise does nothing, silently. An installation here would have recorded nothing and said nothing. Not fixed in this record.

## Limits

One run, one model, seven turns, one wording of each message; headless, where every resumed turn runs the session-start hook again; real time, so "last week" was the same day; the project and its files were written for the trial.
