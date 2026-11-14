"""The fixed personality type of a behavioural acceptance attempt, drawn from a recorded seed.

The companion layer is always on in the product, so an acceptance run carries a persona. It is one fixed type for the
whole attempt, given to both arms (the plugin path P and the full-history reference F), set by the harness before
the first turn, never the product's random first assignment and never its one-time announcement. Nobody picks it:

    draw(seed) = IDS[int(sha256(seed as UTF-8).hexdigest(), 16) mod 16]

and the seed is the attempt id. ``IDS`` is a copy of ``membrain.persona_presets.IDS`` in the same order, so that
the attempt driver (standard library only) can check a manifest's draw; the harness refuses to run when the copy
differs from the product's table, and a test pins them equal.

  python acceptance_persona.py SEED     prints {"seed", "preset", "rule"} as one JSON line
"""
from __future__ import annotations

import hashlib
import json
import sys

IDS = ("intj", "intp", "entj", "entp", "infj", "infp", "enfj", "enfp",
       "istj", "isfj", "estj", "esfj", "istp", "isfp", "estp", "esfp")
RULE = "IDS[int(sha256(seed).hexdigest(), 16) % 16], seed = the attempt id"
# The seed a dry run uses when neither the driver nor the environment gives one (never a live attempt's).
STUB_SEED = "stub-practice"


def draw(seed: str) -> str:
    """The personality type for ``seed``: deterministic, the same on every machine and Python version."""
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("the persona seed must be a non-empty string")
    return IDS[int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(IDS)]


def record(seed: str) -> dict:
    """What a manifest records under "persona": the seed and the type it draws."""
    return {"seed": seed, "preset": draw(seed)}


def check(persona, attempt_id: str) -> str | None:
    """Why a manifest's "persona" entry is not the draw of its attempt id, or None."""
    if not isinstance(persona, dict) or set(persona) != {"seed", "preset"}:
        return "persona must be an object with exactly seed and preset"
    if persona["seed"] != attempt_id:
        return "the persona seed must be the attempt_id"
    try:
        expected = draw(persona["seed"])
    except ValueError as error:
        return str(error)
    if persona["preset"] != expected:
        return "the persona preset is not the draw of its seed"
    return None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: acceptance_persona.py SEED")
    print(json.dumps({**record(sys.argv[1]), "rule": RULE}, sort_keys=True))
