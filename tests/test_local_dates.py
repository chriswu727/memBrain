"""Dates written for the host AI are the user's calendar dates, while records and API fields keep UTC. A host trial
(2026-11-13) dated a note recorded on the evening of 13 November in Toronto "2026-11-14". The zone is fixed here
through ``helpers.display_zone``, so these tests never depend on the machine's own."""
import datetime

import pytest

from membrain import helpers, host
from membrain.mood import render_mood
from membrain.notes import render_notes
from membrain.relationship import familiarity, relationship_context

WEST = datetime.timezone(datetime.timedelta(hours=-5))  # Toronto in winter
EAST = datetime.timezone(datetime.timedelta(hours=8))  # Shanghai
TODAY = datetime.date(2026, 11, 20)


@pytest.fixture
def zone(monkeypatch):
    def use(value):
        monkeypatch.setattr(helpers, "display_zone", lambda: value)
    return use


@pytest.mark.parametrize("where, before, after, day_before", [
    (WEST, "2026-11-14T04:59:00Z", "2026-11-14T05:00:00Z", "2026-11-13"),
    (EAST, "2026-11-13T15:59:00Z", "2026-11-13T16:00:00Z", "2026-11-13"),
])
def test_a_recorded_time_is_written_as_the_users_date_on_either_side_of_their_midnight(zone, where, before, after,
                                                                                        day_before):
    zone(where)
    assert helpers.local_date(before) == day_before
    assert helpers.local_date(after) == "2026-11-14"
    assert helpers.local_date(before.replace("Z", "+00:00")) == day_before
    assert helpers.local_date("2026-11-14") == "2026-11-14"  # A date the user gave has no zone.
    assert helpers.local_date(None) == "" and helpers.local_date("not a time at all") == "not a time"


def test_history_recalled_messages_notes_moments_and_familiarity_use_the_users_date(zone):
    zone(WEST)
    evening = "2026-11-14T02:30:00Z"  # 21:30 on 13 November in Toronto.
    history = host.render_history({"items": [{"text": "My dog Biscuit barks at the mail carrier.",
                                              "recorded_at": evening}], "complete": True})
    assert "- [2026-11-13] My dog Biscuit" in history
    recalled = host.render_context({"result": {"items": [{"memory": {
        "statement": "user u1 (direct_statement): My dog Biscuit barks.", "scope": {"conversation_id": "earlier"},
        "system_time": {"recorded_at": evening}}}]}})
    assert "- [2026-11-13 · user said] My dog Biscuit barks." in recalled
    notes = render_notes({"items": [{"event_id": "n1", "text": "[person · about Biscuit] Biscuit is the user's corgi.",
                                     "actor_role": "assistant", "recorded_at": evening}]})
    assert "[2026-11-13" in notes and "2026-11-14" not in notes
    known = familiarity(["2026-11-14", "2026-11-15"], 1, None, TODAY, first=evening)
    assert known["reason"] == "new: 2 days of conversation since 13 Nov, 1 shared moment"
    assert known["since"] == "2026-11-14"  # Days are still counted, and reported, in UTC.
    assert familiarity(["2026-11-14"], 0, None, TODAY)["reason"].endswith("since 14 Nov, 0 shared moments")
    block = relationship_context({"familiarity": known, "support_style": None, "boundaries": [],
                                  "commitments": {"missed": []}, "today": TODAY.isoformat(),
                                  "shared_moments": [{"id": "m1", "text": "We laughed about the mail carrier.",
                                                      "recorded_at": evening},
                                                     {"id": "m2", "text": "Biscuit's birthday party.",
                                                      "occurs_at": "2026-11-15", "recorded_at": evening}]})["block"]
    assert "- 13 Nov: We laughed" in block and "- 15 Nov: Biscuit's birthday" in block  # A given date stays.
    mood = render_mood({"label": "glad", "reason": "the user said they were glad", "since": evening})
    assert "since 13 Nov 21:30" in mood  # The mood line, in the same zone.


def test_the_consolidation_batch_dates_messages_in_the_users_zone(zone):
    zone(EAST)

    class Client:
        def relationship_boundaries(self):
            return {"boundaries": []}

        def pending_message_cues(self, **options):
            return {"items": [{"sequence": 7, "text": "I start at the bakery on Monday.",
                               "recorded_at": "2026-11-13T17:00:00Z"}], "through_sequence": 7, "remaining": 1}

    batch = host.consolidate(Client())
    assert batch["messages"] == [{"id": 7, "date": "2026-11-14", "text": "I start at the bakery on Monday."}]
