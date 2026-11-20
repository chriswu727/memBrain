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
| OpenAI-compatible proxy | Request adapter | None (no tools; no notes are written) | API/SDK only | Memory page or API/SDK |
| TypeScript client | Host must orchestrate context | `writeNote` | `addBoundary` | Explicit client methods |

Automatic companion context uses the shared host layer to render the current persona, note-linked reported/inferred feelings, labelled simulated mood, and relationship settings/moments/commitments. The host supplies interpretation and replies. A note must explicitly carry `affect` or `shared`; ordinary storage does not infer a feeling or turn every exchange into a shared moment. The host AI reports the user's feedback on its manner through the manner-feedback tool; a narrow phrase table still recognises some comments without it. A proposal changes nothing until the user accepts. A new memory starts with one of sixteen personality types (the four-letter types familiar from MBTI), picked at random when a session first builds its memory context (not for role-play memories or while recording is paused), and that session's notice asks the host AI to mention it once. On the coding hosts (Claude Code, Codex and WorkBuddy, through the plugin's hooks) the companion is on but quiet since 2026-11-19: a session starts with the persona's voice, the user's agreements and the boundaries, and the prompt hook hands the full card, the mood, familiarity, shared moments, the absence sentence and the held introduction once, at the first casual or emotional message or after the host uses a companion tool ([record](../evaluations/quiet-companion-2026-11-19.md)). Chat hosts, OpenClaw and role-play are unchanged. The persona tool (`memory_persona` on MCP hosts, `membrain_persona` on OpenClaw and AstrBot, `membrain plugin tool persona` elsewhere) lists the presets, switches when the user asks, and proposes a change that the user confirms in a later message; the service refuses a confirmation without a user message after the proposal's reply. Only Claude Code has a slash command for it (`/membrain:persona`); on other hosts the user asks in words. Switching changes only the card: mood and familiarity carry over.

Standalone MCP and TypeScript are low-level interfaces. Connecting an MCP server alone does not capture a conversation or inject all companion layers. The MCP tool set has no dedicated persona/mood/relationship inspection tools, persona-proposal acceptance, mood pinning or every relationship/reset control. Hosts requiring those APIs use the shared host layer or authenticated API/SDK; the memory page provides the user's one-click controls, not a form. Bundled plugin hooks supply companion context separately from the MCP tools. TypeScript supplies those controls and both bounded maps, but no ready-made automatic TypeScript text runtime. The proxy has no conversational boundary tool or automatic boundary extractor, and since 2026-11-18 the memory page only lists and removes boundaries, so a boundary behind the proxy can be added only through the API/SDK. Without tools no notes or feelings are written behind the proxy: memBrain calls no model of its own, and the separate note-extraction model that earlier versions offered has been removed (its `MEMBRAIN_EXTRACT_*` variables are ignored). The same applies to AstrBot with a model that does not call tools. Recording and recall are unaffected.

Persona proposal decisions and destructive/reset operations belong to the user. The host must not silently accept a proposal. Each reset explains its scope; feelings, persona, mood and relationship are not interchangeable. See [TypeScript controls](reference.md#typescript-companion-controls-and-maps) and the [Phase C design](../architecture/phase-c-design.md).

## What the user can change by talking

Since 2026-11-18 the memory page has no text entry for memory content. It shows what is kept and where it came from, deletes any item (a note, a message or conversation, a feeling, a shared moment, a boundary), and holds the controls for the whole memory: restoring a persona version, switching the personality type, accepting or rejecting a suggestion, pause and resume, export, search and erasing everything; deleting the personality history, the mood pin, resetting the mood or the relationship and clearing feelings are under a collapsed "More". Everything else is changed by telling the agent, so what a user can change depends on the tools their host gives the AI:

| Integration | Add or correct a note (`replaces`) | Add a boundary | Change the persona | Manner feedback | Forget one item |
| --- | --- | --- | --- | --- | --- |
| Claude Code / Codex / WorkBuddy / CodeBuddy plugin, standalone MCP server | `memory_note` | `memory_boundary` | `memory_persona` | `memory_manner_feedback` | `memory_forget` |
| OpenClaw | `membrain_note` | `membrain_boundary` | `membrain_persona` | `membrain_manner_feedback` | None: delete it on the page |
| AstrBot | `membrain_note` | `membrain_boundary` | `membrain_persona` (none in role-play) | `membrain_manner_feedback` | None per item: `/membrain_forget confirm` erases everything of that person |
| Hermes | `membrain_note` | `membrain_boundary` | None | None | None: delete it on the page |
| Chat bots on `ChatMemory` | `note` | `boundary` | `persona` (refused in role-play) | `manner_feedback` | `forget` erases a whole speaker |
| OpenAI-compatible proxy | None (read-only) | None | None | None | None |
| TypeScript client or your own API/SDK host | What that host exposes; the routes cover all of it | | | | |

On every host with a persona tool, a persona proposal can add, remove or replace traits, values and persona boundaries (`changes.remove` names the card's entries to take off, beside any additions, so a replacement is one proposal the user confirms once), change or clear voice fields, and replace or clear the name or baseline mood. A removal changes the current card only: a later switch of type starts from that type's own card plus what the user agreed. Limits that hold on every host: lifting a boundary and deleting a shared moment are done on the page. On Hermes the persona can be changed only by switching the type or restoring a version on the page, and on the proxy nothing can be added or corrected at all; whether `ChatMemory`'s methods reach the model is up to the integrator, and its session notice names only the note, recall, pause and resume tools. The support style and the familiarity cap were removed the same day (see the [reference](reference.md#retired-relationship-records)).

## Refresh, failures and host-owned history

The authenticated [server recording control](reference.md#server-recording-control) stops source ingestion for one brain and closes unfinished runtime turns that an older runtime left. Hosts read this policy before staging and carry its revision through reply delivery and offline replay. Known server pauses prevent staging even offline; local resume cannot override them. A pause/resume cycle rejects older captured observations without spooling or archiving their content. Legacy queued input is accepted only while the server revision remains zero. Disconnected hosts cannot discover a remote change until reconnecting; local conversation/timed controls are not synchronized back to the server, and external host transcripts are outside this control. The fence does not cover separately submitted derived notes or make delivery crash-atomic.

The direct Python `BrainRuntime`, `open_agent` and `desktop chat`, with their temporary chat under server pause and their own local recording controls, were removed with runtime mode after `ba70e7cd` ([details](reference.md#bundled-chat-and-python-sessions-removed)). A pause that a host conversation asked for covers the host conversations listed when it was set. Other adapters keep their existing host-owned response flows and separate local controls.

The shared host lifecycle recognizes documented direct English/Chinese pause commands before storing raw input, including in the tool-free proxy. This is a bounded command grammar, not general intent classification. The current exchange is excluded from staging and spooling; ordinary recording resumes through controls or the existing new-conversation rule. Local MCP observations also respect pause. Raw HTTP/SDK writes and a directly constructed `BrainRuntime` do not inherit this local policy; `open_agent` sessions apply it at their own boundary. See [recording scope and limits](reference.md#chat-adapter-identity-compatibility) and the [backend review](../architecture/backend-control-flow-2026-11-07.md). The repair does not turn the historical failed R4 result into a pass.

The bot/proxy request adapter and OpenClaw rebuild their memory contribution for each request. Hermes refreshes the provider block whenever its host asks for it. Personal content is not cached for five minutes or for the lifetime of a provider. The Python bot constructor still accepts `block_seconds` for source compatibility, but it no longer enables personal-context caching.

Boundary-read errors propagate to the caller so an unavailable relationship service cannot be interpreted as an empty boundary list. Hooks may omit memory while the conversation continues; MCP reports a tool error. Only the older-service compatibility case of an absent route (404/405) permits no boundaries. A failed session snapshot also prevents unfiltered earlier history from being injected.

memBrain cannot withdraw text already supplied to a model, or erase a host's independently retained transcript. Refreshing memBrain's contribution does not rewrite a host's chat history. Native hosts must invoke their lifecycle/provider hooks; framework-level caching outside this adapter is not controlled by memBrain.

## When the runtime cannot run

Launchers need uv; `uvx` is optional (`uv tool run` is used without it). Without uv, or before the installed runtime runs, the launcher itself tells the host's AI once at session start ([wording](reference.md#when-the-runtime-cannot-run)). Checked on Linux with fake `uv` and `uvx` commands on a sandboxed path, not in the host applications.

| Integration | Told when uv is missing | Told when uv is present but the runtime does not run |
| --- | --- | --- |
| Claude Code, Codex | Session-start hook context | Session-start hook context |
| WorkBuddy / CodeBuddy | Session-start hook context from `bin/membrain-hook`; `membrain-hook.cmd` by inspection only | The same |
| OpenClaw | Appended system context, once per session, owner's conversations only | Not told; memory tools answer that memBrain "may still be installing" |
| AstrBot, Hermes, proxy | Not applicable: AstrBot and Hermes install the runtime into their own Python with pip or `uv pip`, and the user runs the proxy; no launcher | Not applicable |

Not shown at all when the host does not run the plugin's hooks: Codex before the user trusts them in `/hooks`; Claude Code on Windows without Git Bash, which runs hooks with PowerShell; WorkBuddy's PowerShell fallback. A failed tool server is shown only where the host shows MCP status (in Claude Code, `/mcp` and `claude mcp list`).

## What was actually exercised

- **Shared installed runtime on macOS:** runtime `fc149df` passed [49 fresh launcher checks, 112 installed regressions and two 187-input installed comparisons](../evaluations/maturity-semantic-balance-2026-11-07.md#exact-runtime-installation-and-fullscreen-qualification), including MCP, proxy, companion preservation, upgrade/restart and backup/restore. This is not a claim that every native macOS host application ran. The earlier `d4d7126` result remains scoped to its own runtime.
- **Claude Code on Linux x86_64:** local-marketplace install and separate sessions ran with a local model stub, demonstrating recording and cross-session injection. This verifies integration rather than real model answer quality. Native Codex, WorkBuddy and CodeBuddy journeys are not inferred from that result.
- **Windows 11:** earlier evidence covers the embedded service, both shell launchers, and partial AstrBot/OpenClaw integration. Native Claude Code/Codex and a complete current-candidate host/model matrix are not verified there.
- **OpenClaw:** its JavaScript suite is also driven through a real embedded runtime by `tests/test_openclaw_plugin.py`. This is separate from a full native OpenClaw/model acceptance.
- **AstrBot:** `tests/test_chatbot_adapter.py` uses framework interface stubs with a real local memory service, including per-person isolation, boundary tools and shared notes. The earlier partial Windows run does not replace current native-host acceptance.
- **Hermes:** provider interface and real local-service sessions are tested in `tests/test_hermes_adapter.py`; a complete real Hermes installation/model journey remains unverified.
- **TypeScript:** 50 local tests and 36 fresh installed-service API checks cover the client extension; [exact evidence](../evaluations/maturity-typescript-companion-2026-11-04.md). This is not a model-behaviour result.

The [maturity matrix](../evaluations/maturity-test-matrix.md), [release checklist](releasing.md) and dated evidence reports determine release readiness. This inventory does not waive any open gate.

## Recording outcomes

Whether an exchange reached memory can be [looked up afterwards](reference.md#looking-up-a-recording-outcome) on every host that records through the shared host layer. The result is the last observation with its age: server-confirmed, locally queued (not yet confirmed), excluded with the policy's reason and scope, failed, or unknown. It is not a statement about chat delivery or about current controls, and a lookup never stores, retries or sends anything.

| Integration | Surfaced as |
| --- | --- |
| Claude Code / Codex / WorkBuddy / CodeBuddy / OpenClaw hooks | `membrain plugin outcome` by session and turn ID, or a listing of recent exchanges; hook output is unchanged |
| OpenAI-compatible proxy | `X-Membrain-Exchange` response header; `GET /v1/membrain/recording-outcomes[/{exchange}]` for the same token and person |
| Hermes | `membrain_recording_status` tool and `MembrainProvider.recording_outcomes()` |
| AstrBot / `ChatMemory` | `ChatMemory.outcome()` and `recent_outcomes()`; the returned receipt and the AstrBot warning are unchanged |

Outcomes are kept in the local session ledger for the last 256 exchanges of a session and 14 days, scoped to their owner and recording target, and removed by host-level erasure. Standalone MCP, raw HTTP/SDK writes and the direct `BrainRuntime`/`open_agent` path do not use this ledger; the runtime's own turn and delivery receipts remain separate. This was exercised with interface stubs, a real local service and real hook and CLI processes on WSL2 Linux, not inside native host applications; see the [validation report](../evaluations/backend-host-recording-outcome-query-2026-11-10.md).

## Concurrent host callbacks

The host ledger now matches user, producer and turn identity, including out-of-order replies. Context refresh leaves active inputs staged. Supplied proxy session headers are bound to the user, group and character. Hosts should supply a stable turn ID and the same user on both callbacks. Missing IDs support only unambiguous pairing; identical overlapping prompts are excluded.

The ledger is bounded to 64 active turns and 256 finished markers per session. It rejects unknown callbacks in staged sessions after compaction. Hermes retains whole-turn reporting without prefetch through an explicit adapter option, but a session that excluded or erased content requires staging for later unknown turns (or a new session). See [the lifecycle contract](reference.md) and the [concurrency report](../evaluations/backend-turn-isolation-2026-11-07.md) for verification and limits. This does not establish server-wide recording policy or atomicity between a pause and an already-running network write.
