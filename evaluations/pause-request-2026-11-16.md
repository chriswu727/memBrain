# A host AI's pause needs the user's words

Runtime `a85ca152`; launcher pin `4513d133`. No migration, no new dependency, no model call. It closes no release gate: **R4 remains not passed and C5 invalid and unscored.**

## Why

In the [sixth maturity attempt](maturity-sixth-attempt-stop-2026-11-16.md) a host AI, its answer already written and a consolidation batch handed back, called the pause tool with no arguments and no reasoning. The user had said nothing about not being remembered. A pause without arguments ends recording for the rest of the conversation and leaves the current exchange unstored; nothing asked the host to tell the user. Twelve replays of the turn did not repeat the slip, so it is rare. It is also silent, and it costs the user every later message of that conversation.

## What changed

- **The pause tool takes the user's words.** Every pause tool a host AI can call (`memory_pause` over MCP, `membrain plugin tool pause` and OpenClaw's `membrain_pause`, the chat-bot adapter's and AstrBot's `membrain_pause`, Hermes's `membrain_pause`) requires `request`: the user's own words asking not to be remembered, copied from their current message. The call is refused, and nothing is paused, when `request` is missing or shorter than two characters, or when the user's current message is known and does not contain those words. Both sides are compared after Unicode normalisation, case folding and collapsing of whitespace, with quotation marks and punctuation stripped from the ends of the request.
- **The answer asks the host to tell the user**, in the pause's own scope: that this conversation is no longer being recorded, that nothing is recorded for the next N hours, or that nothing is recorded until they say to start again. A wrong pause is then seen and can be undone.
- **After consolidation the host is told it is finished**: the tool's last answer now adds "If it is already written, you are finished: call no other tool."
- **The user's own controls are unchanged** and need no quotation: the `membrain plugin pause` command, the memory page and the service's recording controls.
- The session notice says to call the pause tool "with their words"; the skill, the plugin's README, the reference, the AstrBot READMEs and the OpenClaw and Hermes tool schemas describe the argument. The standing instructions of the tool server are unchanged.

## Where the current message comes from

Every host stages the user's message before its AI can call a tool: the prompt hook of Claude Code, Codex and WorkBuddy, OpenClaw's `before_prompt_build`, Hermes's `prefetch`, the chat-bot adapter's `context()`. The staged text is the message with `<private>` parts and credentials already removed, so the request is compared as given and with the same removal applied. The message compared is the newest unfinished turn of each of the user's conversations (or their role-play) started within six hours.

The words alone are trusted, with no comparison, when no unfinished turn of the user is known (a path that stages nothing, a pause called before staging) or when a current message was not kept because it was itself excluded from recording ("Off the record: …", or a message sent while already paused): that text cannot be compared, and refusing there would refuse a real request.

## What this does and does not prevent

- It prevents the slip that was seen: a call with no arguments, and a call with invented words.
- It does not prove that the quoted words ask for a pause. Any two characters of the current message pass. A host that pauses wrongly while quoting the user is not stopped; the note that makes it tell the user is the remaining guard.
- A real request can be refused when the host paraphrases or translates the user's words. The refusal says what to pass, and the phrases the runtime recognises by itself ("off the record", "don't remember this", and their kin in other languages) still pause without any tool. How often a host fails to retry has not been measured.
- An OpenClaw or AstrBot plugin older than this runtime has no `request` in its tool schema, so its AI's pause would be refused. The launchers pin plugin and runtime together, and nothing has been released.
- The listed MCP schema marks `request` as required through a private attribute of the MCP library, while the function accepts a missing one so that the refusal is memBrain's own; a test pins both.

## Tried on one host model, with public messages

Added later on 2026-11-16, before the seventh maturity attempt. `deepseek-v4-pro` was given the plugin path's standing prompt on this source (the tool server's instructions, the recording and privacy notices, all fourteen tools) and nine messages written for the probe, twice each ([script](evidence/pause-request-2026-11-16/host-probe.py), [results](evidence/pause-request-2026-11-16/host-probe-results.json)); the tool's answer was computed with the runtime's own comparison.

| Message | Should pause | Paused | What the host passed |
| --- | --- | --- | --- |
| English, plain ("Off the record … Don't remember this.") | yes | 2 of 2 | the whole message, both times |
| English, softer ("Can you not keep what I say next? …") | yes | 2 of 2 | the sentence that asks, both times |
| Chinese, plain ("这段别记：…") | yes | 2 of 2 | the asking words once, the whole message once |
| Chinese, softer ("接下来说的你不要存下来好吗？…") | yes | 2 of 2 | the whole message, both times |
| German ("Das bitte nicht speichern: …") | yes | 2 of 2 | the whole message, both times |
| English, a request for privacy ("Keep this between us: …") | no | 0 of 2 | (no pause; a note was saved) |
| Chinese, a request for privacy | no | 0 of 2 | (no pause; a note was saved) |
| English, someone else's "off the record" quoted | no | 0 of 2 | (no pause, no note) |
| English, nothing of the kind | no | 0 of 2 | (no pause; a note was saved) |

All ten pauses were accepted at the first call, with the user's words copied exactly; no call was refused, so what a host does after a refusal was not seen. In every one of the ten the host then told the user in a few words that it was not keeping this. The conservative count of the probe is 1.75 CNY, run under the owner's standing leave for small diagnostic probes.

**Still not tried:** a real plugin host (Claude Code, Codex, OpenClaw, AstrBot, Hermes); a request the host would have to find in a long message; what a host does after a refusal; and the frequency of the original slip, which is unknown beyond one in the sixth attempt's one consolidation turn and none in twelve replays. Eighteen trials of nine messages are a check that the tool can be used as described, not a rate.

## Verification

- Before the change, nothing refused a pause: the new tests of refusal fail on the previous runtime by construction (the argument did not exist).
- 34 new tests in `tests/test_pause_request.py`, no database: accepted words (differences of case, whitespace and surrounding quotes; a Chinese request), a missing or blank request, words that are not in the message (nothing paused, the turn recorded afterwards), an unknown or unkept current message, other people's messages, the note for each scope, the user's own controls, each host's entry point, one description on every host, the consolidation note, the harness's scripted pause.
- Two focused runs on fresh task-owned databases: 688 passed with the pin test failing as it must before the pin (host recording and pause, MCP, plugin tool and command, chat-bot, Hermes, consolidation, the OpenClaw node test, persona, receipts, role-play), and 767 passed (the acceptance harness and its hardening, review, driver, kit, supervisor, MCP over HTTP, server recording, journal, queue, legacy data). These overlap each other and the full run.
- **Full local suite on the pinned source `4513d133`: 4,140 passed, none failed, 3 skipped** (the three desktop end-to-end tests that need Docker), 3 existing fork warnings, 34 min 52 s, PostgreSQL 16.15 with pgvector 0.8.6; the source was unchanged during the run and the database stopped.
- Not run for this runtime: GitHub Verify (so the 39 TypeScript SDK tests, the type check and the package builds), the five native platform jobs, the R5 overhead protocol, any host or paid evaluation.

A sub-session implemented the change to the lead's design and ran the focused checks; another ran the full suite; the lead reviewed the diff and integrated it. Two decisions were the implementer's and are kept: an unkept current message counts as unknown, and "current" means the newest unfinished turn of a conversation within six hours.

