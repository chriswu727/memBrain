# Conversation-bound recording resumption

Runtime `816662f6241da587895aa2e1109346ef60eb2050` fixes a recording privacy defect reproduced independently with public synthetic conversations. Previously, an unscoped resume selected the latest paused turn. If another conversation started while the requesting agent was preparing its reply, that other private exchange could be recorded instead. The installation owner's resume could also select another user's turn.

Three initial regression cases fail on the predecessor. A separate MCP reproduction on build `44c034fefd9278d180578307e2169d6ed630f101ff2736a4c6ba7e8e1462a319` delivers two records from the wrong private conversation while the requester remains unresumed. Its first setup encountered the macOS `/var` symbolic-link alias and was refused by the existing profile guard; resolving the temporary directory allowed the reproduction without changing that runtime. Both outcomes are preserved.

## Recording contract

Reactivating a turn already in progress requires the caller's explicit session. The core reads that session's marker and checks its user/role-play ownership and that it began while paused. A turn paused during its exchange cannot be restored. An unscoped resume enables future recording only and returns `current_turn_resumed: false`, `reason: "session_required"`; it never guesses, even when there is only one paused turn. Existing private turns stay unrecorded.

The MCP bridge accepts `session_id`, supplied in each paused prompt's recording notice. The CLI tool accepts the same field. OpenClaw binds the tool to its canonical host session, including session-key aliases, and overrides model-supplied scope. AstrBot forwards its request event's stored session. Custom chatbot adapters must pass `session` to include the resume request itself. The [reference](../docs/reference.md#plugin-mode) documents the contract.

The public practice stub now passes its own `s7-recording` session when resuming. Its scenario text, expected recording behavior and scoring criteria are unchanged. The execution harness, frozen fourth-attempt checkout and hidden workloads were not modified or rerun.

## Qualification

- The focused group passes 23 checks, with 13 unrelated cases deselected. The complete related group passes 253 tests in 189.54 seconds, zero skips, covering recording controls, user isolation, host adapters, first use, proxy and harness hardening. OpenClaw's real-runtime bridge executes all nine Node tests within that group. The existing latest-turn fallback assertion was tightened to require explicit scope; the underlying privacy expectations were not relaxed.
- After those tests, an obsolete latest-turn comment was removed. Parsed Python AST equality is recorded; no executable change followed the run. Full-source Ruff and both immutable pin checks pass.
- All nine launchers pin this runtime. Fresh installation passes 49 checks. Both installed homes match all 197 runtime inputs; all four profiles and eight ports close. The installed package passes all 20 recording-state/scope regressions in 0.40 seconds.
- Public deterministic rehearsal passes 250 checks and strict validity, with 18 turns per arm and 24/18/18 returned-round journal rows. Public frozen inputs remain unchanged, no reasoning content is retained and all four ports close. These are keyword/stub integration checks, not model behavioral acceptance.
- [The evidence manifest](evidence/maturity-resume-scope-2026-11-07/manifest.json) preserves 27 payloads, including failures, original and corrected setup, public results and reproduction wrappers. Hashes and decompression are verified. All 84 known credential values from 32 synthetic profiles are absent. The related-test database directory was removed after all 21 profile port checks passed; raw test logs and receipts remain.

Build: `954cd01a7a8e4cf396035eb4e111888a37485d39973a876aa60f5fa4ee1cebff`. Schema identity is unchanged. The repair and pins are being delivered to `integration/maturity-candidate` after the preceding recording-state Verify and five-platform Native runs passed. Complete CI for this new source remains pending. No previous runtime's full-suite pass is attributed to this one.

The [fourth behavioral attempt](maturity-fourth-attempt-2026-11-07.md) remains stopped and unscored. This public defect does not establish the cause or meaning of that hidden failure. No new paid/subscription behavioral round or final release review has been started. R4/C5, main merge, tag and publication remain blocked.
