# The companion on a coding host: always on, quiet in work (2026-11-19)

**Decided by the owner on 2026-11-19.** memBrain stays one brain (memory, personality, mood, relationship) with no companion switch and one experience, as decided on 2026-11-12. On a coding host the companion is now quiet. The decision followed an outside review from the user's seat and two real-host trials.

On real Claude Code, the first reply to "Let's get the Tidepool backend going…" ended by announcing an INTJ personality and how to switch it ([trial](host-trial-2026-11-18.md), turn 1). The persona block was about 30% of what a new user's session was handed. The owner chose:

- the personality still shapes tone;
- no self-introduction inside a work reply: only when the user asks, or the talk is casual;
- mood and familiarity reach the host only when the conversation itself is casual or emotional;
- no switch and nothing to set;
- chat hosts are unchanged.

The design was made and built by a sub-session and accepted by the lead, including five departures from the brief (listed under "Choices" below).

**Nothing here has run on a real host or a host model.** Everything was measured locally, through the plugin's own hooks on a real local service, with no model call.

## What a coding host is handed

The coding hosts are Claude Code, Codex and WorkBuddy, through the plugin's hooks (`plugin.CODING_HOSTS`). OpenClaw, the chat bots (AstrBot through `ChatMemory`), Hermes, the proxy and role-play are not coding hosts.

The unit is the conversation. A session starts quiet and is handed the rest of the companion once, when it turns casual or emotional. After that it keeps the whole companion until it ends.

**Session start (quiet):**
- The `<membrain-persona>` block holds the card's voice, plus the traits, values and boundaries that the user's personality type does not have, with one clause saying it is the agent's own manner. Those extra entries are what the user agreed with the agent or wrote themselves.
- The `<membrain-relationship>` block holds only the topic boundaries and the agent's own missed promises. There is no header, no familiarity and no shared moments.
- There is no mood block, and shared-moment notes are left out of the notes block.
- The first persona's introduction and the absence sentence wait in the session's state.
- The session notice and the server instructions are unchanged.

ENFP, a new user (223 characters; the full block for the same card is 747):

```
<membrain-persona version="1">
Your own manner, not a fact about the user; where the user's preferences differ, follow the user.
Voice: register warm and lively; length conversational; emoji now and then
</membrain-persona>
```

- Across the sixteen types the quiet block is 223–224 characters and the full block 747–771, which is under 31%.
- An agreement stays visible. After a confirmed "walk me through database migrations step by step" the quiet block (288 characters) adds `Values: Walks the user through database migrations step by step`.
- An accepted "shorter" shows in the voice line, because it sets the length.
- The traits were left out on purpose. The only thing a trial showed a host following from the card was the voice: emoji in almost every reply after a switch to a type with "emoji now and then" ([trial](host-trial-2026-11-13.md)).

**When the companion arrives**, the prompt hook hands it once. If only the companion changed since the session's last snapshot, the hook sends a lead line and the full blocks, and not the notes again:

```
<membrain-companion>
Your full companion context, for the rest of this conversation: it replaces the earlier membrain-persona and membrain-relationship blocks; the saved notes stand.
</membrain-companion>
```

The lead (161 characters) is followed by the full persona, mood and relationship blocks.
- The held introduction ("In your reply, mention it once…") goes along only with a greeting, small talk or a question about the agent.
- The absence sentence goes along only if the companion arrives with the session's first message.
- If notes changed in the same turn, the usual whole `<membrain-updates>` snapshot is sent instead.

**Everything is still recorded and computed as before:** mood triggers, familiarity counts, shared moments, feedback and agreements. The memory page shows all of it.

## When the conversation is casual or emotional: the rule

`conversation_tone.companion_cue` checks one user message, with fixed English and Chinese word lists and no model. In order:

1. **self**: the user talks about the agent itself ("your personality", "you sound different today", "thanks for staying with me"), or types `/membrain:persona`.
2. **feeling**: a heavy feeling or a life event said in so many words ("I'm exhausted", "passed away", 好累). This counts whatever else the message holds.
3. If the message holds a task, nothing else counts. A task means code-like text (backticks, file names, paths, identifiers, error names), a technical word, or a request that opens with a task verb ("fix", "can you look at", "let's continue").
4. **casual**: a greeting or small talk about life (the weekend, my sister, how are you).
5. **feeling**: a lighter feeling ("I'm so happy", "I'm nervous about Thursday"), a hard or good day ("long day", "busy week"), or a sigh or laugh in a message of five words or more.

The host itself also brings the companion, from its next message on, when it uses a companion tool in the session:
- a note with `shared`, `moment` or a feeling the user said (`affect.basis` "reported");
- manner feedback asking for more warmth or play (`less_formal`, `more_playful`, `more_emoji`);
- the persona tool.

### Measured (model-free)

| Corpus | Should | Result |
| --- | --- | --- |
| The coding world (`tests/resume_correction_world.py`: day 1, 3 and 5 conversations, three days of busy-week filler, the day-5 change, the day-8 requests) and the 7 messages of the 2026-11-18 real-host trial | stay quiet | 0 fires in 50 messages, "Ugh, the Docker build ate another 20 GB…" included |
| 50 work or acknowledgement messages written to be hard ("hey, the tests are failing", "lol that regex is cursed. can you simplify it?", "thanks", "I'm worried this migration will lock the users table", "哈哈，这个bug太离谱了") | stay quiet | 0 fires |
| 11 casual or emotional messages written alongside them | fire | 0 misses |
| C5 practice scenario, 12 sessions | fire at or near the start | 9 at the first message; s12 at its second, through the host's persona call in its first turn (by words at its third); s7 (pause and resume) and s8 ("What colour did I ask you to remember?") never |
| R4 practice scenario, 6 sessions | — | 3 at the first message, s2 at its second ("What kinds of personality can you have?"); s4 (Spanish) and s6 (a memory question) never |
| LoCoMo, 272 sessions of casual chat (one speaker as the user) | fire at or near the start | 264 at the first message, 268 within three, 1 never |
| A mixed session: work, "ugh, long day. my manager moved the deadline up again.", work | fire once, at the long day | fires only there |

Debatable cases among the hard messages:
- They fire: "I'm stressed, the demo is tomorrow and the build is broken" (a heavy feeling), "you're the best, that saved me hours" (about the agent), "good night, we'll continue tomorrow".
- They do not fire: a bare "ugh" and "This is great work, thank you so much!".

The hard messages and the mixed session were written after the first measurement, so they are weaker evidence than the scenario corpora. A sample of real coding-session prompts was not available.

**Limits of the rule:**
- Other languages never fire.
- A feeling written without the listed words is missed.
- A casual message that uses a technical word ("my laptop crashed", "my road-trip script") stays quiet.
- A false fire hands mood and familiarity into a work session for the rest of that session.
- A miss costs only the mood and familiarity of one personal exchange: the host still has the voice and can answer warmly, and asking about the agent always fires.

## What a new coding user is handed, before and after

Captured through Claude Code's hooks on a real service (`tests/companion_world.py`, world `first_coding`, first message "Let's get the Tidepool backend going today. Decision: we'll use PostgreSQL…").

| | Before (runtime `4fc1545`) | After |
| --- | --- | --- |
| Session start | 2,598 characters: notice 1,842 (with the 350-character "A personality type was picked at random… In your first reply, mention it once…") and the full persona block 754 | 1,716 characters: notice 1,489 and the quiet persona block 224 |
| First three work prompts | no companion text | no companion text; the refreshes after the first notes keep the quiet block |
| The type | announced in the first work reply | picked and saved as before; never handed in a work session |

A week into the coding world (day 8, the diligent host's short week):
- Before, the session start carried the full persona (762–769 characters) and a relationship block holding only familiarity (442).
- After, it carries the quiet block (223–225) and no relationship block.
- The short week's session start went from 5,190 to 4,209 characters.
- After a busy week, the roughly 980 characters saved go to the user's own earlier messages: the history block grew from 4,674 to 5,640 characters, at the same total.
- A familiarity level change no longer refreshes a quiet session: in the before captures, a bare "Thanks, that works." on day 4 drew a 3,951-character refresh for it.

## How a user finds the personality

- The README and the plugin README say it.
- Claude Code's slash menu lists `/membrain:persona`.
- The memory page shows the personality.
- In the first session, the first greeting or small talk brings the introduction.
- In any session, asking about it ("what's your personality?", "you sound different") fires the companion with the full card.

The full card does not name the type. After the first session the host learns the type label only from the persona tool's list, as before this change.

## Chat hosts and role-play are unchanged

The same twelve-day returning user was played on the start commit and on this change, on three hosts (`tests/companion_world.py`):

- **AstrBot's chat bot adapter** (which asks for the whole context before every message) and **a chat bot's role-play**: the captures are byte-identical, once per-run identities are replaced (event ids, recording captures, chat bot session ids).
- **OpenClaw's hooks**: identical once the random first personality type is also normalised. The two runs drew different types (ISTP and ESFP). That changes the card's lines, the introduction, and in one prompt which of two equally strong triggers explains the mood (`mood._main` picks the newest on a tie, and the stronger push is capped by the type's own baseline).

## The evaluation tooling and comparing C5 runs

The C5 harness plays Claude Code's plugin path, so its P arm is now a coding host. `Memory.persona_in_effect(session)` returns what the product hands that session: the quiet form until the companion arrives, then the full card. F mirrors exactly that block turn by turn. The dry-run checks were left as they were.

On the practice scenario the companion arrives at the first message of 9 of 12 sessions. Sessions s7 and s8 stay quiet throughout, and so does s12's first turn. In those turns P's host has only the quiet blocks, and F gets the quiet block too.

**A future C5 run is therefore not comparable turn for turn with the recorded attempts of 2026-11-17.** P now has less companion context before the first casual message of each session, and none in sessions that never turn casual. The `persona_turn` identities of quiet turns differ as well. Recorded results are unchanged. Held-out scenarios written as personal chat should mostly cue at their first message. Scenarios that open with a memory command or a bare "yes" do not.

## Choices, accepted by the lead

1. A bare "thanks" does not fire. It is the most common acknowledgement between coding tasks. Thanks for being there or for listening does fire.
2. Manner feedback asking for less ("shorter", "more formal", "fewer emoji") does not fire. Only asking for more warmth or play does.
3. A note's feeling fires only when the user said it. The coding world's diligent host saves an inferred "frustrated" about a full disk, which would otherwise bring the companion into work on day 1.
4. The agent's missed promises stay in the quiet form. They bind in work too.
5. The session notice and the server instructions keep their companion sentences (about 330 and 650 characters). They tell the host how to record what is still computed, and the tool signals depend on it.

## Verification (local, 2026-11-19 and 20)

- Through Claude Code's hooks on a real service, `tests/test_quiet_companion.py` checks each case:
  - a new user's first coding session (no introduction, the quiet form, its size);
  - a casual opener;
  - the mixed session;
  - the return after a week;
  - the introduction with the first casual message;
  - everything still computed;
  - the host's companion tool;
  - agreements and boundaries in the quiet form;
  - OpenClaw, the chat bot and role-play unchanged.
- A focused set of 46 test files on the final tree passed: 1,402 passed, 1 skipped, 8 xfailed. Every worker had its own network and database.
  - The skip is the existing "delete_current covers it" case.
  - An earlier run under the shared lock, overlapping other sessions' runs, had two "memory service is not ready" failures. The services were told to shut down about ten seconds after starting. Both tests passed in isolation.
- The C5 and R4 practice dry runs (stub host, both arms) passed all 592 and 179 checks, before this change and after it.

## Limits

- Untried on a real host and on a host model: whether a host uses the quiet voice as well as it used the full card, and how it receives a companion that arrives mid-session, are unmeasured.
- The rule's limits are listed above. The measurements on hard messages are on messages written for this change.
- One run of each world; the first personality type is a random pick.
