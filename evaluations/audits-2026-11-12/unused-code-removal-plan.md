# Unused-code removal plan, 2026-11-12

Scope: the code that exists only for the model-driven cognition/learning pipeline, patterns, belief writers, cognitive budgets and operations, runtime mode (`BrainRuntime`, agent sessions, turns, desktop chat), the separate extraction model and the metered remote embedding provider. Base: worktree branch `worktree-agent-a09c186c4caa23bd3` at `b06a98b9` (runtime `d9c1a70`) plus the setup-prompt change in this branch. Nothing was deleted.

Method. A static import graph of `src/membrain` (152 modules, 43,891 lines) was built with Python's `ast`, counting module-level and lazy (function-level) imports with their line numbers and enclosing function. Each test file was mapped to the `membrain` modules it imports. Call sites below were then read in the source. Scripts, rerunnable on any checkout:

- `/tmp/claude-1000/-home-yichen-src-memBrain/28b99b83-ddec-55d7-af95-9d2753217c08/scratchpad/importgraph.py <src/membrain> <graph.json>`
- `/tmp/claude-1000/-home-yichen-src-memBrain/28b99b83-ddec-55d7-af95-9d2753217c08/scratchpad/groups.py` (group sizes, outside importers with line and scope, tests per group; output in `groups.txt` beside it)
- `/tmp/claude-1000/-home-yichen-src-memBrain/28b99b83-ddec-55d7-af95-9d2753217c08/scratchpad/testmap.py`, `union.py` (tests per group)

Levels: **read** = the cited code was read; **graph** = from the import graph only; **estimate** = line counts for partial edits, not yet made. Nothing here was run against a real profile or measured for latency.

## Summary

- Whole modules that serve only the frozen groups: **50 modules, 14,361 lines** (cognition pipeline 7,586, runtime mode 5,596, patterns 525, extraction 407, budgets 247). Partial edits in shared modules add about **2,600 lines** (estimate), for about **17,000 source lines** (39% of the package). `examples/` adds about 7,000 of its 7,522 lines.
- Tests: up to **141 test files, 38,754 lines, 1,687 test functions** (before parametrization) import a frozen module and are candidates for retirement; **17 further files (6,433 lines)** import one incidentally and must be edited, not retired. The 141 is an upper bound; each file must be checked (section 4 says how).
- The frozen code is not isolated. Four couplings put it on the default plugin path today: `Settings.__post_init__` imports `semantic.py` (`config.py:45`, `:75-80`); every service start imports the semantic provider, which drags in `chat_provider` and the whole runtime chain (`config.py:145-146` → `semantic_provider.py:3` → `recall_provider.py:8` → `chat_provider.py:17` → `runtime.py:14-33`); every worker tick goes through `learning.LearningEngine` (`service.py:1651-1653`); and recall with query embeddings validates its snapshot with `learning.validate_snapshot` (`service.py:300`, `vector_jobs.py:261`). Measured import cost is small (41 extra modules in 0.03 s on a warm interpreter), so this is coupling to untangle, not a speed problem.
- **Data safety rules**: never delete or edit a migration (the schema check requires the applied list to be a prefix of the shipped list, `storage.py:91-110`, and `SCHEMA_ID` hashes every migration file, `build_identity.py:41-45`); keep all tables and their row-security policies; keep erasure of rows in tables that will no longer be written; keep reading and restoring archives and installation backups written by older versions.
- **Order**: (1) patterns, (2) decoupling moves with no behaviour change, (3) extraction model, (4) metered remote embeddings, (5) cognition pipeline with budgets and belief writers, (6) runtime mode, (7) recall reads of tables that stay empty, (8) examples, evaluation scripts, docs and contract. Slices 3 to 6 each need an owner decision first (section 4).
- **Early recall-time win with no output change**: `load_patterns` runs on every recall that finds items (`service.py:826-841`), but only `cognition.prepare` uses the result (`cognition.py:1357-1358`). For the `recall` action, which is what plugin hosts call, that query and the extra event fetch after it do no work. `load_belief_relations` also loads every candidate's assertion document again on every recall before it finds that no relation exists (`belief_store.py:309-318`). Section 5.

## 1. What exists only for each group

Line counts are whole files (`wc -l`). "Partial" names code inside a shared module.

### 1.1 Cognition/learning pipeline (memBrain's own model writes claims, episodes, associations, beliefs)

Whole modules (23, 7,586 lines): `semantic.py` 1,771; `learning_phase_monitor.py` 717; `learning_progress.py` 587; `consolidation.py` 573; `learning_integration.py` 573; `neighborhood.py` 445; `learning_windows.py` 334; `episode_semantics.py` 280; `learning_allocations.py` 274; `consolidation_planning.py` 239; `learning_packages.py` 221; `history_attention.py` 219; `local_semantics.py` 218; `history_semantics.py` 196; `learning_funding.py` 183; `learning_recovery.py` 171; `cognition_config.py` 132; `citation_coverage.py` 127; `belief_capabilities.py` 114; `desktop_cognition.py` 79; `verification_sources.py` 56; `desktop_learning.py` 55; `semantic_provider.py` 22.

Partial:
- `learning.py` (825): everything except `_literal` (`:730-774`), the extract/rebuild/embed branches of `_execute` (`:776-797`), the non-semantic part of `work_once` (`:799-825`) and the source-snapshot core of `validate_snapshot`/`_validated_snapshot` (`:139-189`). About 700 lines go.
- `jobs.py` (601): learning summaries and monitors (`sanitize_learning_summary`, `summarize_learning`, `:84-200`), the learning constants (`:11-56`), `retry_learning`, `cognitive_usage`, `cognitive_budget`, `configure_cognitive_budget`, `learning_progress` (`:309-341`), the phase metadata in `_public` (`:267-304`). About 190 lines go. `reserve_operation`/`get_operation`/`settle_operation` (`:450-558`) also serve metered embeddings (1.7).
- `service.py`: `_append_event` learning-window enqueue (`:531-546`); `orient_turn` (`:110-114`) belongs with runtime mode.
- `config.py`: cognition settings and validation (`:23-31`, `:45-47`, `:52-67`, `:75-80`, `:99-107`, `:123-130`, `:145-146`, `:164-172`), about 45 lines.
- `local_profile.py`: cognition in `settings()` (`:261-272`) and `configure_cognition` (`:492-507`). The `_cognition` parser must stay (section 3).
- `desktop_cli.py`: the frozen `--base-url/--model/--api-key-env/--thinking/--cognition-preset` options and their handling (`:18-30`, `:59-67`, `:70-90`, `:105-106`; line numbers after this branch's setup change), the budget, `cognition-policy`, `learning-status`, `retry-learning` registration and dispatch (`:32`, `:34-35`, `:40-42`, `:162-177`).
- `api.py`: `runtime/learning-progress` (`:902-908`), `retry-learning` (`:931-942`), learning progress in `runtime/status` (`:872-882`).
- `turns.py:263` (learning progress in `TurnStore.status`), `desktop.py:173-175` (cognition fields in the configuration fingerprint), `desktop_backup.py:45-60`, `desktop_restore.py:61-73` (section 3: keep the files, drop only validation through deleted modules).

Tables written only by this group: `memory_episodes`, `memory_episode_members`, `memory_associations` (migration 007), `memory_belief_relations` (009, see 1.3), `memory_pattern_views` (008, see 1.2), derived `memory_assertions` rows with `recall_summary`/`retention_priority`, `memory_jobs` rows of kind `consolidate` and `orient`, and the allocation, reconsideration, window and funding columns (019-022, 032 on `memory_jobs`; 020 on `memory_brains`).

Tests (graph): 97 files import a member. Seven only touch it in passing and must be edited, not retired: `test_affect.py:482-486`, `test_mood.py:478-482`, `test_persona_growth.py:707-711`, `test_relationship.py:617-623` (each monkeypatches `learning_windows.enqueue_window` to assert companion records start no learning), `test_sentence_segmentation.py:166` (`semantic._check_claim_sources`), `test_desktop_connection.py:224` (cognition policy), `test_desktop_upgrade.py:15`, `:216`. The other 90 files (about 24,300 lines) are retirement candidates, including the 36 `test_learning*`/`test_lifecycle_learning*` files, `test_semantic*`, `test_consolidation*`, `test_episode_*` (except where they test archives), `test_history_*`, `test_cognition_policy*`, `test_cognition_preset.py`, `test_cognition_transport.py`, `test_cognitive_configuration.py`. TypeScript SDK: `learning.test.ts`, `funding.test.ts` and `learningProgress`/`retryLearning` in `sdk/typescript/index.ts:714-726`.

### 1.2 Patterns

Whole modules: `patterns.py` 304, `pattern_store.py` 221 (525 lines). Partial: `cognition._pattern_context_units` (`cognition.py:1038-1133`, about 95 lines) and its call in `prepare` (`:1357-1358`). Table: `memory_pattern_views` (008), written by `pattern_store.refresh_patterns` from `consolidation.publish_semantic` (`consolidation.py:561-563`) and by `rebuild_restored_patterns` after an archive restore (`service.py:1620-1623`). Tests: `test_patterns.py` 471, `test_pattern_store.py` 250, `test_pattern_context.py` 297 (1,018 lines, 57 functions).

### 1.3 Belief writers

Writers in `belief_store.py` (440): `_package`, `_validate_package`, `_insert`, `publish_links` (`:146-290`, about 145 lines) and `assertion_fingerprint` (`:48-62`, used by `learning_packages.py:5` and `history_semantics.py:62`). Called only from `consolidation.py:564-566`. The readers stay as long as recall honours existing relations: `load_belief_relations` (`:302-399`), `relation_ref/relation_versions/relation_sources/validate_relation` (`:64-133`), `restore_beliefs` (`:400-440`), and all of `belief_resolution.py` (282). `invalidate_beliefs` (`:292-300`) must stay for erasure (section 3). Table: `memory_belief_relations` (009). Tests that only test writing: `test_belief_store.py` (417, writes through `neighborhood`/`semantic`); `test_belief_recall.py` and `test_context_views.py` test the readers and stay.

### 1.4 Cognitive budgets and operations

Whole modules (247 lines): `cognitive_budget.py` 112, `cognitive_usage.py` 53, `provider_usage.py` 27, `desktop_budget.py` 55. Partial: `jobs.reserve_operation/get_operation/settle_operation` (`jobs.py:450-558`, about 110 lines), `api.py:885-900` (cognitive usage and budget endpoints), `RuntimeBudgetChange`/`CognitiveBudgetPolicy` models (`api.py:178-189`). Tables: `memory_cognitive_operations`, `memory_cognitive_budgets` (006), `memory_cognitive_budget_changes` (017). **Not separable from metered embeddings**: `vector_jobs._call` reserves every metered embedding call through `jobs.reserve_operation` (`vector_jobs.py:111-146`), which checks `cognitive_budget.reservation_policy`/`window_usage` (`jobs.py:453-454`). Tests: `test_cognitive_budget.py` 244, `test_desktop_budget.py` 93, `test_semantic_call_usage.py` 96, `test_cognitive_usage.py` 99; TypeScript `budget.test.ts`, `cognitiveUsage`/`cognitiveBudget` in `sdk/typescript/index.ts:700-712`.

### 1.5 Runtime mode

Whole modules (20, 5,596 lines): `turns.py` 1,075; `runtime.py` 834; `agent_session.py` 617; `desktop_chat.py` 406; `feedback.py` 387; `recall_control.py` 373; `chat_provider.py` 333; `answer_review.py` 267; `runtime_client.py` 235; `chat_config.py` 181; `ephemeral_runtime.py` 178; `prepared_selection.py` 132; `delivery_receipts.py` 125; `desktop_chat_monitor.py` 116; `ephemeral_turns.py` 116; `desktop_turns.py` 67; `orientation.py` 51; `recall_provider.py` 49; `turn_scopes.py` 39; `answer_review_provider.py` 15. `answer_review_provider.py` has no importer in `src` at all (graph).

Partial:
- `api.py`: runtime models (`:140-155`, `:162-275` except `RecordingControl`), `runtime_metadata` (`:277-304`), `turn_store` (`:417-427`), `runtime/status` (`:870-883`), `runtime/scope` (`:910-920`), all `runtime/turns` and `ephemeral-*` endpoints (`:944-1122`). About 390 lines.
- `service.py`: `orient_turn` (`:110-114`), `observe_feedback` call (`:586-590`), `_feedback` (`:1098-1159`), `_commit` with `_proposal` and `_grounded_working_value` (`:1060-1080`, `:1160-1224`), the turn and orientation parts of `_prepare` (`:885-934`), `_context_observations` (`:700-739`). About 230 lines, but `commit` and `feedback` are public actions of the contract (decision in section 4, slice 6).
- `mcp_server.py:291-322`: the `memory_prepare` and `memory_checkpoint` MCP tools, which the plugin MCP server also exposes (decision in slice 7).
- `desktop_cli.py`: chat, configure-chat and turn-status registration and dispatch (`:33`, `:37`, `:39`, `:44`, `:135-153`, `:178-181`).
- `candidates.py:456-461`: `memory_access_state` read (section 5).
- `examples/`: `autonomous.py` and most evaluation drivers use `BrainRuntime`, `runtime_client`, `chat_provider` (10 files import `runtime`).

Tables: `memory_runtime_turns`, `memory_runtime_turn_transitions` (004, altered by 005, 010-013, 015, 033, 034), `memory_feedback_contributions` (014), `memory_access_state` (007, written only by `feedback.recompute_access`, `feedback.py:284-315`), `memory_working_states` (001, written by `_commit` and `_checkpoint`). `memory_event_dependencies` (004) is **not** runtime-only: the plugin path writes it for host replies (`service.py:577-586`), notes and companion records; keep it.

Tests (graph): 71 files import a member. Keep and edit: `test_erasure_recording_fence.py`, `test_recovery_erasure.py`, `test_recovery_quarantine.py`, `test_turn_recording_migration.py` (they prove erasure, recovery and migration of turn rows, which must keep working on old data), `test_recording_controls.py` (agent-session parts only), `test_outbound.py` (chat-provider part). The rest (about 60 files, 15,000 lines) are retirement candidates. TypeScript: `runtime-scope.test.ts` and the runtime methods in `index.ts`.

### 1.6 Separate extraction model

Whole module: `extraction.py` 407. Call sites: `adapters/chatbot.py:66`, `:74`, `:144-157`, `:182-192` (the `extractor` option of `ChatMemory`); `proxy.py:335-340`; `host.py:344-348` (`note_extraction` in installation status); `desktop.py:595-598` (memory status); `diagnostics.py:37-44`; `web/memory.js:1085-1100` and the `extraction-detail` element; `integrations/astrbot/astrbot_plugin_membrain/main.py:39-47` and `_conf_schema.json:40-57`. Evaluation harnesses that use it: `evaluations/c5-harness.py`, `evaluations/v1-2026-10-29-phase-b-harness.py`, `evaluations/locomo/consolidation_experiment.py`. Tests: `test_extraction.py` 205, `test_extraction_delivery.py` 214, `test_extraction_source_fences.py` 249 (retire); `test_affect.py:17`, `:181`, `test_recall_budget_and_notes.py:10`, `:162-178`, `test_evaluation_billing_guard.py:285-295`, `test_c5_harness_hardening.py` (edit). No table of its own; its notes are ordinary notes.

### 1.7 Metered remote embedding provider

Partial only: `embeddings.ChatCompletionsEmbeddingProvider` (`embeddings.py:90-209`, about 120 lines; the dataclasses above it serve the local model too); in `vector_jobs.py` the metered branch of `_call` (`:111-146`), `embed_memory` (`:148-166`, the job-at-a-time path taken when the provider is metered, `learning.py:782-785`), the metered branch of `query_embedding` (`:265-320`), the metered condition in `_embed_documents` (`:61`); `config.py` embedding URL/key/model/version/dimensions settings (`:32-36`, `:53`, `:68-73`, `:89-91`, `:108-112`, `:177-181`); `jobs.reserve_operation` and the budget (1.4). The local model (`local_embeddings.py`, `metered = False`, `:121`) takes `embed_local_batch` and must stay. Tests: `test_embeddings.py`, `test_vector_jobs.py`, `test_cognitive_configuration.py`; about 8 other test files build fake embedding providers without `metered = False` and therefore exercise the metered path (`test_candidates.py`, `test_recall_service_executor.py`, `test_recall_service_transactions.py`, `test_recall_windows.py`, `test_semantic_shared_reads.py`, `test_desktop_supervisor.py`, `test_model_activation.py`, `test_cognitive_configuration.py`); they need `metered = False` added. Check with `grep -l embedding_provider tests/*.py | xargs grep -L metered`.

## 2. What the default plugin path calls into each group

Default path: hooks (`plugin.py`, `host.py`), the plugin MCP server (`plugin_cli` → `mcp_server.create_server(directory=...)`), the HTTP API they use (`v1/actions` `recall` and `observe`, timeline, following, notes, message cues, recording, status, memory map), the service, the worker and the memory page.

### 2.1 Cognition pipeline

| Call site | What it does on the plugin path |
| --- | --- |
| `config.py:45` → `:75-80` | `Settings.__post_init__` calls `semantic_policy()`, which imports `semantic.SemanticPolicy`. Every `Settings` (API, worker, desktop status) imports `semantic.py` |
| `desktop.py:173` | The configuration fingerprint includes `asdict(settings.semantic_policy())` and the cognition fields |
| `config.py:145-146` | `configured_service` imports `SemanticProcessor` and `ChatCompletionsSemanticProvider` unconditionally, which loads `recall_provider` → `chat_provider` → `runtime` and its imports |
| `local_profile.py:261` | `DesktopProfile.settings()` imports `cognition_config` (which imports `chat_provider`, `cognition_config.py:9`, and `semantic`, `:12`) |
| `service.py:1651-1653` | Every worker tick calls `learning.LearningEngine(self).work_once`; `learning.py` imports `semantic`, `consolidation_planning`, `learning_allocations/packages/recovery/windows`, `local_semantics`, `turns` at module level (`:7-27`). Semantic branches are gated on `semantic_processor` (`:801-810`) |
| `service.py:300`, `vector_jobs.py:261` | Recall with a query embedding (the local model) validates the vector's snapshot with `learning.validate_snapshot` |
| `service.py:701` | `_context_observations` imports `learning.validate_snapshot` (returns before any query when working state has no orientation items) |
| `service.py:907` | `_prepare` uses `learning.orientation_result` when a runtime turn has an orientation job (MCP `memory_prepare` reaches `_prepare`) |
| `service.py:542-546` | `_append_event` enqueues a learning window only when a semantic processor exists |
| `archive_views.py:7` | Module-level import of `episode_semantics.ORGANIZATION_STATEMENT_SCHEMA`; `archive_views` is imported by the memory page's structure map (`structure_map.py:4`) and by archive export/restore, so the memory page loads `episode_semantics` → `belief_capabilities` → `consolidation_planning`, `history_semantics` |
| `jobs.py:87`, `:277-290` | `JobStore._public` and `sanitize_learning_summary` use `learning_phase_monitor`, `learning_windows` (runtime/jobs endpoints, not called by plugins) |
| `api.py:872`, `:904`, `:931-942`; `turns.py:263` | Learning progress and retry endpoints (not called by plugins) |
| `service.py:1828` | Dashboard label `extraction: verified_semantic_proposals` vs `deterministic_source_capture` (memory page dashboard) |

### 2.2 Patterns

`service.py:403-406` (`_invalidate` on every edit/delete), `service.py:826-841` (`load_patterns` on every recall with items; output unused by `recall`), `service.py:1620-1623` (archive restore), `erasure.py:53-56` (erasure with content removal), `consolidation.py:436`, `:561-563`, `cognition.py:1039`, `:1357-1358` (prepare only). The memory page reads the table with plain SQL (`structure_map.py:73`), not through the modules.

### 2.3 Belief writers and readers

Writers: only `consolidation.py:564-566`. Readers on the plugin path: `service.py:744-748` (`load_belief_relations` and `merge_belief_candidates` on every recall), `cognition.py:911-912` (`belief_resolution.resolve`, `connected_item_groups` on every recall), `cognition.py:1150`, `:1441` (prepare), `candidates.py:85` (`relation_versions` in endpoint scoring), `archive_views.py:79`, `:145`, `:238`, `:294`, `:410` (archive identities, validation, export, sanitizing, restore), `structure_map.py:204` (memory page). Erasure: `service.py:401-408`, `:1293`, `erasure.py:53-56`.

### 2.4 Budgets and operations

`jobs.py:317-334` (API only), `jobs.py:453-454` (every metered embedding reservation), `learning_integration.py:8`, `semantic.py:1273`. Not reached by a plugin host with the local model.

### 2.5 Runtime mode

| Call site | Effect on the plugin path |
| --- | --- |
| `service.py:587-590` | `observe_feedback` runs for every received user message; it reads `memory_runtime_turns` (`feedback.py:130-152`) and returns without effect for plugin hosts |
| `service.py:427-428` | `invalidate_contributions` on every edit/delete (erasure; keep the SQL) |
| `candidates.py:456-461` | `memory_access_state` read on every recall; the table is never written for plugin hosts |
| `service.py:761`, `:783` | `_working` read and `_context_observations` on every recall; empty for plugin hosts |
| `service.py:874-906` | `_prepare` reads `memory_runtime_turns` by `turn_id` (MCP `memory_prepare`) |
| `mcp_server.py:291-322` | `memory_prepare` and `memory_checkpoint` tools are registered on the plugin MCP server |
| `jobs.py:9`, `cognitive_budget.py:2`, `delivery_receipts.py:5`, `history_semantics.py:10`, `learning*.py`, `ephemeral_turns.py:2` | Import the identifier/integer/hash validators `_identifier`, `_integer`, `_hash`, `_refs` from `turns.py:33-66`; `jobs.py` is on the worker path, so `turns.py` loads with every worker |
| `chat_provider.py:17` | `ModelRequest` from `runtime`; reached from the cognition provider chain (2.1) |
| `cognition_config.py:9`, `desktop_cognition.py:5` | `ReasoningEffort` imported through `chat_provider` although it lives in `reasoning.py` |
| `desktop_backup.py:45`, `:64`; `desktop_restore.py:62` | Installation backup copies `chat.json` and the `sessions/` sidecars and validates them with `chat_config` and `agent_session` |
| `recovery.py:23-57`, `recording_control.py:36-50` | Recovery quarantine and the recording pause update `memory_runtime_turns` rows with plain SQL. Keep (section 3) |
| `desktop.py:566-575` → `local_recording.py` | Device capture for the memory page; `local_recording` is shared with `agent_session` and stays |

### 2.6 Extraction model

`host.py:344-348` and `desktop.py:595-598` call `extraction_status` for every plugin status read and memory-page status (it reads a local status file; returns `None` without extraction). Everything else is the proxy and chatbot adapter (1.6).

### 2.7 Metered embeddings

`service.py:257-259` calls `vector_jobs.query_embedding` on every action; it branches to the local path when the provider is unmetered (`vector_jobs.py:267`). `learning.py:813-825` takes `embed_local_batch` for the local model. No plugin call reaches the metered code unless `MEMORY_EMBEDDING_BASE_URL` is set, which desktop profiles do not expose (`docs/reference.md`, semantic embeddings paragraph).

## 3. What must stay for data safety

1. **Migrations 001-036 stay byte-for-byte.** `schema_status` rejects a database whose applied names are not a prefix of the shipped names (`storage.py:95-97`), and `SCHEMA_ID` is a digest of all migration files (`build_identity.py:41-45`). Deleting or editing one turns every existing installation into `database_schema_incompatible` or `restart_required`. Dropping tables, if ever wanted, needs a new migration 037+ after at least one release in which nothing reads them, and it makes older runtimes refuse the database; this plan does not recommend it.
2. **Tables and row-security policies stay.** Every frozen table has a `principal_isolation` policy created in its migration (004, 006, 007, 008, 009, 014, 017). Leaving the tables in place keeps the policies; no code change touches them.
3. **Erasure of rows that will no longer be written stays.** Old installations, configured profiles and restored archives can hold rows. Keep, as plain SQL in one small module (proposed `legacy_erasure.py`, about 70 lines): `pattern_store.invalidate_patterns` (`pattern_store.py:16-26`, including `deleted=True` from `erasure.py:55`), `belief_store.invalidate_beliefs` (`belief_store.py:292-300`), `feedback.invalidate_contributions` with `recompute_access` (`feedback.py:284-349`), and the existing statements in `service._invalidate` (`service.py:410-426`: superseded jobs, episodes, associations, embeddings) and `erasure.apply_erasure` (`erasure.py:57-87`: working states, traces, stored archives). The recovery quarantine (`recovery.py:23-63`) and the recording pause (`recording_control.py:36-50`) must keep updating `memory_runtime_turns`, `memory_runtime_turn_transitions`, `memory_cognitive_operations` and `memory_jobs`.
4. **Reading and restoring archives written by older versions.** Archives carry `cognitive_views` (episodes, members, associations) and `belief_relations` (`service.py:1454`, `:1465-1466`). Keep `archive_views.py` whole, the archive parts of `belief_store.py` (`validate_relation`, `relation_*`, `restore_beliefs`), and `ORGANIZATION_STATEMENT_SCHEMA` (move it out of `episode_semantics.py` first). Keep the matching definitions in `architecture/memory-contract.schema.json`. `_sanitize_archive` (`service.py:1341`), which rewrites stored archives on erasure, must keep handling those views. Pattern views are a cache that archives omit, so `rebuild_restored_patterns` can go; the restore job detail then loses its `patterns_rebuilt` count (`service.py:1623`, `:1644`).
5. **Installation backups written by older versions.** `desktop_backup._configuration` and `_sessions` back up `profile.json` with its `cognition` key, `chat.json`, `cognition-policy.json` and `sessions/` (`desktop_backup.py:44-75`); `desktop_restore._restore_configuration` writes them back (`desktop_restore.py:61-73`). After removal, restore must still accept these entries (copy them as opaque private files, or drop them with a recorded notice), and `local_profile._cognition` must keep parsing a `profile.json` that contains `cognition`, or older profiles stop loading.
6. **Leftover job rows.** Queued `consolidate`/`orient` jobs will never be claimed once the kinds are gone (`learning.py:799-812`), but `memory_status` (shown by plugin status and the memory page) and `dashboard` count them as pending (`service.py:1781`, `:1821-1824`). Cancel them once with a recorded reason (code, not a migration), or filter by kind.
7. **Configured profiles.** The desktop fingerprint (`desktop.py:173-175`) changes when the cognition fields go, so an upgraded configured profile reports `restart_required` once; `desktop setup`/`start` already restart it. Decide whether `MEMORY_COGNITION_*` in an environment deployment is then ignored with a log line or refused at startup.

## 4. Removal slices

Each slice is meant to leave the full source suite passing on its own, with its own tests retired or edited in the same change. After each slice: `ruff check src tests`, the focused tests of the slice on a task-owned database, then the full suite; update the launcher pins in a second commit (`test_installation_pin.py` fails by design until then). Run `tests/test_longitudinal_*.py` whenever `examples/` changes (they import it).

Owner decisions that gate slices: **D1** keep or stop background learning on profiles that configured a cognition model (audit question 2); **D2** remove runtime mode, desktop chat and the Python session SDK (audit question 1; the 2026-11-12 decision says frozen now, removed later); **D3** remove the proxy/AstrBot extraction model (audit question 3); **D4** drop the metered embedding provider for environment deployments; **D5** retire the public `prepare`, `commit`, `feedback` and `checkpoint` actions and the MCP `memory_prepare`/`memory_checkpoint` tools, or keep them.

### Slice 1: patterns (safest; no owner decision beyond the audit's "Remove")

- Delete: `src/membrain/patterns.py` (304), `src/membrain/pattern_store.py` (221).
- Edit: `service.py:826-841` (delete the `load_patterns` block); `service.py:403-406` and `erasure.py:53-56` (call the pattern-view erasure SQL from `legacy_erasure.py`); `service.py:1620-1623` (no rebuild after restore); `cognition.py:1038-1133`, `:1357-1358` (no pattern grouping in `prepare`; check that `_pattern_context_units(rows, [], ...)` reduces to the ordinary units and inline that); `consolidation.py:436`, `:561-563`.
- Tests retired: `test_patterns.py`, `test_pattern_store.py`, `test_pattern_context.py` (1,018 lines, 57 functions). Edit: `test_learning_monitoring.py` (5 references), `test_learning_progress.py` (1), `test_structure_map.py` (1); check with `grep -n "pattern_views\|patterns_rebuilt\|memory_pattern_views" tests/*.py`.
- Removed: about 640 source lines, 1,018 test lines.
- Risk: low. Recall output does not change. `prepare` output changes only on brains that already hold pattern views (configured cognition, or a restored archive whose episodes were rebuilt into views). Configured profiles stop producing new views. The memory page still shows old views through plain SQL until slice 7 decides.

### Slice 2: decoupling moves (no behaviour change, no owner decision)

Moves that make slices 3-6 leaf deletions. Nothing is deleted except dead indirection.

- `turns.py:33-66` `_identifier`, `_integer`, `_hash`, `_refs` → `helpers.py`; update `jobs.py:9`, `learning.py:27`, `cognitive_budget.py:2`, `delivery_receipts.py:5`, `history_semantics.py:10`, `learning_allocations.py:10`, `learning_funding.py:3`, `learning_recovery.py:9`, `learning_windows.py:20`, `ephemeral_turns.py:2`.
- `semantic.SemanticPolicy` → `config.py` (or a 30-line `cognition_policy.py`); update `config.py:75-80`, `cognition_config.py:12`, `desktop.py:173`. `Settings` then no longer imports `semantic.py`.
- `config.py:145-146`: import the semantic processor and provider only inside `if settings.cognition_base_url is not None:`. A default service start then no longer loads `semantic_provider` → `recall_provider` → `chat_provider` → `runtime`.
- `cognition_config.py:9`, `desktop_cognition.py:5`: import `ReasoningEffort` from `reasoning.py`.
- `episode_semantics.ORGANIZATION_STATEMENT_SCHEMA` → `archive_views.py` (keep the name exported from `episode_semantics` for now).
- `learning.validate_snapshot`: move the source-snapshot core (`learning.py:167-189`, scope and generation checks, source content and supersession) to `vector_jobs.py` or a new `snapshots.py`; `service.py:300`, `vector_jobs.py:261` use it; the memory/episode/belief snapshot checks stay in `learning.py`.
- `learning.py:730-825`: move `_literal`, the extract/rebuild/embed part of `_execute` and the non-semantic part of `work_once` to a new `capture_jobs.py` (about 110 lines); `service.work_once` (`service.py:1651-1653`) calls it, and calls `LearningEngine` only when `semantic_processor` is set.
- Create `legacy_erasure.py` with the pattern, belief and feedback-contribution erasure SQL (section 3.3); `service._invalidate`, `service._correct` (`:1293`), `erasure.apply_erasure` call it.
- Tests: none retired. Expect edits where tests monkeypatch old paths: `grep -n "monkeypatch.setattr(.*\(learning\|turns\|semantic\)" tests/*.py`.
- Removed: about 0 net lines (moves).
- Risk: low to medium. Pure moves, but many monkeypatch targets; the worker split touches the extract job that every message goes through, so run `test_desktop_supervisor.py`, `test_vector_jobs.py`, `test_local_query_concurrency.py`, `test_message_cues.py`, the erasure and archive tests, and the full suite.

### Slice 3: extraction model (needs D3)

- Delete: `src/membrain/extraction.py` (407).
- Edit: `adapters/chatbot.py` (remove the `extractor` option, or accept and ignore it for one release because the AstrBot plugin passes it), `proxy.py:335-340`, `host.py:344-348`, `desktop.py:595-598`, `diagnostics.py:37-44`, `web/memory.js:1085-1100` and the `extraction-detail` element in `web/memory.html` with its `i18n.js` strings, `integrations/astrbot/astrbot_plugin_membrain/main.py:39-47`, `_conf_schema.json:40-57`, the proxy and AstrBot READMEs (both languages), `docs/reference.md` (background extraction paragraphs).
- Evaluation scripts `evaluations/c5-harness.py`, `evaluations/v1-2026-10-29-phase-b-harness.py`, `evaluations/locomo/consolidation_experiment.py` import `membrain.extraction`: keep them as historical evidence and mark them as needing a pre-removal runtime, or remove their extraction arm. Do not edit their recorded results.
- Tests retired: `test_extraction.py`, `test_extraction_delivery.py`, `test_extraction_source_fences.py` (668 lines, 29 functions). Edit: `test_affect.py` (extraction-feeling test at `:181`), `test_recall_budget_and_notes.py:162-178`, `test_evaluation_billing_guard.py:285-295`, `test_c5_harness_hardening.py`.
- Removed: about 520 source and web lines, 668 test lines.
- Risk: medium in product terms, low in code. Hosts without tool calls (the proxy, AstrBot with a model that does not call tools) lose notes. Extraction is the measured `E` arm (78.4% against 76.4% on LoCoMo; R4 attempt 4 passed with it); keep those reports.

### Slice 4: metered remote embeddings (needs D4)

- Edit: `embeddings.py:90-209` (delete `ChatCompletionsEmbeddingProvider`), `vector_jobs.py:61`, `:111-166`, `:265-320` (metered branches and `embed_memory`), `learning.py`/`capture_jobs.py` (`embed` jobs only for the local batch), `config.py` embedding URL/key/model/version/dimensions settings, `docs/reference.md` (semantic embeddings paragraph), `jobs.py:450-558` (operation reservations; only if slice 5 lands in the same change, because the semantic processor also reserves through them).
- Tests: edit fakes to `metered = False` (1.7); retire the metered cases in `test_embeddings.py`, `test_vector_jobs.py`, `test_cognitive_configuration.py`.
- Removed: about 300 source lines.
- Risk: medium. Ranking with the local model must not change: rerun the model-free LoCoMo evidence-recall harness (`evaluations/locomo/`, held-out split) before and after.

### Slice 5: cognition pipeline, cognitive budgets and belief writers (needs D1; after slices 1, 2, 4)

- Delete: the 23 modules of 1.1 (7,586), the 4 of 1.4 (247), the writers in `belief_store.py` (about 160), the remaining semantic code in `learning.py` (about 700), the learning parts of `jobs.py` (about 190, plus the 110 of operations if slice 4 left them).
- Edit: `config.py`, `local_profile.py` (keep `_cognition` parsing), `desktop_cli.py`, `desktop.py:173-175`, `desktop_backup.py:45-60`, `desktop_restore.py:61-73`, `service.py:531-546`, `api.py:870-942` learning and budget endpoints, `turns.py:263` (or slice 6), `service.py:1828`, the job cleanup of section 3.6; `README.md` and `README.zh-CN.md` ("Local operation" lists `membrain desktop learning-status`); `docs/reference.md` cognition sections; `architecture/cognition-policy.md`, `cognitive-budgets.md`, `learning-monitoring.md`; TypeScript SDK learning, funding and budget methods and tests.
- Examples retired: `examples/evaluate_deepseek.py`, `lifecycle_learning.py`, `longitudinal_learning.py`, `evaluate_conversation.py`, `evaluate_episode_scope_repair.py`, `evaluate_temporal_repair.py` and others that import `semantic` or `learning` (8 and 4 files; `grep -lE "membrain(\.| import ).*(semantic|learning)" examples/*.py`), with their `test_*_evaluation.py` tests.
- Tests: retire about 90 files (about 24,300 lines; list from `groups.py`), edit the 7 of 1.1.
- Removed: about 9,100 source lines, about 24,000 test lines, several thousand example lines.
- Risk: high. Largest change; touches configuration, profile loading, backup/restore compatibility and the API. Mitigate with: an old `profile.json` with `cognition` still loads; an old installation backup with `cognition-policy.json` restores; an old archive with `cognitive_views` and `belief_relations` restores and is then erasable; a database holding `consolidate` jobs, episodes and belief relations still serves recall and erasure.

### Slice 6: runtime mode (needs D2, and D5 for the public actions; after slice 5, or after slice 2 if runtime goes first)

- Delete: the 20 modules of 1.5 (5,596).
- Edit: `api.py` (about 390 lines), `service.py` (`orient_turn`, `observe_feedback` call, `_context_observations`, the turn parts of `_prepare`; `_feedback`, `_commit` only with D5), `desktop_cli.py` chat/turn-status commands, `desktop_backup.py`/`desktop_restore.py` (keep `chat.json` and `sessions/` as opaque entries of old backups), `candidates.py:456-461` (no `memory_access_state` read once nothing writes it; changes ranking only for brains with old feedback rows), `client.py` runtime helpers, TypeScript runtime methods; `README.md`/`README.zh-CN.md` frozen chat and Python sections; `docs/reference.md` automatic integration; `architecture/integration-troubleshooting.md`. Keep `recovery.py` and `recording_control.py` SQL on the turn tables.
- Examples retired: `examples/autonomous.py` and the remaining runtime-driven evaluation drivers (`grep -lE "membrain(\.| import ).*(runtime|chat_provider|runtime_client|answer_review)" examples/*.py`).
- Tests: retire about 60 files (about 15,000 lines); keep and edit the 6 listed in 1.5.
- Removed: about 6,300 source lines, about 15,000 test lines.
- Risk: high. It removes the public `runtime/turns` HTTP API, `open_agent`, `desktop chat` and part of the TypeScript client. The project is pre-release and unpublished, so no external user is known, but this cannot be checked from the repository.

### Slice 7: recall reads of tables that stay empty (after slices 5 and 6; needs a decision on old data)

Association expansion (`candidates.py:398-411`), working-state read and context observations (`service.py:761`, `:783`, `:700-739`), MCP `memory_prepare`/`memory_checkpoint` (`mcp_server.py:291-322`, D5), the memory page's derived layers (`structure_map.py:67-204`). Keep the episode expansion (`candidates.py:412-431`): the audit's next steps re-drive episodes from the host AI into the same tables. Removing these reads stops existing derived data (from configured profiles or restored archives) from influencing recall; that is the decision. About 150 source lines.

### Slice 8: documentation, contract and schema tidy

`architecture/autonomous-runtime.contract.json` (statements listed in the task report), `docs/reference.md` reference material for removed parts, the contract schema definitions that nothing reads and no archive needs (check each against `_validate_archive` before removing), `CHANGELOG.md`.

### Totals

| Slice | Source lines removed (estimate) | Test lines retired (upper bound) | Owner decision |
| --- | --- | --- | --- |
| 1 Patterns | 640 | 1,018 | none |
| 2 Decoupling | about 0 | 0 | none |
| 3 Extraction | 520 | 668 | D3 |
| 4 Metered embeddings | 300 | a few hundred | D4 |
| 5 Cognition, budgets, belief writers | 9,100 | 24,000 | D1 |
| 6 Runtime mode | 6,300 | 15,000 | D2, D5 |
| 7 Empty-table reads | 150 | small | old-data decision |
| Total | about 17,000 | up to 38,700 (141 files) | |

Examples: about 7,000 of 7,522 lines, split between slices 5 and 6.

## 5. Recall-time cost removable early

Per `recall` request on a plugin brain (read; not measured):

| Query or work | Call site | Tables | Plugin brains | Early action |
| --- | --- | --- | --- | --- |
| Pattern views and an extra event fetch | `service.py:826-841` → `pattern_store.py:167-200` | `memory_pattern_views`, `memory_events` | Empty | **Skip for `recall` now.** Only `cognition.prepare` reads `state["pattern_views"]` (`cognition.py:1357-1358`) and the extended `working_event_metadata` (`cognition.py:1162`, `:1170`). No recall output changes on any brain |
| Belief relations: reload of every candidate assertion, endpoint probe, parent walk | `service.py:745-748` → `belief_store.py:309-318`, `:320-345` | `memory_assertions`, `memory_belief_relations` | Empty | Run the endpoint probe (`:313-318`) first and return the empty result when nothing is linked, before `_load_memories` (`:311`). Check that the returned `memories`/`incomplete_versions` do not change for unlinked seeds (a retracted or out-of-scope seed currently marks the read incomplete) |
| Belief resolution on items | `cognition.py:911-912`, `:923` | none (Python) | No relations | Falls out of the row above |
| Association expansion | `candidates.py:398-411` | `memory_associations` ⋈ `memory_assertions` | Empty | Keep until slice 7, or skip after one cheap `EXISTS` per brain |
| Episode expansion | `candidates.py:412-431` | `memory_episode_members`, `memory_episodes` | Empty | Keep: host-written episodes are the planned next mechanism |
| Access-state lookup | `candidates.py:456-461` | `memory_access_state` | Never written | Remove with slice 6; output is unchanged where no rows exist (`rank_weight` already receives `None`) |
| Working state | `service.py:761` | `memory_working_states` | Empty, or the default state saved by MCP `memory_checkpoint` | Slice 7 |
| Context observations | `service.py:783` → `:700-739` | `memory_jobs` (only if working items exist) | No query | Slice 6 |

Per received user message (write path): `observe_feedback` (`service.py:587-590` → `feedback.py:351-387`, `_latest_delivery` at `:130-152`) queries `memory_runtime_turns` and never applies for plugin hosts; remove with slice 6, or skip when the brain has no runtime turn.

Per edit or deletion: `service._invalidate` runs five updates on derived tables (`service.py:401-428`). Keep them; they protect old rows.

How to check that the tables are empty for plugin users: on a copy of a plugin profile's database, with `app.tenant_id` and `app.principal_id` set (forced row security), `SELECT count(*)` from `memory_pattern_views`, `memory_belief_relations`, `memory_associations`, `memory_episodes`, `memory_access_state`, `memory_feedback_contributions`, `memory_working_states`, `memory_runtime_turns`, and `memory_jobs` grouped by `kind`. How to check the cost: time `recall` in the model-free LoCoMo evidence-recall harness with each skip, or `EXPLAIN (ANALYZE, BUFFERS)` the statements above on a large synthetic brain. No such measurement exists yet.

## Not determined

- Whether any real installation has a cognition model configured, uses desktop chat, or has derived rows (the checks above answer it for a given profile).
- Whether any host calls the MCP `memory_prepare` or `memory_checkpoint` tools; the plugin's own instructions do not ask for them, but transcripts were not checked.
- The exact test retirement list: the 141-file figure counts every test that imports a frozen module. Some of those test shared behaviour through a frozen import and must be rewritten, not deleted. For each file, check whether its assertions are about the frozen mechanism or about recall, erasure, archives or recovery.
- Partial-edit line counts are estimates from the cited line ranges.
- Whether erasure clears message-derived JSON in `memory_runtime_turns` columns (section 3.3).
