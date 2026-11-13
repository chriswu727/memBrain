---
description: Show the sixteen personality types and the current one, switch to a type, or pick one again at random
argument-hint: "[list|<type>|random|reset [<type>]]  (types: intj intp entj entp infj infp enfj enfp istj isfj estj esfj istp isfp estp esfp)"
allowed-tools: mcp__plugin_membrain_membrain__memory_persona, Bash(membrain plugin tool persona)
---

The user ran `/membrain:persona` with the argument: "$ARGUMENTS".

- Empty or `list`: call the `memory_persona` tool with `action: "list"`.
- A four-letter type (`intj`, `intp`, `entj`, `entp`, `infj`, `infp`, `enfj`, `enfp`, `istj`, `isfj`, `estj`, `esfj`, `istp`, `isfp`, `estp`, `esfp`, in any case), or `reset` followed by a type: call the `memory_persona` tool with `action: "switch"` and that type as `preset`.
- `random` or `reset` alone: call the `memory_persona` tool with `action: "switch"` and `preset: "random"`, which picks a type other than the current one.
- Anything else: do not call the tool; say that the command takes `list`, a type, `random`, or `reset` with or without a type.

For a switch, the user typing this command is the request, so do not ask again. Cite this message as the source: `source_messages` and `recording_capture` from the current `<membrain-source>` block.

If the tool is not available, run `membrain plugin tool persona` with the same arguments as a JSON object on standard input, for example `echo '{"action": "list"}' | membrain plugin tool persona`.

Then answer plainly, in the user's language: for `list`, say in a sentence which type is current, then give the sixteen types as a short list with a few words each from their summaries; for a switch, say in one or two sentences which type is now current and what it is like. The mood and familiarity carry over unchanged. If the tool returns an error, say what it says.
