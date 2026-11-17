# A persona confirmation is never reported as saved when it is not

Runtime `ef0e8727`; launcher pin `0b1c052d`. No migration, no new dependency, no model call. It closes no release gate: **C5 remains invalid and unscored.**

## The defect

When a user asks the agent to behave differently from now on, the host AI proposes the change, asks, and after the user's yes confirms it, citing the user's message. On the plugin path the yes is usually the current message, which is recorded only when the turn ends, so the tool answered "Confirmed. The new persona version is saved when this turn is recorded…" and applied the change then. The change is applied only if the yes answers something the agent said in the same conversation; that rule keeps a host from confirming its own proposal and stays.

But when the rule was not met after all, **the confirmation was dropped without a word**: the host had been told "Confirmed" and had told the user, nothing was saved, and the proposal stayed open on the memory page. It was found on 2026-11-16 while the evaluation harness was being reworked for the companion evaluation: a test put the user's yes in a new conversation. Reproduced on the unchanged runtime before the fix:

| Case | Before | Now |
| --- | --- | --- |
| The yes is the next message of the same conversation | "Confirmed"; saved when the turn was recorded | Saved as before; the tool says "Not saved yet: … takes effect from their next message" |
| The yes opens a new conversation | "Confirmed"; nothing saved; the proposal open for ever; nothing said again | Refused at once: "The user's yes must answer your question in this conversation. Describe the change again here and ask; confirm after their yes in a later message. Nothing was saved." |
| A new conversation, after the agent asked again there | Saved | Saved |
| Confirm in the proposal's own turn | Refused as too early | Refused as too early |
| Confirm in the proposal's own turn while another conversation had a reply since | "Confirmed", then dropped (a second silent path, found while fixing the first) | Refused |
| The turn of the yes is then not recorded (a pause, an erasure during the turn) or fails the rule when recorded | "Confirmed", then dropped | At the host's next contact, once: "Your confirmation of the persona change was not applied (the user's answer could not be used as evidence). The proposal is still open: ask again and confirm after their yes." with the proposal's id |

## How

- **Refused at the call when it can be known then.** For a confirmation that cites the current message, the host layer finds that message's staged turn and sends its conversation; the service refuses when nothing the agent said in that conversation has been recorded since the proposal. The rule itself is still checked on the recorded message.
- **A failed deferred confirmation is reported once.** A waiting confirmation is remembered on the host side as ids only, in a small file beside the pause state (one per user on a multi-user host). At the next per-message context or session notice, once the turn's recording outcome is known, a confirmation that ended without the change and whose proposal is still open is reported and forgotten. It is held back while recording is paused, forgotten after seven days if its outcome never becomes known, and removed when the person's memory is erased.
- Claude Code and Codex over MCP, OpenClaw through the tool command, and chat bots get both. Hermes has no persona tool. A host that records through the API itself gets neither.

## Limits

- The notice belongs to the installation, not to a host: if two hosts share a memory, whichever makes the next contact is told. A notice that the host's hook output drops is not repeated.
- If the proposal is withdrawn between the confirmation and the recording (its cited message erased, the card changed on the page), the host was told the change takes effect from the next message and is not corrected; "the proposal is still open" would be false there, and no second sentence was added.
- After a refusal in a new session the host may not have the proposal's id: the tool has no action that lists open proposals. Proposing again replaces the old proposal.
- A service older than this runtime rejects the new optional field; the launchers pin plugin and service together. The TypeScript client does not send it.
- For the companion evaluation this fixes what the host is told; scenarios still keep a request and its yes in one conversation, since a yes in another conversation is refused by design.
- Not tried on a real host.

## Verification

- Before the fix, five observation tests recorded the behaviour in the "Before" column on the unchanged runtime, and the test of the yes in a new conversation failed as written.
- New tests in `tests/test_persona_confirmation_host.py` and two in `tests/test_persona_confirmation.py`: each case of the table on the plugin path with a real service (what the tool answers, what is saved, what the host sees next), the notice once and only for a failed confirmation, the same refusal through the plugin tool command, MCP and the chat-bot adapter.
- Focused runs on fresh task-owned databases: 301 passed (persona, memory evolution, companion), 398 passed (MCP, plugin, OpenClaw, chat bot, Hermes, host, recording, erasure, journal), 274 passed (the acceptance harness, pause, off-the-record dates). No existing assertion was changed.
- **Full local suite on the pinned source `0b1c052d`: 4,271 passed, none failed, 3 skipped** (the desktop end-to-end tests that need Docker), 3 existing fork warnings, 37 min 59 s; the source was unchanged during the run and the database stopped.
- Not run for this runtime: GitHub Verify, the native platform jobs, the R5 overhead protocol, a real host, any acceptance attempt.

A sub-session implemented and tested the change to the lead's brief and chose the host-side store for the notice after finding no existing channel that could know about a message that was never recorded; the lead reviewed and integrated it.

