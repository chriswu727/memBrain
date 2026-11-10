# Backend control flow and recording policy

This review covers the pre-release integration candidate and the first backend repair batch. It is not a complete security audit or a declaration of release readiness. The user requested module-by-module work instead of a continuing Goal. No new paid or subscription-backed acceptance was started for this review.

## Responsibilities and current paths

| Layer | Responsibility | Current implementation |
| --- | --- | --- |
| Host adapters | Identity, real user/assistant events, context insertion, available tools | Plugin hooks, ChatMemory/proxy, OpenClaw and Hermes call the shared host layer |
| Host lifecycle | Privacy controls, staging, recall composition, delivery/spooling | `host.py`; local session markers and pause state |
| Durable AgentRuntime | Capture, preparation, generation, delivery confirmation, recovery | `runtime.py` and durable turn journal; separate from host staging |
| Public API/SDK | Authenticated memory actions and explicit controls | HTTP, Python, TypeScript and MCP interfaces |
| Memory service | Transactional event/knowledge state, retrieval and lifecycle dependencies | `service.py`, cognition, semantic retrieval, learning and jobs |
| Persistence | Ownership, constraints, RLS, migrations, vectors and recovery | PostgreSQL, pgvector, JSONB; no new storage system is needed for this repair |

```mermaid
flowchart TD
    A[Plugin or chat adapter] --> B[Direct user command check]
    B -->|recording allowed| C[Stage scrubbed input]
    B -->|explicit pause| D[Persist control metadata only]
    C --> E[Recall existing memory and call host model]
    D --> E
    E --> F[Finish callback and recording check]
    F -->|accepted| G[Deliver or spool records]
    F -->|excluded| H[No exchange records or extractor work]
    G --> I[Accepted record references]
    I --> J[Optional note extraction]
    K[Separate AgentRuntime] --> L[Durable journal and direct observe]
    L --> M[Prepare, generate, confirm delivery, commit]
```

Framework dependencies stay outside the core. The main architectural issue is that the host lifecycle and durable AgentRuntime have different capture/control contracts. Moving functions between files alone would not unify those contracts.

## Confirmed defects addressed in this batch

1. The tool-free proxy had no deterministic pre-storage response to an explicit off-record request. Avoiding sensitive extracted notes did not exclude raw conversation history. The public English/Chinese reproductions retained after the fifth acceptance now exercise a shared pre-staging policy, also checked by finish-only callbacks.
2. A pause before the first staged message lacked that session in its conversation scope. The pause operation can now include the originating session explicitly without writing its text.
3. Finish callbacks returned all planned records even when a later pause caused `deliver` to reject them. They now return only accepted delivery/spool receipts, so downstream extraction cannot treat a rejected user record as evidence.
4. Local MCP `memory_observe` did not check pause, although `memory_note` did. Both content-writing tools now check local recording state. Remote MCP without a local installation still has caller-managed policy.
5. Ending a conversation pause read its state before taking the state lock. The read and removal now share the lock, avoiding deletion of a concurrently replaced pause based on an old snapshot.
6. A finish callback with no staged or explicitly supplied input could store an orphan assistant reply after a failed prompt hook, or revive a private reply after pause/resume and a duplicate finish. Three public tests reproduced this on the first repair. Finish now requires a staged or supplied input before accepting an assistant reply; hooks still let the host answer when memory is unavailable.

The initial regression run exposed a duplicate-processing error in the new finish fallback: it could reinstate a pause after a user had resumed. The repair preserves a staged exclusion without replaying its control. The existing extraction regression remains unchanged and is rerun; a focused test also checks that later public turns can be recorded after resuming.

## Policy boundaries

- Only a direct opening control clause matching the documented English/Chinese grammar changes state. No model call, embeddings or new database migration is needed to recognize it. A quote, reported speech, translation request, or confidentiality-only request is not a pause command.
- Automatic pause uses the existing conversation scope and includes role-play through the real person's identity. It does not shorten a pre-existing timed or until-resumed pause. Other users and separate group brains keep their controls.
- Raw input, its assistant reply and automatic extraction are excluded for a protected turn. A same-turn resume cannot resurrect an explicit exclusion. New-conversation and later-turn resume semantics remain those of the existing host controls.
- Previously stored or queued records are not retroactively erased. The host and upstream reply model still receive the conversation. This is not a general no-processing guarantee.
- Direct SDK/HTTP writes and AgentRuntime are separate interfaces: the local pause files do not constitute a transactional server-wide policy. This batch must not be described as making every backend entry point private by default.

## Next architectural work, in priority order

1. Define a server-owned recording policy shared by the durable runtime and host lifecycle. An ephemeral turn must have a deliberate generation/delivery/recovery contract; simply skipping `observe` breaks the runtime's source references. Explicit API controls should be authoritative, with natural-language recognition only an adapter convenience.
2. Make host pending state genuinely per turn, not one mutable pending slot per session. Qualify overlapping requests and late/repeated finish callbacks. Bind supplied proxy session IDs to the authenticated identity, group and role-play instead of relying on callers to choose globally unique headers. These are identified review targets, not fixes claimed by this batch.
3. Specify which writes can already be in flight when a pause is acknowledged. Local file checks and network writes do not form one database transaction; stronger guarantees need service-side policy/version checks, rather than holding a global file lock during all network calls.
4. Normalize delivery receipts across adapters and the durable journal. Keep recorded, queued, rejected, unknown delivery and model-generated claims distinct. Evaluate cancellation and crash recovery against those states.
5. Review retrieval/database cost with the existing 10,000-memory baseline, then larger and passage-heavy workloads. Preserve source/candidate parity where required; a structural refactor is not itself a performance improvement.

A zero-provider [overlap probe](../evaluations/evidence/backend-recording-policy-2026-11-07/same-session-overlap.json) confirms the pending-slot issue: two owners reuse a session ID, and the first owner's finish receipt contains the second owner's pending user record. Stored records retain their original owner, so this probe does not demonstrate cross-user database disclosure. It demonstrates incorrect callback receipts and missing user records in a later receipt, which can break source-linked extraction. The probe is retained as an existing defect, not a passing acceptance check.

## Verification scope

The new regression suite exercises grammar false positives, source-free staging and spooling, extractor suppression, role-play and user/group separation, restarts, existing timed pauses, same-turn resume, finish-only hosts, rejected receipts, local MCP, and streaming/non-streaming proxy requests through real embedded PostgreSQL. Existing host, plugin, adapter, extraction and MCP tests are also checked. CI and final counts belong to the pull request and verification report, not this design document.

The historical fifth acceptance remains R4 failed and C5 invalid/unscored. Public deterministic regression checks cannot establish held-out model behavior or clear release gates. Main merge, tag and package publication remain blocked by those gates.

## Concurrent-turn follow-up

The [turn-isolation batch](../evaluations/backend-turn-isolation-2026-11-07.md) implements the second follow-up above. It retains the failing overlap probe as baseline evidence and adds reverse-order completion, shared-owner privacy, capacity, migration, erasure and proxy-scoping regressions. Its report records qualification separately; the original review is not retroactively treated as a pass.

## Server ingestion follow-up

The [server recording-control batch](../evaluations/backend-server-recording-2026-11-07.md) adds an authenticated, revisioned per-brain policy and serializes it with source ingestion using the existing database lock. It closes unfinished durable turns without reviving them on resume, and prevents hosts from spooling explicit server rejections. This is the first server-side part of follow-ups 1 and 3. Local conversation/timed policies are not synchronized to this separate whole-brain switch; ephemeral durable turns and crash-atomic host delivery still need their own contracts. The older local-pause findings above retain their original scope.

The subsequent capture-revision fence connects server policy reads to host staging and replay. Input and its reply retain the capture revision; pause followed by resume invalidates older queued observations. Known pauses remain effective offline and cannot be cleared by local resume. This closes the delayed-observation gap without widening a local conversation pause to the entire brain. Reverse synchronization, derived-note fencing, ephemeral turns and atomic host delivery remain separate work; a disconnected host cannot immediately discover a remote change.


## Background note extraction follow-up

The [recording-fenced extraction batch](../evaluations/backend-extraction-recording-fence-2026-11-08.md) carries the source turn's server recording target/version through queued extraction, provider retries and note submission. Exact-source reads include the recording policy in their existing transaction; stale or paused queued tasks do not dispatch a provider call. New note writes recheck the frozen revision under the brain lock used by pause/resume, before replacements, feelings or request records. An already-dispatched provider call cannot be recalled; its stale result cannot become a new note. Already committed idempotent retries remain acknowledgements, not new writes.

This closes the automatic ChatMemory/proxy extraction path, not every derived-writing path. Manual host note tools and custom clients that omit the optional capture revision still need their own operation-lifetime contract; separately scheduled cognitive learning remains distinct. Local conversation/timed control synchronization, an ephemeral durable-turn mode and crash-atomic delivery remain open. Existing source reads, export and deletion remain available while recording is paused. The first backend module is still incomplete, and this engineering change does not clear R4/C5.


## Background cognitive learning follow-up

The learning queue now reads the same locked server recording policy during task claiming, provider-operation reservation and publication. Unstarted orientation/consolidation tasks stay queued while paused; their first claim binds the current policy revision. Existing attempts keep their revision across automatic retries and restarts. Paused or stale attempts cannot prepare new snapshots, renew processing, reserve another call or publish a result. Usage settlement remains available so an already dispatched operation is not forgotten or refunded. Historical integration's alternate failure/defer path checks the same guard.

Interrupted tasks report `recording_paused` or `recording_stale` and need explicit recovery after resume; a recovery authorization preserves the original failure and spending while allowing a new task under the current recording policy. Work that never started can begin after resume. Indexing and retrieval of already recorded history remain available. This does not synchronize the separate local conversation/timed controls, provide an ephemeral durable-turn mode or make host delivery crash-atomic. Manual tool capture also remains open. Runtime-bound verification belongs in the accompanying qualification report.


## Manual host tool follow-up

Lifecycle-integrated note tools now consume an opaque `recording_capture` from the original staged turn. The bounded session marker keeps its owner, nonce and captured server revision/target; execution does not refresh them. Plugin, plugin MCP, Hermes, ChatMemory, AstrBot and OpenClaw use the shared resolver. Plugin MCP observations use the same authority. A local pause revokes both active and completed captures for the affected owner and role-plays; later resume cannot restore them. Server policy changes reject stale note writes in the existing transaction before replacements or affect records are persisted.

The standalone desktop MCP connection remains explicitly tools-only and caller-managed; its lack of prompt hooks is not disguised as full lifecycle integration. It reports whether capture is required and never drops a supplied capture silently. Direct SDK writes and Hermes file imports/mirroring retain their separate contracts. Local-only pause acknowledgement still cannot cancel a network call that already passed the local check. Reverse synchronization, ephemeral durable turns and crash-atomic delivery remain open. See the manual-tool section of the [reference](../docs/reference.md#manual-tools-and-original-turn-recording-permission) for upgrade and retention behavior. Qualification is reported separately, and historical R4/C5 failures remain unchanged.

## Recoverable host delivery follow-up

Host completion and abandoned-input recovery now journal their scrubbed payloads before removing staged copies. Queue admission enforces the whole batch's encoded byte limit and synchronizes writes; a full queue retains the unfinished stage, while failed/short writes do not acknowledge completion. Replay retains source identities and recording revisions. Interrupted delivery can therefore repeat a request idempotently, including after the server committed it but before the client acknowledged it. Queue admission and local erasure cleanup share ordered session and queue-write locks. Replay and remote erasure still serialize on the replay lock, but new queue admissions do not wait for network replay. Session and queue-write locks are held only for local state transitions, not network calls. A damaged UTF-8 tail is isolated from later records.

Local erasure also revokes manual-note captures for both unfinished and completed turns. Otherwise a delayed tool call could write content back using the cleared turn's still-valid nonce. New public turns obtain fresh captures. This local revocation does not cancel a request that already passed the capture check before erasure; server-wide erasure fencing for delayed uncommitted writes remains separate work.

This is a local journal plus idempotent server delivery, not one distributed transaction. User and assistant observations remain separate server transactions, so a reader can see a partial exchange during replay. A callback that failed before queue admission needs host retry, and abandoned-input recovery cannot reconstruct an unaccepted reply. Already queued records follow existing local-pause semantics, while server policy changes still reject stale replay. General receipt normalization across the independent durable AgentRuntime, ephemeral turns and local/server control synchronization remain open. Verification and measured filesystem overhead are reported separately; this change does not clear historical R4/C5 failures.


## Bounded host replay follow-up

Foreground replay now processes at most 16 records with a one-second between-request budget. A dedicated local-service thread drains batches of at most 64 without depending on a future host callback. It uses a two-second local HTTP timeout, yields between batches, backs off transient failures up to 30 seconds and joins during service shutdown. This worker does not run model extraction and does not replace the separate cognitive-learning worker. One in-flight request can exceed the batch budget; it is not a hard wall-clock latency guarantee.

Confirmed prefixes are checkpointed even when a later record fails. The cursor contains a byte offset and the acknowledged prefix checksum, validated against the file before skipping records. Missing, corrupt or stale cursors cause safe idempotent replay. Reads are bounded by count and a 256 KiB batch target, with an exception for one oversized record. Compaction occurs at 1 MiB, half the file or completion, streaming remaining content and clearing the cursor before replacement. Recording-policy rejection forces compaction; erasure discards only pending records and invalidates the cursor. Existing queue, write and session lock ordering is retained. The journal remains physically capped at 64 MiB, including any acknowledged prefix awaiting compaction.

This bounds each foreground unit of work and limits repeated sends after a failure; it does not make a checkpoint atomic with the server transaction or eliminate the final unacknowledged batch after a hard process exit. Local/server control synchronization, ephemeral durable turns, independent AgentRuntime receipts and server-wide erasure fencing remain open.

## Recording-control surface follow-up

The memory page now controls the selected brain's authoritative recording policy through the existing versioned server API. Its separate device-capture controls retain the local timed/installation scope. Effective status exposes both causes; resuming either control never silently resumes the other. A local resume while the server is paused reports the combined paused state. Remote service pages retain server controls without claiming access to local device capture. Unknown or unreadable state hides mutation controls, and stale browser reads cannot overwrite newer status. Hosts retain a pause when its file is unreadable, malformed or has an invalid expiry; only absence means no pause. An explicit local resume can clear damaged metadata without resuming the server.

Device mutations can carry an opaque revision derived from the displayed control file. The page always supplies it, and a mismatch rejects the mutation under the session-state lock. New pauses receive a fresh nonce even if their time and duration match; timed expiry uses that same lock so an old expiry read cannot remove a replacement pause. Legacy local callers may omit the revision and retain their previous unconditional semantics. Local API reads default to the home brain or an explicitly authorized selected brain; installation-wide capture and per-person conversation controls are not interchangeable.

This resolves the misleading page control and status path, not automatic cross-device synchronization of every local scope. A conversation pause is deliberately not promoted to a whole-brain pause. Status combines separately read stores, and a local mutation may succeed before its final server-state read fails. Disconnected hosts cannot immediately discover remote changes, and already-dispatched requests still need their existing server fences. Ephemeral durable turns, cross-runtime receipt normalization and delayed-write erasure fencing remain separate backend work. Qualification and retained failures belong to the accompanying report; R4/C5 remain unchanged.


## Erasure-fenced captures and durable turns

Core deletion now advances the same recording revision used by observations, notes and cognitive learning while holding the brain's transaction lock. Erasure and suppression both invalidate older captures across the brain, even when a selective request resolves to no records. This deliberately trades the continuation of unrelated pre-deletion tasks in that brain for a clear authorization boundary; other brains and the paused state are unchanged. Independent deletion intents include a revision floor, replayed with `max(current + 1, floor)` only when their receipt has not already been committed. The floor protects new deletion intents across restoration to an older policy counter. Legacy intents remain readable but cannot supply a historical floor that was never recorded.

Migration 033 adds an immutable capture revision to durable turns. New turns bind it at begin; existing turns default to zero rather than being assigned current permission. Runtime input, output, renewal, recall/review reservations and orientation retain that authority. Orientation jobs bind the turn's revision before claim so a deletion between binding and claim cannot grant new permission. Failed pre-delivery work can terminate without preventing a fresh turn. External delivery settlement remains separate: an already dispatched callback can report its factual receipt, but a recording change withholds returned content and prevents stale state publication. No proactive cancellation discards a known delivery outcome. Source/dependency checks retain their existing diagnostic precedence.

This closes the reproduced delayed-write path for versioned captures, not intentional current-policy writes from tools-only or custom clients that omit capture metadata. It does not recall external model/network operations. Ephemeral durable conversation mode, broader cross-adapter receipt normalization and disconnected-device synchronization remain separate work. Runtime-specific tests, performance scope and retained failures belong in the qualification report; R4/C5 are unchanged.

The full regression run exposed an important distinction: internal note replacement also uses suppression, but is not a new user privacy revocation. Its server-only path preserves recording permission while retaining tombstones, dependency invalidation and an independently replayable intent. That intent stores the distinction inside its integrity-protected document. Public forget requests never select this exemption. Extraction retains source-unavailable/context-change diagnostics; after explicit deletion, an old retry stops instead of refreshing authority, and a fresh turn can proceed.


## Temporary direct chat follow-up

Server recording pause now selects a temporary path in BrainRuntime and open_agent/desktop chat. The existing runtime journal reserves the conversation branch and retains content-free control markers, rather than inventing a second concurrency authority. Migration 034 marks temporary turns and constrains them to a zero input fingerprint, no source references, no draft/context/review content hashes, no delivery bodies, and no prepared memory selection. Durable mutators reject these turns. Temporary-only transitions cannot be replayed to regenerate or redeliver a message.

The current input, response, bounded recent temporary conversation, and optional answer review stay in the calling process. The service returns only bounded existing history from the exact conversation and branch; it does not receive the temporary query or dispatch orientation, semantic planning or learning. Reviewer configuration, reserved call counts and reported delivery-state enums remain visible without retaining the review assessment or any response body. An already dispatched temporary delivery retains its lease for content-free settlement after a recording change, while the returned text is withheld from subsequent context. Existing ownership, brain locking, lease fencing and scope exclusion apply to temporary and durable turns alike. Changes to recording authority or the brain dependency generation fence generation and delivery.

A process crash never reconstructs or retries temporary content. A remaining content-free reservation needs explicit cancellation after lease expiry; uncertain generation, review and delivery remain acknowledged as such. Completed temporary IDs remain deduplication markers even after recording resumes. Normal recording resumes with new message identities and never imports temporary buffers. This closes temporary direct chat under the server pause, not the independent device/conversation switches, all-host receipt normalization, restoration of old control ledgers, or external-provider transcript retention. R4/C5 remain unchanged.


## Direct chat local privacy follow-up

Direct chat previously entered temporary mode only for the brain's server pause, so the memory page's device capture control and any wish to keep one conversation off the record had no effect on `open_agent` or `desktop chat`. The chain is now complete for direct chat, reusing the temporary-turn journal rather than adding a second mechanism.

Three controls stay independent: the server switch for the whole brain, installation-scoped device capture with its existing limited-duration pause, and one conversation branch's off-record choice. Machine-local policy is bound where a machine is known, at `open_agent`/`AgentSession`. The host-independent `BrainRuntime` discovers no local files; it accepts an explicit per-turn `record=False`, which is never downgraded to a recorded turn. The session reads device capture from the host's existing pause file through the host's own parser, read-only, and keeps the conversation choice as a bodyless file keyed like the pending sidecar. Only a pause of the whole installation applies to a direct conversation. The narrower pause a host conversation asked for lists the host conversations active on the installation when it was set, without naming an adapter; a direct conversation is not among them, so it neither inherits nor ends it, and the device status API and page report that scope instead of a device-wide pause. The pause's own identity, taken from the same read, ends a session's temporary context when the device policy changed between two messages.

The service's temporary reservation accepts an explicit `off_record` request while recording is enabled. It changes no recording control and keeps authentication, the expected recording revision, the dependency generation, branch reservation, lease fencing and turn-identity idempotency. The client sends the field only when no server pause applies, so a service that predates it rejects the request before any model call; there is no recorded fallback.

A direct opening command uses the existing bounded English/Chinese grammar and is honoured before capture. Explicit `/off-record` and `/on-record` commands are never sent as messages, and `/resume` keeps its pending-turn meaning. A pending recorded turn is neither converted nor resumed while a local control excludes recording or is unreadable. Results name every cause and its scope; an unreadable control or an unreachable service is reported as unknown, with temporary handling only under a confirmed reservation, and status keeps service reachability apart from local uncertainty. These causes are separate from `DeliveryReceipt`. Local controls decide how a new message is captured; they do not fence a recorded turn whose model or delivery callback is already running, which only the server switch does.

Open after this batch: receipts and failure visibility for plugin hooks, the proxy and Hermes; synchronization of local controls with the server; a cross-store transaction between a local control and a reservation; and storing a temporary turn's cause with its control row. While recording stays enabled, dependency-generation changes from corrections, erasure or published belief relations can stop an in-flight temporary turn. R4/C5 are unchanged.


## Host recording receipts follow-up

Host completion can now report each message's recording outcome without changing what it stores. The shared turn-taking step records why nothing was taken: an unmatched or repeated callback, or the stored cause of an excluded turn. Causes are written where turns are paused, erased or discarded. Queue replay optionally collects per-record outcomes beside its existing acknowledgement. A message is `recorded` only when the service's observation receipt names exactly one accepted or duplicate event. `queued` means journal admission was confirmed while server storage is unconfirmed: a lost answer may already be committed, and another replay worker may drain the journal first. It is not a queue-membership query. Policy exclusions name their scope and control owner. Queue admission failure is a definite `failed`; callbacks this process cannot match are `unknown`. Receipts hold source references, not text, and say nothing about external chat delivery.

The list returned by `finish_turn`, extraction gating, source keys, capture revisions, deletion fences, idempotent replay, the bounded queue and replay acknowledgement are unchanged. A successful answer lacking confirmation is still acknowledged, but reported `unknown`. A receipt records what this call observed, not a subscription to later replay. `ChatMemory.record` returns it and the AstrBot plugin warns on failed or unknown messages. Plugin hooks, Hermes and the OpenAI proxy do not surface it yet. Integration with the independent AgentRuntime turn and delivery receipts, and synchronization of the independent device and conversation controls, remain open. R4/C5 are unchanged.
