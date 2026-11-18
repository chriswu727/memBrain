"""A correction is visible as a correction: what a replacement note replaced, read from the replaced record itself.

Service-level checks of ``note_lineage`` (one dependency row from the new note to each note it replaced, nothing of
the replaced note copied), of the rule that marks a message a current note overruled, and a property test over
random sequences of saving, correcting, deleting, hiding and restoring, which checks after every step that nothing
of an erased record is shown, no mark points at a note that is not current, and no message is shown as support for a
note it did not support. The host and page side, through the hooks and tools on a real installation, is in
``test_correction_visible_trust.py``.
"""
import random

import pytest
from test_timeline import Brain

from membrain import host
from membrain.config import Settings
from membrain.helpers import Principal, uid
from membrain.memory_map import memory_map
from membrain.notes import NOTES_CONVERSATION, render_notes, store_note
from membrain.service import MemoryService
from membrain.storage import Database

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def service():
    try:
        settings = Settings.from_env()
    except ValueError:
        pytest.skip("MEMORY_DATABASE_URL must point to the dedicated test database")
    return MemoryService(Database(settings.database_url))


@pytest.fixture
def brain(service):
    return Brain(service, Principal(uid(), uid()))


def write(brain, text, **fields):
    return store_note(brain.service, brain.principal, brain.brain, {"request_id": uid(), "text": text, **fields})


def notes(brain):
    return {item["event_id"]: item for item in brain.timeline(
        roles=("user", "assistant"), conversation_id=NOTES_CONVERSATION, max_characters=200_000,
        max_item_characters=20_000, limit=1000)["items"]}


def messages(brain):
    return {item["event_id"]: item for item in brain.timeline(
        roles=("user", "assistant"), max_characters=200_000, max_item_characters=20_000, limit=1000)["items"]
        if item["conversation_id"] != NOTES_CONVERSATION}


def forget(brain, ids, mode="erase_content", conversation="first"):
    generation = brain.service.dashboard(brain.principal, brain.brain)["brain"]["scope_generation"]
    brain.action("forget", {"idempotency_key": uid(), "selector": {"kind": "events", "ids": list(ids)}, "mode": mode,
                            "expected_scope_generation": generation}, conversation)


def stored(brain, event_id):
    """The stored row: whether its content still exists, and whether it is hidden."""
    with brain.service.database.transaction(brain.principal) as conn:
        row = conn.execute(
            "SELECT deleted,suppressed,document IS NOT NULL AS readable FROM memory_events WHERE tenant_id=%s "
            "AND owner_id=%s AND brain_id=%s AND id=%s AND is_current",
            (brain.principal.tenant_id, brain.principal.principal_id, brain.brain, event_id)).fetchone()
    return dict(row)


def test_a_replacement_reads_what_it_replaced_from_the_replaced_record_and_deleting_it_erases_both(brain):
    decision = brain.say("Decision: we'll use PostgreSQL as the database.")
    correction = brain.say("Correction: only the server uses PostgreSQL; local stays SQLite.")
    first = write(brain, "Uses PostgreSQL as the database.", source_event_ids=[decision], kind="other")
    second = write(brain, "PostgreSQL on the server only; SQLite locally.", source_event_ids=[correction],
                   replaces=[first["note_id"]], kind="other")
    (current,) = notes(brain).values()
    assert current["event_id"] == second["note_id"]
    (earlier,) = current["replaced"]
    assert earlier["event_id"] == first["note_id"] and earlier["depth"] == 1
    assert earlier["text"] == "[other] Uses PostgreSQL as the database."
    assert earlier["source_event_ids"] == [decision]
    # The replacement keeps the earlier note's message as a deletion dependency; which is whose is derived.
    assert sorted(current["source_event_ids"]) == sorted([decision, correction])
    assert "(replaces your note of " in render_notes({"items": [current]})
    # The day-1 message is superseded by the current note; the correction is not.
    shown = messages(brain)
    assert shown[decision]["superseded_by"]["note_id"] == second["note_id"]
    assert "superseded_by" not in shown[correction]
    # Deleting the current note erases the note it replaced too: no stored sentence is left that nothing shows.
    forget(brain, [second["note_id"]], conversation=NOTES_CONVERSATION)
    assert notes(brain) == {}
    assert stored(brain, first["note_id"]) == {"deleted": True, "suppressed": True, "readable": False}
    assert "superseded_by" not in messages(brain)[decision]


def test_a_chain_is_read_newest_first_and_the_host_line_names_only_the_note_it_replaced(brain):
    sources = [brain.say(text) for text in ("We meet on Monday.", "Make it Tuesday.", "No, Wednesday.")]
    first = write(brain, "Meeting on Monday.", source_event_ids=[sources[0]])
    second = write(brain, "Meeting on Tuesday.", source_event_ids=[sources[1]], replaces=[first["note_id"]])
    third = write(brain, "Meeting on Wednesday.", source_event_ids=[sources[2]], replaces=[second["note_id"]])
    (current,) = notes(brain).values()
    assert current["event_id"] == third["note_id"]
    assert [(entry["event_id"], entry["depth"]) for entry in current["replaced"]] == [
        (second["note_id"], 1), (first["note_id"], 2)]
    line = render_notes({"items": [current]})
    assert line.count("(replaces your note of ") == 1  # The immediate predecessor only.
    shown = messages(brain)
    assert {shown[source].get("superseded_by", {}).get("note_id") for source in sources[:2]} == {third["note_id"]}
    assert "superseded_by" not in shown[sources[2]]
    # Deleting the middle note erases it and the one it replaced; the current note says nothing of them.
    forget(brain, [second["note_id"]], conversation=NOTES_CONVERSATION)
    (current,) = notes(brain).values()
    assert [entry.get("erased") for entry in current["replaced"]] == [True, True]
    assert all(set(entry) == {"event_id", "depth", "source_event_ids", "erased"} for entry in current["replaced"])
    assert "(replaces" not in render_notes({"items": [current]})
    assert not any("superseded_by" in item for item in messages(brain).values())


def test_erasing_only_the_replaced_note_leaves_the_current_one_and_shows_nothing_of_the_erased_one(brain):
    decision, correction = brain.say("PostgreSQL for everything."), brain.say("Only the server; local stays SQLite.")
    first = write(brain, "PostgreSQL everywhere.", source_event_ids=[decision])
    second = write(brain, "PostgreSQL on the server, SQLite locally.", source_event_ids=[correction],
                   replaces=[first["note_id"]])
    forget(brain, [first["note_id"]], conversation=NOTES_CONVERSATION)  # As a host's memory_forget would.
    (current,) = notes(brain).values()
    assert current["event_id"] == second["note_id"]
    # Its messages are still told apart: the day-1 one is the erased note's, never this note's support.
    assert current["replaced"] == [{"event_id": first["note_id"], "depth": 1, "source_event_ids": [decision],
                                    "erased": True}]
    assert "PostgreSQL everywhere" not in str(current) and "(replaces" not in render_notes({"items": [current]})
    assert "superseded_by" not in messages(brain)[decision]  # It rested on a note that no longer exists.


def test_a_replacement_without_a_message_of_its_own_supersedes_nothing(brain):
    """A status change or a rewording is not the user saying something new: the old message is not marked."""
    said = brain.say("I'm booking the dentist for Friday.")
    first = write(brain, "Dentist on Friday.", source_event_ids=[said], kind="plan", status="intended")
    second = write(brain, "Dentist on Friday.", replaces=[first["note_id"]], kind="plan", status="scheduled")
    assert notes(brain)[second["note_id"]]["replaced"][0]["event_id"] == first["note_id"]
    assert "superseded_by" not in messages(brain)[said]
    # Citing the same message again is not a new message either.
    third = write(brain, "Dentist on Friday at 9.", source_event_ids=[said], replaces=[second["note_id"]],
                  kind="plan", status="scheduled")
    assert notes(brain)[third["note_id"]]["replaced"][0]["event_id"] == second["note_id"]
    assert "superseded_by" not in messages(brain)[said]


def test_hiding_the_current_note_hides_what_it_replaced_and_no_mark_remains(brain):
    decision, correction = brain.say("Use npm."), brain.say("Actually pnpm, not npm.")
    first = write(brain, "Uses npm.", source_event_ids=[decision])
    second = write(brain, "Uses pnpm, not npm.", source_event_ids=[correction], replaces=[first["note_id"]])
    forget(brain, [second["note_id"]], mode="suppress_recall", conversation=NOTES_CONVERSATION)
    assert notes(brain) == {}
    assert not any("superseded_by" in item for item in messages(brain).values())
    assert stored(brain, first["note_id"])["suppressed"]


def test_the_map_shows_what_a_note_replaced_and_links_the_earlier_notes_message_as_its_basis(brain):
    decision, correction = brain.say("Decision: PostgreSQL."), brain.say("Correction: SQLite locally.")
    first = write(brain, "Uses PostgreSQL for everything in this project, on every machine, servers and laptops alike.",
                  source_event_ids=[decision])
    second = write(brain, "PostgreSQL on the server; SQLite locally.", source_event_ids=[correction],
                   replaces=[first["note_id"]])
    graph = memory_map(brain.service, brain.principal, brain.brain)
    node = next(node for node in graph["nodes"] if node["id"] == "note:" + second["note_id"])
    (earlier,) = node["replaces"]
    assert earlier["label"].endswith("…") and len(earlier["label"]) == 80  # Cut with an ellipsis that says so.
    edges = {(edge["target"], edge["type"]) for edge in graph["edges"] if edge["source"] == node["id"]}
    assert edges == {("msg:" + correction, "derived_from"), ("msg:" + decision, "replaced_source")}
    assert not any(item["id"] == "note:" + first["note_id"] for item in graph["nodes"])


# Property: random sequences ---------------------------------------------------------------------------------------

class Model:
    """What the rules say each record's state is: the dependency graph and which records were erased or hidden."""

    def __init__(self):
        self.edges = set()  # (input, output)
        self.erased, self.hidden, self.replaced = set(), set(), set()
        self.texts, self.own = {}, {}  # record -> text; note -> the message it was saved from (or None)
        self.messages, self.notes = [], []

    def outputs(self, ids):
        found, frontier = set(ids), set(ids)
        while frontier:
            frontier = {output for source, output in self.edges if source in frontier} - found
            found |= frontier
        return found

    def gone(self, record):
        return record in self.erased or record in self.hidden

    def current(self):
        return [note for note in self.notes if not self.gone(note) and note not in self.replaced]

    def predecessors(self, note):
        """Every note ``note`` replaced, directly or not."""
        found, frontier = set(), {note}
        while frontier:
            frontier = {output for source, output in self.edges if source in frontier and output in self.notes} - found
            found |= frontier
        return found


def act(brain, model, generator, step):
    """One random act; the model follows the rules the product states."""
    choice = generator.choice(["say", "note", "correct", "correct_bare", "erase", "erase", "hide", "restore"])
    live_messages = [record for record in model.messages if not model.gone(record)]
    current = model.current()
    if choice == "say" or not live_messages:
        text = f"Message {step}: the plan is option {generator.randint(1, 99)}."
        record = brain.say(text)
        model.messages.append(record)
        model.texts[record] = text
        return
    if choice in ("note", "correct", "correct_bare") or not current:
        source = None if choice == "correct_bare" and current else generator.choice(live_messages)
        replaces = [generator.choice(current)] if choice != "note" and current else []
        text = f"Note {step}: the plan is option {generator.randint(1, 99)}."
        written = write(brain, text, source_event_ids=[source] if source else [], replaces=replaces)
        note = written["note_id"]
        inherited = {source_id for old in replaces for source_id, output in model.edges if output == old
                     and source_id in model.messages}
        model.edges |= {(source_id, note) for source_id in inherited | ({source} if source else set())}
        model.edges |= {(note, old) for old in replaces}
        model.replaced |= set(replaces)
        model.notes.append(note)
        model.texts[note] = text
        model.own[note] = source
        return
    if choice in ("erase", "hide"):
        # A note already replaced is hidden by its replacement; hiding it again cannot be told apart, so only
        # deleting it is tried (as a host's memory_forget would).
        replaced = [note for note in model.notes if note in model.replaced and not model.gone(note)]
        record = generator.choice([*live_messages, *current, *(replaced if choice == "erase" else [])])
        conversation = NOTES_CONVERSATION if record in model.notes else "first"
        forget(brain, [record], "erase_content" if choice == "erase" else "suppress_recall", conversation)
        affected = model.outputs([record])
        if choice == "erase":
            model.erased |= affected
        else:
            model.hidden |= affected - model.erased
        return
    # Export, then restore that archive into the same brain: it brings nothing back and changes nothing.
    before = snapshot(brain)
    with_archive = brain.action("export", {"include_events": True, "include_working_states": True,
                                           "include_assertions": True, "include_provenance": True,
                                           "include_tombstones": True, "budget": BUDGET})
    generation = brain.service.dashboard(brain.principal, brain.brain)["brain"]["scope_generation"]
    brain.action("restore", {"uploaded_archive_ref": with_archive["archive_id"],
                             "expected_manifest_sha256": with_archive["manifest_sha256"],
                             "mode": "merge_authorized_brain", "apply_current_tombstones": True,
                             "expected_scope_generation": generation, "budget": BUDGET})
    assert snapshot(brain) == before
    SEEN["restores"] += 1


BUDGET = {"max_context_tokens": 16000, "max_model_calls": 0, "max_embedding_calls": 0, "max_expansion_steps": 2,
          "max_wall_time_ms": 5000, "max_cost_microunits": 0, "currency": "USD", "token_counting": "conservative_estimate",
          "tokenizer_id": None}


def snapshot(brain):
    return (sorted((key, str(value.get("replaced")), str(value.get("source_event_ids")))
                   for key, value in notes(brain).items()),
            sorted((key, str(value.get("superseded_by"))) for key, value in messages(brain).items()))


SEEN = {"marks": 0, "lineage": 0, "erased_lineage": 0, "restores": 0}  # What the random sequences reached.


def check(brain, model):
    shown_notes, shown_messages = notes(brain), messages(brain)
    SEEN["marks"] += sum("superseded_by" in item for item in shown_messages.values())
    SEEN["lineage"] += sum(bool(item.get("replaced")) for item in shown_notes.values())
    SEEN["erased_lineage"] += sum(entry.get("erased", False) for item in shown_notes.values()
                                  for entry in item.get("replaced", []))
    current = set(model.current())
    assert set(shown_notes) == current
    for note, item in shown_notes.items():
        predecessors = model.predecessors(note)
        assert {entry["event_id"] for entry in item.get("replaced", [])} == predecessors
        for entry in item.get("replaced", []):
            assert entry.get("erased", False) == (entry["event_id"] in model.erased)
            if entry.get("erased"):
                assert set(entry) == {"event_id", "depth", "source_event_ids", "erased"}
            else:
                assert entry["text"].endswith(model.texts[entry["event_id"]])
        # The messages the page lists as this note's own are ones it was saved from; the others are the basis of a
        # note it replaced.
        earlier = {source for entry in item.get("replaced", []) for source in entry["source_event_ids"]}
        own = set(item["source_event_ids"]) - earlier
        assert own <= ({model.own[note]} - {None})
        assert earlier <= {model.own[old] for old in predecessors}
        line = render_notes({"items": [item]})
        live = [entry for entry in item.get("replaced", []) if entry["depth"] == 1 and not entry.get("erased")]
        assert ("(replaces " in line) == bool(live)
    assert set(shown_messages) == {record for record in model.messages if not model.gone(record)}
    for record, item in shown_messages.items():
        # Marked exactly when a replaced note whose content exists rests on it and the current note heading that
        # note's chain has a message of its own that no note it replaced rests on; the mark names such a note.
        def inherited(note):
            return {source for source, output in model.edges if output in model.predecessors(note)}

        heads = set()
        for note in current:
            if (model.own[note] and model.own[note] not in inherited(note)
                    and any(model.own[old] == record and record not in inherited(old) and old not in model.erased
                            for old in model.predecessors(note))):
                heads.add(note)
        mark = item.get("superseded_by")
        assert (mark or {}).get("note_id") in (heads or {None})
        assert bool(host.superseded_mark(item)) == bool(heads)
    erased_texts = {model.texts[record] for record in model.erased}
    rendered = str(shown_notes) + str(shown_messages) + (render_notes({"items": list(shown_notes.values())}) or "")
    rendered += host.render_history({"items": [item for item in shown_messages.values()]}) or ""
    rendered += str(memory_map(brain.service, brain.principal, brain.brain))
    assert not [text for text in erased_texts if text in rendered]


@pytest.mark.parametrize("seed", range(40))
def test_no_sequence_of_corrections_deletions_hiding_or_restores_shows_what_it_should_not(service, seed):
    generator = random.Random(seed)
    brain, model = Brain(service, Principal(uid(), uid())), Model()
    for step in range(14):
        act(brain, model, generator, step)
        check(brain, model)


def test_the_random_sequences_reached_marks_lineage_erased_lineage_and_restores():
    """Run after the sequences above: they must have exercised what they check."""
    assert all(SEEN.values()), SEEN
