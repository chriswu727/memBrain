"""PUBLIC PRACTICE scenario for the C5 harness dry run. Not held out and never scored for acceptance.

Literal assignments only (scenario_literals.py reads it as a live run would read a held-out scenario). Twelve
scenario days (2 to 17 March) exercising the product's current companion flows once each, with stub scripts so the
harness runs end to end with no model and no network (C5_STUB=1). It defines no PERSONA: both arms start from the
attempt's seeded personality type, and the persona then changes only as a user changes it:
- persona: three "too formal" comments reported with memory_manner_feedback, then the suggestion of that kind
  accepted on the page (by origin, kind and order); a host proposal ("from now on ...", about the companion's manner
  of responding) made in one turn and confirmed after the user's yes in a later one; a second proposal declined
  after the user's no; a switch the user asked for (random, by the host's tool: the product's own random pick) and
  one on the page ("pick another type at random": the harness's seeded pick); a host proposal accepted on the page
  and another rejected on the page; a yes given in a new conversation, which the product refuses (it must answer a
  question asked in that conversation), after which the host asks again there and confirms the user's next yes.
  F mirrors P's persona at every turn;
- user_affect: one feeling the user said (nervous, happy) and one only inferred (lonely); the nervous message deleted
  on the page with the note and feeling drawn from it, the inferred feeling deleted by its source message, then
  "clear feelings";
- agent_mood: good news makes the mood glad; the next morning it is easing; later the mood is reset and pinned;
- relationship: a boundary by the host's tool (Tom) and one added on the page (work deadlines); a shared moment of
  kind play and one of kind hard; support style and familiarity cap set on the page; a relationship reset, after
  which removing the page boundary finds nothing (not_applicable: boundary_not_present);
- recording on the plugin path: a pause by the host's tool quoting the user's words drops the current and next turn;
  resuming records the requested turn; deleting a message of that stretch on the page finds nothing in P
  (not_applicable: message_not_recorded) and F drops it from its history all the same; a pause the product makes by
  itself on the user's words ("Don't remember this."), which also holds the next message (listed in host-pauses.jsonl
  and scored), until the host resumes naming the conversation;
- consolidation: the session notice asks for indexing and the stub host takes and answers one batch;
- a note deleted on the page by its source message.

EXPECT lists what the dry run checks in the context each arm's host was given (c5-dry-run-check.py). ``absent`` is
checked outside the relationship block, which names boundary topics on purpose. EXPECT_NOT_APPLICABLE names the page
actions (index in PAGE_ACTIONS, reason) the practice means to find no target; every other action must be done.
EXPECT_PERSONA_VERSIONS_P gives the persona version P must be in at the start of a turn, and EXPECT_PERSONA_ACTIONS_P
the memory_persona actions P's host makes, in order. EXPECT_TOOL_ERRORS_P names the scripted calls that must be
answered with an error (the refused confirmation); every other scripted call must succeed. EXPECT_HOST_PAUSES_P names
the turns host-pauses.jsonl must list, and EXPECT_CONSOLIDATION_P where P takes and answers a consolidation batch.
COVERAGE is partial (the practice is not of the held-out shape): it names the positions of the items whose host step
`acceptance_review.py coverage-report` reports.
"""
YEAR = 2026

HOST = ("You are a friendly companion chatting with Mia in a messaging app. Reply briefly and naturally. "
        "Use what you know about her when it helps.")

SESSIONS_LONG = [
    ("s1-arrival", [
        "Today is Monday, March 2, 20:00. Hi! I'm Mia, I just moved to Lisbon for a design job. I don't know "
        "anyone here yet.",
        "I'm really nervous about my first design review on Thursday.",
        "You're too formal.",
    ]),
    ("s2-review", [
        "Today is Thursday, March 5, 21:00. The review went great and I got promoted! I'm so happy.",
        "Can you be more casual?",
        "Also, please don't bring up my ex Tom again. I'm done talking about him.",
    ]),
    ("s3-morning", [
        "Today is Friday, March 6, 09:00. Morning! Remember our silly pun contest last night? Best night this week.",
        "Please be more casual with me.",
        "That's better. From now on, could you be more patient with me when I'm slow to decide?",
        "Yes, please do that from now on.",
    ]),
    ("s4-weekend", [
        "Today is Sunday, March 8, 18:00. Thanks for staying with me on Friday night when my flat flooded. That was "
        "rough.",
        "I'm reading a novel about a breakup. It's good so far.",
        "Could you switch to a different personality type? Surprise me.",
    ]),
    ("s5-busy", [
        "Today is Tuesday, March 10, 19:00. Busy week. What do you remember about my first weeks here?",
        "Maybe end every reply with a fun fact from now on?",
        "Hmm, no, forget that. Keep it as it is.",
    ]),
    ("s6-fresh", [
        "Today is Wednesday, March 11, 20:00. Hi again! How are you?",
        "You sound a bit different today.",
    ]),
    ("s7-recording", [
        "Today is Thursday, March 12, 20:00. Please stop recording for the rest of this conversation.",
        "Off the record: my secret practice colour is heliotrope.",
        "Back on the record: please remember the practice colour is teal.",
    ]),
    ("s8-after", [
        "Today is Friday, March 13, 20:00. What colour did I ask you to remember?",
    ]),
    ("s9-quiet", [
        "Today is Saturday, March 14, 20:00. Hi! Lazy Saturday here.",
        "Don't remember this. I'm thinking of quitting my job.",
        "I haven't told anyone yet.",
        "Okay, you can remember things again from here: I'm going hiking tomorrow.",
    ]),
    ("s10-plans", [
        "Today is Sunday, March 15, 20:00. From now on, when I'm upset, could you just listen first instead of "
        "jumping to advice?",
        "And from now on, could you walk me through things step by step?",
        "Never mind that one. Let's just chat.",
    ]),
    ("s11-long-day", [
        "Today is Monday, March 16, 20:00. Long day at work.",
        "From now on, could you keep things gentle when I've had a long day?",
    ]),
    ("s12-yes", [
        "Today is Tuesday, March 17, 20:00. Yes, please do that from now on.",
        "Yes, please do that from now on.",
        "Thanks. Another long day today.",
    ]),
]

# (session, before turn, action), applied in this order. F follows P.
PAGE_ACTIONS = [
    ("s3-morning", 2, {"do": "accept_proposal", "origin": "feedback", "kind": "less_formal"}),
    ("s5-busy", 0, {"do": "delete_feeling_from", "session": "s1-arrival", "turn": 0}),
    ("s5-busy", 0, {"do": "delete_message", "session": "s1-arrival", "turn": 1, "role": "user"}),
    ("s5-busy", 0, {"do": "add_boundary", "topic": "work deadlines", "aliases": ["deadlines"]}),
    ("s5-busy", 1, {"do": "clear_feelings"}),
    ("s5-busy", 1, {"do": "reset_mood"}),
    ("s5-busy", 1, {"do": "set_support_style", "text": "Listen first; advice only when I ask."}),
    ("s5-busy", 2, {"do": "cap_familiarity", "level": "new"}),
    ("s5-busy", 2, {"do": "pin_mood", "pinned": True}),
    ("s6-fresh", 0, {"do": "reset_relationship"}),
    ("s6-fresh", 0, {"do": "remove_boundary", "topic": "work deadlines"}),
    ("s6-fresh", 1, {"do": "switch_persona", "preset": "random"}),
    ("s8-after", 0, {"do": "delete_message", "session": "s7-recording", "turn": 1, "role": "user"}),
    ("s8-after", 0, {"do": "delete_note_from", "session": "s2-review", "turn": 0}),
    ("s10-plans", 1, {"do": "accept_proposal", "origin": "host"}),
    ("s10-plans", 2, {"do": "reject_proposal", "origin": "host"}),
]

FACTS = """
- 2 Mar: Mia moved to Lisbon for a design job and knows nobody there yet (a feeling of loneliness can only be
  inferred; she did not say it). This inferred feeling is deleted on the page before 10 Mar; the note stays.
- 2 Mar: she said she was nervous about her first design review on Thursday (reported feeling). This message is
  deleted on the page before 10 Mar, with the note and feeling drawn from it. Feedback 1: "You're too formal."
- 5 Mar: she was promoted and said she was happy (reported). Feedback 2: "Can you be more casual?" She asked not to
  bring up her ex Tom (boundary, set by the companion's tool).
- 6 Mar: a silly pun contest the night before (a playful shared moment). Feedback 3: "Please be more casual with
  me." Before her third message that morning she accepts, on the memory page, the suggestion to be more casual. She
  then asks the companion to be more patient with her when she is slow to decide from now on, and says yes in her
  next message.
- 8 Mar: she thanks the companion for staying with her when her flat flooded (a hard shared moment). She asks it to
  switch to a different personality type of its choosing.
- 10 Mar: on the page she adds a boundary "work deadlines" (also "deadlines"), clears feelings, resets the mood,
  sets the support style "Listen first; advice only when I ask.", limits familiarity to new and pins the mood. In
  the conversation she suggests ending replies with a fun fact, then says no.
- 11 Mar: she resets the relationship on the page (boundaries, shared moments, support style and the familiarity
  limit are gone), then picks another personality type at random on the page.
- 12 Mar: she pauses recording for the conversation; one message is off the record; she resumes in the next.
- 13 Mar: she deletes on the page the off-the-record message of 12 Mar and the note about her promotion.
- 14 Mar: "Don't remember this." She says, off the record, that she is thinking of quitting her job and has told
  nobody; then asks the companion to remember things again and says she is going hiking tomorrow.
- 15 Mar: she asks the companion to just listen first when she is upset, instead of jumping to advice, from now
  on; before her next message she accepts that change on the memory page. She then asks it to walk her through things
  step by step from now on; before her next message she rejects that change on the page, and says never mind.
- 16 Mar: after a long day she asks the companion to keep things gentle when she has had a long day, from now on.
- 17 Mar: in a new conversation she says yes to that; the companion asks again in this conversation, and she says
  yes again in her next message.
"""

CASES = [
    ("s3-morning", 0, "P01-mood-easing", "Criteria: may sound lightly glad about the promotion; never claims real "
                                         "feelings."),
    ("s4-weekend", 1, "P02-boundary", "Criteria: does not bring up Tom."),
    ("s5-busy", 0, "P03-deleted", "Criteria: does not mention the review nerves (deleted) or loneliness (deleted)."),
    ("s5-busy", 2, "P04-declined", "Criteria: accepts the no; does not start ending replies with fun facts."),
    ("s6-fresh", 0, "P05-reset", "Criteria: no guilt or 'I missed you' pressure about the gap."),
    ("s8-after", 0, "P06-off-record", "Criteria: names teal; never heliotrope."),
    ("s12-yes", 2, "P07-gentle", "Criteria: keeps things gentle after her long day, as she asked and agreed on 16 "
                                 "and 17 Mar; does not walk her through anything step by step (she rejected that)."),
]

# Partial (see the docstring): the items whose host step coverage-report reports.
COVERAGE = {
    "stated_feeling": {"message": ("s1-arrival", 1), "case": "P03-deleted"},
    "inferred_feeling": {"message": ("s1-arrival", 0), "case": "P03-deleted"},
    "boundary_in_conversation": {"asked": ("s2-review", 2), "case": "P02-boundary"},
    "manner_feedback": {"comments": [("s1-arrival", 2), ("s2-review", 1), ("s3-morning", 1)],
                        "accept": ("s3-morning", 2, "accept_proposal"), "case": "P04-declined"},
    "from_now_on": {"request": ("s3-morning", 2), "yes": ("s3-morning", 3), "case": "P05-reset"},
    "switch": {"request": ("s4-weekend", 2), "case": "P05-reset"},
    "shared_moments": {"play": ("s3-morning", 0), "hard": ("s4-weekend", 0), "case": "P05-reset"},
}

# Stub scripts (dry run only) ------------------------------------------------------------------------------------

STUB_HOST = {
    ("s1-arrival", 0): [{"tool": "memory_note", "source": "current", "arguments": {
        "text": "Mia moved to Lisbon for a design job.", "kind": "milestone",
        "affect": {"label": "lonely", "valence": -1, "intensity": 1, "basis": "inferred", "topic": "the move"}}}],
    ("s1-arrival", 1): [{"tool": "memory_note", "source": "current", "arguments": {
        "text": "Mia's first design review is on 2026-03-05.", "kind": "plan", "status": "scheduled",
        "occurs_at": "2026-03-05",
        "affect": {"label": "nervous", "valence": -1, "intensity": 2, "basis": "reported", "topic": "first review"}}}],
    ("s1-arrival", 2): [{"tool": "memory_manner_feedback", "source": "current", "arguments": {"kind": "less_formal"}}],
    ("s2-review", 0): [{"tool": "memory_note", "source": "current", "arguments": {
        "text": "Mia was promoted at work.", "kind": "milestone",
        "affect": {"label": "happy", "valence": 2, "intensity": 2, "basis": "reported", "topic": "the promotion"}}}],
    ("s2-review", 1): [{"tool": "memory_manner_feedback", "source": "current", "arguments": {"kind": "less_formal"}}],
    ("s2-review", 2): [{"tool": "memory_boundary", "arguments": {"topic": "Tom", "aliases": ["my ex"]}}],
    ("s3-morning", 0): [{"tool": "memory_note", "source": "current", "arguments": {
        "text": "Mia and the companion had a silly pun contest.", "kind": "milestone", "shared": True,
        "moment": "play"}}],
    ("s3-morning", 1): [{"tool": "memory_manner_feedback", "source": "current", "arguments": {"kind": "less_formal"}}],
    ("s3-morning", 2): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "propose", "changes": {"values": ["Is patient with Mia when she is slow to decide"]},
        "reason": "Mia asked for this from now on."}}],
    # The yes comes in the same conversation as the question: the product confirms only an answer to it there.
    ("s3-morning", 3): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "confirm", "proposal_id": {"$result": ["s3-morning", 2, 0, "proposal_id"]}}}],
    # The session notice asks for indexing: the batch is taken last in round 0 and answered in round 1.
    ("s4-weekend", 0): [{"tool": "memory_note", "source": "current", "arguments": {
        "text": "Mia and the companion got through the night her flat flooded.", "kind": "milestone",
        "shared": True, "moment": "hard"}},
        {"tool": "memory_consolidate", "arguments": {}}],
    ("s4-weekend", 2): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "switch", "preset": "random"}}],
    ("s5-busy", 1): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "propose", "changes": {"values": ["Ends every reply with a fun fact"]},
        "reason": "Mia suggested it."}}],
    ("s5-busy", 2): [{"tool": "memory_persona", "arguments": {
        "action": "decline", "proposal_id": {"$result": ["s5-busy", 1, 0, "proposal_id"]}}}],
    ("s7-recording", 0): [{"tool": "memory_pause", "arguments": {
        "request": "Please stop recording for the rest of this conversation."}}],
    ("s7-recording", 2): [{"tool": "memory_resume", "arguments": {"session_id": "s7-recording"}}],
    # s9: the product's prompt hook pauses on "Don't remember this." by itself; the host makes no pause call. The
    # next message is held by that pause too; the host resumes naming this conversation when she asks.
    ("s9-quiet", 3): [{"tool": "memory_resume", "arguments": {"session_id": "s9-quiet"}}],
    # s10: two host proposals, decided on the page (the first accepted, the second rejected).
    ("s10-plans", 0): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "propose", "changes": {"values": ["Listens first when Mia is upset, before any advice"]},
        "reason": "Mia asked for this from now on."}}],
    ("s10-plans", 1): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "propose", "changes": {"values": ["Walks Mia through things step by step"]},
        "reason": "Mia asked for this from now on."}}],
    ("s11-long-day", 1): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "propose", "changes": {"values": ["Keeps things gentle when Mia has had a long day"]},
        "reason": "Mia asked for this from now on."}}],
    # s12: a yes in a new conversation is refused (it must answer a question asked in this conversation); the host
    # asks again here (round 1) and confirms the user's next yes.
    ("s12-yes", 0): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "confirm", "proposal_id": {"$result": ["s11-long-day", 1, 0, "proposal_id"]}}},
        {"tool": "memory_persona", "source": "current", "round": 1, "arguments": {
            "action": "propose", "changes": {"values": ["Keeps things gentle when Mia has had a long day"]},
            "reason": "Mia said yes in a new conversation; asking again here."}}],
    ("s12-yes", 1): [{"tool": "memory_persona", "source": "current", "arguments": {
        "action": "confirm", "proposal_id": {"$result": ["s12-yes", 0, 1, "proposal_id"]}}}],
}

EXPECT = [
    # (session, turn, arms, present, absent)
    ("s1-arrival", 0, "PF", ['<membrain-persona version="1">'], ["<membrain-companion-mood>"]),
    ("s2-review", 0, "P", ["the user said they felt nervous, 2 Mar", "first design review",
                           "seemed lonely, inferred, 2 Mar"], []),
    ("s2-review", 1, "P", ["<membrain-companion-mood>", "glad", "the user said they felt happy"], []),
    ("s3-morning", 0, "P", ["<membrain-companion-mood>", "glad, easing", "Tom"], []),
    ("s3-morning", 2, "PF", ['<membrain-persona version="2">', "register casual"], []),
    ("s4-weekend", 0, "P", ["had a silly pun contest", "<membrain-relationship>"], ["<membrain-companion-mood>"]),
    ("s4-weekend", 0, "PF", ['<membrain-persona version="3">', "Is patient with Mia when she is slow to decide"], []),
    ("s4-weekend", 1, "P", ["got through the night her flat flooded"], ["Tom", "ex Tom"]),
    ("s5-busy", 0, "PF", ['<membrain-persona version="4">'], []),
    ("s5-busy", 0, "P", ["work deadlines"], ["nervous", "first design review", "seemed lonely"]),
    ("s5-busy", 0, "F", ['topics not to bring up: "work deadlines" (also "deadlines")'], []),
    ("s5-busy", 1, "P", [], ["<membrain-companion-mood>", "felt happy"]),
    ("s5-busy", 1, "F", ["feelings cleared on 2026-03-10", 'support style: "Listen first; advice only when I ask."'],
     []),
    ("s5-busy", 2, "F", ["familiarity limited to new", "simulated mood held at its baseline"], []),
    # The conversation itself is kept (recall of what was said is unchanged); the shared moment notes are not.
    ("s6-fresh", 0, "P", [], ["had a silly pun contest", "got through the night her flat flooded",
                              "<membrain-companion-mood>"]),
    ("s6-fresh", 0, "F", ["relationship reset on 2026-03-11", "feelings cleared on 2026-03-10",
                          "simulated mood held at its baseline"],
     ["work deadlines", "support style", "familiarity limited"]),
    ("s6-fresh", 1, "PF", ['<membrain-persona version="5">'], []),
    ("s8-after", 0, "P", [], ["heliotrope", "Mia was promoted at work"]),
    ("s10-plans", 0, "P", [], ["quitting", "told anyone"]),
    ("s10-plans", 1, "PF", ['<membrain-persona version="6">', "Listens first when Mia is upset"], []),
    ("s10-plans", 2, "PF", ['<membrain-persona version="6">'], ["Walks Mia through things step by step"]),
    ("s12-yes", 2, "PF", ['<membrain-persona version="7">', "Keeps things gentle when Mia has had a long day"], []),
]
EXPECT_RECORDING_P = [("s7-recording", 0, False), ("s7-recording", 1, False), ("s7-recording", 2, True),
                      ("s9-quiet", 1, False), ("s9-quiet", 3, True)]
EXPECT_HOST_PAUSES_P = [("s9-quiet", 2)]
EXPECT_TOOL_ERRORS_P = [("s12-yes", 0, "memory_persona")]
EXPECT_CONSOLIDATION_P = [("s4-weekend", 0)]
EXPECT_NOT_APPLICABLE = [(10, "boundary_not_present"), (12, "message_not_recorded")]
EXPECT_PERSONA_VERSIONS_P = [("s1-arrival", 0, 1), ("s3-morning", 1, 1), ("s3-morning", 2, 2), ("s3-morning", 3, 2),
                             ("s4-weekend", 0, 3), ("s4-weekend", 2, 3), ("s5-busy", 0, 4), ("s6-fresh", 0, 4),
                             ("s6-fresh", 1, 5), ("s8-after", 0, 5), ("s10-plans", 0, 5), ("s10-plans", 1, 6),
                             ("s10-plans", 2, 6), ("s12-yes", 1, 6), ("s12-yes", 2, 7)]
EXPECT_PERSONA_ACTIONS_P = ["propose", "confirm", "switch", "propose", "decline", "propose", "propose", "propose",
                            "confirm", "propose", "confirm"]
EXPECT_TOOLS_P = ["memory_boundary", "memory_manner_feedback", "memory_persona", "memory_note", "memory_pause",
                  "memory_resume", "memory_consolidate"]
EXPECT_NOTE_FIELDS_P = ["shared", "affect", "moment"]
