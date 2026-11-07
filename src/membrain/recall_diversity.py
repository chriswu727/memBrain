import re

from .source_scripts import source_text

MAX_CHARACTERS = 2048
REPRESENTATIVES = 2


def _signature(row):
    memory = row["document"]
    statement = memory["statement"]
    text = source_text(memory)
    envelope = statement[:-len(text)] if text and text != statement else ""
    start, end = row.get("start_offset"), row.get("end_offset")
    if type(start) is int and type(end) is int and 0 <= start < end <= len(statement):
        text = statement[start:end]
    if len(text) > MAX_CHARACTERS:
        return None
    normalized = " ".join(text.split())
    parts = re.split(r"(\d+)", normalized)
    template = tuple(None if index % 2 else part for index, part in enumerate(parts))
    return (envelope, memory.get("world"), memory.get("claim_kind"),
            memory.get("derivation", {}).get("method"), template)


def diversify(rows):
    counts, first, later = {}, [], []
    for row in rows:
        signature = _signature(row)
        if signature is None:
            first.append(row)
            continue
        counts[signature] = counts.get(signature, 0) + 1
        (first if counts[signature] <= REPRESENTATIVES else later).append(row)
    return first + later
