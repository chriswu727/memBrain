"""Persona development from explicit feedback (P2): suggestions for a new persona card version, which the user accepts
or rejects on the memory page.

The companion's card never changes by itself. When the user gives the same kind of feedback on how the companion
behaves at least ``THRESHOLD`` times, in any sessions ("you're too formal", "能不能活泼一点"), memBrain stores one
suggestion (a "proposal") that names the card edit and the messages it came from. Accepting it saves a new persona
version with ``made_by="feedback"`` and a reason citing those messages; rolling back is the ordinary restore.

Two sources say which messages are feedback of one of the kinds in ``KINDS``, and both feed the same counting below:

- The host AI reports it (``report_feedback``, the ``memory_manner_feedback`` tool): the kind and the user messages
  it came from. It understands paraphrases and every language. A report stores the kind and message ids (or the
  exact reference of the current message, which is recorded when the turn finishes), never words. A reported
  message counts only while it is itself eligible (below).
- A small fixed table (``detect``): English and Chinese patterns that only match feedback addressed to the
  companion's manner ("your replies are too long", not "the formal dinner was too long"). There is no model call.

A message counts once for each kind it gives, whichever source saw it, or both: the counting is by message and kind,
so feedback the table recognises and the host AI also reports is never counted twice.

What counts as feedback: a current, undeleted message the user wrote (``actor_role`` user) in an ordinary
conversation, recorded after the latest persona reset marker (written by "Delete personality history"). Role-play,
hypothetical and quoted messages, messages typed on the memory page, conversations imported from other assistants and
every reserved conversation never count. Feedback given before a decision on a suggestion of the same kind is used up
by that decision, so a rejected suggestion is never offered again from the same messages; a new one needs new
feedback, and after a rejection none of that kind is offered for ``PAUSE``.

Contradictory feedback: some kinds edit the same card field in opposite directions (``OPPOSITES``: more casual and
more formal, shorter and longer, fewer and more emoji). The user's latest direction decides. Feedback of one kind
counts only after the latest feedback of the opposite kind, and after the latest accepted change the opposite way
(the earlier messages were about the card before that change). An open suggestion is withdrawn ("contradicted") once
the user gives feedback the opposite way after its newest source, so two contradictory suggestions are never open at
once. Nothing is deleted: the messages stay, and a suggestion of either kind needs ``THRESHOLD`` messages given after
the latest change of direction.

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

Changes the host AI proposes (kind ``host``) use the same records and decisions. The host AI proposes an edit of the
card with a reason (``propose_change``); nothing changes until the user says yes in the conversation
(``confirm_change``) or accepts it on the memory page, where it is listed with the others. At most one is open: a new
one withdraws the previous one ("replaced"), and a proposal made on an older version of the card is withdrawn once the
card changes ("persona_changed"). A declined one is rejected without a pause; the tool tells the AI not to propose the
same change again in that conversation. The rule that keeps the AI from confirming its own proposal is stated at
``confirm_change``.
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
# Written when a native feedback message arrives: {"persona_feedback_seen": "<event id>"}; ids only, never words.
SEEN = "persona_feedback_seen"
SEEN_PREFIX = '{"' + SEEN + '"'
# Written when the host AI reports feedback: {"persona_feedback_reported": {"kind": ..., "event_id": ...}}, or with
# "message" (producer_ref, source_event_key, source_revision) for a message not recorded yet. Ids only, never words.
REPORTED = "persona_feedback_reported"
REPORTED_PREFIX = '{"' + REPORTED + '"'
# A change the host AI proposed (``propose_change``), and a confirmation waiting for the user's message to be recorded:
# {"persona_confirmation": {"proposal_id": ..., "message": <exact reference>}}.
HOST = "host"
HOST_LABEL = ("suggested by the agent", "由 agent 提出")
HOST_PROPOSAL_KEYS = {"persona_proposal", "changes", "proposed_card", "base_version", "reason", "source_event_ids",
                      "source_messages", "proposed_at"}
CHANGE_FIELDS = ("name", "traits", "voice", "values", "boundaries", "baseline_mood")
CONFIRMATION = "persona_confirmation"
CONFIRMATION_PREFIX = '{"' + CONFIRMATION + '"'
THRESHOLD = 3
PAUSE = _datetime.timedelta(days=30)
MAX_SOURCES = 10  # The most recent matching messages a suggestion quotes.
QUOTE_CHARACTERS = 300
REASON_CHARACTERS = 200  # The reason of a host proposal; it becomes the version's reason (persona.REASON_CHARACTERS).
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

# Kinds that edit the same card field in opposite directions; the user's latest direction decides (see above).
OPPOSITES = {"less_formal": "more_formal", "more_formal": "less_formal", "shorter": "longer", "longer": "shorter",
             "less_emoji": "more_emoji", "more_emoji": "less_emoji"}

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
_WORLD = re.compile(r"角色扮演|扮演|假如|假设|如果|要是|梦见|梦到|做梦|引用|原文|例句|台词|翻译|角色|"
                    r"\b(?:role[ -]?play(?:ing)?|pretend(?:ing)?|imagine|suppose|hypothetically|in\s+character|"
                    r"dream(?:t|ed|ing)?|quote[sd]?|quotation|examples?|characters?|translat\w*|line\s+from)\b",
                    re.IGNORECASE)
_ZH_START = r"(?:^|" + _B + r"|我觉得|我感觉)"
# Reported speech, conditions and negations earlier in the same sentence: not feedback to the companion.
_EN_GUARD = re.compile(r"\b(?:said|says|told\s+me|tells\s+me|wrote|asked\s+me|according\s+to|if|whether|not|never|"
                       r"don't|dont|doesn't|isn't|aren't|wasn't|weren't|didn't)\b|[\"“”:]|(?:^|[\s(\[])'", re.IGNORECASE)
_ZH_GUARD = re.compile(r"(?:他|她|他们|她们|别人|老板|同事|朋友|有人|大家)(?:都|也)?(?:说|觉得|认为)|如果|假如|要是|不觉得|并不|"
                       r"[：:「『“\"']")
# Feedback that ends in a closing quote is quoted, not said to the companion ("'you're too formal' is a line").
_CLOSING_QUOTE = re.compile(r"""\s*['"”」』]""")


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


_PAIRS = {"“": "”", "「": "」", "『": "』"}
_FENCED_CODE = re.compile(r"(?:```|~~~).*?(?:```|~~~|$)", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]*`")


def _inside_quote(text: str, position: int) -> bool:
    """Whether ``position`` falls inside quoted text anywhere in the message, across sentences: double quotes,
    “…”, 「…」 and 『…』, and single quotes that open after a space or the start and close before one."""
    double, closers, single = False, [], False
    for index, character in enumerate(text[:position]):
        if character == '"':
            double = not double
        elif character in _PAIRS:
            closers.append(_PAIRS[character])
        elif closers and character == closers[-1]:
            closers.pop()
        elif character == "'":
            before = text[index - 1] if index else " "
            after = text[index + 1] if index + 1 < len(text) else " "
            if not single and (before.isspace() or before in "([") and not after.isspace():
                single = True
            elif single and not before.isspace() and (after.isspace() or after in ".,!?:;)]"):
                single = False
    return double or bool(closers) or single


def _matches(patterns, text: str) -> bool:
    for pattern in patterns:
        for match in pattern.finditer(text):
            guard = _ZH_GUARD if _CJK.search(match.group(0)) else _EN_GUARD
            # A boundary character the pattern consumed (a colon before "你…") counts as before the feedback.
            before = _sentence_before(text, match.start()) + match.group(0)[:1]
            if (not guard.search(before) and not _CLOSING_QUOTE.match(text, match.end())
                    and not _inside_quote(text, match.start())):
                return True
    return False


def detect(text: str) -> list[str]:
    """The feedback kinds a message gives about the companion's manner, in table order; usually none."""
    if not isinstance(text, str) or not text.strip() or len(text) > SCAN_CHARACTERS:
        return []
    # Code is quoted text: a fenced block (an unclosed fence runs to the end) and inline `code` never count.
    text = _INLINE_CODE.sub(" ", _FENCED_CODE.sub(" ", text))
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


def _reference(value) -> dict:
    """An exact message reference, as the host's source block gives it; ValueError for anything else."""
    if (not isinstance(value, dict) or set(value) != {"producer_ref", "source_event_key", "source_revision"}
            or any(not isinstance(value[name], str) or not 0 < len(value[name]) <= 256
                   for name in ("producer_ref", "source_event_key"))
            or type(value["source_revision"]) is not int or not 1 <= value["source_revision"] <= 2**63 - 1):
        raise ValueError("source reference")
    return {name: value[name] for name in ("producer_ref", "source_event_key", "source_revision")}


def _key(reference: dict) -> tuple:
    return reference["producer_ref"], reference["source_event_key"], reference["source_revision"]


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
        if set(stored) == HOST_PROPOSAL_KEYS and stored["persona_proposal"] == HOST:
            if (not isinstance(stored["changes"], dict) or not stored["changes"]
                    or not set(stored["changes"]) <= set(CHANGE_FIELDS)
                    or type(stored["base_version"]) is not int or stored["base_version"] < 0
                    or not isinstance(stored["source_messages"], list) or len(stored["source_messages"]) > MAX_SOURCES):
                return None
            return {**base, "type": "proposal", "kind": HOST, "language": None, "changes": stored["changes"],
                    "proposed_card": normalize_card(stored["proposed_card"]), "base_version": stored["base_version"],
                    "reason": _short(stored["reason"]),
                    "source_event_ids": _ids(stored["source_event_ids"], 0, MAX_SOURCES),
                    "source_messages": [_reference(item) for item in stored["source_messages"]],
                    "proposed_at": _iso(_time(stored["proposed_at"]))}
        if set(stored) == {CONFIRMATION}:
            confirmation = stored[CONFIRMATION]
            if (not isinstance(confirmation, dict) or set(confirmation) != {"proposal_id", "message"}
                    or not isinstance(confirmation["proposal_id"], str)
                    or not 0 < len(confirmation["proposal_id"]) <= 200):
                return None
            return {**base, "type": "confirmation", "proposal_id": confirmation["proposal_id"],
                    "message": _reference(confirmation["message"])}
        if set(stored) == {"persona_proposal", "source_event_ids", "language", "proposed_at"}:
            if stored["persona_proposal"] not in KINDS or stored["language"] not in ("en", "zh"):
                return None
            return {**base, "type": "proposal", "kind": stored["persona_proposal"], "language": stored["language"],
                    "source_event_ids": _ids(stored["source_event_ids"], THRESHOLD, MAX_SOURCES),
                    "proposed_at": _iso(_time(stored["proposed_at"]))}
        if set(stored) == {SEEN}:
            if not isinstance(stored[SEEN], str) or not 0 < len(stored[SEEN]) <= 200:
                return None
            return {**base, "type": "seen", "event_id": stored[SEEN]}
        if set(stored) == {REPORTED}:
            report = stored[REPORTED]
            if not isinstance(report, dict) or report.get("kind") not in KINDS:
                return None
            if set(report) == {"kind", "event_id"} and isinstance(report["event_id"], str) and (
                    0 < len(report["event_id"]) <= 200):
                return {**base, "type": "reported", "kind": report["kind"], "event_id": report["event_id"]}
            if set(report) == {"kind", "message"}:
                return {**base, "type": "reported", "kind": report["kind"], "message": _reference(report["message"])}
            return None
        if set(stored) == {"persona_proposal_decision", "proposal_id", "kind", "decided_at", "version"}:
            decision, version = stored["persona_proposal_decision"], stored["version"]
            if decision not in ("accepted", "rejected") or (stored["kind"] not in KINDS and stored["kind"] != HOST):
                return None
            if not isinstance(stored["proposal_id"], str) or not 0 < len(stored["proposal_id"]) <= 200:
                return None
            if (decision == "accepted") != (type(version) is int and version >= 1) or (
                    decision == "rejected" and version is not None):
                return None
            decided_at = _time(stored["decided_at"])
            if decision == "rejected":
                _iso(decided_at + PAUSE)
            return {**base, "type": "decision", "decision": decision, "proposal_id": stored["proposal_id"],
                    "kind": stored["kind"], "decided_at": _iso(decided_at), "version": version}
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, DomainError):
        return None
    return None


def _short(value) -> str:
    if not isinstance(value, str) or not 0 < len(value) <= REASON_CHARACTERS:
        raise ValueError("reason")
    return value


_VISIBLE = ("tenant_id=%s AND owner_id=%s AND brain_id=%s AND is_current AND NOT deleted AND NOT suppressed "
            "AND NOT retired AND document IS NOT NULL")


def _records(service, conn, principal, brain_id) -> list[dict]:
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' NOT LIKE %s "
        "AND document->'observed'->'content'->>'text' NOT LIKE %s ORDER BY sequence DESC LIMIT 2000",
        (*service._params(principal, brain_id), PROPOSALS_CONVERSATION, SEEN_PREFIX + "%",
         REPORTED_PREFIX + "%")).fetchall()
    return list(reversed([entry for entry in map(_entry, rows) if entry is not None]))


def _seen(service, conn, principal, brain_id) -> list[str]:
    """The ids of messages this module saw arrive as the companion's own feedback (not imported, not typed on the
    memory page). The records hold ids only, never the words, and are archived like the suggestions, so feedback
    given before a backup still counts after it is restored."""
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' LIKE %s",
        (*service._params(principal, brain_id), PROPOSALS_CONVERSATION, SEEN_PREFIX + "%")).fetchall()
    return [entry["event_id"] for entry in map(_entry, rows) if entry is not None and entry["type"] == "seen"]


def _reports(service, conn, principal, brain_id) -> list[dict]:
    """Every feedback report the host AI made, oldest first."""
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' LIKE %s ORDER BY sequence",
        (*service._params(principal, brain_id), PROPOSALS_CONVERSATION, REPORTED_PREFIX + "%")).fetchall()
    return [entry for entry in map(_entry, rows) if entry is not None and entry["type"] == "reported"]


def _recorded(service, conn, principal, brain_id, keys) -> dict[tuple, str]:
    """The ids of the current, visible messages with these exact references (producer, key, revision)."""
    keys = list(dict.fromkeys(keys))
    if not keys:
        return {}
    rows = conn.execute(
        "SELECT id,producer_ref,source_key,source_revision FROM memory_events "
        f"WHERE {_VISIBLE} AND (producer_ref,source_key,source_revision) IN "
        "(SELECT * FROM unnest(%s::text[],%s::text[],%s::bigint[]))",
        (*service._params(principal, brain_id), [key[0] for key in keys], [key[1] for key in keys],
         [key[2] for key in keys])).fetchall()
    return {(row["producer_ref"], row["source_key"], row["source_revision"]): row["id"] for row in rows}


def _reported(service, conn, principal, brain_id) -> dict[str, set[str]]:
    """The kinds the host AI reported for each message id. A report on a message that was not recorded yet counts
    once that message is recorded. Whether the message itself may count is checked where it is read
    (``_candidates``), as for the table's own matches."""
    reports = _reports(service, conn, principal, brain_id)
    found = _recorded(service, conn, principal, brain_id,
                      [_key(entry["message"]) for entry in reports if "message" in entry])
    result: dict[str, set[str]] = {}
    for entry in reports:
        ident = found.get(_key(entry["message"])) if "message" in entry else entry["event_id"]
        if ident:
            result.setdefault(ident, set()).add(entry["kind"])
    return result


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


def _candidates(service, conn, principal, brain_id, *, after: int, ids=None, seen=(), reported=(), newest=True):
    """Candidate rows after ``after`` that may count as feedback: the newest ``SCAN_ROWS`` (newest first), or with
    ``newest=False`` the oldest ``SCAN_ROWS`` (oldest first). Messages the host AI reported (``reported``) are read
    whatever their words and length; every other rule applies to them as to the rest."""
    return conn.execute(
        "SELECT id,sequence,conversation_id,document->'observed'->'content'->>'text' AS text,"
        "document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
        f"WHERE {_VISIBLE} AND sequence>%s AND document->'observed'->>'event_kind'='message' "
        "AND document->'observed'->>'actor_role'='user' AND document->'observed'->>'delivery_state'='received' "
        "AND coalesce(document->'observed'->>'interpretation_hint','unknown') IN ('unknown','real_world_report') "
        "AND conversation_id IS NOT NULL AND NOT (conversation_id = ANY(%s::text[])) "
        "AND producer_ref <> 'membrain-memory-page' AND producer_ref NOT LIKE 'membrain-import:%%' "
        # A restore files every message under archive-import and drops the producer that wrote it, so a restored
        # message could have been typed on the memory page or imported from another assistant. Such a message
        # counts toward a new suggestion only when it was seen arriving as native feedback (``seen``), or the restore
        # kept its original producer and that producer may count; suggestions and decisions restored from the
        # archive keep their already checked sources (ids).
        "AND (%s::text[] IS NOT NULL OR producer_ref <> %s OR id = ANY(%s::text[]) OR ("
        "document->>'imported_producer_ref' IS NOT NULL "
        "AND document->>'imported_producer_ref' NOT IN ('membrain-memory-page', %s) "
        "AND document->>'imported_producer_ref' NOT LIKE 'membrain-import:%%')) "
        "AND (%s::text[] IS NULL OR id = ANY(%s::text[])) "
        "AND (id = ANY(%s::text[]) OR (length(document->'observed'->'content'->>'text') <= %s "
        "AND document->'observed'->'content'->>'text' ~* %s)) ORDER BY sequence " + ("DESC" if newest else "ASC")
        + " LIMIT %s",
        (*service._params(principal, brain_id), after, _reserved(), ids, ARCHIVE_PRODUCER, list(seen), ARCHIVE_PRODUCER,
         ids, ids, list(reported), SCAN_CHARACTERS, STEMS, SCAN_ROWS)).fetchall()


def _items(rows, reported=None) -> list[dict]:
    """The rows that give feedback, each with its kinds in table order: what the table recognises and what the host
    AI reported, each kind once."""
    result = []
    for row in rows:
        found, given = detect(row["text"]), (reported or {}).get(row["id"], ())
        kinds = [kind for kind in KINDS if kind in found or kind in given]
        if kinds:
            result.append({"event_id": row["id"], "sequence": row["sequence"], "text": row["text"],
                           "recorded_at": row["recorded_at"], "conversation_id": row["conversation_id"],
                           "kinds": kinds})
    return result


def _feedback(service, conn, principal, brain_id, *, after: int, ids=None, seen=(), reported=None) -> list[dict]:
    """Messages after ``after`` that count as feedback, oldest first, each with the kinds it gives. With ``ids``,
    only those messages (to check a suggestion's sources); otherwise the most recent candidates. ``reported``: the
    host AI's reports (``_reported``)."""
    rows = _candidates(service, conn, principal, brain_id, after=after, ids=ids, seen=seen, reported=reported or ())
    return _items(reversed(rows), reported)


def _first_feedback(service, conn, principal, brain_id, kind: str, *, after: int, seen=(),
                    reported=None) -> dict | None:
    """The first message after ``after`` that gives feedback of ``kind``, or None. Every later message is read, in
    pages of ``SCAN_ROWS``, so however long the history is, an earlier message is never missed; memory stays bounded
    by one page."""
    while True:
        rows = _candidates(service, conn, principal, brain_id, after=after, seen=seen, reported=reported or (),
                           newest=False)
        found = next((item for item in _items(rows, reported) if kind in item["kinds"]), None)
        if found is not None or len(rows) < SCAN_ROWS:
            return found
        after = rows[-1]["sequence"]


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
        self.reported = _reported(service, conn, principal, brain_id)
        self.card, self.version = _current_card(service, conn, principal, brain_id)
        self.decisions = {entry["proposal_id"]: entry for entry in self.records if entry["type"] == "decision"}
        self.decision_sequences, self.accepted_sequences = {}, {}
        for decision in self.decisions.values():
            kind = decision["kind"]
            self.decision_sequences[kind] = max(self.decision_sequences.get(kind, 0), decision["sequence"])
            if decision["decision"] == "accepted":
                self.accepted_sequences[kind] = max(self.accepted_sequences.get(kind, 0), decision["sequence"])
        proposals = [entry for entry in self.records if entry["type"] == "proposal"]
        self.confirmations = [entry for entry in self.records if entry["type"] == "confirmation"]
        hosts = [entry for entry in proposals if entry["kind"] == HOST]
        self._newest_host = max((entry["sequence"] for entry in hosts), default=0)
        self._quotes = _host_quotes(service, conn, principal, brain_id, hosts)
        undecided = sorted({source for entry in proposals if entry["kind"] != HOST
                            for source in entry["source_event_ids"]})
        valid = {item["event_id"]: item for item in _feedback(
            service, conn, principal, brain_id, after=self.after, ids=undecided,
            reported=self.reported)} if undecided else {}
        self._contradiction = lambda kind, after: _first_feedback(
            service, conn, principal, brain_id, OPPOSITES[kind], after=max(self.after, after),
            seen=self._seen_ids(service, conn, principal, brain_id), reported=self.reported)
        self._seen_cache = None
        self.proposals = [self._status(entry, valid) for entry in proposals]

    def _seen_ids(self, service, conn, principal, brain_id):
        if self._seen_cache is None:
            self._seen_cache = _seen(service, conn, principal, brain_id)
        return self._seen_cache

    def _host_status(self, entry) -> dict:
        """A change the host AI proposed: open until it is decided, replaced by a newer one, or the card it was made
        on changes."""
        sources = self._quotes.get(entry["id"], [])
        result = {"id": entry["id"], "kind": HOST, "label": HOST_LABEL[0], "language": None,
                  "proposed_at": entry["proposed_at"], "sequence": entry["sequence"], "status": "open",
                  "withdrawn_because": None, "decided_at": None, "version": None, "paused_until": None,
                  "sources": sources, "source_count": len(sources), "change": None, "changes": None,
                  "proposed_card": None, "current_version": self.version, "reason": entry["reason"],
                  "base_version": entry["base_version"],
                  "waiting_for_confirmation": any(item["proposal_id"] == entry["id"] for item in self.confirmations)}
        decision = self.decisions.get(entry["id"])
        if decision is not None:
            result.update(status=decision["decision"], decided_at=decision["decided_at"], version=decision["version"],
                          decision_sequence=decision["sequence"], waiting_for_confirmation=False)
            return result
        if entry["sequence"] < self._newest_host:
            return {**result, "status": "withdrawn", "withdrawn_because": "replaced", "waiting_for_confirmation": False}
        if entry["base_version"] != self.version:
            return {**result, "status": "withdrawn", "withdrawn_because": "persona_changed",
                    "waiting_for_confirmation": False}
        return {**result, "changes": _changes(self.card, entry["proposed_card"]),
                "proposed_card": entry["proposed_card"]}

    def _status(self, entry, valid) -> dict:
        kind = entry["kind"]
        if kind == HOST:
            return self._host_status(entry)
        sources = [valid[ident] for ident in entry["source_event_ids"]
                   if ident in valid and kind in valid[ident]["kinds"]]
        decision = self.decisions.get(entry["id"])
        if decision is not None:
            sources = [source for source in sources if source["sequence"] < decision["sequence"]]
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
        after = self.feedback_cutoff(kind)
        # Decisions outlive their feedback messages; deleting or revising those messages cannot reopen
        # an older suggestion from before the decision.
        if after and (entry["sequence"] <= after or sum(
                source["sequence"] > after for source in sources) < THRESHOLD):
            reason = "feedback_used" if after == self.decision_sequences.get(kind) else "contradicted"
            return {**result, "status": "withdrawn", "withdrawn_because": reason}
        # Contradicted: the user gave feedback the opposite way after this suggestion's newest source.
        if kind in OPPOSITES and self._contradiction(kind, max(source["sequence"] for source in sources)):
            return {**result, "status": "withdrawn", "withdrawn_because": "contradicted"}
        proposed, why_not = _apply(kind, self.card, entry["language"])
        if proposed is None:
            return {**result, "status": "withdrawn", "withdrawn_because": why_not}
        return {**result, "change": _change(kind, self.card, proposed), "proposed_card": proposed}

    def open(self, kind):
        return next((item for item in self.proposals if item["kind"] == kind and item["status"] == "open"), None)

    def feedback_cutoff(self, kind):
        return max(self.after, self.decision_sequences.get(kind, 0),
                   self.accepted_sequences.get(OPPOSITES.get(kind), 0))

    def last_decision(self, kind, *, accepted_only=False):
        statuses = ("accepted",) if accepted_only else ("accepted", "rejected")
        decided = [item for item in self.proposals if item["kind"] == kind and item["status"] in statuses]
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
            feedback = _feedback(service, conn, principal, brain["id"], after=state.after,
                                 seen=_seen(service, conn, principal, brain["id"]), reported=state.reported)
        after = state.feedback_cutoff(kind)
        opposite = OPPOSITES.get(kind)
        if opposite:
            after = max([after, *(item["sequence"] for item in feedback if opposite in item["kinds"])])
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
        if item["status"] == "rejected" and item["paused_until"] and now < _time(item["paused_until"]):
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


def _decide(service, principal, brain_id, proposal_id, decision, now, *, only_host=False):
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
        if only_host and proposal["kind"] != HOST:
            raise DomainError("validation_failed", NOT_HOST)
        saved = _settle(service, conn, principal, brain, proposal, decision, when, confirmed_by=None)
        after = _State(service, conn, principal, brain_id)
    return _decided(after, when, proposal_id, saved)


def _decided(state, when, proposal_id, saved) -> dict:
    result = _public(state, when)
    result["proposal"] = next((item for item in result["proposals"] if item["id"] == proposal_id), None)
    if saved is not None:
        from .persona import _public as persona_public

        result["persona"] = persona_public({key: value for key, value in saved.items() if key != "unchanged"},
                                           unchanged=False)
    return result


def _settle(service, conn, principal, brain, proposal, decision, when, *, confirmed_by) -> dict | None:
    """Record a decision on an open suggestion, saving the new persona version first when it is accepted."""
    saved = None
    if decision == "accepted":
        saved = (_accept_host(service, conn, principal, brain, proposal, confirmed_by) if proposal["kind"] == HOST
                 else _accept(service, conn, principal, brain, proposal))
    _write(service, conn, principal, brain, {
        "persona_proposal_decision": decision, "proposal_id": proposal["id"], "kind": proposal["kind"],
        "decided_at": _iso(when), "version": saved["version"] if saved else None})
    return saved


def _short_day(value: str, language: str) -> str:
    day = _time(value).date()
    return f"{day.month}月{day.day}日" if language == "zh" else f"{day.day} {_MONTHS[day.month - 1]}"


def reason_for(proposal: dict) -> str:
    """The reason saved with the accepted version: the feedback kind and the dates of the messages it came from.

    The messages' words are never copied into the version: it keeps their ids, and the version list quotes the ones
    that still exist (``persona.persona_versions``). Deleting a message therefore removes its words from the
    personality history too, and an older archive restored later cannot bring them back."""
    from .persona import REASON_CHARACTERS

    language, sources = proposal["language"], proposal["sources"]
    days = [_short_day(source["recorded_at"], language) for source in sources]
    if language == "zh":
        reason = f"接受的建议：{KINDS[proposal['kind']]['label'][1]}，来自你的 {len(sources)} 条消息（{'、'.join(days)}）"
    else:
        reason = (f"Accepted suggestion: {KINDS[proposal['kind']]['label'][0]}, from {len(sources)} messages "
                  f"({'; '.join(days)})")
    return reason if len(reason) <= REASON_CHARACTERS else reason[:REASON_CHARACTERS - 1] + "…"


def _accept(service, conn, principal, brain, proposal) -> dict:
    from .persona import _save_in

    feedback = {"proposal_id": proposal["id"], "kind": proposal["kind"],
                "source_event_ids": [source["event_id"] for source in proposal["sources"]]}
    from .persona import _origin

    saved = _save_in(service, conn, principal, brain,
                     lambda find: (proposal["proposed_card"], {"feedback": feedback,
                                                               **_origin(find(lambda entry: True), edited=True)}),
                     made_by="feedback", reason=reason_for(proposal), action="feedback")
    if saved.get("unchanged"):
        raise DomainError("version_conflict", "The card already has this change.")
    return saved


def accept_proposal(service, principal, brain_id: str, proposal_id: str, *, now=None) -> dict:
    """Save the suggested card as a new persona version (``made_by="feedback"``) and record the decision."""
    return _decide(service, principal, brain_id, proposal_id, "accepted", now)


def reject_proposal(service, principal, brain_id: str, proposal_id: str, *, now=None) -> dict:
    """Record the rejection: no suggestion of the same kind for ``PAUSE``, and the feedback it used never counts
    again. A change the host AI proposed is rejected without a pause."""
    return _decide(service, principal, brain_id, proposal_id, "rejected", now)


# The host AI as a source ------------------------------------------------------------------------------------------

UNUSABLE_SOURCE = ("Manner feedback must cite the user's own messages in an ordinary conversation of this memory, "
                   "recorded after the latest personality reset and not deleted. Nothing was recorded.")
UNUSABLE_PERSONA_SOURCE = ("A persona change must cite the user's own messages in an ordinary conversation of this "
                           "memory, recorded after the latest personality reset and not deleted. Nothing was saved.")


def _sources(source_event_ids, source_messages, low=1, high=MAX_SOURCES,
             count=f"Cite 1 to {MAX_SOURCES} user messages the feedback came from.") -> tuple[list[str], list[dict]]:
    try:
        if not all(isinstance(value or [], (list, tuple)) for value in (source_event_ids, source_messages)):
            raise ValueError("sources")
        ids = _ids(list(dict.fromkeys(source_event_ids or [])), 0, MAX_SOURCES)
        messages = list({_key(reference): reference
                         for reference in map(_reference, list(source_messages or []))}.values())
    except (ValueError, TypeError):
        raise DomainError("validation_failed", "Cite the messages as source_event_ids (message ids) or "
                                               "source_messages (exact producer, key and revision).") from None
    if not low <= len(ids) + len(messages) <= high:
        raise DomainError("validation_failed", count)
    return ids, messages


def _usable(service, conn, principal, brain_id, ids, messages, *, seen, refusal) -> tuple[list[str], list[dict]]:
    """(the cited messages already recorded, by id; the references not recorded yet). Every recorded one must be the
    user's own message in an ordinary conversation, after the latest persona reset marker and not deleted, or the
    whole call is refused (``source_unavailable``) with ``refusal``."""
    marker = latest_marker(service, conn, principal, brain_id)
    found = _recorded(service, conn, principal, brain_id, [_key(reference) for reference in messages])
    recorded = list(dict.fromkeys(ids + [found[_key(reference)] for reference in messages if _key(reference) in found]))
    waiting = [reference for reference in messages if _key(reference) not in found]
    if recorded:
        usable = {row["id"] for row in _candidates(
            service, conn, principal, brain_id, after=marker["applies_from_sequence"] if marker else 0,
            ids=recorded, seen=seen, reported=recorded)}
        if any(ident not in usable for ident in recorded):
            raise DomainError("source_unavailable", refusal)
    return recorded, waiting


def report_feedback(service, principal, brain_id: str, kind: str, *, source_event_ids=(), source_messages=(),
                    now=None) -> dict:
    """The host AI reports that the user gave feedback of ``kind`` on the companion's manner, in these messages.

    It feeds the same counting as the table's own matches (``THRESHOLD``, ``PAUSE``, decisions using up feedback,
    ``OPPOSITES``); only the source of the reading is new. Each cited message that is already recorded must be the
    user's own message in an ordinary conversation, after the latest persona reset marker and not deleted, or the
    whole report is refused and nothing is stored. A reference to the current message (``source_messages`` from the
    host's source block) may not be recorded yet: it is kept, and counts once that message is recorded and passes
    the same checks. Reporting the same kind for the same message again changes nothing.

    The result says what was recorded and nothing about suggestions: a pending suggestion never reaches the agent.
    """
    if kind not in KINDS:
        raise DomainError("validation_failed", f"kind must be one of {', '.join(KINDS)}.")
    ids, messages = _sources(source_event_ids, source_messages)
    when = _clock(now)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        seen = _seen(service, conn, principal, brain_id)
        recorded, waiting = _usable(service, conn, principal, brain_id, ids, messages, seen=seen,
                                    refusal=UNUSABLE_SOURCE)
        reported = _reported(service, conn, principal, brain_id)
        known = {_key(entry["message"]) for entry in _reports(service, conn, principal, brain_id)
                 if "message" in entry and entry["kind"] == kind}
        added = 0
        for ident in recorded:
            if kind in reported.get(ident, ()):
                continue
            _write(service, conn, principal, brain, {REPORTED: {"kind": kind, "event_id": ident}})
            if ident not in seen:  # As for a match of the table, so it still counts after an archive restore.
                _write(service, conn, principal, brain, {SEEN: ident})
            added += 1
        for reference in waiting:
            if _key(reference) in known:
                continue
            _write(service, conn, principal, brain, {REPORTED: {"kind": kind, "message": reference}})
            added += 1
        if added and recorded:
            _sync(service, conn, principal, brain, when, [kind])
    return {"kind": kind, "label": KINDS[kind]["label"][0], "recorded": added,
            "unchanged": len(recorded) + len(waiting) - added, "waiting_for_message": len(waiting)}


def check_sources(service, principal, brain_id: str, source_event_ids=(), source_messages=(), *, low=1,
                  high=MAX_SOURCES) -> tuple[list[str], list[dict]]:
    """The cited user messages, checked as ``report_feedback`` checks them: (recorded ids, references not recorded
    yet). Used by persona changes the user asks for in conversation."""
    ids, messages = _sources(source_event_ids, source_messages, low, high,
                             count=f"Cite {low} to {high} user messages." if low != high else
                             f"Cite exactly {low} user message.")
    with service.database.transaction(principal) as conn:
        service._brain(conn, principal, brain_id)
        return _usable(service, conn, principal, brain_id, ids, messages, seen=_seen(service, conn, principal, brain_id),
                       refusal=UNUSABLE_PERSONA_SOURCE)


# Changes the host AI proposes, confirmed by the user in conversation -------------------------------------------

NOT_HOST = ("Only a change the agent proposed is decided in conversation. Suggestions from feedback are the user's "
            "to accept or reject on the memory page.")


def _changes(before: dict, after: dict) -> list[dict]:
    """Each card field the proposal changes, with its value before and after (voice fields one by one)."""
    before, after = {**EMPTY_CARD, **before}, {**EMPTY_CARD, **after}
    result = []
    for field in CHANGE_FIELDS:
        if field == "voice":
            result += [{"field": f"voice.{name}", "before": before["voice"].get(name) or "",
                        "after": after["voice"].get(name) or ""}
                       for name in after["voice"] if (before["voice"].get(name) or "") != (after["voice"].get(name) or "")]
        elif before[field] != after[field]:
            result.append({"field": field, "before": before[field], "after": after[field]})
    return result


def _host_quotes(service, conn, principal, brain_id, proposals) -> dict[str, list[dict]]:
    """The cited user messages each host proposal quotes, read from the messages themselves (so a deleted message
    is never quoted); references to messages recorded after the proposal resolve to them."""
    keys = [_key(reference) for entry in proposals for reference in entry["source_messages"]]
    found = _recorded(service, conn, principal, brain_id, keys)
    wanted = {entry["id"]: list(dict.fromkeys(entry["source_event_ids"] + [
        found[_key(reference)] for reference in entry["source_messages"] if _key(reference) in found]))
        for entry in proposals}
    ids = sorted({ident for values in wanted.values() for ident in values})
    rows = conn.execute(
        "SELECT id,conversation_id,document->'observed'->'content'->>'text' AS text,"
        "document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
        f"WHERE {_VISIBLE} AND id = ANY(%s::text[]) AND document->'observed'->>'actor_role'='user'",
        (*service._params(principal, brain_id), ids)).fetchall() if ids else []
    quoted = {row["id"]: {"event_id": row["id"], "text": _quote(row["text"]), "recorded_at": row["recorded_at"],
                          "conversation_id": row["conversation_id"]} for row in rows}
    return {proposal: [quoted[ident] for ident in values if ident in quoted] for proposal, values in wanted.items()}


LIST_FIELDS = ("traits", "values", "boundaries")


def _merged(card: dict, changes) -> dict:
    """The current card with the proposed change applied: ``traits``, ``values`` and ``boundaries`` are ADDED to the
    ones the card has (a host asked for "be more patient" would otherwise have to repeat every value of the
    personality type or wipe them; in a trial it squeezed the behaviour into a 60-character voice field instead);
    ``voice`` is changed field by field; ``name`` and ``baseline_mood`` are replaced. Removing or rewriting an entry
    is the user's edit on the memory page."""
    if not isinstance(changes, dict) or not changes or not set(changes) <= set(CHANGE_FIELDS):
        raise DomainError("validation_failed", f"changes must name one or more of {', '.join(CHANGE_FIELDS)}.")
    merged = json.loads(json.dumps({**EMPTY_CARD, **card}))
    for field, value in changes.items():
        if field == "voice":
            if not isinstance(value, dict):
                raise DomainError("validation_failed", "changes.voice must be an object of voice fields.")
            merged["voice"] = {**merged["voice"], **value}
        elif field in LIST_FIELDS:
            if not isinstance(value, list):
                raise DomainError("validation_failed", f"changes.{field} must be a list of phrases to add.")
            merged[field] = merged[field] + [entry for entry in value if entry not in merged[field]]
        else:
            merged[field] = value
    return normalize_card(merged)


def _accept_host(service, conn, principal, brain, proposal, confirmed_by) -> dict:
    """Save a host proposal's card as a new version. ``made_by`` is "user": the user decided; ``host_proposal`` says
    the host AI proposed it and names the message that confirmed it (None when accepted on the memory page)."""
    from .persona import _origin, _save_in

    host_proposal = {"proposal_id": proposal["id"], "confirmed_by": confirmed_by}
    saved = _save_in(service, conn, principal, brain,
                     lambda find: (proposal["proposed_card"], {"host_proposal": host_proposal,
                                                               **_origin(find(lambda entry: True), edited=True)}),
                     made_by="user", reason=proposal["reason"], action="proposal")
    if saved.get("unchanged"):
        raise DomainError("version_conflict", "The card already has this change.")
    return saved


def propose_change(service, principal, brain_id: str, changes, *, reason, source_event_ids=(), source_messages=(),
                   now=None) -> dict:
    """The host AI proposes a change to the persona card: ``changes`` is a partial card (any of ``CHANGE_FIELDS``;
    lists are added to, ``voice`` changes field by field) and ``reason`` says why in a sentence. Nothing changes: an
    open proposal of kind ``host`` is stored, and any earlier open one is withdrawn ("replaced"). The resulting card
    must pass ``persona.normalize_card`` now. Cited messages (optional, up to ``MAX_SOURCES``) are checked like manner
    feedback: recorded ones must be the user's own messages; a reference to the current message may wait."""
    if not isinstance(reason, str) or not reason.strip() or len(reason) > REASON_CHARACTERS:
        raise DomainError("validation_failed", f"Give a reason of at most {REASON_CHARACTERS} characters.")
    from .persona import _reason

    reason = _reason(reason)
    ids, messages = _sources(source_event_ids, source_messages, 0, MAX_SOURCES,
                             count=f"Cite at most {MAX_SOURCES} user messages.")
    when = _clock(now)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        _usable(service, conn, principal, brain_id, ids, messages, seen=_seen(service, conn, principal, brain_id),
                refusal=UNUSABLE_PERSONA_SOURCE)
        card, version = _current_card(service, conn, principal, brain_id)
        proposed = _merged(card, changes)
        if proposed == normalize_card(card):
            raise DomainError("validation_failed", "The persona already is like that: nothing to propose.")
        # The fields as stored in the card (scrubbed and trimmed like it), never the raw request.
        changes = {field: {name: proposed["voice"][name] for name in changes["voice"]} if field == "voice"
                   else proposed[field] for field in changes}
        proposal_id = _write(service, conn, principal, brain, {
            "persona_proposal": HOST, "changes": changes, "proposed_card": proposed, "base_version": version,
            "reason": reason, "source_event_ids": ids, "source_messages": messages, "proposed_at": _iso(when)})
        state = _State(service, conn, principal, brain_id)
    return _decided(state, when, proposal_id, None)


def _answered(service, conn, principal, brain_id, message_id: str, after: int) -> bool:
    """Whether ``message_id`` is a user message that answers something said after ``after``: an assistant message of
    the same conversation was recorded after ``after`` and before it."""
    return conn.execute(
        "SELECT EXISTS(SELECT 1 FROM memory_events m JOIN memory_events a ON a.tenant_id=m.tenant_id "
        "AND a.owner_id=m.owner_id AND a.brain_id=m.brain_id AND a.conversation_id=m.conversation_id "
        "WHERE m.tenant_id=%s AND m.owner_id=%s AND m.brain_id=%s AND m.id=%s "
        "AND m.document->'observed'->>'actor_role'='user' "
        "AND a.is_current AND NOT a.deleted AND NOT a.suppressed AND NOT a.retired AND a.document IS NOT NULL "
        "AND a.document->'observed'->>'actor_role'='assistant' AND a.sequence>%s AND a.sequence<m.sequence) AS found",
        (*service._params(principal, brain_id), message_id, after)).fetchone()["found"]


def _replied_since(service, conn, principal, brain_id, after: int) -> bool:
    """Whether any assistant message of an ordinary conversation was recorded after ``after``."""
    return conn.execute(
        f"SELECT EXISTS(SELECT 1 FROM memory_events WHERE {_VISIBLE} AND sequence>%s "
        "AND document->'observed'->>'actor_role'='assistant' AND NOT (conversation_id = ANY(%s::text[]))) AS found",
        (*service._params(principal, brain_id), after, _reserved())).fetchone()["found"]


TOO_EARLY = ("The user has not answered this proposal yet: describe the change to them, ask, and confirm only in a "
             "later turn, citing the message in which they said yes. Nothing was saved.")
NOT_AN_ANSWER = ("That message is not the user's answer to this proposal: cite the user's message that came after "
                 "you described the change (in this conversation's current turn). Nothing was saved.")


def confirm_change(service, principal, brain_id: str, proposal_id: str, *, source_event_ids=(), source_messages=(),
                   now=None) -> dict:
    """Apply an open host proposal as a new persona version, because the user said yes in the conversation.

    The rule that keeps the host AI from confirming its own proposal: the confirmation cites exactly one message,
    and that message must be the user's own message in an ordinary conversation, recorded after an assistant message
    of the same conversation that was itself recorded after the proposal. Hosts record a turn's user message and reply
    together when the turn ends, so the reply that described the proposal is recorded after the proposal and before
    the user's next message; a message from the turn the proposal was made in, an older message or an assistant
    message cannot pass.

    - A cited message already recorded is checked now: refused (``source_unavailable``) unless it passes.
    - A reference to the current message, not recorded yet, is refused now when no assistant message has been
      recorded since the proposal (the proposal was made in this turn). Otherwise it is kept as a confirmation
      waiting for the message: the version is saved when the message is recorded (``observe_feedback``), and only if
      it passes the rule then and the proposal is still open.

    The saved version has ``made_by`` "user", ``action`` "proposal" and ``host_proposal`` with the proposal id and
    the confirming message's id.
    """
    ids, messages = _sources(source_event_ids, source_messages, 1, 1,
                             count="Cite exactly one message: the user's message that says yes.")
    when = _clock(now)
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        state = _State(service, conn, principal, brain_id)
        proposal = _open_host(state, proposal_id)
        recorded, waiting = _usable(service, conn, principal, brain_id, ids, messages,
                                    seen=_seen(service, conn, principal, brain_id), refusal=NOT_AN_ANSWER)
        if recorded:
            if not _answered(service, conn, principal, brain_id, recorded[0], proposal["sequence"]):
                raise DomainError("source_unavailable", NOT_AN_ANSWER)
            saved = _settle(service, conn, principal, brain, proposal, "accepted", when, confirmed_by=recorded[0])
            result = _decided(_State(service, conn, principal, brain_id), when, proposal_id, saved)
            return {**result, "status": "confirmed"}
        if not _replied_since(service, conn, principal, brain_id, proposal["sequence"]):
            raise DomainError("source_unavailable", TOO_EARLY)
        reference = waiting[0]
        if not any(item["proposal_id"] == proposal_id and _key(item["message"]) == _key(reference)
                   for item in state.confirmations):
            _write(service, conn, principal, brain, {CONFIRMATION: {"proposal_id": proposal_id, "message": reference}})
        result = _decided(_State(service, conn, principal, brain_id), when, proposal_id, None)
    return {**result, "status": "waiting_for_message"}


def _open_host(state: _State, proposal_id) -> dict:
    if not isinstance(proposal_id, str) or not 0 < len(proposal_id) <= 200:
        raise DomainError("validation_failed", "A proposal id is required.")
    proposal = next((item for item in state.proposals if item["id"] == proposal_id), None)
    if proposal is None:
        raise DomainError("not_found_or_forbidden", "That suggestion is not available.")
    if proposal["kind"] != HOST:
        raise DomainError("validation_failed", NOT_HOST)
    if proposal["status"] != "open":
        raise DomainError("version_conflict", "That suggestion is no longer open.")
    return proposal


def decline_change(service, principal, brain_id: str, proposal_id: str, *, now=None) -> dict:
    """The user said no to an open host proposal: it is rejected. There is no pause; the tool tells the host AI not
    to propose the same change again in the conversation."""
    return _decide(service, principal, brain_id, proposal_id, "rejected", now, only_host=True)


def _confirm_waiting(service, conn, principal, brain, event, event_id) -> None:
    """A user message has arrived: apply each open host proposal a confirmation was waiting for on this message's
    exact reference, if the message passes ``confirm_change``'s rule."""
    key = (event.get("producer_ref"), event.get("source_event_key"), event.get("source_revision"))
    rows = conn.execute(
        f"SELECT producer_ref,document FROM memory_events WHERE {_VISIBLE} AND conversation_id=%s "
        "AND document->'observed'->'content'->>'text' LIKE %s ORDER BY sequence",
        (*service._params(principal, brain["id"]), PROPOSALS_CONVERSATION, CONFIRMATION_PREFIX + "%")).fetchall()
    wanted = [entry["proposal_id"] for entry in map(_entry, rows)
              if entry is not None and entry["type"] == "confirmation" and _key(entry["message"]) == key]
    for proposal_id in dict.fromkeys(wanted):
        state = _State(service, conn, principal, brain["id"])
        proposal = next((item for item in state.proposals if item["id"] == proposal_id and item["kind"] == HOST
                         and item["status"] == "open"), None)
        if proposal is not None and _answered(service, conn, principal, brain["id"], event_id, proposal["sequence"]):
            row = conn.execute("SELECT document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
                               f"WHERE {_VISIBLE} AND id=%s",
                               (*service._params(principal, brain["id"]), event_id)).fetchone()
            _settle(service, conn, principal, brain, proposal, "accepted", _time(row["recorded_at"]),
                    confirmed_by=event_id)


def _waiting(service, conn, principal, brain_id, event) -> list[str]:
    """The kinds the host AI reported for this message before it was recorded (by its exact reference)."""
    key = (event.get("producer_ref"), event.get("source_event_key"), event.get("source_revision"))
    given = {entry["kind"] for entry in _reports(service, conn, principal, brain_id)
             if "message" in entry and _key(entry["message"]) == key}
    return [kind for kind in KINDS if kind in given]


def observe_feedback(service, conn, principal, brain, target, event, event_id) -> None:
    """Called for each new user message: when it is feedback (the table matches it, or the host AI reported it
    before it was recorded), store a suggestion if it brought its kind to the threshold. A report on the message's
    reference is stored again by the message's id, so it stays tied to the message through an archive restore. A
    confirmation of a host proposal that waited for this message is applied (``confirm_change``).
    Never fails the observation: any error is rolled back to a savepoint and logged."""
    if (target.get("conversation_ref") in _reserved() or event.get("producer_ref") == "membrain-memory-page"
            or str(event.get("producer_ref", "")).startswith("membrain-import:")
            or event.get("interpretation_hint", "unknown") not in ("unknown", "real_world_report")
            or event.get("event_kind") != "message"):
        return
    kinds = detect((event.get("content") or {}).get("text"))
    sequence = brain["durable_sequence"]
    try:
        with conn.transaction():
            _confirm_waiting(service, conn, principal, brain, event, event_id)
            waiting = _waiting(service, conn, principal, brain["id"], event)
            if not kinds and not waiting:
                return
            row = conn.execute(
                "SELECT document->'system_time'->>'recorded_at' AS recorded_at FROM memory_events "
                f"WHERE {_VISIBLE} AND id=%s", (*service._params(principal, brain["id"]), event_id)).fetchone()
            if row is not None:
                for kind in waiting:
                    _write(service, conn, principal, brain, {REPORTED: {"kind": kind, "event_id": event_id}})
                _write(service, conn, principal, brain, {SEEN: event_id})
                _sync(service, conn, principal, brain, _time(row["recorded_at"]),
                      [kind for kind in KINDS if kind in kinds or kind in waiting])
    except Exception:  # A suggestion must never stop a message from being recorded.
        brain["durable_sequence"] = sequence
        _logger.warning("persona feedback check failed", exc_info=True)
