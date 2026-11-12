---
description: Turn memBrain's companion layer (persona, simulated mood, familiarity) on or off, or show whether it is on
argument-hint: "[on|off]"
allowed-tools: mcp__plugin_membrain_membrain__memory_companion, Bash(membrain plugin companion *)
---

The user ran `/membrain:companion` with the argument: "$ARGUMENTS".

- `off`: call the `memory_companion` tool with `enabled: false`.
- `on`: call the `memory_companion` tool with `enabled: true`.
- Empty or `status`: call the `memory_companion` tool without arguments.
- Anything else: do not call the tool; say that the command takes `on`, `off` or nothing.

If the tool is not available, run `membrain plugin companion off`, `membrain plugin companion on` or `membrain plugin companion status` instead.

Then tell the user the returned state in one or two plain sentences. When it is off, say that the persona, simulated mood and familiarity are no longer shown to the agent, that nothing was deleted, and that boundaries, feelings on notes, commitments and recall keep working. The change applies from the next message in every host that shares this memory; it does not change what earlier messages in this conversation said.
