# A real host, second time: showing the source works; forgetting does not

The owner allowed real-host checks with Sonnet for the week. Claude Code 2.1.322, headless (`claude -p`, sessions resumed with `--resume`), `claude-sonnet-5-5`, on WSL2, against a frozen copy of runtime `b465c4b7`, a new empty memory and the same synthetic project as the [trial of 2026-11-18](host-trial-2026-11-18.md). Eight turns, user messages as a user would write them, nothing naming a tool, no rerun after the failure. It closes no release gate.

| The user says | Result |
| --- | --- |
| "Can you show me where I said that?" | **Works.** The host ran `membrain plugin ui --note` with the corrected note's id and told the user what the page shows. This failed on 2026-11-18; the [sentence added to the notes block](page-hint-and-launchers-2026-11-18.md) is what changed. |
| "And please don't bring up Docker with me again." | **Works.** The host looked the boundary tool up by name and saved the topic with four other words for it; it told the user the boundary can be removed on the memory page. |
| "Forget what I told you about pnpm. I don't want that kept." | **Fails.** The note and the message were still stored afterwards. |

The first five turns repeated the earlier trial and gave the same result: the decision saved as a note, replaced when corrected, and a new session going on with SQLite against project files that still said PostgreSQL. Asked why, the host answered in words and opened nothing, as intended.

## The failure

Per-turn summaries with ids, tokens and paths removed are in [evidence](evidence/host-recheck-2026-11-19/); the messages are in [messages.txt](evidence/host-recheck-2026-11-19/messages.txt).

The host found `memory_forget` by its name and tried three times:

1. With the note's id (from the notes block), `kind` "memories", an expected scope generation of 0: refused, and shown to the host as a bare HTTP 422 with a link to a page about HTTP status codes.
2. It looked `memory_inspect` up and asked about the id: "not found". A note is stored as an event, not as a "memory"; the tool leaves it to the caller to know that.
3. `memory_forget` again with the generation it had learned from the inspect answer: "completed", a deletion id, "recall blocked", and nothing affected.

The host then told the user the truth: "The server says it completed, but it also reports 0 objects affected, so I can't confirm the note was erased… The message where you first said it … may also still sit in your raw history. I haven't touched that message." So the feared outcome, a false "I've forgotten it", did not happen. The request was still not carried out.

The cause is the tool, not the host: it is a low-level contract (ids of the right kind, a scope generation, a mode); the way to use it is written only in the plugin's skill, which a real host does not open; a request that matches nothing completes; and a refusal arrives as an HTTP error. A test had shown a host forgetting a message and its note, but that test followed the skill step by step.

Nothing was changed and no further turn was run. The fix is in progress and will be checked on a real host.

## What else it showed

- **The link went into the reply.** With no browser to open in this environment, the host pasted the single-use link (valid for two minutes) into its answer and said it would open a new one if it had expired.
- **The boundary's other words** ("containers", "docker compose", "Dockerfile", "container images") were the host's own choice, wider than what the user said.
- **A personality announcement closed the first work reply** again ("PostgreSQL is now wired into the Tidepool backend… 🌊"), with the type's emoji.

## Cost on the host

By the host's own accounting: 0.56 USD for eight turns and 45 model calls over four sessions.

## How it was run

As on 2026-11-18: a copy of the plugin whose hooks and tool server run the frozen runtime directly ([difference](evidence/host-recheck-2026-11-19/plugin-diff.txt)), loaded with `--plugin-dir`; a new memory with its own ports, its service started beforehand; the owner's own host login, nothing else of the owner's configuration or memory read or written by memBrain; the plugin's tools, file reads and edits in the project and `membrain plugin ui` allowed without asking; a `membrain` command on the path.

## Limits

One run, one model, one wording of each message; headless; all sessions on one calendar day; a synthetic project.
