from .helpers import digest
from .mood import render_mood
from .notes import render_coming_up, render_notes
from .persona import render_persona


def _notes(saved, budget, **options):
    # Fitted without feelings, so they never change which notes are shown; they have their own allowance on top.
    selection_budget = budget
    for _ in range(4):
        block = render_notes(saved, budget=selection_budget, affect=False, **options)
        if not block or len(block) <= budget:
            return render_notes(saved, budget=selection_budget, **options)
        selection_budget = max(0, selection_budget - (len(block) - budget) - 100)
    return "<membrain-notes>Saved notes did not fit. Search memory when personal context matters.</membrain-notes>"


# Relationship (R1) --------------------------------------------------------------------------------------------

def _outside_boundaries(response, boundaries, *, drop_shared=False):
    """Saved notes without those about a boundary topic (a session start has no current message that raises it)
    and, when the relationship block shows them, without the shared moments."""
    from .notes import parse_note
    from .relationship import touches

    if response is None or not (boundaries or drop_shared):
        return response
    kept = [item for item in response.get("items", []) if not touches(item.get("text") or "", boundaries)
            and not (drop_shared and parse_note(item.get("text") or "")[0].get("shared"))]
    return {**response, "items": kept}


def _without_reset_commitments(saved, relationship):
    from .notes import parse_note

    after = max((marker["applies_from_sequence"] for marker in ((relationship or {}).get("markers") or [])
                 if marker.get("marker") == "reset"), default=0)
    if not after or saved is None:
        return saved
    return {**saved, "items": [item for item in saved.get("items", [])
                               if parse_note(item.get("text") or "")[0].get("kind") != "agent_commitment"
                               or (type(item.get("sequence")) is int and item["sequence"] > after)]}


def snapshot(saved, *, brain_id, tools, skip_imports_from=(), shared=None, persona=None, mood=None,
             relationship=None, companion=True):
    """Saved memory for the host's context. The persona block comes first, apart from the user's memory, with its
    own size limit: it never takes room from the notes. The companion's simulated mood follows it in its own block
    (none at the baseline); its text changes only when the label, the easing or the trigger does, so the
    fingerprint refreshes it only then, and a mood back at its baseline disappears. The relationship block
    follows, also on its own; notes about a boundary topic are left out, and shared moments are shown in the
    relationship block only.

    With ``companion`` off the persona and mood blocks are left out and the relationship block keeps only the
    boundaries and missed promises (``relationship_context``); shared moments then stay among the notes. Everything
    else is the same."""
    from .relationship import relationship_context

    persona_block = render_persona(persona) if companion else None
    mood_block = render_mood(mood) if companion else None
    bond = relationship_context(relationship, companion=companion)
    boundaries = (relationship or {}).get("boundaries") or []
    saved = _without_reset_commitments(saved, relationship)
    saved = _outside_boundaries(saved, boundaries, drop_shared=companion and bond["block"] is not None)
    shared = _outside_boundaries(shared, boundaries)
    blocks = [persona_block, mood_block, bond["block"],
              render_coming_up(saved, skip_imports_from=skip_imports_from, budget=1000),
              _notes(saved, 2800 if shared is not None else 3600, tool=tools["note"] if tools else None,
                     skip_imports_from=skip_imports_from)]
    if shared is not None:
        blocks.append(_notes(shared, 1100, tool=None, real_life=True))
    text = "\n\n".join(block for block in blocks if block)
    # The relationship block counts by what it means (level, style, boundaries, moments, which promises were missed),
    # not by its day count or one-time line, so a new day or an acknowledgement alone does not refresh everything.
    others = "\n\n".join(block for block in blocks if block and block is not bond["block"])
    basis = [brain_id, text] if bond["stable"] is None else [brain_id, others, bond["stable"]]
    if not companion:
        basis.append("companion off")  # Turning the layer off always refreshes, so the agent is told at once.
    return {"fingerprint": digest(basis), "text": text,
            "persona_version": persona["version"] if persona_block else None, "mood_shown": bool(mood_block),
            "boundaries": boundaries, "acknowledge": bond["once"], "companion": companion}


COMPANION_OFF = ("The user turned the companion layer off: no persona, simulated mood or familiarity is given, so "
                 "do not claim a mood or a relationship level of your own.")


def update(current, previous, previous_persona=None, previous_mood=False, previous_companion=True):
    """The refreshed snapshot when it changed since ``previous``; ``previous_persona`` is the persona version the
    session was last given, so a removed or reset card is announced instead of silently lingering. Likewise
    ``previous_mood`` says the session was given a simulated mood, so its return to the baseline is announced, and
    ``previous_companion`` says whether the companion layer was on, so turning it off or on is announced."""
    if current["fingerprint"] == previous:
        return None
    companion = current.get("companion", True)
    if not companion:
        removed = (" The companion layer was turned off: earlier membrain-persona, membrain-companion-mood and "
                   "membrain-relationship blocks in this session no longer apply. " + COMPANION_OFF
                   if previous_companion else "")
    else:
        removed = " The companion layer is on again." if not previous_companion else ""
        removed += ("" if not previous_persona or current.get("persona_version") else
                    f" The companion persona (v{int(previous_persona)}) was reset or removed: earlier membrain-persona "
                    "blocks in this session no longer apply.")
        # Companion mood (M1).
        removed += ("" if not previous_mood or current.get("mood_shown") else
                    " The companion's simulated mood is back at its baseline: earlier membrain-companion-mood blocks "
                    "in this session no longer apply.")
    return ("<membrain-updates>\nSaved memory has been refreshed. This snapshot replaces earlier persona, relationship, saved-note "
            "and coming-up blocks in this session. Do not use earlier versions as current notes; an omitted "
            "note may have been removed or may not fit. Omission does not prove a fact false. Search when "
            "personal context is missing. Original conversations remain historical data." + removed
            + "\n</membrain-updates>"
            + ("\n\n" + current["text"] if current["text"] else "\nNo saved notes are currently shown."))
