# Host features and verification scope

This describes the pre-release integration candidate. Interface support, a real local service test and a real host/model journey are separate claims. R4/C5 and final independent review remain open; no integration below has passed the new held-out companion acceptance.

## Companion interfaces

| Integration | Automatic companion context | Feelings / shared notes | Boundary creation | Persona decisions and layer resets |
| --- | --- | --- | --- | --- |
| Claude Code / Codex / WorkBuddy / CodeBuddy plugin | Lifecycle hooks | `memory_note` | `memory_boundary` | Memory page or API/SDK |
| Standalone MCP server | Host must orchestrate context | `memory_note` | `memory_boundary` | Memory page or API/SDK |
| OpenClaw | Prompt hooks | `membrain_note` | `membrain_boundary` | Memory page or API/SDK |
| AstrBot | Request adapter | `membrain_note` | `membrain_boundary` | Memory page or API/SDK |
| Hermes | Provider block and prefetch | `membrain_note` | `membrain_boundary` | Memory page or API/SDK |
| OpenAI-compatible proxy | Request adapter | Optional extractor | Memory page or API/SDK | Memory page or API/SDK |
| TypeScript client | Host must orchestrate context | `writeNote` | `addBoundary` | Explicit client methods |

Automatic companion context uses the shared host layer to render the current persona, note-linked reported/inferred feelings, labelled simulated mood, and relationship settings/moments/commitments. The host supplies interpretation and replies. A note must explicitly carry `affect` or `shared`; ordinary storage does not infer a feeling or turn every exchange into a shared moment. Persona feedback recognition uses the documented narrow phrase table; a proposal changes nothing until the user accepts.

Standalone MCP and TypeScript are low-level interfaces. Connecting an MCP server alone does not capture a conversation or inject all companion layers. The MCP tool set has no dedicated persona/mood/relationship inspection tools, persona-proposal acceptance, mood pinning or every relationship/reset control. Hosts requiring those APIs use the shared host layer or authenticated API/SDK; the memory page provides user controls. Bundled plugin hooks supply companion context separately from the MCP tools. TypeScript supplies those controls and both bounded maps, but no ready-made automatic TypeScript text runtime. The proxy has no conversational boundary tool or automatic boundary extractor. Its user sets boundaries through the page or API/SDK; note extraction needs its separately configured model provider.

Persona proposal decisions and destructive/reset operations belong to the user. The host must not silently accept a proposal. Each reset explains its scope; feelings, persona, mood and relationship are not interchangeable. See [TypeScript controls](reference.md#typescript-companion-controls-and-maps) and the [Phase C design](../architecture/phase-c-design.md).

## Refresh, failures and host-owned history

The bot/proxy request adapter and OpenClaw rebuild their memory contribution for each request. Hermes refreshes the provider block whenever its host asks for it. Personal content is not cached for five minutes or for the lifetime of a provider. The Python bot constructor still accepts `block_seconds` for source compatibility, but it no longer enables personal-context caching.

Boundary-read errors propagate to the caller so an unavailable relationship service cannot be interpreted as an empty boundary list. Hooks may omit memory while the conversation continues; MCP reports a tool error. Only the older-service compatibility case of an absent route (404/405) permits no boundaries. A failed session snapshot also prevents unfiltered earlier history from being injected.

memBrain cannot withdraw text already supplied to a model, or erase a host's independently retained transcript. Refreshing memBrain's contribution does not rewrite a host's chat history. Native hosts must invoke their lifecycle/provider hooks; framework-level caching outside this adapter is not controlled by memBrain.

## What was actually exercised

- **Shared installed runtime on macOS:** runtime `fb249da` passed [49 fresh launcher checks and two 187-input installed comparisons](../evaluations/maturity-lexical-cue-2026-11-06.md#exact-runtime-installation-and-fullscreen-qualification), including MCP, proxy, companion preservation, upgrade/restart and backup/restore. This is not a claim that every native macOS host application ran. The earlier `d4d7126` result remains scoped to its own runtime.
- **Claude Code on Linux x86_64:** local-marketplace install and separate sessions ran with a local model stub, demonstrating recording and cross-session injection. This verifies integration rather than real model answer quality. Native Codex, WorkBuddy and CodeBuddy journeys are not inferred from that result.
- **Windows 11:** earlier evidence covers the embedded service, both shell launchers, and partial AstrBot/OpenClaw integration. Native Claude Code/Codex and a complete current-candidate host/model matrix are not verified there.
- **OpenClaw:** its JavaScript suite is also driven through a real embedded runtime by `tests/test_openclaw_plugin.py`. This is separate from a full native OpenClaw/model acceptance.
- **AstrBot:** `tests/test_chatbot_adapter.py` uses framework interface stubs with a real local memory service, including per-person isolation, boundary tools and shared notes. The earlier partial Windows run does not replace current native-host acceptance.
- **Hermes:** provider interface and real local-service sessions are tested in `tests/test_hermes_adapter.py`; a complete real Hermes installation/model journey remains unverified.
- **TypeScript:** 50 local tests and 36 fresh installed-service API checks cover the client extension; [exact evidence](../evaluations/maturity-typescript-companion-2026-11-04.md). This is not a model-behaviour result.

The [maturity matrix](../evaluations/maturity-test-matrix.md), [release checklist](releasing.md) and dated evidence reports determine release readiness. This inventory does not waive any open gate.
