"""Deterministic recording controls for direct user messages, independent of model tools."""
import re

_PAUSE = re.compile(
    r"(?:please[, ]+)?(?:"
    r"(?:this(?: part| message| conversation)? is |let's keep this )?off[ -]the[ -]record|"
    r"(?:do not|don't) (?:record|remember|save|store|retain) "
    r"(?:this(?: message| conversation| part)?|the following)(?: in (?:your )?memory)?|"
    r"(?:do not|don't) keep this in (?:your )?memory|"
    r"(?:pause|stop) (?:recording|saving (?:this )?(?:conversation|chat))"
    r")|"
    r"(?:请)?(?:不要|别)(?:记录|保存|记住)"
    r"(?:这(?:一)?(?:段(?:话|内容)?|条(?:消息)?|次(?:聊天|对话)?|件事))?|"
    r"(?:请)?(?:暂停|停止)记录",
    re.IGNORECASE,
)


def requests_pause(text: str) -> bool:
    """Recognize an unquoted opening control clause, not arbitrary privacy intent.

    Restricting the grammar avoids treating quoted examples, reported speech, and requests to keep
    an existing memory confidential as permission to change recording state.
    """
    clause = re.split(r"[:：。.!！?？\n]", text.strip(), maxsplit=1)[0]
    clause = " ".join(clause.replace("’", "'").split())
    return _PAUSE.fullmatch(clause) is not None
