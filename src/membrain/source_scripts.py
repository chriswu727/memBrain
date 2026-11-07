import re
from functools import cache

from .helpers import digest

_HAN = re.compile("[\u3400-\u9fff]")
BACKFILL_BATCH = 256


def han_majority(text):
    return len(_HAN.findall(text)) * 2 > sum(character.isalpha() for character in text)


def source_text(memory):
    text = memory["statement"]
    refs = memory.get("evidence_refs", [])
    if memory.get("derivation", {}).get("method") == "direct_capture" and len(refs) == 1:
        span = refs[0].get("span") or {}
        if (span.get("unit") == "unicode_code_point" and type(span.get("start")) is int
                and type(span.get("end")) is int and 0 < span["end"] - span["start"] <= len(text)):
            text = text[-(span["end"] - span["start"]):]
    return text


def classify(memory):
    return han_majority(source_text(memory))


@cache
def nonletter_pattern():
    # PostgreSQL's POSIX alpha class depends on the cluster locale; match Python's Unicode letters exactly.
    ranges, start, end = [], None, None
    for codepoint in range(0x110000):
        if chr(codepoint).isalpha():
            if start is None:
                start = codepoint
            end = codepoint
        elif start is not None:
            ranges.append(chr(start) if start == end else chr(start) + "-" + chr(end))
            start = None
    return "[^" + "".join(ranges) + "]"


def maintain(conn, params):
    acquired = conn.execute("SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0)) AS acquired",
                            (digest(["source-script-projection", *params]),)).fetchone()["acquired"]
    if not acquired:
        return
    rows = conn.execute(
        "SELECT id,revision,document FROM memory_assertions WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
        "AND source_han_majority IS NULL AND is_current AND NOT invalidated AND NOT deleted AND NOT suppressed "
        "AND document IS NOT NULL ORDER BY id,revision LIMIT %s", (*params, BACKFILL_BATCH),
    ).fetchall()
    if rows:
        conn.execute(
            "UPDATE memory_assertions a SET source_han_majority=projection.majority "
            "FROM unnest(%s::text[],%s::bigint[],%s::boolean[]) AS projection(id,revision,majority) "
            "WHERE a.tenant_id=%s AND a.owner_id=%s AND a.brain_id=%s "
            "AND a.id=projection.id AND a.revision=projection.revision AND a.source_han_majority IS NULL",
            ([row["id"] for row in rows], [row["revision"] for row in rows],
             [classify(row["document"]) for row in rows], *params),
        )
