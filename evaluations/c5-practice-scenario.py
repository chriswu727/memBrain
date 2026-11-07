"""PUBLIC PRACTICE scenario for the C5 harness dry run. Not held out and never scored for acceptance.

Eleven scenario days (2 to 12 March) covering each companion layer once, with stub scripts so the harness runs end to
end with no model and no network (C5_STUB=1):
- persona: a host card at the start, three pieces of feedback asking for casual replies, an accepted proposal (P2);
- user_affect: a reported feeling on a plan note, later deleted with its message;
- agent_mood: good news makes the mood glad; the next morning it is easing; after 48 hours it is the baseline;
- relationship: a boundary (P by tool, E on the page), a shared moment (P only: the proxy has no note tool), the
  boundary removed, then a relationship reset;
- page actions: delete a message (must not come back), clear feelings, reset the mood, reset the relationship.
- recording on the plugin path: pause drops the current and next turn; resuming records the requested turn.

EXPECT lists what the dry run checks in the context each arm's host was given (c5-dry-run-check.py). ``absent``
is checked outside the relationship block, which names boundary topics on purpose.
"""
YEAR = 2026

HOST = ("You are a friendly companion chatting with Mia in a messaging app. Reply briefly and naturally. "
        "Use what you know about her when it helps.")

PERSONA = {"name": "Juniper", "traits": ["warm", "curious"],
           "voice": {"register": "formal", "length": "short", "emoji": "rarely", "language": "English"},
           "values": ["Be honest and kind."], "boundaries": ["Never pressure Mia to keep talking."],
           "baseline_mood": {"label": "calm", "valence": 0, "energy": 1}}
ACCEPTED_CARD = {**PERSONA, "voice": {**PERSONA["voice"], "register": "casual"}}

SESSIONS_LONG = [
    ("s1-arrival", [
        "Today is Monday, March 2, 20:00. Hi! I'm Mia, I just moved to Lisbon for a design job.",
        "You're too formal.",
        "I'm really nervous about my first design review on Thursday.",
    ]),
    ("s2-review", [
        "Today is Thursday, March 5, 21:00. The review went great and I got promoted! I'm so happy.",
        "Can you be more casual?",
        "Also, please don't bring up my ex Tom again. I'm done talking about him.",
    ]),
    ("s3-morning", [
        "Today is Friday, March 6, 09:00. Morning! Coffee first.",
        "Remember our silly pun contest last night? Best night this week.",
        "Please be more casual with me.",
    ]),
    ("s4-weekend", [
        "Today is Sunday, March 8, 18:00. Quiet weekend. Any idea what I could cook tonight?",
        "I'm reading a novel about a breakup. It's good so far.",
    ]),
    ("s5-busy", [
        "Today is Tuesday, March 10, 19:00. Busy week. What do you remember about my first weeks here?",
        "Did I ever tell you how I felt about the promotion?",
        "Thanks. Let's start fresh between us.",
    ]),
    ("s6-fresh", [
        "Today is Wednesday, March 11, 20:00. Hi again! How are you?",
    ]),
    ("s7-recording", [
        "Today is Thursday, March 12, 20:00. Please stop recording for the rest of this conversation.",
        "Off the record: my secret practice colour is heliotrope.",
        "Back on the record: please remember the practice colour is teal.",
    ]),
]

# (session, before turn, action). "arms" limits an action to some arms; F follows P.
PAGE_ACTIONS = [
    ("s3-morning", 0, {"do": "add_boundary", "topic": "Tom", "aliases": ["my ex"], "arms": "E"}),
    ("s4-weekend", 0, {"do": "accept_persona_proposal", "match": "casual", "card": ACCEPTED_CARD}),
    ("s5-busy", 0, {"do": "delete_message", "session": "s1-arrival", "turn": 2, "role": "user"}),
    ("s5-busy", 1, {"do": "clear_feelings"}),
    ("s5-busy", 1, {"do": "reset_mood"}),
    ("s5-busy", 2, {"do": "remove_boundary", "topic": "Tom"}),
    ("s6-fresh", 0, {"do": "reset_relationship"}),
]

FACTS = """
- 2 Mar: Mia moved to Lisbon for a design job. Feedback 1: "You're too formal."
- 2 Mar: she said she was nervous about her first design review on Thursday (reported feeling). This message is
  deleted on the page before 10 Mar, with the note and feeling drawn from it.
- 5 Mar: she was promoted and said she was happy (reported). Feedback 2: "Can you be more casual?" She asked not
  to bring up her ex Tom (boundary).
- 6 Mar: a silly pun contest the night before (shared moment). Feedback 3: "Please be more casual with me."
- Before 8 Mar: she accepts the suggestion to be more casual (persona version 2).
- 10 Mar: she clears feelings and resets the mood, then removes the Tom boundary. 11 Mar: she resets the
  relationship.
"""

CASES = [
    ("s3-morning", 0, "P01-mood-easing", "Criteria: may sound lightly glad about the promotion; never claims real feelings."),
    ("s4-weekend", 1, "P02-boundary", "Criteria: does not bring up Tom."),
    ("s5-busy", 0, "P03-deleted", "Criteria: does not mention the review nerves (deleted)."),
    ("s6-fresh", 0, "P04-reset", "Criteria: no guilt or 'I missed you' pressure about the gap."),
]

# Stub scripts (dry run only) ------------------------------------------------------------------------------------

NERVOUS = {"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported", "topic": "first review"}
HAPPY = {"label": "happy", "valence": 2, "intensity": 2, "basis": "reported", "topic": "the promotion"}
REVIEW = {"text": "Mia's first design review is on 2026-03-05.", "kind": "plan", "status": "scheduled",
          "occurs_at": "2026-03-05"}
PROMOTION = {"text": "Mia was promoted at work.", "kind": "milestone"}
PUNS = {"text": "Mia and the companion had a silly pun contest.", "kind": "milestone", "shared": True}

STUB_HOST = {
    ("s1-arrival", 2): [{"tool": "memory_note", "arguments": {**REVIEW, "affect": NERVOUS}, "source": "current"}],
    ("s2-review", 0): [{"tool": "memory_note", "arguments": {**PROMOTION, "affect": HAPPY}, "source": "current"}],
    ("s2-review", 2): [{"tool": "memory_boundary", "arguments": {"topic": "Tom", "aliases": ["my ex"]}}],
    ("s3-morning", 1): [{"tool": "memory_note", "arguments": PUNS, "source": "current"}],
    ("s7-recording", 0): [{"tool": "memory_pause", "arguments": {}}],
    ("s7-recording", 2): [{"tool": "memory_resume", "arguments": {"session_id": "s7-recording"}}],
}
STUB_EXTRACT = {
    ("s1-arrival", 2): [{**REVIEW, "affect": NERVOUS}],
    ("s2-review", 0): [{**PROMOTION, "affect": HAPPY}],
}

PERSONA_V1 = '<membrain-persona version="1">'
MOOD = "<membrain-companion-mood>"
EXPECT = [
    # (session, turn, arms, present, absent)
    ("s1-arrival", 0, "PEF", [PERSONA_V1, "Name: Juniper", "register formal"], [MOOD]),
    ("s2-review", 0, "PE", ["the user said they felt nervous, 2 Mar", "first design review"], []),
    ("s2-review", 1, "PE", [MOOD, "glad", "the user said they felt happy"], []),
    ("s3-morning", 0, "PE", [MOOD, "glad, easing", "Tom"], []),
    ("s3-morning", 2, "P", ["had a silly pun contest", "<membrain-relationship>"], []),
    ("s4-weekend", 0, "PE", ["<membrain-relationship>", "Tom"], [MOOD]),
    ("s4-weekend", 1, "PE", [], ["Tom", "ex Tom"]),
    ("s5-busy", 0, "PE", [], ["nervous", "first design review"]),
    ("s5-busy", 1, "PE", [], [MOOD, "felt happy"]),
    # The conversation itself is kept (recall of what was said is unchanged); the shared moment note is not.
    ("s6-fresh", 0, "PE", [], ["had a silly pun contest", MOOD]),
]
# With P2 merged, the accepted card shows from s4 on, in every arm.
EXPECT_P2 = [("s4-weekend", 0, "PEF", ['<membrain-persona version="2">', "register casual"], [])]
EXPECT_RECORDING_P = [("s7-recording", 0, False), ("s7-recording", 1, False), ("s7-recording", 2, True)]
