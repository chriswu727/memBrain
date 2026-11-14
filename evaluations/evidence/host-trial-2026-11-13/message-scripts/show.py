"""Summarise headless turns' stream-json logs: model, plugin tools, hook context, tool calls and results, replies,
usage per model call and per turn. ``--full`` prints hook context and tool results whole; ``--redact`` removes
session ids, record ids, capture tokens and local paths (for publishable summaries)."""
import json
import re
import sys
from pathlib import Path

args = [a for a in sys.argv[1:] if not a.startswith("--")]
FULL = "--full" in sys.argv
REDACT = "--redact" in sys.argv
LIMIT = 100000 if FULL else 700


def red(text):
    if not REDACT:
        return text
    text = re.sub(r'("recording_capture"\s*:\s*\\?")[^"\\]+', r'\1(removed)', text)
    text = re.sub(r'(recording_capture\\?"?\s*[:=]\s*\\?"?)[A-Za-z0-9_.\-]{16,}', r'\1(removed)', text)
    text = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '(id)', text)
    text = re.sub(r'\b[0-9a-f]{24,}\b', '(id)', text)
    text = re.sub(r'toolu_[A-Za-z0-9]+', 'toolu_(id)', text)
    text = re.sub(r'/home/[^\s"\\]*', '(path)', text)
    text = re.sub(r'am_[A-Za-z0-9_\-]{20,}', '(key)', text)
    text = re.sub(r'\bACCOUNT_NAME\b', '(user)', text)
    return text


def out(*parts):
    print(red(" ".join(str(p) for p in parts)))


def cut(text, n=LIMIT):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + f" …[{len(text)} chars]"


def context_of(raw):
    try:
        data = json.loads(raw)
        return data.get("hookSpecificOutput", {}).get("additionalContext") or ""
    except (ValueError, AttributeError):
        return raw or ""


for path in args:
    path = Path(path)
    name = path.name[:-len(".jsonl")]
    out("==", name)
    prompt = path.with_name(name + ".prompt.txt")
    if prompt.exists():
        out("USER", prompt.read_text())
    calls = {}
    for line in open(path, encoding="utf-8"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            tools = [t for t in event.get("tools", []) if "membrain" in t]
            out("INIT model", event.get("model"), "| claude", event.get("claude_code_version"),
                "| membrain tools", len(tools),
                "| mcp", [(s.get("name"), s.get("status")) for s in event.get("mcp_servers", []) if "membrain" in s.get("name", "")],
                "| plugins", [p.get("name") for p in event.get("plugins", [])],
                "| membrain commands", [c for c in event.get("slash_commands", []) if "membrain" in c])
        elif kind == "system" and event.get("subtype") == "hook_response":
            ctx = context_of(event.get("output") or event.get("stdout") or "")
            if ctx or event.get("exit_code"):
                out("HOOK", event.get("hook_name"), "exit", event.get("exit_code"), "context chars", len(ctx))
                if ctx:
                    out("  CONTEXT", cut(ctx, 100000 if FULL else 1200))
        elif kind == "assistant":
            message = event["message"]
            mid = message.get("id")
            if mid:
                calls[mid] = message.get("usage", {})
            for block in message.get("content", []):
                if block.get("type") == "tool_use":
                    out("TOOL", block["name"].rsplit("__", 1)[-1], json.dumps(block.get("input"), ensure_ascii=False))
                elif block.get("type") == "text" and block["text"].strip():
                    out("SAYS", block["text"].strip())
        elif kind == "user":
            content = event["message"].get("content")
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        body = block.get("content")
                        if isinstance(body, list):
                            body = " ".join(b.get("text", "") if b.get("type") == "text" else json.dumps(b) for b in body)
                        out("RESULT", ("ERROR " if block.get("is_error") else "") + cut(body, 100000 if FULL else 900))
            elif isinstance(content, str) and content.strip() and event.get("isSynthetic") is None and False:
                pass
        elif kind == "result":
            usage = event.get("usage", {})
            since = event.get("model_usage_since_last_result") or {}
            turn_cost = sum(v.get("costUSD", 0) or 0 for v in since.values()) if since else None
            out("MODEL CALLS", len(calls), "|", "; ".join(
                f"in {u.get('input_tokens')} cache_read {u.get('cache_read_input_tokens')} cache_write {u.get('cache_creation_input_tokens')} out {u.get('output_tokens')}"
                for u in calls.values()))
            out("RESULT-EVENT turns", event.get("num_turns"), "| models", list(since or event.get("modelUsage", {})),
                "| turn cost_usd", round(turn_cost, 5) if turn_cost is not None else None,
                "| conversation total_cost_usd", round(event.get("total_cost_usd") or 0, 5),
                "| turn usage in", usage.get("input_tokens"), "cache_read", usage.get("cache_read_input_tokens"),
                "cache_write", usage.get("cache_creation_input_tokens"), "out", usage.get("output_tokens"),
                "| ms", event.get("duration_ms"), "| error", event.get("is_error"),
                "| denials", event.get("permission_denials"))
    hook = path.with_name(name + ".prompt-hook.json")
    if hook.exists():
        ctx = context_of(hook.read_text())
        out("PROMPT-HOOK context chars", len(ctx))
        if ctx:
            out("  CONTEXT", cut(ctx, 100000 if FULL else 1200))
    print()
