"""Reading a host turn's stream-json log, redacting it for publication, and writing a trial's report and record draft.

``parse_log`` reads one headless turn's log as Claude Code writes it (``--output-format stream-json --verbose``):
the init event, hook responses, tool calls with their results, the reply, and the host's own result event (cost per
turn from ``model_usage_since_last_result``, else the difference of the conversation's ``total_cost_usd``).

``redact`` removes what must not leave the machine: capture tokens, UUIDs and other record ids, tool-use and message
ids, thinking signatures, local paths, the user name, e-mail addresses, the memory page's single-use code, local ports
and anything shaped like an API key or token. It is applied to every published line; raw logs stay in the trial.
"""
from __future__ import annotations

import getpass
import json
import os
import re
from pathlib import Path

SUMMARY_CHARACTERS = 900
CONTEXT_CHARACTERS = 1200


def _user_names() -> set[str]:
    names = set()
    for value in (os.environ.get("USER"), os.environ.get("LOGNAME"), Path.home().name):
        if value and len(value) >= 3:
            names.add(value)
    try:
        names.add(getpass.getuser())
    except (KeyError, OSError):
        pass
    return {name for name in names if len(name) >= 3}


_RULES = (
    # Capture tokens: as a JSON field, as the context's recording_capture="..." and as a bare token after the word.
    (re.compile(r'("recording_capture"\s*:\s*\\?")[^"\\\s]+'), r"\1(removed)"),
    (re.compile(r'(recording_capture(?:\\|")*\s*[:=]\s*\(?(?:\\|")*)[A-Za-z0-9_.:\-]{8,}'), r"\1(removed)"),
    (re.compile(r'("signature"\s*:\s*\\?")[^"\\\s]+'), r"\1(removed)"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]+"), "(key)"),
    (re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{16,}"), "(key)"),
    (re.compile(r"\bam_[A-Za-z0-9_\-]{16,}"), "(key)"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}|\bgithub_pat_[A-Za-z0-9_]{20,}"), "(key)"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), "(key)"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "(key)"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/\-]{8,}=*"), "Bearer (removed)"),
    (re.compile(r'(?i)((?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|password|passwd)\\?"?\s*[:=]\s*\\?"?)'
                r'[^\s"\\,}]{6,}'), r"\1(removed)"),
    (re.compile(r"(?i)\b(code=)[^#&\s\"'\\]+"), r"\1(removed)"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "(id)"),
    (re.compile(r"\b[0-9a-f]{24,}\b", re.I), "(id)"),
    (re.compile(r"\b(toolu|msg|req|srvtoolu)_[A-Za-z0-9]+"), r"\1_(id)"),
    (re.compile(r"(?:/home|/Users|/root)(?:/[^\s\"'\\)\]:,;]*)?"), "(path)"),
    (re.compile(r"(?i)\b[A-Z]:\\Users\\[^\s\"']*"), "(path)"),
    (re.compile(r"/tmp/[^\s\"'\\)\]:,;]+"), "(path)"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "(email)"),
    (re.compile(r"\b(127\.0\.0\.1|localhost):\d{2,5}\b"), r"\1:(port)"),
    # Anything long and token-shaped that the rules above did not name.
    (re.compile(r"(?<![A-Za-z0-9_/.\-])(?=[A-Za-z0-9_\-+/]*\d)(?=[A-Za-z0-9_\-+/]*[A-Za-z])[A-Za-z0-9_\-+/]{32,}={0,2}"),
     "(token)"),
)


def redact(text: str, extra: tuple[str, ...] = ()) -> str:
    """``text`` with every private value replaced by a placeholder. ``extra`` adds literal strings (the trial
    directory) that are replaced first."""
    for literal in sorted({value for value in extra if value}, key=len, reverse=True):
        text = text.replace(literal, "(trial)")
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, "(path)")
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    for name in sorted(_user_names(), key=len, reverse=True):
        text = re.sub(rf"(?i)(?<![A-Za-z0-9]){re.escape(name)}(?![A-Za-z0-9])", "(user)", text)
    return text


# Logs --------------------------------------------------------------------------------------------------------------

def _context_of(raw: str) -> str:
    try:
        data = json.loads(raw)
    except ValueError:
        return raw or ""
    if isinstance(data, dict):
        return (data.get("hookSpecificOutput") or {}).get("additionalContext") or ""
    return ""


def _result_text(body) -> str:
    if isinstance(body, list):
        return " ".join(part.get("text", "") if part.get("type") == "text" else json.dumps(part) for part in body)
    return body if isinstance(body, str) else json.dumps(body)


def _json_or_text(text: str):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text


def parse_log(path: Path, previous_total: float | None = None) -> dict:
    """One turn's log. ``previous_total`` is the conversation's total cost after the session's previous turn."""
    out = {"init": None, "hooks": [], "calls": [], "texts": [], "reply": None, "result": None, "cost": None,
           "denials": [], "events": 0, "unparsed": 0}
    by_id: dict[str, dict] = {}
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            out["unparsed"] += 1
            continue
        if not isinstance(event, dict):
            continue
        out["events"] += 1
        kind, subtype = event.get("type"), event.get("subtype")
        if kind == "system" and subtype == "init":
            out["init"] = {
                "model": event.get("model"), "version": event.get("claude_code_version"),
                "membrain_tools": sorted(t for t in event.get("tools") or [] if "membrain" in t),
                "mcp": [(s.get("name"), s.get("status")) for s in event.get("mcp_servers") or []
                        if "membrain" in (s.get("name") or "")],
                "permission_mode": event.get("permissionMode"),
                "commands": [c for c in event.get("slash_commands") or [] if "membrain" in c]}
        elif kind == "system" and subtype == "hook_response":
            context = _context_of(event.get("output") or event.get("stdout") or "")
            out["hooks"].append({"event": event.get("hook_event"), "name": event.get("hook_name"),
                                 "exit": event.get("exit_code"), "context": context})
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if block.get("type") == "tool_use":
                    call = {"id": block.get("id"), "name": block.get("name") or "", "input": block.get("input"),
                            "result": None, "is_error": None}
                    by_id[call["id"]] = call
                    out["calls"].append(call)
                elif block.get("type") == "text" and (block.get("text") or "").strip():
                    out["texts"].append(block["text"].strip())
        elif kind == "user":
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else ():
                if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id") in by_id:
                    call = by_id[block["tool_use_id"]]
                    call["result"] = _json_or_text(_result_text(block.get("content")))
                    call["is_error"] = bool(block.get("is_error"))
        elif kind == "result":
            since = event.get("model_usage_since_last_result")
            total = event.get("total_cost_usd")
            if isinstance(since, dict) and since:
                cost = sum((value or {}).get("costUSD") or 0 for value in since.values())
            elif isinstance(total, (int, float)):
                cost = total - (previous_total or 0)
            else:
                cost = None
            out["cost"] = round(cost, 6) if cost is not None else None
            out["reply"] = event.get("result") if isinstance(event.get("result"), str) else None
            out["denials"] = [{"tool": d.get("tool_name"), "input": d.get("tool_input")}
                              for d in event.get("permission_denials") or [] if isinstance(d, dict)]
            out["result"] = {"is_error": event.get("is_error"), "subtype": subtype, "num_turns": event.get("num_turns"),
                             "duration_ms": event.get("duration_ms"), "total_cost_usd": total,
                             "stop_reason": event.get("stop_reason")}
    if out["reply"] is None and out["texts"]:
        out["reply"] = out["texts"][-1]
    return out


def _cut(text, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit] + f" ...[{len(text)} chars]"


def summary(name: str, message: str, parsed: dict, extra: tuple[str, ...] = ()) -> str:
    """The redacted per-turn summary (the shape of the hand-made trial's show.py)."""
    lines = [f"== {name}", f"USER {message}"]
    for hook in parsed["hooks"]:
        if hook["context"] or hook["exit"]:
            lines.append(f"HOOK {hook['name']} exit {hook['exit']} context chars {len(hook['context'])}")
            if hook["context"]:
                lines.append("  CONTEXT " + _cut(hook["context"], CONTEXT_CHARACTERS))
    init = parsed["init"] or {}
    lines.append(f"INIT model {init.get('model')} | host {init.get('version')} | membrain tools "
                 f"{len(init.get('membrain_tools') or [])} | mcp {init.get('mcp')} | commands {init.get('commands')}")
    for call in parsed["calls"]:
        lines.append(f"TOOL {call['name'].rsplit('__', 1)[-1]} {json.dumps(call['input'], ensure_ascii=False)}")
        result = call["result"] if isinstance(call["result"], str) else json.dumps(call["result"], ensure_ascii=False)
        lines.append("RESULT " + ("ERROR " if call["is_error"] else "") + _cut(result, SUMMARY_CHARACTERS))
    for text in parsed["texts"]:
        lines.append(f"SAYS {text}")
    result = parsed["result"] or {}
    lines.append(f"RESULT-EVENT turns {result.get('num_turns')} | turn cost_usd {parsed['cost']} | conversation "
                 f"total_cost_usd {result.get('total_cost_usd')} | ms {result.get('duration_ms')} | error "
                 f"{result.get('is_error')} | denials {parsed['denials']}")
    return redact("\n".join(lines), extra) + "\n"


# The report --------------------------------------------------------------------------------------------------------

def _table_cell(text) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def checks_table(results: list[dict], extra: tuple[str, ...] = ()) -> str:
    lines = ["| Turn | Check | Verdict | Detail |", "| --- | --- | --- | --- |"]
    for item in results:
        lines.append("| " + " | ".join(_table_cell(redact(str(value), extra))[:400] for value in (
            item["turn"], item["label"], item["verdict"], item["detail"])) + " |")
    shown = [item for item in results if item.get("shown")]
    for item in shown:
        lines.append("")
        lines.append(f"**For the lead to read ({item['turn']}: {item['label']}).**")
        for title, text in item["shown"]:
            lines.append("")
            lines.append(f"- {title}:")
            lines.append("")
            lines.append("  > " + redact(str(text), extra).replace("\n", "\n  > "))
    return "\n".join(lines) + "\n"


def state_summary(state: dict | None, extra: tuple[str, ...] = ()) -> str:
    if state is None:
        return "The memory could not be read.\n"
    lines = ["Current notes:"]
    for note in state["notes"]:
        replaced = [entry for entry in note.get("replaced") or () if entry.get("depth") == 1]
        lines.append(f"- {note.get('text')}" + (f" (replaced {len(replaced)} earlier note(s))" if replaced else ""))
    if not state["notes"]:
        lines.append("- none")
    lines.append("")
    lines.append("Topic boundaries: " + (", ".join(entry.get("topic") or "" for entry in state["boundaries"]) or "none"))
    roles = {}
    for record in state["records"]:
        roles[record.get("role")] = roles.get(record.get("role"), 0) + 1
    lines.append(f"Stored records: {sum(roles.values())} ({', '.join(f'{k} {v}' for k, v in sorted(roles.items()))})")
    return redact("\n".join(lines), extra) + "\n"
