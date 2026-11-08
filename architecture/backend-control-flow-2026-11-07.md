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
