"""Persona development from explicit feedback (P2): suggestions for a new persona card version, which the user accepts
or rejects on the memory page.

The companion's card never changes by itself. When the user gives the same kind of feedback on how the companion
behaves at least ``THRESHOLD`` times, in any sessions ("you're too formal", "能不能活泼一点"), memBrain stores one
suggestion (a "proposal") that names the card edit and the messages it came from. Accepting it saves a new persona
version with ``made_by="feedback"`` and a reason citing those messages; rolling back is the ordinary restore.

Detection is deterministic and deliberately narrow: a small fixed table of feedback kinds (``KINDS``), each with
English and Chinese patterns that only match feedback addressed to the companion's manner ("your replies are too
long", not "the formal dinner was too long"), and the edit it proposes. There is no model call.

What counts as feedback: a current, undeleted message the user wrote (``actor_role`` user) in an ordinary
conversation, recorded after the latest persona reset marker (written by "Delete personality history"). Role-play,
hypothetical and quoted messages, messages typed on the memory page, conversations imported from other assistants and
every reserved conversation never count. Feedback given before a decision on a suggestion of the same kind is used up
by that decision, so a rejected suggestion is never offered again from the same messages; a new one needs new
feedback, and after a rejection none of that kind is offered for ``PAUSE``.

Suggestions and decisions are ``system`` events in a reserved conversation, like persona versions: never learned,
recalled or counted as messages, refused from outside writers, kept by export and archive restore (read back
strictly), and removed by erasing all memory or by "Delete personality history". A suggestion stores the source
event ids only; the quotes are read from the messages themselves, so a deleted message is never quoted, and a
suggestion left with fewer than ``THRESHOLD`` sources is withdrawn.

Context: a pending suggestion is not put into the agent's context at all, not even a one-line notice. Only an
accepted version changes the ``<membrain-persona>`` block. A notice would invite the agent to adopt or argue for a
change the user has not accepted, which is the one thing the persona layer must never do, and it would cost tokens on
every turn for something only the user can act on; the user finds suggestions on the memory page.

Clock: listing and deciding take ``now`` (the current time by default), so the 30-day pause can be tested on a fixed
clock. A new message is checked at its own recorded time.
"""
from __future__ import annotations

import datetime as _datetime
import json
import logging
import re

from .helpers import DomainError, uid
from .helpers import now as _now
from .persona import EMPTY_CARD, PERSONA_CONVERSATION, normalize_card

PROPOSALS_CONVERSATION = "membrain-persona-proposals"
PROPOSALS_PRODUCER = "membrain-persona-proposals"
ARCHIVE_PRODUCER = "archive-import"
THRESHOLD = 3
PAUSE = _datetime.timedelta(days=30)
MAX_SOURCES = 10  # The most recent matching messages a suggestion quotes.
QUOTE_CHARACTERS = 300
SCAN_CHARACTERS = 2000  # Longer messages are not read for feedback.
SCAN_ROWS = 5000
LISTED = 50
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_logger = logging.getLogger(__name__)

# The feedback table ------------------------------------------------------------------------------------------------
# Each kind: a label (English, Chinese), the card edit (a field and its value in each language), and the words its
# patterns are built from. ``less``: what the user says the companion is too much of ("too formal"); ``more``: what
# they ask for ("more casual"); ``comparative``: "be shorter"; ``keep``: "keep it short". Chinese: ``zh_less`` after
# 太 ("太正式了"), ``zh_more`` before 一点 ("活泼一点"). ``en_extra`` and ``zh_extra`` are whole patterns.

KINDS = {
    "less_formal": {
        "label": ("more casual", "更随意"), "field": "voice.register", "value": {"en": "casual", "zh": "随意"},
        "less": "formal|stiff|robotic|stuffy|businesslike|professional|polite",
        "more": "casual|relaxed|informal|chill|laid-back|laid back|natural",
        "keep": "casual|relaxed|informal|light",
        "zh_less": "正式|官方|生硬|客气|拘谨|死板|书面|一本正经",
        "zh_more": "随意|随便|轻松|口语化|口语|自然|放松",
    },
    "more_formal": {
        "label": ("more formal", "更正式"), "field": "voice.register", "value": {"en": "formal", "zh": "正式"},
        "less": "casual|informal|flippant|sloppy|slangy",
        "more": "formal|professional|polite|serious",
        "zh_less": "随便|随意|轻浮|油腻",
        "zh_more": "正式|礼貌|专业|严肃|稳重",
    },
    "more_playful": {
        "label": ("more playful", "更活泼"), "field": "traits", "value": {"en": "playful", "zh": "活泼"},
        "less": "serious|boring|dull|dry|bland",
        "more": "playful|fun|funny|lively|cheerful|humorous|humourous|silly|cheeky|witty",
        "comparative": "funnier|livelier|sillier",
        "zh_less": "严肃|无聊|沉闷|呆板|冷淡|闷",
        "zh_more": "活泼|俏皮|有趣|幽默|好玩|调皮",
    },
    "shorter": {
        "label": ("shorter replies", "回复更简短"), "field": "voice.length", "value": {"en": "short", "zh": "简短"},
        "less": "long|long-winded|wordy|verbose|lengthy|rambly|rambling",
        "more": "concise|brief|succinct",
        "comparative": "shorter|briefer",
        "keep": "short|brief|concise|shorter|briefer",
        "en_extra": [r"\byou\s+(?:talk|write|ramble|go\s+on)\s+(?:way\s+|far\s+)?too\s+much\b"],
        "zh_less": "长|啰嗦|啰唆|罗嗦|冗长|磨叽|墨迹", "zh_needs_subject": True,
        "zh_more": "简短|简洁|精简|短",
        "zh_extra": [r"(?:^|{B})(?:你|你的)话(?:有点|也|总是|真的|实在)?(?:太|好|这么|那么)多",
                     r"(?:^|{B})(?:你)?(?:别|不要|少)(?:说|写)(?:那么|这么)多"],
    },
    "longer": {
        "label": ("longer, more detailed replies", "回复更详细"), "field": "voice.length",
        "value": {"en": "detailed", "zh": "详细"},
        "less": "short|brief|terse|curt",
        "more": "detailed|thorough|elaborate|in-depth",
        "comparative": "longer",
        "zh_less": "短|简略|敷衍", "zh_needs_subject": True,
        "zh_more": "详细|具体|完整|长",
    },
    "less_emoji": {
        "label": ("fewer emoji", "少用表情"), "field": "voice.emoji", "value": {"en": "rarely", "zh": "很少"},
        "en_extra": [r"\byou\s+(?:use|send|put|add)\s+(?:way\s+|far\s+)?too\s+many\s+emojis?\b",
                     r"(?:^|{B}|\b(?:please|pls|can\s+you|could\s+you|would\s+you|just)\s+)(?:stop|quit)\s+(?:using|sending|adding)"
                     r"\s+(?:so\s+many\s+|all\s+the(?:se|\s+)?\s*)?emojis?\b",
                     r"(?:^|{B}|\b(?:please|pls|just)\s+)(?:don't|dont|do\s+not)\s+(?:use|send|add)\s+(?:so\s+many\s+)?emojis?\b",
                     r"(?:^|{B}|\b(?:please|pls|can\s+you|could\s+you)\s+)(?:use\s+)?(?:fewer|less|no\s+more)\s+emojis?\b"],
        "zh_extra": [r"(?:^|{B})(?:你)?(?:能不能|可不可以|可以|请)?(?:少|别|不要|不用|别再|不要再)(?:用|发|加|打)"
                     r"(?:点|些|那么多|这么多)?(?:表情|emoji)",
                     r"(?:^|{B})(?:你的?(?:回复|消息)?里?的?)?(?:表情|emoji)(?:符号|包)?(?:太多|用得太多|有点多|好多)"],
    },
    "more_emoji": {
        "label": ("more emoji", "多用表情"), "field": "voice.emoji", "value": {"en": "often", "zh": "经常"},
        "en_extra": [r"(?:^|{B}|\b(?:please|pls|can\s+you|could\s+you|would\s+you|you\s+should|you\s+could|you\s+can|"
                     r"feel\s+free\s+to|just)\s+)(?:use|add|send|throw\s+in)\s+(?:a\s+few\s+)?(?:more|some)\s+emojis?\b"],
        "zh_extra": [r"(?:^|{B})(?:你)?(?:能不能|可不可以|可以|请)?多(?:用|发|加|打)(?:点|些|一点|一些)?(?:表情|emoji)",
                     r"(?:^|{B})(?:你)?(?:能不能|可不可以|可以|请)(?:用|发|加)(?:点|些|一点|一些)(?:表情|emoji)"],
    },
}

# Pattern pieces. A clause starts at the start of the message or after punctuation.
_B = r"[.!?;:,，。！？；：、~～\n]\s*"
_NOUNS = r"(?:replies|reply|answers|answer|responses|response|messages|texts|tone|writing|style|sentences)"
_SOFT = r"(?:a\s+(?:bit|little|tad|lot)\s+|way\s+|much\s+|kind\s+of\s+|kinda\s+|sort\s+of\s+)?"
_TOO = r"(?:too|so|overly|really\s+too|way\s+too|far\s+too)"
_ASK = (r"(?:^|" + _B + r"|\b(?:please|pls|plz|can\s+you|could\s+you|would\s+you|will\s+you|you\s+should|"
        r"you\s+could|you\s+can|just|i(?:'d|\s+would)\s+like\s+you\s+to|i\s+want\s+you\s+to|i\s+need\s+you\s+to|"
        r"i\s+wish\s+you\s+would|i\s+wish\s+you'd)\s+)")
# The companion ("你") or its replies, named before the complaint.
_ZH_SUBJECT = r"(?:你的?(?:回复|回答|说话|讲话|语气|消息)?|回复|回答|说话|讲话|语气)"
# Anywhere in the message: role-play, a hypothetical, a dream or a quotation is never feedback to the companion.
_WORLD = re.compile(r"角色扮演|扮演|假如|假设|如果|要是|梦见|梦到|做梦|引用|原文|\b(?:role[ -]?play(?:ing)?|"
                    r"pretend(?:ing)?|imagine|suppose|hypothetically|in\s+character|dream(?:t|ed|ing)?|quote|"
                    r"quotation)\b", re.IGNORECASE)
_ZH_START = r"(?:^|" + _B + r"|我觉得|我感觉)"
# Reported speech, conditions and negations earlier in the same sentence: not feedback to the companion.
_EN_GUARD = re.compile(r"\b(?:said|says|told\s+me|tells\s+me|wrote|asked\s+me|according\s+to|if|whether|not|never|"
                       r"don't|dont|doesn't|isn't|aren't|wasn't|weren't|didn't)\b|[\"“”]", re.IGNORECASE)
_ZH_GUARD = re.compile(r"(?:他|她|他们|她们|别人|老板|同事|朋友|有人|大家)(?:都|也)?(?:说|觉得|认为)|如果|假如|要是|不觉得|并不")


def _compile(spec: dict) -> list[re.Pattern]:
    patterns = []
    if spec.get("less"):
        less = f"(?:{spec['less']})(?:ly)?"
        patterns += [
            rf"\byou(?:'re|\s+are|\s+sound|\s+seem|\s+come\s+across\s+as|\s+talk|\s+write|\s+speak|\s+always\s+sound)"
            rf"\s+(?:being\s+)?{_SOFT}{_TOO}\s+{less}\b",
            rf"(?:\byour\s+|^|{_B}){_NOUNS}\s+(?:are|is|feel|feels|sound|sounds|seem|seems|read|reads|get|gets|"
            rf"have\s+been|keep\s+being)\s+{_SOFT}{_TOO}\s+{less}\b",
            rf"(?:^|{_B}|\b(?:please|pls|just)\s+)(?:stop|quit)\s+being\s+(?:so\s+|too\s+)?{less}\b",
            rf"(?:^|{_B}|\b(?:please|pls|just)\s+)(?:don't|dont|do\s+not)\s+be\s+(?:so|too|that)\s+{less}\b",
            rf"\bno\s+need\s+to\s+be\s+(?:so|that)\s+{less}\b",
        ]
    targets = [f"more\\s+(?:{spec['more']})" if spec.get("more") else None,
               f"less\\s+(?:{spec['less']})" if spec.get("less") else None, spec.get("comparative")]
    target = "|".join(value for value in targets if value)
    if target:
        patterns.append(rf"{_ASK}(?:be|sound|talk|speak|write|reply|answer|act|get)\s+{_SOFT}(?:{target})\b")
        patterns.append(rf"(?:^|{_B})(?:{target})\s+{_NOUNS}(?:,?\s+please|\s+from\s+now\s+on)?\s*(?:[.!?]|$)")
    if spec.get("keep"):
        patterns.append(rf"{_ASK}keep\s+(?:it|them|things|your\s+{_NOUNS})\s+{_SOFT}(?:{spec['keep']})\b")
    patterns += [pattern.replace("{B}", _B) for pattern in spec.get("en_extra", ())]
    # "太长了" or "短一点" alone could be about anything (a film, a haircut), so the length kinds need the reply or
    # the companion named: "回复太长了", "你说话太啰嗦", "回答短一点".
    named = bool(spec.get("zh_needs_subject"))
    subject = _ZH_SUBJECT if named else _ZH_SUBJECT + "?"
    noun = r"(?:(?:说话|回复|回答|讲话|语气|写)得?)"
    ask = r"(?:能不能|能否|可不可以|可以|能|请|麻烦|就)?(?:再|更)?"
    if spec.get("zh_less"):
        bare = f"{_ZH_START}{noun}" if named else _ZH_START
        patterns += [
            rf"{_ZH_START}{subject}得?(?:有点|有些|也|总是|老是|真的|实在|还是|一直)?(?:太过|太|过于|好|这么|那么)"
            rf"(?:{spec['zh_less']})",
            rf"(?:{bare}|你{noun}?)(?:别|不要|不用|不必|没必要)(?:那么|这么|太|总是|老是)(?:{spec['zh_less']})",
        ]
    if spec.get("zh_more"):
        lead = f"(?:你{ask}{noun}?|{ask}{noun})" if named else f"你?{ask}{noun}?"
        patterns.append(rf"{_ZH_START}{lead}(?:{spec['zh_more']})(?:一点|一些|点|些)")
    patterns += [pattern.replace("{B}", _B) for pattern in spec.get("zh_extra", ())]
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


_PATTERNS = {kind: _compile(spec) for kind, spec in KINDS.items()}
_CJK = re.compile(r"[㐀-鿿]")


def _stems() -> str:
    """A coarse filter for the database: every message the patterns can match contains one of these words."""
    words = {"emoji", "talk", "write", "ramble", "go on", "表情", "话", "说", "写"}
    for spec in KINDS.values():
        for name in ("less", "more", "comparative", "keep", "zh_less", "zh_more"):
            words.update(word.strip() for word in spec.get(name, "").split("|") if word.strip())
    return "|".join(sorted(word.replace("-", ".") for word in words))


STEMS = _stems()


def _sentence_before(text: str, start: int) -> str:
    """The part of the sentence before ``start``, from the last full stop, question or exclamation mark."""
    before = text[:start]
    cut = max(before.rfind(mark) for mark in ".!?。！？\n")
    return before[cut + 1:]


def _matches(patterns, text: str) -> bool:
    for pattern in patterns:
        for match in pattern.finditer(text):
            guard = _ZH_GUARD if _CJK.search(match.group(0)) else _EN_GUARD
            if not guard.search(_sentence_before(text, match.start())):
                return True
    return False


def detect(text: str) -> list[str]:
    """The feedback kinds a message gives about the companion's manner, in table order; usually none."""
    if not isinstance(text, str) or not text.strip() or len(text) > SCAN_CHARACTERS:
        return []
    text = " ".join(text.replace("’", "'").replace("‘", "'").split())
    if _WORLD.search(text):
        return []
    return [kind for kind, patterns in _PATTERNS.items() if _matches(patterns, text)]


# Reading -----------------------------------------------------------------------------------------------------------

def _time(value) -> _datetime.datetime:
    if isinstance(value, _datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=_datetime.UTC)
    return _datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _iso(value: _datetime.datetime) -> str:
    return value.astimezone(_datetime.UTC).isoformat().replace("+00:00", "Z")


def _clock(now) -> _datetime.datetime:
    return _time(now if now is not None else _now())


def _ids(value, low, high) -> list[str]:
    if (not isinstance(value, list) or not low <= len(value) <= high or len(set(value)) != len(value)
            or not all(isinstance(item, str) and 0 < len(item) <= 200 for item in value)):
        raise ValueError("source ids")
    return list(value)


def _entry(row) -> dict | None:
    """A stored suggestion or decision, or None for anything else. Only the exact forms this module writes are
    accepted, so an archive (which is outside this module's control) cannot add anything else."""
    document = row["document"]
    observed = document["observed"]
    if observed.get("actor_role") != "system" or row["producer_ref"] not in (PROPOSALS_PRODUCER, ARCHIVE_PRODUCER):
        return None
    base = {"id": document["event_id"], "sequence": int(document["sequence"]),
            "recorded_at": str(document["system_time"]["recorded_at"])}
    try:
        stored = json.loads(observed["content"].get("text") or "")
        if not isinstance(stored, dict):
            return None
        if set(stored) == {"persona_proposal", "source_event_ids", "language", "proposed_at"}:
            if stored["persona_proposal"] not in KINDS or stored["language"] not in ("en", "zh"):
                return None
            return {**base, "type": "proposal", "kind": stored["persona_proposal"], "language": stored["language"],
                    "source_event_ids": _ids(stored["source_event_ids"], THRESHOLD, MAX_SOURCES),
                    "proposed_at": _iso(_time(stored["proposed_at"]))}
        if set(stored) == {"persona_proposal_decision", "proposal_id", "kind", "decided_at", "version"}:
            decision, version = stored["persona_proposal_decision"], stored["version"]
            if decision not in ("accepted", "rejected") or stored["kind"] not in KINDS:
                return None
            if not isinstance(stored["proposal_id"], str) or not 0 < len(stored["proposal_id"]) <= 200:
                return None
            if (decision == "accepted") != (type(version) is int and version >= 1) or (
                    decision == "rejected" and version is not None):
                return None
            return {**base, "type": "decision", "decision": decision, "proposal_id": stored["proposal_id"],
                    "kind": stored["kind"], "decided_at": _iso(_time(stored["decided_at"])), "version": version}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    return None


_VISIBLE = ("tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current AND NOT deleted AND NOT suppressed "
            "AND NOT retired AND document IS NOT NULL")


def _records(service, conn, principal, brain_id) -> list[dict]:
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "ORDER BY sequence DESC LIMIT 2000", (*service._params(principal, brain_id), PROPOSALS_CONVERSATION)).fetchall()
    return list(reversed([entry for entry in map(_entry, rows) if entry is not None]))


def latest_marker(service, conn, principal, brain_id) -> dict | None:
    """The latest persona reset marker ("Delete personality history"); feedback counts only after it."""
    from .persona import _entry as persona_entry

    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' LIKE %s ORDER BY sequence DESC",
        (*service._params(principal, brain_id), PERSONA_CONVERSATION, '{"persona_marker"%'))
    for row in rows:
        entry = persona_entry(row)
        if entry is not None and "marker" in entry:
            return entry
    return None


def _reserved() -> list[str]:
    from .affect import AFFECT_CONVERSATION
    from .mood import MOOD_CONVERSATION
    from .notes import NOTES_CONVERSATION
    from .relationship import RELATIONSHIP_CONVERSATION

    return [NOTES_CONVERSATION, PERSONA_CONVERSATION, PROPOSALS_CONVERSATION, AFFECT_CONVERSATION,
            MOOD_CONVERSATION, RELATIONSHIP_CONVERSATION, "membrain-memory-page"]


def _feedback(service, conn, principal, brain_id, *, after: int, ids=None) -> list[dict]:
    """Messages after ``after`` that count as feedback, oldest first, each with the kinds it gives. With ``ids``,
    only those messages (to check a suggestion's sources); otherwise the most recent candidates."""
    rows = conn.execute(
        "SELECT id,sequence,conversation_id,document->'observed'->'content'->>'text' AS text,"
        "document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
        f"WHERE {_VISIBLE} AND sequence>%s AND document->'observed'->>'event_kind'='message' "
        "AND document->'observed'->>'actor_role'='user' AND document->'observed'->>'delivery_state'='received' "
        "AND coalesce(document->'observed'->>'interpretation_hint','unknown') IN ('unknown','real_world_report') "
        "AND conversation_id IS NOT NULL AND NOT (conversation_id = ANY(%s::text[])) "
        "AND producer_ref <> 'membrain-memory-page' AND producer_ref NOT LIKE 'membrain-import:%%' "
        "AND length(document->'observed'->'content'->>'text') <= %s "
        "AND (%s::text[] IS NULL OR id = ANY(%s::text[])) "
        "AND document->'observed'->'content'->>'text' ~* %s ORDER BY sequence DESC LIMIT %s",
        (*service._params(principal, brain_id), after, _reserved(), SCAN_CHARACTERS, ids, ids, STEMS,
         SCAN_ROWS)).fetchall()
    result = []
    for row in reversed(rows):
        kinds = detect(row["text"])
        if kinds:
            result.append({"event_id": row["id"], "sequence": row["sequence"], "text": row["text"],
                           "recorded_at": row["recorded_at"], "conversation_id": row["conversation_id"],
                           "kinds": kinds})
    return result


def _current_card(service, conn, principal, brain_id) -> tuple[dict, int]:
    from .persona import _rows

    versions = _rows(service, conn, principal, brain_id, limit=1)
    if not versions:
        return dict(EMPTY_CARD), 0
    return {**EMPTY_CARD, **versions[0]["card"]}, versions[0]["version"]


def _apply(kind: str, card: dict, language: str) -> tuple[dict | None, str | None]:
    """The card with the kind's edit, or (None, why not): already in the card, or it would not fit."""
    spec = KINDS[kind]
    value = spec["value"][language]
    known = {text.casefold() for text in spec["value"].values()}
    card = json.loads(json.dumps({**EMPTY_CARD, **card}))
    if spec["field"] == "traits":
        if any(trait.casefold() in known for trait in card["traits"]):
            return None, "already_in_card"
        card["traits"] = [*card["traits"], value]
    else:
        name = spec["field"].split(".", 1)[1]
        if (card["voice"].get(name) or "").casefold() in known:
            return None, "already_in_card"
        card["voice"] = {**card["voice"], name: value}
    try:
        return normalize_card(card), None
    except DomainError:
        return None, "does_not_fit"


def _change(kind: str, before: dict, after: dict) -> dict:
    field = KINDS[kind]["field"]
    if field == "traits":
        return {"field": field, "before": before["traits"], "after": after["traits"]}
    name = field.split(".", 1)[1]
    return {"field": field, "before": before["voice"].get(name) or "", "after": after["voice"].get(name) or ""}


def _language(sources: list[dict]) -> str:
    chinese = sum(bool(_CJK.search(source["text"])) for source in sources)
    return "zh" if chinese * 2 > len(sources) else "en"


def _quote(text: str) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= QUOTE_CHARACTERS else text[:QUOTE_CHARACTERS - 1].rstrip() + "…"


class _State:
    """Everything a listing or a decision needs, read in one transaction."""

    def __init__(self, service, conn, principal, brain_id):
        self.marker = latest_marker(service, conn, principal, brain_id)
        self.after = self.marker["applies_from_sequence"] if self.marker else 0
        self.records = _records(service, conn, principal, brain_id)
        self.card, self.version = _current_card(service, conn, principal, brain_id)
        self.decisions = {entry["proposal_id"]: entry for entry in self.records if entry["type"] == "decision"}
        proposals = [entry for entry in self.records if entry["type"] == "proposal"]
        undecided = sorted({source for entry in proposals for source in entry["source_event_ids"]})
        valid = {item["event_id"]: item for item in _feedback(
            service, conn, principal, brain_id, after=self.after, ids=undecided)} if undecided else {}
        self.proposals = [self._status(entry, valid) for entry in proposals]

    def _status(self, entry, valid) -> dict:
        kind = entry["kind"]
        sources = [valid[ident] for ident in entry["source_event_ids"]
                   if ident in valid and kind in valid[ident]["kinds"]]
        decision = self.decisions.get(entry["id"])
        result = {"id": entry["id"], "kind": kind, "label": KINDS[kind]["label"][0], "language": entry["language"],
                  "proposed_at": entry["proposed_at"], "sequence": entry["sequence"], "status": "open",
                  "withdrawn_because": None, "decided_at": None, "version": None, "paused_until": None,
                  "sources": [{"event_id": source["event_id"], "text": _quote(source["text"]),
                               "recorded_at": source["recorded_at"], "conversation_id": source["conversation_id"]}
                              for source in sources],
                  "source_count": len(sources), "change": None, "proposed_card": None,
                  "current_version": self.version}
        if decision is not None:
            result.update(status=decision["decision"], decided_at=decision["decided_at"], version=decision["version"],
                          decision_sequence=decision["sequence"])
            if decision["decision"] == "rejected":
                result["paused_until"] = _iso(_time(decision["decided_at"]) + PAUSE)
            return result
        if len(sources) < THRESHOLD:
            return {**result, "status": "withdrawn", "withdrawn_because": "sources_removed"}
        proposed, why_not = _apply(kind, self.card, entry["language"])
        if proposed is None:
            return {**result, "status": "withdrawn", "withdrawn_because": why_not}
        return {**result, "change": _change(kind, self.card, proposed), "proposed_card": proposed}

    def open(self, kind):
        return next((item for item in self.proposals if item["kind"] == kind and item["status"] == "open"), None)

    def last_decision(self, kind):
        decided = [item for item in self.proposals if item["kind"] == kind and item["status"] in ("accepted",
                                                                                                  "rejected")]
        return max(decided, key=lambda item: item["decision_sequence"]) if decided else None


def _write(service, conn, principal, brain, stored: dict) -> str:
    target = {"brain_ref": brain["id"], "conversation_ref": PROPOSALS_CONVERSATION, "branch_ref": "main"}
    event_id, _, _ = service._append_event(conn, principal, brain, target, {
        "source_event_key": "persona-proposal-" + uid(), "source_revision": 1, "producer_ref": PROPOSALS_PRODUCER,
        "actor_ref": PROPOSALS_PRODUCER, "actor_role": "system", "event_kind": "message",
        "content": {"media_type": "text/plain", "text": json.dumps(stored, ensure_ascii=False, sort_keys=True)},
        "occurred_time": {"start": None, "end": None, "precision": "unknown", "basis": "unknown"},
        "interpretation_hint": "unknown", "delivery_state": "received", "parent_source_event_keys": []})
    return event_id


def _sync(service, conn, principal, brain, now: _datetime.datetime, kinds=None) -> _State:
    """Store a suggestion for every kind that has reached the threshold and is not open, paused or already in the
    card. Returns the state after any new suggestion."""
    state = _State(service, conn, principal, brain["id"])
    feedback = None
    created = False
    for kind in kinds or KINDS:
        if state.open(kind):
            continue
        last = state.last_decision(kind)
        if last and last["status"] == "rejected" and now < _time(last["paused_until"]):
            continue
        if feedback is None:
            feedback = _feedback(service, conn, principal, brain["id"], after=state.after)
        after = max(state.after, last["decision_sequence"] if last else 0)
        sources = [item for item in feedback if kind in item["kinds"] and item["sequence"] > after][-MAX_SOURCES:]
        if len(sources) < THRESHOLD:
            continue
        language = _language(sources)
        if _apply(kind, state.card, language)[0] is None:
            continue
        _write(service, conn, principal, brain, {
            "persona_proposal": kind, "source_event_ids": [item["event_id"] for item in sources],
            "language": language, "proposed_at": _iso(now)})
        created = True
    return _State(service, conn, principal, brain["id"]) if created else state


def _public(state: _State, now: _datetime.datetime) -> dict:
    listed = sorted(state.proposals, key=lambda item: (item["status"] != "open", -item["sequence"]))[:LISTED]
    pauses = {}
    for item in state.proposals:
        if item["status"] == "rejected" and now < _time(item["paused_until"]):
            pauses[item["kind"]] = max(pauses.get(item["kind"], ""), item["paused_until"])
    return {"proposals": [{key: value for key, value in item.items() if key not in ("sequence", "decision_sequence")}
                          for item in listed],
            "open": sum(item["status"] == "open" for item in state.proposals),
            "pauses": [{"kind": kind, "label": KINDS[kind]["label"][0], "until": until}
                       for kind, until in sorted(pauses.items())],
            "current_version": state.version, "threshold": THRESHOLD, "pause_days": PAUSE.days,
            "marker": state.marker, "now": _iso(now)}


def persona_proposals(service, principal, brain_id: str, *, now=None) -> dict:
    """Suggestions for the persona card, open ones first, with their quoted feedback and the proposed change.

    Reading first stores any suggestion that has become due (a rejection's pause ended, or feedback arrived through
    a path that does not check), so the listing is always complete for ``now``.
    """
    when = _clock(now)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        state = _sync(service, conn, principal, brain, when)
    return _public(state, when)


def _decide(service, principal, brain_id, proposal_id, decision, now):
    if not isinstance(proposal_id, str) or not 0 < len(proposal_id) <= 200:
        raise DomainError("validation_failed", "A suggestion id is required.")
    when = _clock(now)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        state = _State(service, conn, principal, brain_id)
        proposal = next((item for item in state.proposals if item["id"] == proposal_id), None)
        if proposal is None:
            raise DomainError("not_found_or_forbidden", "That suggestion is not available.")
        if proposal["status"] != "open":
            raise DomainError("version_conflict", "That suggestion is no longer open.")
        saved = None
        if decision == "accepted":
            saved = _accept(service, conn, principal, brain, proposal)
        _write(service, conn, principal, brain, {
            "persona_proposal_decision": decision, "proposal_id": proposal_id, "kind": proposal["kind"],
            "decided_at": _iso(when), "version": saved["version"] if saved else None})
        after = _State(service, conn, principal, brain_id)
    result = _public(after, when)
    result["proposal"] = next((item for item in result["proposals"] if item["id"] == proposal_id), None)
    if saved is not None:
        from .persona import _public as persona_public

        result["persona"] = persona_public({key: value for key, value in saved.items() if key != "unchanged"},
                                           unchanged=False)
    return result


def _short_day(value: str, language: str) -> str:
    day = _time(value).date()
    return f"{day.month}月{day.day}日" if language == "zh" else f"{day.day} {_MONTHS[day.month - 1]}"


def reason_for(proposal: dict) -> str:
    """The reason saved with the accepted version: the feedback kind, then each message it came from, quoted with
    its date, shortened so the whole reason fits ``REASON_CHARACTERS``. The version also keeps the message ids."""
    from .persona import REASON_CHARACTERS

    language, sources = proposal["language"], proposal["sources"]
    if language == "zh":
        head = f"接受的建议：{KINDS[proposal['kind']]['label'][1]}，来自你的 {len(sources)} 条消息："
        open_, close, separator = "「", "」", "；"
    else:
        head = f"Accepted suggestion: {KINDS[proposal['kind']]['label'][0]}, from {len(sources)} messages: "
        open_, close, separator = "“", "”", "; "
    dates = [f" ({_short_day(source['recorded_at'], language)})" if language == "en"
             else f"（{_short_day(source['recorded_at'], language)}）" for source in sources]
    fixed = len(head) + sum(len(open_) + len(close) + len(date) for date in dates) + len(separator) * (len(sources) - 1)
    room = max(8, (REASON_CHARACTERS - fixed) // max(1, len(sources)))
    quoted = []
    for source, date in zip(sources, dates):
        text = " ".join(source["text"].split())
        text = text if len(text) <= room else text[:room - 1].rstrip() + "…"
        quoted.append(f"{open_}{text}{close}{date}")
    reason = head + separator.join(quoted)
    return reason if len(reason) <= REASON_CHARACTERS else reason[:REASON_CHARACTERS - 1] + "…"


def _accept(service, conn, principal, brain, proposal) -> dict:
    from .persona import _save_in

    feedback = {"proposal_id": proposal["id"], "kind": proposal["kind"],
                "source_event_ids": [source["event_id"] for source in proposal["sources"]]}
    saved = _save_in(service, conn, principal, brain, lambda find: (proposal["proposed_card"], {"feedback": feedback}),
                     made_by="feedback", reason=reason_for(proposal), action="feedback")
    if saved.get("unchanged"):
        raise DomainError("version_conflict", "The card already has this change.")
    return saved


def accept_proposal(service, principal, brain_id: str, proposal_id: str, *, now=None) -> dict:
    """Save the suggested card as a new persona version (``made_by="feedback"``) and record the decision."""
    return _decide(service, principal, brain_id, proposal_id, "accepted", now)


def reject_proposal(service, principal, brain_id: str, proposal_id: str, *, now=None) -> dict:
    """Record the rejection: no suggestion of the same kind for ``PAUSE``, and the feedback it used never counts
    again."""
    return _decide(service, principal, brain_id, proposal_id, "rejected", now)


def observe_feedback(service, conn, principal, brain, target, event, event_id) -> None:
    """Called for each new user message: when it is feedback, store a suggestion if it brought its kind to the
    threshold. Never fails the observation: any error is rolled back to a savepoint and logged."""
    if (target.get("conversation_ref") in _reserved() or event.get("producer_ref") == "membrain-memory-page"
            or str(event.get("producer_ref", "")).startswith("membrain-import:")
            or event.get("interpretation_hint", "unknown") not in ("unknown", "real_world_report")
            or event.get("event_kind") != "message"):
        return
    kinds = detect((event.get("content") or {}).get("text"))
    if not kinds:
        return
    sequence = brain["durable_sequence"]
    try:
        with conn.transaction():
            row = conn.execute(
                "SELECT document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
                f"WHERE {_VISIBLE} AND id=%s", (*service._params(principal, brain["id"]), event_id)).fetchone()
            if row is not None:
                _sync(service, conn, principal, brain, _time(row["recorded_at"]), kinds)
    except Exception:  # A suggestion must never stop a message from being recorded.
        brain["durable_sequence"] = sequence
        _logger.warning("persona feedback check failed", exc_info=True)
