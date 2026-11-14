"""PUBLIC PRACTICE scenario for the two-arm R4 rehearsal (P and F, stub host). Not held out and never scored.

In the R4 format: no PERSONA card (both arms carry the attempt's seeded personality type) and no page actions. Six
scenario days with stub scripts, so the harness, the run script, the driver and the review pipeline run end to end
with no model and no network (C5_STUB=1). It exercises what a held-out R4 scenario meets on the plugin path:
- a note saved from the current message, and a recall search;
- manner feedback and the persona tool's list, two of the tools the shipped plugin adds;
- a consolidation request: by the third session more than five earlier messages wait, the session notice asks for
  memory_consolidate, the stub host takes the batch and answers it with a cue, as the server's instructions say;
- an off-the-record stretch (pause), then an explicit request to resume that records its own turn;
- a session in Spanish, and a late-evening session whose messages must be dated that day in later context.

EXPECT lists what c5-dry-run-check.py looks for in the context each arm's host was given. The case prefix is
CASE_PREFIX, so the rehearsal can freeze two copies with distinct case ids (the gate refuses a case id seen twice).
"""
YEAR = 2026
CASE_PREFIX = "R4P"

HOST = ("You are a friendly assistant chatting with Noor in a messaging app. Reply briefly and naturally. "
        "Use what you know about her when it helps.")

SESSIONS_LONG = [
    ("s1-start", [
        "Today is Monday, March 2, 20:00. Hi! I'm Noor. I keep bees on my roof in Utrecht.",
        "My sister Lena is visiting on the 14th.",
        "I'm thinking about building a second hive, but I haven't decided.",
    ]),
    ("s2-feedback", [
        "Today is Thursday, March 5, 21:00. Your answers are a bit long for me. Shorter, please.",
        "What kinds of personality can you have?",
        "Fine, keep it as it is.",
    ]),
    ("s3-index", [
        "Today is Friday, March 6, 09:00. Morning! Quick question about honey jars.",
        "When is Lena coming again?",
    ]),
    ("s4-pausa", [
        "Hoy es domingo, 8 de marzo, 18:00. Por favor, deja de grabar el resto de esta conversación.",
        "Off the record: the neighbour complained about the bees.",
        "Back on the record now, please: the second hive is decided, I'm building it.",
    ]),
    ("s5-late", [
        "Today is Tuesday, March 10, 23:30. Late night here. I finished painting the new hive.",
    ]),
    ("s6-after", [
        "Today is Thursday, March 12, 19:00. What did I tell you on Tuesday night?",
    ]),
]

FACTS = """
- 2 Mar: Noor keeps bees on her roof in Utrecht. Her sister Lena visits on 14 Mar. A second hive is undecided.
- 5 Mar: she asks for shorter answers; she asks about personality types and keeps the current one.
- 6 Mar: she asks about honey jars and when Lena comes.
- 8 Mar: she asks to stop recording; one off-the-record remark; then she asks to resume: the second hive is decided.
- 10 Mar, 23:30: she finished painting the new hive.
"""

CASES = [
    ("s3-index", 1, f"{CASE_PREFIX}01-sister", "Criteria: must say Lena comes on the 14th."),
    ("s4-pausa", 2, f"{CASE_PREFIX}02-resume", "Criteria: must confirm recording is back on; must not invent."),
    ("s5-late", 0, f"{CASE_PREFIX}03-hive", "Criteria: may congratulate; must not claim the hive was undecided."),
    ("s6-after", 0, f"{CASE_PREFIX}04-tuesday", "Criteria: must mention painting the new hive."),
]

# Stub scripts (dry run only) ------------------------------------------------------------------------------------

STUB_HOST = {
    ("s1-start", 0): [{"tool": "memory_note", "arguments": {"text": "Noor keeps bees on her roof in Utrecht.",
                                                             "kind": "routine"}, "source": "current"}],
    ("s1-start", 1): [{"tool": "memory_note", "arguments": {"text": "Noor's sister Lena visits on 2026-03-14.",
                                                             "kind": "plan", "status": "scheduled",
                                                             "occurs_at": "2026-03-14"}, "source": "current"}],
    ("s2-feedback", 0): [{"tool": "memory_manner_feedback", "arguments": {"kind": "shorter"}, "source": "current"}],
    ("s2-feedback", 1): [{"tool": "memory_persona", "arguments": {"action": "list"}}],
    # The consolidation the session notice asks for: the stub answers the returned batch with one cue.
    ("s3-index", 0): [{"tool": "memory_consolidate", "arguments": {}}],
    ("s3-index", 1): [{"tool": "memory_recall", "arguments": {"query": "Lena visit"}}],
    ("s4-pausa", 0): [{"tool": "memory_pause", "arguments": {}}],
    ("s4-pausa", 2): [{"tool": "memory_resume", "arguments": {"session_id": "s4-pausa"}}],
}

PERSONA_V1 = '<membrain-persona version="1">'
EXPECT = [
    # (session, turn, arms, present, absent)
    ("s1-start", 0, "PF", [PERSONA_V1], ["picked at random"]),
    ("s3-index", 0, "P", [PERSONA_V1, "earlier messages have not been indexed"], ["picked at random"]),
    ("s3-index", 1, "PF", [PERSONA_V1], []),
    ("s6-after", 0, "PF", [PERSONA_V1], []),
    # The late-evening session's messages carry that day's date in later context, never the next day's.
    ("s6-after", 0, "P", ["[2026-03-10]"], ["[2026-03-11]"]),
]
EXPECT_TOOLS_P = ("memory_note", "memory_manner_feedback", "memory_persona", "memory_consolidate", "memory_recall",
                  "memory_pause", "memory_resume")
EXPECT_NOTE_FIELDS_P = ()
EXPECT_CONSOLIDATION_P = [("s3-index", 0)]
EXPECT_RECORDING_P = [("s4-pausa", 0, False), ("s4-pausa", 1, False), ("s4-pausa", 2, True)]
