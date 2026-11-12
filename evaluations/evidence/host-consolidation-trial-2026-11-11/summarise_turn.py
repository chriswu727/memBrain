"""Summarise one headless turn's stream-json log: model, plugin tools, hook context, tool calls, reply, usage."""
import json
import sys

for path in sys.argv[1:]:
    print("==", path.rsplit("/", 1)[-1])
    for line in open(path, encoding="utf-8"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            tools = [tool for tool in event.get("tools", []) if "membrain" in tool]
            print("model", event.get("model"), "| membrain tools", len(tools), tools[:3],
                  "| mcp", [(s.get("name"), s.get("status")) for s in event.get("mcp_servers", []) if "membrain" in s.get("name", "")])
        elif kind == "system" and "hook" in str(event.get("subtype")):
            text = json.dumps(event, ensure_ascii=False)
            print("hook", event.get("subtype"), event.get("hook_name") or event.get("hook_event"), len(text),
                  "| indexed-notice" if "not been indexed" in text else "")
        elif kind == "assistant":
            for block in event["message"].get("content", []):
                if block.get("type") == "tool_use":
                    print("TOOL", block["name"].rsplit("__", 1)[-1], json.dumps(block.get("input"), ensure_ascii=False)[:700])
                elif block.get("type") == "text" and block["text"].strip():
                    print("SAYS", " ".join(block["text"].split())[:300])
        elif kind == "user":
            for block in event["message"].get("content", []) if isinstance(event["message"].get("content"), list) else []:
                if block.get("type") == "tool_result":
                    print("RESULT", " ".join(json.dumps(block.get("content"), ensure_ascii=False).split())[:500])
        elif kind == "result":
            usage = event.get("usage", {})
            print("result turns", event.get("num_turns"), "cost_usd", event.get("total_cost_usd"),
                  "in", usage.get("input_tokens"), "cache_read", usage.get("cache_read_input_tokens"),
                  "cache_write", usage.get("cache_creation_input_tokens"), "out", usage.get("output_tokens"),
                  "ms", event.get("duration_ms"))
