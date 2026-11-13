---
description: Show memBrain's preset personas and the current one, or switch to another preset
argument-hint: "[list|steady|bright|wry|gentle|blunt|random]"
allowed-tools: mcp__plugin_membrain_membrain__memory_persona, Bash(membrain plugin tool persona)
---

The user ran `/membrain:persona` with the argument: "$ARGUMENTS".

- Empty or `list`: call the `memory_persona` tool with `action: "list"`.
- A preset id (`steady`, `bright`, `wry`, `gentle`, `blunt`) or `random`: call the `memory_persona` tool with `action: "switch"` and that `preset`. The user typing this command is the request, so do not ask again. Cite this message as the source: `source_messages` and `recording_capture` from the current `<membrain-source>` block.
- Anything else: do not call the tool; say that the command takes `list`, a preset id or `random`.

If the tool is not available, run `membrain plugin tool persona` with the same arguments as a JSON object on standard input, for example `echo '{"action": "list"}' | membrain plugin tool persona`.

Then answer in one or two plain sentences, in the user's language: for `list`, the presets with their one-line summaries and which one is current; for a switch, which persona is now current. The mood and familiarity carry over unchanged. If the tool returns an error, say what it says.
