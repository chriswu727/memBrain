# Companion fixes, two trust defects from an outside review, and a conversation-first memory page

Runtime `66e06afa`; launcher pin `dc0f0b56`. No migration, no new dependency, no model call of memBrain's own, no new tool, no new user-facing control. **It closes no release gate.** R4 and C5 were each passed once on runtime `3afc0dda` ([R4](maturity-seventh-attempt-2026-11-16.md), [C5, with reservations](maturity-c5-second-attempt-2026-11-17.md)); nothing in this record was part of a scored run, and no paid acceptance run has been made on this runtime.

Four commits make up the change since `3afc0dda`'s record:

| Commit | What |
| --- | --- |
| `55a2f27b`, `11a0fc63` | Companion fixes A to G from the second two-arm attempt, and the wording of two of them chosen by a probe |
| `e9b64c3a` | Two trust defects reproduced by an outside review on `55a2f27b`, with the audit that followed |
| `6344909a` | The memory page no longer takes typed memory content; support style and the familiarity cap are removed |
| `66e06afa` | The agent can remove or replace a persona entry when the user asks |

## 1. Companion fixes (owner's decisions after the second two-arm attempt)

The attempt's reservations were: the simulated mood never moved, saved shared moments were never used, "shorter" was not followed, and a manner agreement was lost on a personality switch.

- **A. Agreements are memory.** A manner suggestion the user accepted and a "from now on" change the user confirmed survive a change of personality type; every switch applies those still in force on top of the new type's card.
- **B. A relationship reset keeps the "don't bring up" boundaries.** The rarely used reset sits in a collapsed "More".
- **C. The mood moves on news and may show.** The note tool asks for an inferred feeling on news that plainly carries one; the mood line asks for one small touch in the host's own words, never a set phrase, and nothing when the message is serious.
- **D. A return after seven or more whole days is acknowledged once**, without saying it missed the user or asking why they were away.
- **E. A saved shared moment may be referred to when relevant**, and is not recited.
- **F. "Shorter" writes a limit a reader can check**: "one to three sentences unless the user asks for detail".
- **G. Something the user only tells about is not a shared moment.**

### Probe of the wording (diagnostic, not a gate)

The owner's condition for C was "visible, but never rigid: the agent must not keep applying a template to show mood". Three rounds on the provider's host model (`deepseek-v4-pro`, the product's server instructions, session notice and blocks as a host receives them; replies read by the lead, not scored blind; conservative cost bound 6.11 CNY in total). Replies are in [`evidence/companion-wording-probe-2026-11-18/`](evidence/companion-wording-probe-2026-11-18/), one file per round; each later round reran only the cases whose wording had changed.

| Case | Result with the wording kept |
| --- | --- |
| News that plainly carries a feeling → a note with an inferred feeling | 5 of 5 |
| Mood on an unrelated topic shows as a light touch | about 4 of 13 (English and Chinese); no two alike |
| Mood left out when the message is serious | 4 of 4 |
| Welcome back after 19 days | 5 of 6, each in different words; none said it missed the user or asked why |
| A relevant shared moment is referred to | 6 of 6 |
| An irrelevant question does not get moments recited | 0 of 3 recited |

Rejected on the way: "if it fits" left the mood invisible in 13 of 13 replies and the welcome back in 5 of 6; wording that let the agent nod to what caused the mood produced stock sentences about its own mood. **Limit:** the mood shows in about a third of replies, by choice; a small sample on one model under an emulated host.

## 2. Two trust defects from an outside review

A reviewer outside the project reproduced two defects on `55a2f27b` and stated the rule they break: a correction or deletion must reach everything derived from it, and switching personality may change the manner of expression but must not add consent on the user's behalf.

### A deleted message's date came back

The return notice (D above) named the day of the user's last conversation. The lookup was right: the service's timeline leaves out deleted, erased, suppressed and retired messages, so a brand-new session never named a deleted message's day. **The leak was a cache**: the sentence, with its date, was kept in the session's state from the session's first context until its first prompt, so a context rebuilt in between (a resumed or compacted session, a chat bot asking before each message) showed it after the message had been deleted.

Now only "whether to say it" is kept; the sentence is worked out again from the service each time it is shown, so the message before the deleted one is used, or nothing is said. A sentence an earlier runtime kept is dropped unread.

We could reproduce only this path. If the reviewer saw the date in a session started after the deletion, that is a different path and we have not found it.

### Deleting a persona version widened what the user had agreed to

An agreement (A above) was computed as the difference between the accepted card and the kept version before it. With that version deleted, the difference was taken against an older or empty card, so the personality type's own traits, values and baseline mood became "agreed" and would have been carried into every later type.

Now **an agreement is exactly what the user accepted, as recorded when they accepted it, and is never read from another version**: for an accepted manner suggestion, its kind's one change; for a confirmed proposal, what the accepted version records as `agreed_changes`. A version that does not record enough carries nothing. A property test runs 400 seeded sequences of 30 steps (accept, confirm, remove, delete or hide any version, restore, switch, delete the history) and checks after every step that each agreement is within what was accepted and still on the card.

### What the audit that followed found and fixed

| Found | Fixed by |
| --- | --- |
| An accepted suggestion's stored reason kept the dates of every feedback message; the page showed them after the messages were deleted | No dates are stored; they are added on read from the messages that still exist |
| An export carried those stored dates | Exports and archives write the reason without dates |
| A proposal made on a version kept a copy of that card after the version was deleted | A proposal now depends on its version and is erased with it |
| Version numbers are reused after the newest version is deleted, so a proposal made on a deleted version could reopen, and a "yes" would save the deleted card back as agreed | A proposal is open only while the current version predates it |

Checked and found unable to show a deleted source: the familiarity line and shared-moment count, the history and recall blocks, notes' dates, the mood's "since" and reason, shared moments, persona version dates, and the session caches (ids and times only). Off-the-record dates are dates of turns that were never recorded: deleting a message does not touch them; erasing everything removes them.

### For an independent re-check

Each runs through the host entry points on a real service.

- **Date.** Record a message in session A (session-start, prompt and stop hooks). Move the clock 12 days on and start session B: its notice names A's day. Delete the message as the memory page does. Ask for B's session context again before B's first prompt: no date, and the session state holds neither the sentence nor a date. `tests/test_dates_after_deletion.py::test_a_deletion_after_the_first_context_and_before_it_is_shown_again_is_seen` (failed on `a6a58593`), and `::test_the_only_message_deleted_on_the_page_gives_no_notice_in_a_new_session`.
- **Agreement.** Save a type; send three "too long" comments through the hooks; accept "shorter"; delete the version before the accepted one; switch type. The new card carries one voice field, "one to three sentences unless the user asks for detail", and nothing else of the old type. `tests/test_persona_agreement_deletion.py::test_deleting_the_version_before_an_accepted_suggestion_keeps_only_what_was_accepted` and `::test_deleting_the_version_before_a_confirmed_change_keeps_only_what_the_agent_proposed` (both failed on `a6a58593`); the property test is `::test_no_sequence_of_deleting_hiding_restoring_removing_or_switching_widens_an_agreement`.

## 3. The memory page: look, check the source, delete

Owner's decision: users will not hand-edit memory text; memBrain rides on an agent, so the user should only need to talk. **Conversation is the way to change memory; the page is for looking, checking where something came from, deleting, and a few whole-memory privacy controls.**

- **Removed from the page:** the note editor and its seven entry points (add, edit, merge duplicate, save a message as a note, edit on the 2D and 3D map, add or edit a shared moment, add a first preference), the persona card editor, the add-boundary form. Empty states and headers say what to tell the agent instead.
- **Stays, one click:** every Delete, boundary Remove, version Restore, type switch and random pick, Accept and Reject of a suggestion, pause and resume, export, search, erase everything with its typed guard.
- **In a collapsed "More":** the mood pin (the only way to turn the simulated mood off), Reset mood, Reset relationship, Delete personality history; in Feelings, Clear feelings.
- **Two features removed entirely:** "how you like to be supported" and the familiarity cap (routes, client methods in Python and TypeScript, the relationship block's line, graph nodes). A preference about support is an ordinary note; familiarity is the derived level.
- **The agent can remove or replace a persona entry** (`66e06afa`): `memory_persona` `propose` takes `changes.remove`, applied before additions, so "replace X with Y" is one proposal and one yes. An entry the card does not hold is refused with the card's entries listed. A removal changes the current card only; it is never an agreement carried to another type, and removing an agreed entry ends that agreement.
- **The evaluation tooling follows the page:** page actions are format 3 (adding a boundary, editing the card, support style and cap are refused by name); the companion coverage table's page boundary became a second boundary asked for in conversation. Recorded runs are unchanged and still readable.

## Limits

- **Not tried on a real host.** Every path here is driven through the hooks and tools by tests, and the wording by an emulated host.
- **Hosts that cannot make a change by conversation can no longer make it at all:** Hermes has no persona, manner-feedback or forget tool; OpenClaw has no forget tool; AstrBot's forget erases everything; the OpenAI-compatible proxy is read-only, so its user cannot set a boundary.
- **Records stored before this runtime:** a support style or cap is ignored when read but stays stored and exported until a relationship reset or erasing everything, and nothing tells the user it went; a user who had capped familiarity gets the derived level at once. An accepted suggestion's stored reason keeps its dates in the database (no reader or export shows them). A proposal confirmed before `agreed_changes` existed carries its voice, name and mood across types, not the entries it added.
- **Restoring a cleaned archive** into the brain that still holds the legacy version quarantines that version (hash mismatch); the existing one is kept.
- **A removed persona entry that the type itself has comes back** when the user switches to that type again.
- **The tool description sent each session grew** from 1,679 to 1,856 characters; the server instructions are unchanged at 1,388 of 1,400.
- **The page still falls short of "check the source"** in places this change did not touch: a corrected note shows no "corrected from" history; boundaries, promises and mood triggers do not link to the message they came from; search results cannot be deleted.

## Verification

All local, on Linux under WSL2; nothing was run in CI or on another platform.

| Check | Result | On |
| --- | --- | --- |
| Full source suite | 4,653 passed, none failed, 3 skipped (desktop end-to-end tests that need Docker), seven Python fork warnings | `dc0f0b56` (runtime `66e06afa`, pinned) |
| The same suite one commit earlier | 4,643 passed, 2 failed: the pin test, by design before the pin, and a page-translation test that still expected strings removed with the card editor (fixed in `66e06afa`) | `6344909a` |
| The same suite on the companion fixes alone | 4,613 passed, none failed, 3 skipped | `a6a58593` |
| New trust tests on the runtime before the fix | 11 failed, 3 passed (the three that exercise the lookup, which was already right) | `a6a58593` |
| Free stub rehearsal of a two-arm companion attempt | ok: both scenarios valid, 592 dry-run checks each, coverage 13 of 13, no network | `dc0f0b56` |
| Free stub rehearsal of a two-arm R4 attempt | ok: both scenarios valid, 179 dry-run checks each, no network | `dc0f0b56` |
| TypeScript client | 40 tests passed; the type check was not run (no compiler available offline) | `66e06afa` |

The wording probe in section 1 is the only model call behind this record. No held-out scenario was used, and no acceptance run was made.
