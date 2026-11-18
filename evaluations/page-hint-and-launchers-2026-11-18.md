# After the real-host trial: the page command where a host reads it, and launchers that say when they cannot run

Runtime `b465c4b7`; launcher pin `504156c2`. No migration, no new dependency, no model call of memBrain's own, no new tool, no new control; the server instructions are unchanged (1,388 of 1,400 characters). **It closes no release gate. Neither change has been tried on a real host**; no acceptance run has been made on this runtime.

Both come from the [trial on Claude Code of 2026-11-18](host-trial-2026-11-18.md).

## 1. The host is told how to show where a note came from

In the trial the host was asked "Can you show me where I said that?" and answered that it could not show the conversation. The command that opens the memory page at a note was described only in the plugin's skill, which the host never opened: the same lesson as the [trial of 2026-11-13](host-trial-2026-11-13.md).

The sentence is now in the notes block, which a host is handed at every session start that has notes and where every note's id already is (241 characters):

> If the user asks to see where a note came from (where they said it) or to check it, run membrain plugin ui --note <id>: it opens their memory page at that note, what it replaced and its source messages. Never say you cannot show the source.

- **Only where it can be done:** Claude Code, Codex and WorkBuddy/CodeBuddy. Not OpenClaw, Hermes, chat bots, the proxy, a multi-user installation (the page shows the installation's own memory), a role-play session, or a session without notes.
- **A command that runs.** `membrain` alone when it resolves on the hook's PATH to this runtime's own program; otherwise that program's path, written under `~/` so the user's name stays out of the context. File lookups only; nothing is run in the hook.

### Probe (diagnostic, not a gate)

The diligent world's day-8 context after the change, replayed to the provider's host model (`deepseek-v4-pro`, the plugin's tool schemas plus a shell tool; replies in [evidence](evidence/resume-correction-probe-2026-11-18/show-source-after.json); conservative cost bound 1.67 CNY):

| The user says | The host model | |
| --- | --- | --- |
| "Why do you think local is SQLite?" (English and Chinese) | answers in words, quoting the message; opens nothing | 6 of 6 |
| "Can you show me where I said that?" (English and Chinese) | runs the command with the corrected note's id | 6 of 6 |
| "I want to check that note about the database myself." | runs the command | 3 of 3 |

One model through an emulated host, with every tool schema in view from the start; a real Claude Code host loads tools on demand and has its own instructions.

### The same mistake elsewhere (listed, not fixed)

Instructions a host needs that are only in the skill or only in a tool description it would not have looked up at that moment:

1. **Forgetting.** "Forget that" → find the record, call the forget tool, report exactly what it returned. Only in the skill and in the recall and forget tool descriptions. The risk is a false "I've forgotten it".
2. **Boundaries.** "Don't bring up X" → the boundary tool. Only in the skill and the tool's own description.
3. **The memory page in general**: reviewing everything, exporting, erasing. Only in the skill.

A host sees the tools' names and reads a description when it looks the tool up, so the first two may well work; that has not been seen on a real host.

## 2. Launchers run with `uv` alone, and say when they cannot run

Found while preparing the trial: the machine had `uv` but no `uvx`. Every Claude Code launcher began "if `uvx` is found" and otherwise did nothing; the tool server's command was `uvx`. An installation there would have recorded nothing, recalled nothing, offered no tools, and said nothing.

| | Before | After |
| --- | --- | --- |
| `uv` without `uvx` (Claude Code, Codex, WorkBuddy/CodeBuddy, OpenClaw, the Windows wrapper) | silent; OpenClaw's tools answered "may still be installing" indefinitely | runs through `uv tool run`, which is the same command |
| Neither installed | silent | at session start the agent is told, once: "memBrain is installed but cannot run: uv was not found on this computer, so nothing is remembered or recalled…" and asks the user to install uv and start a new session |
| First session, runtime still installing; or the installation failing | silent | at session start the agent is told the runtime is not ready, that it installs in the background and needs an internet connection the first time, and that seeing this again later means the installation is failing |

The notices are printed by the launcher itself, since the runtime is what is missing; only at session start; exit status 0; no added wait. The pin mechanism is unchanged: the same nine launchers each hold one pinned requirement.

**Still silent, now documented:** Codex before the user trusts the hooks; Claude Code on Windows without Git Bash; WorkBuddy's PowerShell fallback.

## Limits

- **Not tried on a real host**, either change.
- **Windows and macOS were not run.** The `.cmd` wrapper was checked line by line only; two points of its syntax are unverified. The path form of the page command is unverified there, and a Windows path carries the user's folder name.
- The page command relies on the hook and the host's shell sharing the same memory directory setting.
- The not-ready notice appears in every new user's first session, where it is true; it may also appear if a session starts while an upgrade is replacing the runtime.
- The release install check's own helpers still call `uvx` directly and would fail on a machine without it.
- Sessions with notes cost 241 characters more; the companion evaluation's contexts change by the same amount.

## Verification

Local, on Linux under WSL2; nothing was run in CI or on another platform.

| Check | Result | On |
| --- | --- | --- |
| Full source suite | 4,903 passed, none failed, 11 strict expected failures (the resume-after-correction scenario's remaining gaps), 4 skipped (three desktop end-to-end tests that need Docker; one trust case that applies only to a three-note chain), seven Python fork warnings; 57 minutes | `504156c2` (runtime `b465c4b7`, pinned) |
| Launcher tests on the launchers before the change | 38 of 49 fail | `8757aeee` |
