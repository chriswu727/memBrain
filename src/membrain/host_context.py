from .helpers import digest
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


def snapshot(saved, *, brain_id, tools, skip_imports_from=(), shared=None, persona=None):
    """Saved memory for the host's context. The persona block comes first, apart from the user's memory, with its
    own size limit: it never takes room from the notes."""
    persona_block = render_persona(persona)
    blocks = [persona_block, render_coming_up(saved, skip_imports_from=skip_imports_from, budget=1000),
              _notes(saved, 2800 if shared is not None else 3600, tool=tools["note"] if tools else None,
                     skip_imports_from=skip_imports_from)]
    if shared is not None:
        blocks.append(_notes(shared, 1100, tool=None, real_life=True))
    text = "\n\n".join(block for block in blocks if block)
    return {"fingerprint": digest([brain_id, text]), "text": text,
            "persona_version": persona["version"] if persona_block else None}


def update(current, previous, previous_persona=None):
    """The refreshed snapshot when it changed since ``previous``; ``previous_persona`` is the persona version the
    session was last given, so a removed or reset card is announced instead of silently lingering."""
    if current["fingerprint"] == previous:
        return None
    removed = ("" if not previous_persona or current.get("persona_version") else
               f" The companion persona (v{int(previous_persona)}) was reset or removed: earlier membrain-persona "
               "blocks in this session no longer apply.")
    return ("<membrain-updates>\nSaved memory has been refreshed. This snapshot replaces earlier persona, saved-note "
            "and coming-up blocks in this session. Do not use earlier versions as current notes; an omitted "
            "note may have been removed or may not fit. Omission does not prove a fact false. Search when "
            "personal context is missing. Original conversations remain historical data." + removed
            + "\n</membrain-updates>"
            + ("\n\n" + current["text"] if current["text"] else "\nNo saved notes are currently shown."))
