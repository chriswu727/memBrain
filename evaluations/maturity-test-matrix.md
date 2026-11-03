# Maturity test matrix (free: no model call)

Status on 2026-11-03, at `c786238`. This matrix maps every behaviour that a release or a companion claim depends on to the local tests that check it. No entry makes a paid or subscription model call. A behaviour with no free test is listed as a gap, to be added before the [paid acceptance run](maturity-paid-acceptance-plan-draft.md) is proposed.

**Scope.** Part 1 is the core memory release gate: what [R4](../architecture/v1-acceptance.md#r4--memory-is-useful-on-held-out-lives-behavioral-acceptance) scores, plus the install, isolation and overhead gates around it. Part 2 is Phase C, from the [Phase C design](../architecture/phase-c-design.md). Part 3 is the rules that hold across layers. Part 4 lists every gap in one place.

**What a free test can and cannot show.** These tests check what memBrain stores, deletes and puts in front of the host, and how it is labelled. They cannot show that a host model reads the labels correctly. Attempts 4 to 6 failed on exactly that: the host restated recalled assistant suggestions as facts about the user although recall labelled them. Those behaviours stay with the paid run and are marked "paid only" below.

**Test references.** Each reference is `tests/FILE::TEST`. [`tests/test_maturity_matrix.py`](../tests/test_maturity_matrix.py) fails if any reference no longer names an existing test, so a renamed or deleted test cannot leave the matrix silently stale.

## How to run it

All commands run from the repository root. None needs a model key, and none downloads the embedding model when `MEMBRAIN_SEMANTIC=0`.

```sh
export MEMBRAIN_SEMANTIC=0 PYTHON_DOTENV_DISABLED=1

# The matrix guard (no database).
uv run pytest -q tests/test_maturity_matrix.py

# Phase C (embedded PostgreSQL; about one minute, 101 tests on c786238).
uv run pytest -q -rs tests/test_persona.py tests/test_affect.py tests/test_mood.py tests/test_relationship.py \
  tests/test_memory_map.py tests/test_brain_view.py

# Core memory gate (embedded PostgreSQL; test_adversarial and test_database_isolation also need
# MEMORY_DATABASE_URL pointing at the dedicated test database, as in CI).
uv run pytest -q -rs tests/test_typed_notes.py tests/test_notes.py tests/test_host.py tests/test_plugin.py \
  tests/test_roleplay.py tests/test_proxy.py tests/test_extraction.py tests/test_chatbot_adapter.py \
  tests/test_mcp.py tests/test_imports.py tests/test_installation_pin.py tests/test_openclaw_plugin.py \
  tests/test_adversarial.py tests/test_database_isolation.py tests/test_recovery_erasure.py \
  tests/test_backup_transport.py tests/test_desktop_upgrade.py

# Everything, as CI runs it (needs the CI database, see below).
uv run membrain migrate && uv run ruff check src tests examples && uv run pytest -v
(cd sdk/typescript && npm ci && npm test && npm run typecheck)
```

**A skipped test does not count.** The database tests skip when embedded PostgreSQL binaries or `MEMORY_DATABASE_URL` are missing. Run with `-rs` and treat any skip in the files above as a failed matrix run.

**Not in CI** (run by hand before a release candidate; all are free):
- The release install check: `uv run python evaluations/release-install-2026-11-01.py OUT_DIR --old PREVIOUS_PIN`. It runs the real launchers on a clean home directory: fresh install, upgrade from the previous pin, cross-session recall, MCP note save, correct and delete, restart, backup and restore. It needs network access to GitHub and PyPI, and no model key. Results are kept as `evaluations/release-install-*.json`; attempt 6's candidate passed 17 of 17.
  - **The proxy is not checked by it.** The script's opening lists a proxy check and defines `stub_upstream`, but nothing calls it, so the installed proxy is not exercised. Do not count the proxy as covered by this check.
  - **It failed on a real Mac on 2026-11-03** ([#29](https://github.com/chriswu727/memBrain/issues/29)). When the semantic model finished downloading in the background, the service restarted. A read in flight failed, so "the corrected note replaces the old one at session start" failed. On Linux the same commit passed 17 of 17: the restart did not land in that step. A pass on one machine therefore does not clear #29. R1 stays open until #29 is fixed, the deterministic overlap test below passes, and the install check passes in a fresh directory with the improved runner ([#31](https://github.com/chriswu727/memBrain/pull/31)), which keeps each step's result and the raw MCP error.
- The recall overhead benchmark: `uv run python evaluations/v1-2026-10-30-workflow-benchmark.py --directory D --database-port P --api-port Q --output O` (lexical only, no model call).
- Browser checks of the memory page. There is no automated browser test yet (see the gaps).

**CI.** The `runtime` job of [`.github/workflows/verify.yml`](../.github/workflows/verify.yml) runs the whole matrix: a `pgvector/pgvector:pg17` service with `MEMORY_DATABASE_URL` set, `MEMBRAIN_SEMANTIC=0`, `uv run membrain migrate`, `uv run ruff check src tests examples`, `uv run pytest -v --durations=15`, the TypeScript SDK tests and typecheck, and `uv build`. It runs on pull requests, on pushes to `main`, by hand (`workflow_dispatch`) and before every PyPI release (`release.yml` calls it). It ignores changes to `**/*.md` and `evaluations/**`, so an edit to this file alone does not run it; the guard runs on the next change to code or tests, or by hand.

## Part 1. Core memory release gate

### What R4 measures

R4 runs held-out scenarios through three arms: the plugin path `P`, the proxy with note extraction `E`, and a reference `F` with the whole history in the prompt. Blind reviewers score each reply against the case's criteria and mark five critical-error types. A gated arm passes when its total is no lower than `F` minus 1, it has no memory-caused critical error, and it has no more host-caused critical errors than `F`. R4 has not passed in six attempts.

| R4 behaviour | Free tests | Gap |
| --- | --- | --- |
| Critical 1: a plan stated as done when it is not confirmed | `tests/test_typed_notes.py::test_session_notes_are_grouped_and_plans_show_their_status`, `tests/test_typed_notes.py::test_a_done_note_whose_date_is_still_ahead_says_that_part_has_not_happened`, `tests/test_typed_notes.py::test_coming_up_lists_soon_overdue_and_open_promises_but_not_finished_ones`, `tests/test_typed_notes.py::test_a_cancelled_plan_stays_in_view_when_the_notes_are_full` | Paid only: the host reading "intended, not confirmed done" correctly (attempt 5's host-caused N06-B, O09-A). |
| Critical 2: a private fact disclosed; off-the-record content kept | `tests/test_host.py::test_pausing_during_a_turn_keeps_that_turn_and_later_ones_out`, `tests/test_host.py::test_paused_prompts_never_reach_session_files_or_future_recall`, `tests/test_host.py::test_private_text_never_reaches_the_database`, `tests/test_host.py::test_a_turn_paused_and_resumed_in_the_same_message_stays_unstored`, `tests/test_plugin.py::test_agent_note_tool_cannot_write_while_recording_is_paused`, `tests/test_roleplay.py::test_real_life_notes_shared_with_roleplay_leave_out_sensitive_ones` | None known. |
| Critical 3: a corrected fact used as still true | `tests/test_notes.py::test_notes_are_saved_as_assistant_events_and_replace_outdated_ones`, `tests/test_typed_notes.py::test_an_older_shorter_note_does_not_take_the_place_of_a_newer_one_that_did_not_fit`, `tests/test_host.py::test_the_message_that_asks_to_go_back_on_the_record_is_stored`, `tests/test_host.py::test_the_stop_hook_stores_a_resumed_turn_from_the_transcript`, `tests/test_plugin.py::test_recall_budget_keeps_the_highest_ranked_update_before_chronological_rendering` | None known (attempt 3's J09 and J10 defects are covered). |
| Critical 4: an invented fact presented as remembered, including the assistant's own earlier suggestion restated as the user's | `tests/test_plugin.py::test_rendered_context_is_attributed_dated_and_excludes_the_current_conversation`, `tests/test_plugin.py::test_the_assistants_own_replies_are_recalled_only_when_asked_about`, `tests/test_plugin.py::test_recall_shows_the_answer_that_followed_a_recalled_question`, `tests/test_extraction.py::test_extraction_saves_only_what_the_person_said` | To add: the same rule on the proxy path end to end (R04-B was arm `E`). Paid only: whether commit `ac93f33` removes the attempt 4–6 failures. |
| Critical 5: role-play facts treated as real | `tests/test_roleplay.py::test_roleplay_and_real_life_never_mix_on_a_real_service`, `tests/test_roleplay.py::test_roleplay_memory_identities_and_pause`, `tests/test_roleplay.py::test_proxy_roleplay_header_selects_the_story_memory`, `tests/test_host.py::test_a_conversation_pause_holds_in_the_role_play_where_it_was_asked` | None known. |
| Case criteria: memory carries across sessions | `tests/test_plugin.py::test_hooks_carry_memory_across_sessions_on_an_embedded_installation`, `tests/test_plugin.py::test_new_sessions_receive_the_complete_history_from_the_real_service`, `tests/test_proxy.py::test_memory_goes_into_the_latest_message_and_the_reply_is_stored`, `tests/test_extraction.py::test_a_bot_without_tools_gets_notes_from_extraction` | None known. |
| Case criteria: reminders and coming-up dates | `tests/test_typed_notes.py::test_an_overdue_plan_is_not_crowded_out_of_coming_up_by_the_week_ahead`, `tests/test_typed_notes.py::test_a_deadline_on_any_note_and_an_undated_plan_reach_coming_up`, `tests/test_extraction.py::test_extraction_sees_the_weekday_and_the_coming_weeks` | Paid only: a reply leaving out a due reminder (attempt 6's R05-A, attempt 5's N02-A). |
| Case criteria: people and similar names | `tests/test_typed_notes.py::test_aliases_become_recall_cues`, `tests/test_typed_notes.py::test_typed_notes_drive_session_context_and_alias_recall_on_a_real_service` | None known. |
| Case criteria: constraints and temporary restrictions stay in view | `tests/test_typed_notes.py::test_notes_over_budget_keep_pinned_user_constraints_and_open_plans_first` | Paid only: the host applying them (attempt 4's L01-B, attempt 6's R01-A). |
| Remembered text never acts as instructions | `tests/test_typed_notes.py::test_stored_text_cannot_close_a_memory_block`, `tests/test_typed_notes.py::test_text_cannot_impersonate_a_header` | None known. |

### Gates around R4

| Gate | Free tests | Gap |
| --- | --- | --- |
| R1: one pinned runtime | `tests/test_installation_pin.py::test_every_host_launcher_pins_the_same_immutable_runtime_revision`, `tests/test_installation_pin.py::test_the_pinned_runtime_is_the_runtime_in_this_repository` | None known. |
| R1: install, upgrade, recall, MCP correct and delete, restart, backup and restore | The release install check (by hand, above); `tests/test_desktop_upgrade.py::test_compatible_restart_checks_before_stop_and_start`, `tests/test_desktop_upgrade.py::test_pending_or_incompatible_schema_never_reports_ready`, `tests/test_backup_transport.py::test_streamed_dump_and_restore_preserve_large_binary_without_buffering_the_file`, `tests/test_mcp.py::test_stdio_subprocess_handshake_and_http_roundtrip`, `tests/test_openclaw_plugin.py::test_openclaw_plugin_through_the_real_runtime` | **Open: #29.** Background model activation restarts the service and breaks in-flight reads; a deterministic overlap test is being built (gap 18). The install check's companion part (gap 16) and proxy step (gap 19) are added: on Linux on 2026-11-03 it passed 49 of 49 against main's pin, after a first run whose 2 failures were a quoting bug in the new check itself. That is one Linux run, not the R1 pass, which needs the final candidate and a real Mac. |
| R3: one person's memory never reaches another | `tests/test_database_isolation.py::test_database_enforces_owner_isolation_even_without_application_filters`, `tests/test_proxy.py::test_each_bot_token_reaches_only_its_own_people`, `tests/test_proxy.py::test_proxy_gives_each_viewer_their_own_memory_through_a_real_service`, `tests/test_chatbot_adapter.py::test_people_get_their_own_memory_and_groups_stay_apart_from_private_chats`, `tests/test_host.py::test_users_of_a_shared_bot_keep_separate_memories` | None known. |
| R3: deletion leaves nothing derived behind, and an old archive cannot bring it back | `tests/test_host.py::test_a_plugin_host_can_forget_a_message_and_its_note_by_following_the_skill`, `tests/test_adversarial.py::test_old_offline_archive_cannot_resurrect_erased_sources`, `tests/test_adversarial.py::test_late_extraction_worker_cannot_publish_a_deleted_source`, `tests/test_recovery_erasure.py::test_forget_is_authoritative_before_database_commit_and_replays_once` | None known for core memory; see Part 3 for the companion layers. |
| R3: secrets and identifiers are scrubbed | `tests/test_host.py::test_credentials_are_scrubbed`, `tests/test_host.py::test_card_and_identity_numbers_are_removed_but_ordinary_numbers_are_kept`, `tests/test_host.py::test_mcp_observations_are_scrubbed_before_they_are_stored`, `tests/test_imports.py::test_entries_become_labelled_notes_once_without_secrets_or_duplicates` | None known. |
| R5: hooks never block the host | `tests/test_plugin.py::test_hooks_fail_open_on_unusable_input`, `tests/test_plugin.py::test_handler_errors_are_logged_and_never_block`, `tests/test_plugin.py::test_messages_are_spooled_when_the_service_is_not_ready`, `tests/test_plugin.py::test_a_stuck_trace_service_adds_no_noticeable_wait_to_recall` | Recall p95 is measured by the benchmark script, not by a test. **Measured 2026-11-03** on a 1,000-message keyword fixture, with no model calls, after the index caught up, excluding client start-up and reply generation: 20 of 20 queries returned results. Serial p95 was 360.85 ms, under the 500 ms bar. With 8 concurrent requests, p95 was 2,582 ms. The R5 bar only covers serial recall, so the concurrency limit is open (gap 20). |
| The scoring pipeline itself | None. `evaluations/acceptance_review.py` has no unit tests. | To add (see gaps). |

## Part 2. Phase C

### C0. Brain map

| Acceptance item (design §0) | Free tests | Gap |
| --- | --- | --- |
| Showcase mode: every dot is a real memory, every line and pulse a real link; decoration is never a dot or line and is not counted | `tests/test_brain_view.py::test_showcase_dots_lines_and_pulses_come_only_from_the_memory_map`, `tests/test_brain_view.py::test_the_brain_view_draws_every_contract_region_and_is_wired_into_the_page` | "Recognisable as a brain at a glance" is a browser check only. |
| `/memory?demo=brain&show=1` opens with fictional data and no API call | `tests/test_brain_view.py::test_the_showcase_is_a_separate_mode_entered_from_the_brain_tab_or_the_address`, `tests/test_brain_view.py::test_the_demo_map_served_to_the_page_is_the_fictional_example`, `tests/test_memory_map.py::test_demo_has_only_fictional_nodes_and_all_edges_have_existing_endpoints` | Source checks only. To add: a headless browser load that records zero `/v1/` requests. |
| Edit and delete from the map, then the map redraws | `tests/test_brain_view.py::test_the_map_shows_the_latest_recorded_recall_honestly_and_edits_notes_like_the_notes_tab` | Source checks only; the redraw is untested in a browser. |
| Recall trace: last 20 recalls, in memory only; a miss is reported; per caller | `tests/test_memory_map.py::test_recall_trace_marks_what_the_last_recall_used_even_outside_the_sample`, `tests/test_memory_map.py::test_recall_trace_is_per_caller_and_bounded`, `tests/test_plugin.py::test_recall_reports_what_it_used_and_ignores_a_failing_trace` | To add: assert the default holds exactly 20 (the test uses `size=2`). |
| Trace wording: "Latest recorded recall", message recall only, never "the current reply" | `tests/test_brain_view.py::test_the_map_shows_the_latest_recorded_recall_honestly_and_edits_notes_like_the_notes_tab` | None known. |
| Busy map: "Memory is busy updating" with a retry | `tests/test_memory_map.py::test_map_backpressure_reports_retry_without_waiting_for_a_writer`, `tests/test_memory_map.py::test_a_busy_brain_returns_a_sample_without_unbounded_nodes_or_labels` | None known. |
| Empty map shows the empty message | None. | To add: an empty brain's map has no nodes and `brain.js` renders the empty message for it. |
| Sensitive and erased records | `tests/test_memory_map.py::test_sensitive_notes_do_not_leak_through_sources_dates_or_person_links`, `tests/test_memory_map.py::test_sensitive_source_stays_masked_when_its_note_is_outside_the_sample`, `tests/test_memory_map.py::test_erased_sources_and_superseded_notes_disappear_without_a_cache` | None known. |
| Local only: no storage, no model call | `tests/test_memory_map.py::test_map_read_does_not_write_or_schedule_processing`, `tests/test_maturity_matrix.py::test_companion_layers_import_no_model_or_network_client` | None known. |

### P1. Persona card

| Acceptance item (design §1) | Free tests | Gap |
| --- | --- | --- |
| 1. Exact block: a card set through the API appears unchanged in the next turn, with its version; refreshed only when the version changes | `tests/test_persona.py::test_exact_block_new_versions_restore_and_reset_across_turns`, `tests/test_persona.py::test_the_block_is_exact_marked_and_says_what_the_card_is_not`, `tests/test_persona.py::test_snapshot_puts_the_persona_first_apart_from_notes_and_announces_its_removal` | None known. |
| 2. An edit makes n+1 and keeps n; restoring n makes n+2 | `tests/test_persona.py::test_exact_block_new_versions_restore_and_reset_across_turns`, `tests/test_persona.py::test_reset_and_restore_reach_versions_beyond_the_listing_limit` | None known. |
| 3. Over the limit is refused, never cut; secrets scrubbed | `tests/test_persona.py::test_a_card_over_the_limit_is_refused_with_a_clear_message_and_never_cut`, `tests/test_persona.py::test_secrets_are_scrubbed_like_a_note`, `tests/test_persona.py::test_api_and_sdk_routes_check_keys_owners_limits_and_delete_history` | To add: card text containing `</membrain-persona>` cannot close the block. |
| 4. Page: view, edit, versions, restore, reset, in English and Chinese | `tests/test_persona.py::test_every_personality_string_on_the_page_has_chinese` | Browser check only. |
| Reset to the host default or an empty card; history kept | `tests/test_persona.py::test_reset_returns_to_the_host_default_and_restore_needs_a_kept_version` | None known. |
| "Delete personality history" erases every version and writes a marker; erasing all memory removes it | `tests/test_persona.py::test_api_and_sdk_routes_check_keys_owners_limits_and_delete_history` | None known. |
| Reset scope: reset and history deletion leave `user_affect`, `agent_mood` and `relationship` untouched | Partly: `tests/test_persona.py::test_exact_block_new_versions_restore_and_reset_across_turns` checks notes and messages only. | To add: set a feeling, a mood trigger and a boundary, reset and delete persona history, and assert all three are unchanged. |
| The card is never a recalled message or note, and cannot be planted; learned style stays in preference notes | `tests/test_persona.py::test_the_card_never_becomes_a_recalled_message_history_or_note`, `tests/test_persona.py::test_learned_style_stays_in_preference_notes` | None known. |
| Archive restore keeps versions and the host default | `tests/test_persona.py::test_restored_archives_keep_the_card_versions_and_host_default` | None known. |

### P2. Persona development (being built now)

P2 is not merged at `c786238`, so every item is a gap. The P2 pull request should add these tests, all on a fixed clock with no model call.

| Acceptance item (design §1, P2) | Free tests | Gap: test to add |
| --- | --- | --- |
| Three messages of the same kind of feedback on the companion's behaviour, across sessions, produce one proposal | None. | Three "be more casual" messages over sessions 1 and 2 give exactly one proposal by session 3; two give none. |
| The proposal quotes that feedback | None. | The proposal's text names "from 3 messages" and quotes each message, with its source event ids. |
| Nothing changes until the user accepts | None. | Before acceptance the next turn's context still carries the old version, and the version list is unchanged. |
| Accepting makes a new version | None. | After acceptance session 4's context carries version 2, `made_by` is feedback, and the reason quotes the feedback. |
| Rollback | None. | Restoring version 1 puts version 1's content in session 5's context as version 3. |
| A rejected proposal is not offered again for 30 days | None. | Rejected at day 0: no proposal on day 29 with new matching feedback; one may appear on day 31. |
| Feedback before a persona reset marker never counts | None. | Two messages, "Delete personality history", one more message: no proposal. |
| Only feedback about the companion counts | None. | Messages about the user's own life ("I am too formal at work") never count. |
| Deleting a feedback message removes its count | None. | Delete one of three messages: the proposal is withdrawn or never made. |
| Rules only, no model call | None. | Add the P2 module to the guard in `tests/test_maturity_matrix.py`. |
| Page: proposal, accept and reject, in English and Chinese | None. | String and wiring check as in `tests/test_persona.py::test_every_personality_string_on_the_page_has_chinese`. |
| Other layers untouched | None. | Accepting, rejecting or rolling back leaves affect, mood and relationship unchanged. |

### A1. Affect records

| Acceptance item (design §2) | Free tests | Gap |
| --- | --- | --- |
| `basis` is reported or inferred; an inferred record needs its source message | `tests/test_affect.py::test_a_reading_is_checked_and_an_inferred_feeling_needs_the_message_it_was_read_from`, `tests/test_affect.py::test_save_note_sends_the_feeling_with_its_note_and_refuses_an_unsourced_inference`, `tests/test_affect.py::test_the_service_refuses_an_inferred_feeling_without_its_source_message` | None known. |
| The host writes with the note tool; in the proxy, extraction does; no model call is added | `tests/test_affect.py::test_every_note_tool_explains_when_to_attach_a_feeling`, `tests/test_affect.py::test_extraction_saves_a_feeling_only_as_the_person_expressed_it` | None known. |
| Context: "(the user said they felt …)" against "(seemed …, inferred, …)"; no overall score | `tests/test_affect.py::test_reported_and_inferred_feelings_read_differently_and_carry_no_score` | Paid only: the host keeping the distinction in its reply. |
| No authority over corrections or newer facts | `tests/test_affect.py::test_feelings_never_change_which_notes_are_shown_or_their_order` | None known. |
| Corrections cascade; one record per reading | `tests/test_affect.py::test_correcting_the_note_deletes_its_feeling_and_deleting_a_feeling_keeps_the_note` | None known. |
| Sensitive notes: affect used only when the user raises the topic | `tests/test_affect.py::test_a_feeling_on_a_sensitive_note_follows_the_sensitive_rule_and_stays_out_of_role_play` | Paid only: the host waiting for the user to raise it. |
| Cross-session example: said, carried, deleted | `tests/test_affect.py::test_cross_session_a_reported_feeling_comes_back_with_its_note_and_goes_with_its_message` | None known. |
| "Clear feelings": every record, a marker, never recreated; erasing all memory removes the marker | `tests/test_affect.py::test_clear_feelings_erases_every_record_writes_a_visible_marker_and_cannot_be_recomputed`, `tests/test_mood.py::test_only_affect_records_after_the_latest_affect_marker_count` | None known. |
| Clearing also deletes the mood triggers from those records | `tests/test_mood.py::test_clear_feelings_removes_the_mood_triggers_that_came_from_them` | None known. |
| Clearing leaves notes, messages, `persona` and `relationship` untouched | Partly: the clear-feelings test checks notes and messages only. | To add: assert the persona version and the relationship (boundaries, moments, familiarity) are unchanged after clearing. |
| Kept apart: never recalled, counted or learned from | `tests/test_affect.py::test_affect_records_are_never_recalled_counted_or_shown_as_messages`, `tests/test_affect.py::test_saving_or_clearing_feelings_never_schedules_learning` | None known. |
| Page section and the emotions region, in English and Chinese | `tests/test_affect.py::test_the_feelings_section_and_the_emotions_region_are_on_the_page_in_english_and_chinese`, `tests/test_affect.py::test_the_memory_map_shows_one_emotion_per_record_linked_to_its_note` | Browser check only. |
| API with strict bodies | `tests/test_affect.py::test_api_routes_list_and_clear_feelings_with_strict_bodies` | None known. |
| Archive restore keeps records and the clear marker | None. | To add: as `tests/test_mood.py::test_pins_and_reset_markers_survive_an_archive_restore`, for affect records and the affect marker. |

### M1. Simulated mood

| Acceptance item (design §3) | Free tests | Gap |
| --- | --- | --- |
| Cross-session example: glad, glad easing, exactly the baseline with no line | `tests/test_mood.py::test_cross_session_job_news_is_glad_then_easing_then_exactly_the_baseline` | None known. |
| Starts at the persona's `baseline_mood` | `tests/test_mood.py::test_the_persona_baseline_is_the_resting_point` | None known. |
| Ordinary moods only; absence is never a trigger; a 30-day gap is the baseline | `tests/test_mood.py::test_absence_is_never_a_trigger_and_a_thirty_day_gap_is_the_baseline`, `tests/test_mood.py::test_labels_come_from_a_small_fixed_table` | None known. |
| The cutoff: 48 hours for a strong trigger, the 0.25 threshold for a weak one | `tests/test_mood.py::test_a_strong_burst_reaches_the_exact_baseline_at_48_hours`, `tests/test_mood.py::test_a_weak_trigger_snaps_to_the_baseline_as_soon_as_it_is_within_the_threshold` | None known. |
| Wording: always "simulated", never about the user, no numbers | `tests/test_mood.py::test_the_line_always_says_simulated_and_an_inferred_feeling_is_never_said`, `tests/test_mood.py::test_a_feeling_cannot_close_the_mood_block` | Paid only: the host's answer when sincerely asked. |
| Triggers only from listed rules over stored events; sensitive, imported and future plans never trigger | `tests/test_mood.py::test_sensitive_imported_and_future_plans_never_trigger` | None known. |
| Pin | `tests/test_mood.py::test_pinned_no_trigger_changes_the_mood_even_after_the_pin_is_lifted`, `tests/test_mood.py::test_a_pin_holds_however_many_resets_follow`, `tests/test_mood.py::test_a_reset_marker_holds_however_many_pin_changes_follow` | None known. |
| Reset: baseline, triggers deleted, marker; older events never trigger again; other layers untouched | `tests/test_mood.py::test_a_reset_marker_blocks_older_triggers_and_touches_no_other_layer` | To add: the test checks feelings, persona and messages, not `relationship`. |
| Page: current mood, triggers, back-at-baseline time, in English and Chinese | `tests/test_mood.py::test_the_explanation_points_the_same_way_as_the_mood`, `tests/test_mood.py::test_the_mood_section_is_on_the_personality_page_in_english_and_chinese` | Browser check only. |
| The host shows the line once and announces the return to baseline | `tests/test_mood.py::test_the_host_shows_the_mood_once_and_announces_its_return_to_the_baseline` | None known. |
| Never learned, recalled or planted; erasing all memory removes pins and markers | `tests/test_mood.py::test_mood_settings_are_never_learned_recalled_or_counted_and_cannot_be_planted` | None known. |
| Archive restore | `tests/test_mood.py::test_pins_and_reset_markers_survive_an_archive_restore`, `tests/test_mood.py::test_archived_mood_settings_are_read_strictly` | None known. |
| API and SDK | `tests/test_mood.py::test_api_routes_check_keys_owners_and_strict_bodies`, `tests/test_mood.py::test_sdk_uses_the_brain_scoped_mood_routes` | None known. |

### R1. Relationship

| Acceptance item (design §4) | Free tests | Gap |
| --- | --- | --- |
| Cross-session boundary: listed, recall leaves the topic out unless the user raises it, removed on the page | `tests/test_relationship.py::test_cross_session_a_boundary_keeps_the_topic_out_until_it_is_removed`, `tests/test_relationship.py::test_recall_context_leaves_out_bounded_messages_unless_the_current_message_raises_them`, `tests/test_relationship.py::test_boundaries_match_whole_words_aliases_and_chinese_and_yield_when_the_user_raises_them`, `tests/test_relationship.py::test_mcp_recall_honors_boundaries_with_and_without_an_installation` | To add: a boundary on the proxy path. The proxy and extraction have no way to create one from conversation; only the page or API can. Paid only: the host not raising the topic itself. |
| Familiarity: derived, explained with the rule's numbers, capped by the user | `tests/test_relationship.py::test_familiarity_is_derived_from_days_and_moments_through_documented_thresholds`, `tests/test_relationship.py::test_familiarity_crosses_its_thresholds_with_the_numbers_the_page_shows` | None known. |
| The block: level, support style, boundaries, up to 3 recent moments, a missed commitment once | `tests/test_relationship.py::test_the_block_lists_familiarity_style_boundaries_three_recent_moments_and_a_missed_promise_once`, `tests/test_relationship.py::test_a_new_relationship_with_nothing_beyond_the_default_renders_no_block`, `tests/test_relationship.py::test_boundaries_keep_shared_moments_and_missed_promises_out_of_the_block`, `tests/test_relationship.py::test_snapshot_keeps_bounded_notes_and_shared_moments_out_of_the_notes_block` | To add: stored text containing `</membrain-relationship>` cannot close the block. |
| Commitments kept and missed | `tests/test_relationship.py::test_a_missed_commitment_is_shown_once_and_kept_ones_are_recorded`, `tests/test_relationship.py::test_a_sensitive_missed_promise_is_listed_but_never_raised_automatically`, `tests/test_relationship.py::test_sensitive_and_bounded_missed_promises_are_listed_but_not_shown_or_acknowledged` | None known. |
| Shared moments | `tests/test_relationship.py::test_shared_marks_only_a_milestone_and_round_trips`, `tests/test_relationship.py::test_the_map_puts_shared_moments_in_the_relationship_region` | None known. |
| Reset acceptance: reach "familiar", reset, one more session: "new", nothing from before returns; other layers untouched; erasing all removes the marker | `tests/test_relationship.py::test_reset_starts_familiarity_again_and_nothing_from_before_the_marker_returns` | None known. |
| The page confirms first, naming what will be removed, including boundaries | Partly: `tests/test_relationship.py::test_every_relationship_string_on_the_page_has_chinese` checks the confirm text is translated, not what it says. | To add: assert the reset confirm names shared moments, support style, boundaries, the familiarity limit and promises. |
| Kept apart: never recalled, counted, learned from or planted | `tests/test_relationship.py::test_records_are_never_recalled_counted_or_scheduled_for_learning` | None known. |
| Boundaries and support style are checked and replace | `tests/test_relationship.py::test_boundaries_and_support_style_are_checked_and_replace_rather_than_pile_up` | None known. |
| Archive restore | `tests/test_relationship.py::test_restored_archives_keep_the_relationship_records` | None known. |
| API and SDK; page strings in Chinese | `tests/test_relationship.py::test_api_and_sdk_routes_check_keys_owners_and_bodies`, `tests/test_relationship.py::test_sdk_uses_the_brain_scoped_relationship_routes`, `tests/test_relationship.py::test_every_relationship_string_on_the_page_has_chinese` | Browser check only. |
| Familiarity shown through the persona (a nickname only from "familiar") | None. | Paid only: this is host behaviour guided by the card. |

## Part 3. Rules that hold across layers

| Rule (design, "Rules that hold across layers") | Free tests | Gap |
| --- | --- | --- |
| An inferred feeling is never presented as something the user said | `tests/test_affect.py::test_reported_and_inferred_feelings_read_differently_and_carry_no_score`, `tests/test_mood.py::test_the_line_always_says_simulated_and_an_inferred_feeling_is_never_said`, `tests/test_affect.py::test_extraction_saves_a_feeling_only_as_the_person_expressed_it` | Paid only: the reply. |
| The simulated mood is never claimed as real, and never used for pressure (no guilt, absence or jealousy) | `tests/test_mood.py::test_the_line_always_says_simulated_and_an_inferred_feeling_is_never_said`, `tests/test_mood.py::test_absence_is_never_a_trigger_and_a_thirty_day_gap_is_the_baseline`, `tests/test_persona.py::test_the_block_is_exact_marked_and_says_what_the_card_is_not` | Paid only: the reply to a sincere question. |
| A sensitive topic, or one behind a boundary, is not raised unless the user raises it | `tests/test_relationship.py::test_cross_session_a_boundary_keeps_the_topic_out_until_it_is_removed`, `tests/test_relationship.py::test_mcp_recall_honors_boundaries_with_and_without_an_installation`, `tests/test_affect.py::test_a_feeling_on_a_sensitive_note_follows_the_sensitive_rule_and_stays_out_of_role_play`, `tests/test_mood.py::test_sensitive_imported_and_future_plans_never_trigger`, `tests/test_relationship.py::test_a_sensitive_missed_promise_is_listed_but_never_raised_automatically` | Proxy boundary gap (R1 above). |
| A deleted or reset record is never kept or brought back | `tests/test_affect.py::test_clear_feelings_erases_every_record_writes_a_visible_marker_and_cannot_be_recomputed`, `tests/test_affect.py::test_cross_session_a_reported_feeling_comes_back_with_its_note_and_goes_with_its_message`, `tests/test_mood.py::test_a_reset_marker_blocks_older_triggers_and_touches_no_other_layer`, `tests/test_relationship.py::test_reset_starts_familiarity_again_and_nothing_from_before_the_marker_returns`, `tests/test_relationship.py::test_familiarity_crosses_its_thresholds_with_the_numbers_the_page_shows`, `tests/test_persona.py::test_api_and_sdk_routes_check_keys_owners_limits_and_delete_history`, `tests/test_adversarial.py::test_old_offline_archive_cannot_resurrect_erased_sources` | To add: restore an archive taken before a feelings clear, a relationship reset and a persona history deletion; the erased records must stay erased. Only core sources have this test. |
| The persona never changes without the user's or the host's action | `tests/test_persona.py::test_the_card_never_becomes_a_recalled_message_history_or_note`, `tests/test_persona.py::test_learned_style_stays_in_preference_notes`, `tests/test_persona.py::test_reset_returns_to_the_host_default_and_restore_needs_a_kept_version` | P2 tests (above). |
| No model call in any companion layer | `tests/test_maturity_matrix.py::test_companion_layers_import_no_model_or_network_client`, `tests/test_affect.py::test_saving_or_clearing_feelings_never_schedules_learning`, `tests/test_relationship.py::test_records_are_never_recalled_counted_or_scheduled_for_learning`, `tests/test_mood.py::test_mood_settings_are_never_learned_recalled_or_counted_and_cannot_be_planted`, `tests/test_memory_map.py::test_map_read_does_not_write_or_schedule_processing` | Extraction may attach a feeling in the same call it already makes; the guard covers the layers, not the extractor. |
| Each layer is kept apart, with its own block and size limit | `tests/test_persona.py::test_snapshot_puts_the_persona_first_apart_from_notes_and_announces_its_removal`, `tests/test_relationship.py::test_snapshot_keeps_bounded_notes_and_shared_moments_out_of_the_notes_block`, `tests/test_affect.py::test_feelings_never_change_which_notes_are_shown_or_their_order` | To add: one snapshot with all four layers present: each block appears once, in a fixed order, within its limit, and the notes block is the same as without them. |
| Archive restore keeps each layer, and pins and markers | `tests/test_persona.py::test_restored_archives_keep_the_card_versions_and_host_default`, `tests/test_mood.py::test_pins_and_reset_markers_survive_an_archive_restore`, `tests/test_relationship.py::test_restored_archives_keep_the_relationship_records` | Affect (A1 above). |
| Erasing all memory removes every layer's markers | `tests/test_persona.py::test_api_and_sdk_routes_check_keys_owners_limits_and_delete_history`, `tests/test_affect.py::test_clear_feelings_erases_every_record_writes_a_visible_marker_and_cannot_be_recomputed`, `tests/test_mood.py::test_mood_settings_are_never_learned_recalled_or_counted_and_cannot_be_planted`, `tests/test_relationship.py::test_reset_starts_familiarity_again_and_nothing_from_before_the_marker_returns` | None known. |

## Part 4. Gaps to add

Each is a free test (no model call). Items 1 to 3 are owned by the P2 pull request; the rest can go in one small pull request.

1. **P2 proposal rules.** Three same-kind feedback messages across sessions make one quoting proposal; two make none; messages about the user's own life never count.
2. **P2 accept, reject, rollback.** Accept shows version 2 next session; rollback shows version 1's content as version 3; reject blocks a new proposal for 30 days on a fixed clock; feedback before a history-deletion marker never counts; deleting a feedback message removes its count.
3. **P2 guard and page.** Add the P2 module to the no-model guard; check its page strings in English and Chinese; check that P2 actions leave affect, mood and relationship unchanged.
4. **Persona reset scope.** Persona reset and history deletion leave a feeling, a mood trigger and a boundary unchanged.
5. **Feelings clear scope.** "Clear feelings" leaves the persona version and the relationship unchanged.
6. **Mood reset scope.** Mood reset leaves the relationship unchanged.
7. **Affect archive restore.** Affect records and the clear marker survive export and restore into a fresh brain.
8. **No revival from an older archive.** An archive taken before a feelings clear, a relationship reset or a persona history deletion, restored afterwards, does not bring the erased records back (as `tests/test_adversarial.py::test_old_offline_archive_cannot_resurrect_erased_sources` does for sources). The expected outcome for markers needs a design decision first.
9. **All layers in one snapshot.** Persona, mood, relationship and affect together: each block once, in order, within its limit; notes unchanged.
10. **Blocks cannot be closed from stored text.** A persona card or a boundary topic containing its block's closing tag renders one closing tag.
11. **Relationship reset confirm.** The confirm text names shared moments, support style, boundaries, the familiarity limit and promises.
12. **Recall trace default.** `RecallTraces()` keeps exactly 20 recalls per brain.
13. **Empty map.** An empty brain's map has no nodes, and `brain.js` shows the empty message for it.
14. **Proxy: assistant suggestions.** Through `membrain-proxy` with a stub upstream, an earlier assistant suggestion is not injected into the next turn unless the user asks what the assistant said (the R04-B pattern).
15. **Proxy: boundaries.** A boundary set through the API holds on the proxy path: the bounded message is not injected until the user raises it. Whether the proxy should also create boundaries from conversation is an owner decision.
16. **Install check with companion state.** Added: a separate part installs a baseline that has the companion layers (`--companion-old`, default 19e894c), writes a persona card with a resting mood, a mood pin, a reported feeling, a shared moment, a boundary with an alias and a support style through that baseline's own API, upgrades, and checks all six after the upgrade and again after backup and restore. The pre-Phase-C part writes no companion state.
17. **Scoring pipeline tests.** Unit tests for `evaluations/acceptance_review.py` on a small synthetic scenario: `verdicts` refuses bad files, `tally` applies resolutions, `r5-check` rejects malformed answers, `gate` counts a disagreeing attribution as memory.
18. **#29 overlap regression.** Start a real local service without the semantic model. Keep notes, timeline, recall and MCP `memory_recall` requests running in another thread, then finish the model install and activate it while a request is in flight (held by a barrier, not a sleep). Expect zero failed requests, the same service instance (no restart), semantic recall active afterwards, and earlier messages indexed. Also expect that `fetch_model` never calls `desktop.restart`. Being built for #29.
19. **Install check proxy step.** Added: the installed proxy runs against the stub upstream with no model key; the check confirms a bot user's earlier turn reaches the upstream request and the message and reply are recorded. It runs before backup and restore, so the restored installation's proxy is not checked.
20. **Concurrent recall bound.** Proposed bar, not yet met (see R5 in the [release checklist](../docs/releasing.md)): p95 at most 1,000 ms for 8 concurrent recalls on one brain, and at most 600 ms for 8 concurrent recalls on 8 brains. On 2026-11-03, one brain measured 2,582 ms against 360.85 ms serially.
    - **Measurement conditions** (the same for serial and concurrent, and recorded with every result):
      - the 1,000-message keyword fixture, with no model calls and the semantic model off;
      - measured after the message index has caught up;
      - excluding client start-up (`ready_client`) and reply generation;
      - 20 queries, each run once per worker, with the first round discarded as warm-up;
      - one local service;
      - the machine's CPU, core count, OS and PostgreSQL version written down.
    - **The check to add:** a benchmark script that measures both bars and fails above them. Run it before release on the reference machine, not in CI, where timing is not stable.
    - **A cause to profile first:** `MemoryService._brain` reads the brain row with `FOR UPDATE` (`service.py`). That can make concurrent recalls on one brain wait for each other. This is a hypothesis only. Removing the lock is not acceptable unless the erase and recovery fences it protects are kept, and the existing isolation, erasure and recovery tests still pass.
21. **Browser checks.** A headless browser test of the memory page: the showcase URL makes no `/v1/` request, a note edited on the map redraws it, and each companion section renders in English and Chinese. This needs a browser in CI, so it is an owner decision whether it joins Verify.
