# Honest about an off-the-record stretch, and one reply per turn

Runtime `c280dcbf`; launcher pin `e66ec48b`. No migration, no new dependency, no model call. It closes no release gate: **C5 remains invalid and unscored**, and the R5 overhead protocol, GitHub Verify and the native platforms were not rerun for this runtime.

Both changes come from the [seventh maturity attempt](maturity-seventh-attempt-2026-11-16.md), which passed R4 and whose final review found two defects that are not critical errors under the rule and are visible to a user. The lead found the causes and tried the wording on the attempt's own turns before anything was built; a sub-session implemented and tested it; the lead reviewed the patches and integrated them.

## 1. The agent can say that part of a conversation was off the record

**The defect.** After an off-the-record stretch nothing told the host AI in a later conversation that anything had been kept out. Asked later about what was said then, the host denied it: in one case it said, in Chinese, that the user probably had not said why or had mixed up the day. Nothing was leaked, which is what the stretch is for; the denial was the defect.

**The change.** When a user message is left unrecorded because recording was paused, the host side remembers the user's local date of that turn and nothing else: no text, no topic, no conversation. It does so where every host's turn is settled, for every kind of pause (the host AI's pause tool, the product's own pause on the user's words, the user's controls on the device or on the memory service), and also for a turn settled late after its host went away and for a queued message the service refused as paused. At most ten dates are kept per person, in a small file beside the pause state; a role-play's dates are its person's.

While a person has such dates, the session notice names the five latest and says:

> At the user's request, part of your conversation on 2026-04-29 and 2026-05-12 was off the record and nothing of it was kept. If the user asks about something from then, or about something they say they told you that you find no record of, tell them it may have been in that part and that you kept nothing of it because they asked; do not say it was not said, and do not guess.

Every host gets it, since every host's AI gets the session notice. Erasing a person's whole memory through the host (`membrain plugin forget-user`, a chat bot's forget) removes the dates; erasing single messages does not.

**Tried on the attempt's two cases** (`deepseek-v4-pro`, the recorded turn replayed with the sentence added to the session notice, three times per case and wording; [script and results](evidence/offrecord-dates-and-one-reply-2026-11-16/)):

| Case | In the attempt | First wording (only "something said then") | Final wording |
| --- | --- | --- | --- |
| The user asks what a named company offered them, without saying when (`S110`) | "nothing comes up in my notes … Could you be thinking of the other print place?" | 0 of 3 mention the off-the-record part: the host searched, found nothing and said it had no record | 3 of 3: "It could well have come up in that off-the-record chat we had on 29 April — you asked me to keep nothing from that" |
| The user asks what they said on a day they name (`S210`) | in Chinese: the user probably had not said why, or had mixed up the day (the lead's translation) | 3 of 3 say that part was not kept at the user's request | 3 of 3 |

The first wording failed when the user did not name the day, so the sentence now also covers "something they say they told you that you find no record of". No reply revealed anything; there was nothing to reveal.

**Limits.**

- The dates are a host-side file: they are not exported, not in a desktop backup, and not shared between devices. On a new device the agent is as it was before this change.
- **Erasing everything from the memory page or through the API does not remove the dates.** The host side learns of erasures message by message and cannot tell that the whole memory was erased. A date with no content stays until the person's memory is erased through the host. This is a known gap.
  - *Note added 2026-11-16 (later the same day):* closed for a local installation. When the installation's own service completes an erase-everything of a brain (`forget` with `all_authorized_scope` and `erase_content`, as the memory page sends it), it now removes that brain's dates file from the same installation ([reference](../docs/reference.md#off-the-record-dates)). A service that is not the installation's own, such as a remote deployment, still cannot reach the host's files, so this limit remains there.
- The date of a queued message refused as paused is the date of the refusal, which can be later than the message if the service was down.
- On a bot with many users, a pause of the whole installation marks every user whose turn it left out, since their words were dropped too.
- The sentence makes the session notice up to about 420 characters longer, and the history shown at the start of a session shorter by as much. Chat-bot hosts repeat the notice before every message.
- A person who has ever gone off the record keeps the sentence in every later session, for the five latest dates. Whether old dates should stop being named has not been decided.
- Six replays of two turns on one host model are a check of the wording, not a rate. No real plugin host has been run on it.

## 2. One reply per turn when the host indexes earlier messages

**The defect.** In 11 of the plugin arm's 124 turns the user was shown two answers. Nine of the eleven were the turns in which the host indexed earlier messages (9 of the attempt's 14 such turns): it wrote its answer, called the consolidation tool twice, and then had to write again, a closing line ("Sorted.", "Already replied — done.") or a second answer. **The product asked for that order**: the session notice said to call the tool "after you have answered the user's first message". In a tool-calling host, text written before a tool call is shown to the user, and the AI writes again after the last tool answer. The other two doubled turns followed a note written beside the answer; they are not addressed here.

**The change.** The notice now asks the host to call the tool before it writes its reply, do what it returns, then write the reply; the tool's last answer asks for the reply once, and, if it was already written before the call, not to write it again:

> Done. Now write your reply to the user's message, once. If you already wrote it before calling this tool, do not write it again: end your turn with no more than a word and call no other tool. Do not describe the indexing beyond a few words.

It still asks for the reply itself: on 2026-11-13 a host ended a turn with only "Memory's updated.". The sentence added on 2026-11-16 for a host whose answer is already written ("you are finished: call no other tool") is replaced by this one.

**Tried on the attempt's own turns.** The 14 turns with consolidation were replayed once each with the new notice and the new last answer (one replay was cut off by the probe's cost ceiling): **0 of 13 showed two answers, and all 13 wrote exactly one reply**, after indexing and after any notes. In the attempt it was 9 of 14.

**Limits.** One pass over 13 turns on one host model. A host that still answers first is told to end with "no more than a word", which is still a second line. Doubling after a note is not addressed. No real plugin host has been run on it.

## Verification

- New tests: 20 in `tests/test_off_record_dates.py` (each kind of pause records the date; a recorded turn, a refused pause and a resumed turn record nothing; at most ten dates and never text; the display zone and the scenario clock; an abandoned turn gets the date it began on; the notice's exact wording, the five latest dates, absent when there are none, shown to that person only; whole-memory erasure through the host removes the file and single-message erasure does not; the chat-bot, Hermes and OpenClaw paths), and pins of the new notice and last answer with a check that no shared text still asks for the answer first.
- With the write in `host._take_turn` disabled on purpose, 14 of the 20 new tests fail; restored, they pass.
- Focused run on a fresh task-owned database, 82 test files: 2,177 passed and 2 failed; the two pinned the replaced last answer and pass after being updated to the new one (69 passed in the rerun of those files with the pause and off-the-record tests).
- **Full local suite on the pinned source `e66ec48b`: 4,184 passed, none failed, 3 skipped** (the three desktop end-to-end tests that need Docker), 3 existing fork warnings, 35 min 45 s, PostgreSQL 16.15 with pgvector 0.8.6; the source was unchanged during the run and the database stopped.
- Not run for this runtime: GitHub Verify (so the 39 TypeScript SDK tests, the type check and the package builds), the five native platform jobs, the R5 overhead protocol, a real plugin host, any acceptance attempt. The R4 pass of the seventh attempt was measured on the runtime before this one.

The implementing sub-session's own commits were refused by the session's permission layer; it handed back patches, which the lead read line by line and committed on the integration branch.

## Two gaps closed the same day (runtime `55a88f1f`, pin `99ee0356`)

Added later on 2026-11-16, at the owner's request to close the gaps this record listed.

- **Erasing everything now removes the dates.** When the local service of an installation completes an erase-everything (the memory page's button, or the same request through the API: a `forget` of the whole scope with content erasure), it removes that person's off-the-record dates from the same installation's host state. Only a completed erasure does: a single-message erasure, a conflict, a rejection or a failure leaves them, and a date recorded after the erasure is kept. What remains: a memory service that is not the installation's own cannot reach host files; an identical request resent with the same idempotency key removes the dates again; an erasure finished later by the recovery authority, or made through a route other than the action route, leaves them until the person's memory is erased through the host.
- **Memory tools before the reply, as a standing instruction.** The tool server's instructions now say "Use memory tools before your reply, not after it." (1,382 characters of a budget of 1,400; 1,392 with OpenClaw's tool names). It addresses the two doubled turns that followed a note written beside the answer. Not tried on a host: at 2 of about 60 note turns the rate is too low to measure with a few replays.

Checks: 31 new tests for the erasure hook (the removal function, the service's filter, the route, and the real local application with the exact request the page sends), which fail as expected with the hook disabled; a focused run of 72 files, 1,861 passed and 1 Docker skip; **full local suite on the pinned source `99ee0356`: 4,216 passed, none failed, 3 skipped** (the desktop end-to-end tests that need Docker), 36 min 12 s. GitHub Verify and the native platforms were not rerun. A sub-session implemented and tested both; its own commits were refused by the session's permission layer, and the lead read the patches and committed them, shortening the new sentence so that it fits the budget with OpenClaw's tool names too.

## Cost of the probes

Three replays on `deepseek-v4-pro`, under the owner's standing leave for small diagnostic probes: 4.62, 1.50 and 1.38 CNY on the conservative count (every prompt token at the uncached peak price); the account's balance fell by 0.33 CNY across the three.
