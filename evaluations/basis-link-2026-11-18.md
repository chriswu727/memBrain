# From a reply to its basis: the memory page opens at a note

Runtime `f69d4cda`; launcher pin `3e888dd4`. No migration, no new dependency, no model call, no new tool, no new route, no new control; the server instructions are unchanged (1,388 of 1,400 characters). **It closes no release gate**, was not tried on a real host, and no acceptance run has been made on this runtime.

It continues [the resume-after-correction work](correction-visible-2026-11-18.md), whose limits said: "the host has no link it can give the user to the basis of a reply; a source message on the page does not open its conversation."

## What a user gets

On day 8 the agent says it will use SQLite locally, and the user asks why it thinks so.

1. The agent answers from the note it was given (its date, that it replaced a note of 2 Nov) and runs `membrain plugin ui --note <id>`; the id is on every note line.
2. The browser opens the memory page at that note, outlined, with "Replaced an earlier note on 2026-11-04.", "Earlier (2026-11-02): …" and both source lists open.
3. "In the conversation: …" under a source message is now a link: it opens that conversation at that message, outlined. The overruled day-1 message shows "Superseded by a note saved on 2026-11-04."

## How

- **Addresses in the fragment.** `/memory#note=<id>` and `/memory#message=<id>`. The fragment is never sent to the server or logged. It survives the page's code exchange and a reload. The address of a note that a current note replaced opens the current note with the earlier line outlined, since that is where the page shows it.
- **The credential is unchanged**: the single-use code of `membrain plugin ui`, valid for two minutes. No link and no code is ever put into the host's context; the host is told to run the command, in one sentence (226 characters) added to the skill's existing line about the memory page.
- **The address only navigates.** It reads two keys, expands, scrolls and outlines; it never puts an id into HTML and never performs an action.
- **A missing, deleted, hidden or other user's id** shows "This item is no longer here." above the normal view, and makes no request the normal view does not make, so the page cannot be used to test whether an id exists.

## Checks

Browser tests on a real service: opening at a note through the real command, the code exchange and a reload; opening at a message; a replaced note's id; four unknown ids; another user's brain on the same installation and another account; four crafted fragments (for example `#note=<id>&delete=1&action=forget&mode=erase_content` and an id carrying an `<img onerror>`), none of which made a request beyond reads and the code exchange, opened a dialog, injected an element or changed a count; Chinese; and the three ids of a deleted chain, with nothing of the notes in the DOM and exactly the normal view's requests.

Of the scenario's 13 strict expected failures, 2 now pass and are asserted exactly; 11 remain.

## Limits

- **Not tried on a real host.** Whether a host asked "why do you think that?" consults the skill and runs the command is not known, nor whether `membrain` is on the user's PATH where the plugin is started through its launcher.
- **Only notes have an address the host can use.** A host that saves no notes has no id to give; a message is reached from a note's sources.
- **A stored reply does not lead to its basis.** That would need a record of what each reply was given.
- **The two-minute code suits "open the browser now"**, not a link left in a reply to be read later.
- Hermes, OpenClaw and AstrBot tell their AI nothing about the memory page; on a multi-user bot the page shows the installation's brain, not each person's; a host reached over SSH prints a link to `127.0.0.1`.

## Verification

Local, on Linux under WSL2; nothing was run in CI or on another platform.

| Check | Result | On |
| --- | --- | --- |
| Full source suite | 4,832 passed, none failed, 11 strict expected failures (the scenario's remaining gaps), 4 skipped (three desktop end-to-end tests that need Docker; one trust case that applies only to a three-note chain), seven Python fork warnings; 56 minutes | `3e888dd4` (runtime `f69d4cda`, pinned) |
