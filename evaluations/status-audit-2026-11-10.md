# Status audit, 2026-11-10

Scope: the whole repository at integration head `c15ee26057f98bd5fcaee0aafc69aba987220c47` (runtime `d6aa3d5`, pinned by `9a546fa8`). This is a review, not a qualification: it changes no runtime file, clears no release gate and called no model. **R4 remains failed and C5 invalid/unscored; main merge, tags and publication remain blocked.**

Each finding carries the level at which it was checked:

- **reproduced**: a test or run in this audit shows it;
- **read**: the cited code was read by the auditor and does what is described, but nothing was executed;
- **reported**: found by a read-only reviewer agent with file and line citations; the auditor did not re-read every cited line;
- **not exercised**: the mechanism is in the code, no attack or fault was run.

Compact results, the runner and the two failing reproductions are in [evidence](evidence/status-audit-2026-11-10/results.json).

## Summary

The engineering base holds: the full source suite, the TypeScript client, lint, row-level security, parameterised SQL, backup verification and the erasure fence all check out. The product is not releasable. Behavioural acceptance has not passed, several release-bar items rest on evidence for older runtimes, and this audit found privacy and erasure defects in the host layer, three defects on the default memory path, and credential-handling findings that need a fix before publication.

Four days of work since the fifth behavioural attempt (pull requests 46 to 65) went into recording controls, receipts and outcomes. None of it has been through a new held-out behavioural run, and no public benchmark has been repeated since the recall changes of 2026-11-08.

## What was run

| Check | Result |
| --- | --- |
| Full Python suite, task-owned embedded PostgreSQL 16.15 with pgvector 0.8.6 | **8,457 passed, 1 failed, 15 skipped**, 3 fork warnings, 40 min 36 s |
| The failed test, alone and with its file | 5 of 5 passes alone; 19 passed as a file. Intermittent; cause not established |
| TypeScript client | 56 passed, 0 skipped; strict typecheck passed |
| Ruff, `src tests examples` | Passed |
| Two host-layer findings | Reproduced ([reproductions.py](evidence/status-audit-2026-11-10/reproductions.py)) |

The failed test is `tests/test_longitudinal_learning.py::test_history_failure_stops_even_when_the_current_exchange_was_encoded[unknown]` (`current_encoding_not_ready` where no stop reason was expected). The machine was also running the audit's reviewers at the time. The 15 skips need Docker (`MEMORY_DESKTOP_E2E`) or the pinned local embedding model; they are not passes. Runtime and migration files were hashed before and after the run and did not change. The database was stopped and its directory removed afterwards; the JUnit file and log are kept outside the repository, with their hashes in the results file.

Not run: native Windows or macOS, five-platform qualification, the 36-window R5 protocol, Docker journeys, any model evaluation, and any exploitation of the security findings.

## Release bar

| Item | State at this head | Note |
| --- | --- | --- |
| R4 behavioural acceptance | Failed | [Fifth attempt](maturity-fifth-attempt-2026-11-07.md): plugin 20 (pass), extraction 16 with one memory-caused privacy reply (fail), full-history reference 15.5 |
| C5 companion evaluation | Invalid, unscored | C1 stopped on a page-action failure; C2 did not run |
| R5 overhead | Checked in [the checklist](../docs/releasing.md), but stale | Evidence is runtime `f5e265c` (2026-11-07). 38 later commits touch `src` or `migrations`, including the recall path (`cebc6d82`, `d54a521b`, `10dbeb05`). No later run repeated the 36-window protocol, which the item itself requires |
| Five-platform native qualification | Last covered `978312c` | Not repeated for `fcae167`, `294db3d`, `2ef05f3`, `d6aa3d5` |
| Mac 49-check installation | Last covered `7902c16e` | |
| Full Verify | Recorded in the repository up to `2ef05f3` | A reviewer agent reports that pull request 65's Verify succeeded on `3d94a645`; the checklist entry for `d6aa3d5` still says the result is recorded only in the pull request |

Dated memory-quality measurements, none repeated on the current runtime and none to be read as its present accuracy:

- [LoCoMo](locomo-2026-10-29.md), 1,540 questions: plugin path 76.4%, with note extraction 78.4% ([comparison](mem0-and-extraction-2026-11-01.md)), Mem0 open source 81.3%, full context 81.4%. The largest gap is multi-hop (62.5% against 74.5% on the held-out conversations).
- [LongMemEval](longmemeval-2026-10-29.md), a 30-question sample: tied with full history at 73.3%; one of five questions about the assistant's own earlier replies was answered.

## Findings: host layer (module 1)

| # | Finding | Where | Level |
| --- | --- | --- | --- |
| H1 | A conversation-scoped pause is ended by any other session that starts. After "off the record" in one window, opening a second window resumes recording in the first; its later messages are stored. The resume notice goes to the new window | `src/membrain/host.py:483-495`, called from `session_context` at `:1923-1924`; `paused()` at `:642-649` does not consider the asking session | reproduced |
| H2 | A record the service permanently refuses is appended, with its text, to `plugin/spool-rejected.jsonl`. Per-person erasure cleans the queue and the session ledgers and never this file | `host.py:884-892`, `:556-588` | reproduced (function level) |
| H3 | `session_context` rewrites the session ledger from a fixed key list that omits `last_prompt`. Hosts that call it before every message (`ChatMemory`, so the proxy and AstrBot; OpenClaw) therefore never have the previous-prompt recall cue | `host.py:1113-1116`; `src/membrain/adapters/chatbot.py:117-121` | read |
| H4 | `session_context` calls `flush` unguarded, and `flush` re-raises every non-permanent replay error. Reported consequence for `ChatMemory` hosts: `context()` raises before staging, and the later `record()` is refused as `turn_not_staged`, so that exchange is neither stored nor queued | `host.py:981-985`, `:1937-1938` | raise path read; consequence reported |
| H5 | `forget-user` and `export-user` act on one user id and one brain; a person's separate role-play brains (`user\|roleplay:<character>`) are not covered | `src/membrain/plugin_cli.py:76-105`, `host.py:545-552`, `src/membrain/proxy.py:204` | reported |
| H6 | A host whose Stop callback carries no turn id (OpenClaw, WorkBuddy) returns `turn_ambiguous` once one stale unfinished entry exists, and each following turn stays unfinished until a 30-minute gap: prompts are stored alone, replies never | `src/membrain/host_turns.py:101-117`, `integrations/openclaw/membrain/index.js:190-193`, `src/membrain/plugin.py:192-198` | reported |
| H7 | The Hermes `USER.md` import at owner session start does not check the pause that `on_memory_write` checks | `src/membrain/adapters/hermes.py:147-175`, `src/membrain/imports.py:146-172` | reported |

Reported and not confirmed: no retry cap for a record that always fails transiently (it blocks every later record of every user until the journal limit); abandonment after 30 minutes stores the prompt of a long live turn alone; the owner's conversation pause blocks every bot user sharing the directory; the opening pause phrase must end its first clause with punctuation ("Off the record, my salary…" is recorded); `_write_state` has no fsync and a corrupt session ledger reads as empty.

The four items the project already lists as open were confirmed still open in code: local controls are not synchronised to the service (`pause` and `resume` write local files only, so they do not stop standalone MCP, `BrainRuntime` or SDK writes); `BrainRuntime` has its own receipt types; outcomes do not learn of deletions made in the service; local files and server writes are separate transactions. The project documents call the direct runtime "AgentRuntime"; the class is `BrainRuntime` (`src/membrain/runtime.py:382`).

Found sound: journal append, rollback, fsync, checksum and bounds; fail-closed handling of unreadable pause and policy files; excluded turns never reach the journal on any host entry point; proxy token comparison, header whitelist and per-person sessions; hooks always exit 0.

## Findings: memory path

| # | Finding | Where | Level |
| --- | --- | --- | --- |
| M1 | `list_notes` reads the newest 200 current notes; `select_notes` ranks only within them. Beyond 200 notes, older pinned and constraint notes are no longer candidates for the session-start block, which then says only that some notes did not fit | `src/membrain/notes.py:121-122`, `:398-415`, `:483-485` | read |
| M2 | Malformed or truncated extractor output returns an empty list and is recorded as a successful read with zero notes; `failed_since_success` is reset. A degraded extractor is invisible in its status | `src/membrain/extraction.py:143-147`, `:258-261`, `:396` | read |
| M3 | Cognition runtime (not the default path): `forget(kind="memories")` erases every event in the selected assertion's `event_ids`. For a derived claim that list is reported to be its whole learning-batch closure, up to 256 events, so forgetting one inferred claim would erase unrelated messages and everything citing them | `src/membrain/erasure.py:11-16`; closure at `src/membrain/consolidation.py:376-408` | selector read; closure reported; not executed |
| M4 | Archive restore renumbers event revisions from 1 while `superseded_evidence_refs` keep the source brain's revisions, and `evidence_overlaps` requires equal revisions. Reported consequence: a retracted capture of an event whose revision was above 1 can be republished after export and restore | `src/membrain/service.py:491`, `:1583-1590`, `:1299-1301`; `src/membrain/cognition.py:494-498` | renumbering and comparison read; chain not executed |

Reported and not confirmed: note replacement is not atomic with the recovery authority's suppress intent; a permanently failed extract job pins `indexed_sequence`; source truncation by id order instead of rank; a dependency-generation change during the extractor's model call drops that turn's notes without retry; every recall scans all eligible assertions and no vector index is defined (it fails loudly as `budget_exceeded`).

Found sound: every candidate query filters tenant, owner, brain, current, not invalidated, deleted or suppressed; erasure blanks the lexical projection and embeddings and supersedes vector jobs; the read cache is cleared on every dependency advance; superseded evidence is filtered on every source-text path; a deleted source cannot be re-added as an edit and restore blocks tombstoned ids. Derived memories that touch a deleted event are invalidated without a surviving-evidence check; tests pin this as the intended behaviour.

H3 and M2 sit on the extraction proxy path, the path that failed R4 in the fifth attempt. Whether they contributed to any scored reply is not established.

## Findings: security

Sound: every `/v1` route authenticates; loopback bind, trusted-host check, bearer tokens only and a strict content security policy; sign-in codes are 256-bit, hashed, single-use and expire in 120 seconds; stored text is rendered with `textContent`; all 30 `memory_*` tables have forced row-level security with a tenant and owner policy; tenant context is set per transaction; SQL is parameterised; profile secrets are owner-only on POSIX and Windows; the embedded engine uses `scram-sha-256` on loopback with no Unix socket and checks its supplier archive and every file; backups and snapshots verify names and hashes; erasure intents are replayed after a restore.

Findings that can be stated here:

- **Secret scrubbing is applied by the host layer, the MCP bridge, the adapters and note saving, and not by the service.** Text sent through `POST /v1/actions`, the SDKs, archive import or `membrain desktop chat` is stored unscrubbed. `SECURITY.md` says such values are removed "before anything is queued or stored". Level: read (`privacy.scrub` has no call in `service.py`, `api.py`, `turns.py`, `agent_session.py` or `desktop_chat.py`).
- **The loopback proxy without a token serves any local process for any person**, including recording into that person's memory. `SECURITY.md` discloses this under "whoever controls a bot", while its first boundary row says other local users are excluded. Level: read (`src/membrain/proxy.py:138-161`).
- **Backups include the model provider key** from the cognition configuration; `SECURITY.md` mentions only memory. Level: reported (`src/membrain/desktop_backup.py:51-57`).
- **`membrain init`** writes `.env` under the default umask before restricting it, and its `chmod` sets no ACL on Windows. Developer flow only. Level: reported (`src/membrain/cli.py:21-42`).
- **Supply chain**: workflow actions are pinned by tag, including the PyPI publish action in a job with `id-token: write`; launchers install a commit-pinned archive without a hash (already disclosed).

Two further findings concern how local credentials are presented and need another local account or process to exploit. Neither was exercised. Their details are kept out of this public file until they are fixed, in line with the private-reporting request in `SECURITY.md`; they are recorded with the owner.

## Findings: documentation and repository

- **The documented install commands deliver an older runtime.** The READMEs install from the default branch; `origin/main` is `52c08818` (2026-11-03), 603 commits behind this head, with launchers pinned to `cb694865`. The READMEs describe `d6aa3d5` features such as `membrain plugin outcome`. Neither README says so.
- **"GitHub Actions is manual-only" is false** in `README.md:308`, `README.zh-CN.md:318`, `docs/reference.md:950` and `architecture/v1-release-plan.md:47`: `verify.yml` runs on pull requests and on pushes to `main`.
- **The maturity test matrix is stale.** Its header names `7902c16e` as the current runtime with all nine launchers pinned to it. It lists none of the recording-control, recording-fence, receipt or outcome tests added from 2026-11-07 to 2026-11-10, so "no open gap for a shipped behaviour" (R2) is unsupported for that work. `tests/test_maturity_matrix.py` checks only that named test ids exist; all 282 do.
- **The checklist contradicts itself**: R2 says the embedded-engine security baseline remains open and R3 says it is addressed; C-1 is unchecked although its own text says every step is implemented; several paragraphs label different runtimes "current".
- **`CHANGELOG.md` was last edited on 2026-11-04** and says personality and emotion are outside the release, which its own earlier entries contradict. The same sentence remains in `architecture/memory-quality-and-efficiency.md:5` and `architecture/v1-release-plan.md:13`. Three native-engine documents still call PostgreSQL 16.2 current.
- **Status cannot be read quickly.** `docs/releasing.md` has 32 dated paragraphs before the bar itself; the README status section is a chronicle; there are two attempt numberings and "R5" names both a gate and a review stage.
- **Repository state**: eight pull requests from 2026-11-03 are still open, and issue 29 is open although its fix is on this branch; 92 remote branches, 81 already merged into this head; `ruff check .` reports 995 findings, all in `evaluations/` scripts outside the CI scope.
- No substantive mismatch between the English and Chinese READMEs. Versions are consistent at 0.1.0. All relative links resolve. No build or cache directory is tracked.

## Recommended order

1. **Close module 1 with a finite batch.** Fix H1, H2, H4 and H5 with regressions, and decide H6 and H7. Record local-to-server control synchronisation as a stated limit instead of continuing to build on it.
2. **Rebuild the baseline.** Repeat the 36-window R5 protocol on the resulting runtime; put a short current-state table (runtime, then last Verify, five-platform, Mac installation, R5, R4, C5, each with the runtime it covered) at the top of the checklist and move the dated paragraphs under a history heading; bring the matrix up to date.
3. **Work on memory quality.** Fix H3, M1 and M2; measure multi-hop recall and the extraction path on held-out material against the raw-record and full-history references at equal budgets; then the correction and deletion chain (M3, M4, surviving independent evidence). Only then propose a new paid R4 attempt, which needs the owner's separate approval.

The security findings belong to module 6 and must be fixed before any publication; the two withheld ones before the default branch receives this runtime.

## Follow-up

H1, H2, H4 and H7 are fixed in runtime `ede5769`: see [conversation-scoped pause and module-1 closing fixes](backend-conversation-pause-scope-2026-11-10.md). That batch's reruns also show that four background-learning test files fail intermittently on both runtimes, so the single failure in this audit's full run was not an isolated case. The other findings are unchanged. H3, M1 and M2 are fixed in runtime `1f5d268`: see [recall block budget, note paging and extraction outcomes](memory-path-recall-budget-2026-11-10.md).
