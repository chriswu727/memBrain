# Forgetting from the agent, project labels, and the documented install command, on a real host

Runtime `6106561a`; launcher pin: the commit that adds this record. No migration, no new dependency, no model call of memBrain's own, no new tool, no new control. **It closes no release gate**, and no acceptance run has been made on this runtime.

Two changes and three checks on Claude Code 2.1.322 (headless, `claude-sonnet-5-5`, WSL2; eight turns in all, 0.58 USD by the host's accounting; user messages as a user would write them).

## 1. "Forget what I told you" now forgets

On [2026-11-19](host-recheck-2026-11-19.md) a real host asked to forget a statement called the forget tool three times and nothing was erased. The tool was a low-level contract: ids of the right kind, a scope generation, a mode; its use was described only in the plugin's skill; a request that matched nothing "completed"; a refusal arrived as an HTTP status.

- **One call with what a host has.** A note's id from the notes block: the note, the notes it replaced, the user's own message it was drawn from and the agent's reply to it are erased. A message's id: the message, the reply and every note drawn from either. No id: `query` returns candidates and erases nothing.
- **It does not sweep what was not asked for.** A source message that also supports another current note is kept, and the answer names it and how to erase both.
- **What goes with it is computed once.** The plan, the tool's answer, the memory page's question and the erasure all use the same dependency walk.
- **An answer the host can repeat:** "Forgotten for good: the note of D; the message it came from, said on D; your reply to it. Do not keep using it from earlier in this conversation." Nothing matched is a refusal that says what to do next. Every error is a sentence.
- **Fewer tools.** Plugin hosts are offered 9 tools instead of 14: the five low-level tools, which no real-host trial saw used well, are kept for a tools-only connection. The schemas a session is sent go from 17,290 to 14,009 characters.

### On a real host (five turns, scenario `host-trial/scenarios/forget.json`, [evidence](evidence/host-trial-forget-2026-11-21/))

| The user says | What happened |
| --- | --- |
| "For the frontend packages I prefer pnpm over npm." | A preference note. |
| "…Decision: we'll use PostgreSQL as the database for the project." | A note on the decision. |
| New session: "Forget what I told you about pnpm. I don't want that kept." | A first call with no arguments was refused with a sentence; the second, with the note's id, erased the note, the message and the reply. The host said: "I deleted the pnpm preference note, the message it came from, and my reply to it… The Tidepool/PostgreSQL note is still saved." |
| "Which package manager should the frontend use?" | "I don't have a package manager preference on record for you…" |
| New session: "What's left to do on the frontend?" | Nothing about pnpm was handed to the session by memBrain; the database decision was. |

All seven checks passed: the records named are gone from the service; the user's own message is no longer stored; no pnpm note; the request to forget is itself not kept; the other decision is untouched.

**A boundary this showed.** In the last turn the host said "the package manager is pnpm, per the README". On day 1 it had written the preference into the project's own README. Forgetting erases memBrain's memory; it does not go back over what the agent wrote into the user's project.

## 2. A second project is told apart

One memory per user serves every project. Before this change a session in project Harbor was handed project Tidepool's database note with nothing saying where it came from. Now each recorded message carries the project folder's name (never the path); a line from another project is marked "· in Tidepool" with one sentence explaining the mark; the current project's lines come first, and nothing is hidden. The record is [workspaces](workspaces-2026-11-19.md).

Replayed by the lead to the provider's host model (`deepseek-v4-pro`, twelve replies each side, read not scored blind; [evidence](evidence/workspaces-probe-2026-11-21/)): asked to "finish the local install" in Harbor, where MySQL was decided, every reply before the change mentioned Tidepool's SQLite and two of four mentioned MySQL; after it, four of four used MySQL and none SQLite. In a project never seen, three of four named no database; one said "assuming Lantern follows your local-SQLite setup". **Not tried on a real host:** the trial tool has one working directory per trial.

## 3. The documented install command, from a clean seat

`claude plugin install membrain --marketplace chriswu727/membrain` had never been run on a real host. In an empty Claude configuration directory it added the marketplace and installed the plugin, whose launchers point at the pinned runtime. Then three turns with that plugin unmodified, uv's tool directories and memBrain's data directory redirected into a sandbox ([evidence](evidence/host-trial-install-2026-11-21/)):

| Turn | What happened |
| --- | --- |
| 1, runtime not installed yet | The session-start line arrived (429 characters) and the host told the user memBrain was still installing and would start by itself. It tried to save the decision, was told memory was not ready, and said the decision was not saved. |
| 2, same session, about a minute later | Memory worked: the tool server had connected. The host saved the new preference and, unasked, saved the decision from turn 1. |
| 3, new session | Asked what was decided and which package manager the user likes: both answered. |

**Limits of this check:** the bundled database engine and the dependency wheels were already cached on this machine, so a truly new machine takes longer; Linux only; one run; the host's own login was the owner's.

**Found:** the plugin has no command to stop its service; `membrain desktop stop --directory …` does it, which a plugin user would not find. With no uninstall instructions anywhere, stopping, uninstalling and removing the data is a path still to be written.

## Limits

- One model, one run of each scenario, headless.
- OpenClaw, AstrBot and Hermes have no per-item forget.
- Hiding without erasing is no longer offered to plugin hosts; a boundary covers "don't bring it up".
- A project's label is its folder name: two projects with the same folder name share one, a renamed folder starts a new one, records from before this runtime have none, and the name (which may be a client's) reaches the host, the memory page and exports.
- The speaker-attribution evaluation of 2026-11-21 (another session's, on runtime `5f16fd7f`) found the automatic context behind plain labelled retrieval on who said what (19 of 26 against 26 of 26). Not addressed in this runtime.

## Verification

Local, on Linux under WSL2; nothing was run in CI or on another platform.

| Check | Result | On |
| --- | --- | --- |
| Full source suite, sharded over two workers | 5,100 passed, 3 failed, 11 strict expected failures, 4 skipped; 18 minutes. The three: the pin test, by design before the pin; a test-matrix entry naming a renamed test (fixed in `6106561a`); and one recall test known to give different results on the same commit (under investigation) | `c3efd22d` |
| Pin test and the matrix test after the fix and the pin | pass | the commit that adds this record |
| The forget fix and project labels together, focused | 593 passed, 8 strict expected failures, 1 skipped | `92720278` |
