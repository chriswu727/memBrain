# Four lines of work at once: a companion switch, consolidation on two more hosts, two privacy fixes, and no more prompt for a second model

Base: pin `5b7ec232` (runtime `fa88a4b`). Runtime commits `134091a9` to `75f3f49d` (thirteen); pin commit `df630c25` points all nine launchers at the last. No migration. No model was called. It closes no release gate: **R4 remains failed and C5 invalid/unscored.**

## How this batch was made

On 2026-11-12 the owner asked that the project move on several modules at once and not on memory alone. Three read-only audits and four pieces of work were handed to sub-sessions, each in its own working copy; the lead reviewed every diff, merged them, and made the privacy fixes. The audits and a removal plan are in [audits-2026-11-12](audits-2026-11-12/).

The owner's decisions that this batch carries out:

- memBrain is a brain fitted to agents and not a product of its own. Its bundled chat mode and the learning pipeline driven by a model of its own are frozen, to be removed; code that is not used is to be cleaned up.
- The companion layer (persona, simulated mood, familiarity) is on by default in every host and can be turned off by the user.
- Old memories are not forgotten; recent and important ones come first. (Not in this batch; to be measured first.)

## What changed

**A companion switch.** The persona block, the simulated-mood block and the familiarity part of the relationship block can be turned off and on, per person. Off deletes nothing; on shows the same state as before. Boundaries and their filter, feelings on notes, commitments, notes, recall and consolidation are unaffected: boundaries and missed-promise lines move to a block of their own while the layer is off. Three ways to flip it: the `/membrain:companion on|off` command in Claude Code, a `memory_companion` tool the host AI calls when the user asks in words, and `membrain plugin companion on|off|status`. The setting is a local file beside the pause files, so it applies to every host that shares the installation. Codex, WorkBuddy, CodeBuddy and OpenClaw have no slash command for it: nothing in the repository shows a command format for them, and none was guessed.

**Consolidation and the assistant's replies on OpenClaw and AstrBot.** Both hosts gain a consolidation tool and the option to search the assistant's own earlier replies; until now nothing wrote cues there. One routine now serves every host's consolidation tool. OpenClaw runs a new process for each tool call, so there the batch's number travels with the cues; AstrBot and the MCP hosts remember the batch they handed out.

**Two privacy fixes**, both found by the audits.

- A consolidation batch handed the host AI every unreviewed message, including messages about a topic the user had asked not to have raised. Such messages are now never handed out; they count as read with their batch and get no cue, and a batch that holds nothing else is passed over. An id the batch did not hand out is refused. This gap was in the consolidation built on 2026-11-11.
- A client could write a "reported feeling" straight into the reserved feelings conversation, with no note and no source behind it; the persona, mood, relationship and proposal conversations refused such writes and this one did not. It now does.

**No prompt for a second model.** `membrain desktop setup` no longer asks for a "memory learning" model, and start-up no longer warns that none is configured. The explicit options remain for profiles that already use them, marked frozen. The READMEs no longer tell users to enter one, and the reference marks the bundled chat mode, server-side cognition and the proxy's extraction model as frozen. Nothing was deleted yet: the [removal plan](audits-2026-11-12/unused-code-removal-plan.md) counts about 17,000 source lines (39% of the package) that serve only the frozen modes and orders their removal in slices.

**A small fix on the way.** OpenClaw's manifest did not declare the boundary tool that its plugin registers.

## Verification

- **Full local source suite on the pin commit `df630c25`**, with the local embedding model: 8,558 passed, 4 skipped (the Docker journeys), none failed, in 56 minutes; source and migrations unchanged during the run. It ran alone, holding the lock that test sessions on this machine now share.
- Before the merge, each line's own tests passed in its working copy, and the affected test files passed on the combined change (310 tests).
- New tests cover: the switch (default on, per person, off removing exactly three blocks, on restoring them unchanged, the tool, the command line and the page route); consolidation on OpenClaw and AstrBot through real local services, including refusals and pauses; messages about a boundary topic never handed out, a batch wholly about one passed over, and an id outside the batch refused; a feeling that cannot be planted; setup that never asks for a model.
- TypeScript client and the OpenClaw plugin's own tests pass (the two that need a real OpenClaw runtime are skipped there and run through the Python suite).

## Not done, not known

- **No real host ran any of this.** The companion switch and the slash command were tested against the repository's own tests, not in Claude Code; OpenClaw was not run in a real gateway nor AstrBot in its runtime.
- OpenClaw and AstrBot rebuild the session context before every message, so the request to consolidate stays in every turn's context while five or more messages wait. Whether a host then consolidates more often than once a conversation is not known.
- On OpenClaw a wrong batch number from the host AI is accepted if it is at least every cue's id: too high counts unread messages as read, too low has them offered again.
- Persona switching and persona edits proposed by the host AI are investigated, not built; the owner's answers to a short list of questions come first.
- The decay of old memories has not been measured or changed.
- The frozen code is still in the package.
