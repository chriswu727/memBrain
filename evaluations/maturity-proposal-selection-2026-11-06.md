# Unambiguous persona proposal actions

Acceptance-tooling commit `bee76ca6e3b0c5aa32d19f44c580206f879d6cda` fixes a public-input selector defect without changing runtime `5048e13` or its launcher pins.

The harness previously searched the complete JSON representation of each open persona proposal and selected the first match. That representation includes an inherited full persona card and quoted feedback. For example, a persona named "Casual companion" makes a newer playful proposal match "casual", even when the intended older proposal is about a casual speaking style. Acceptance could modify the wrong card before detecting the mismatch; rejection could silently reject the wrong proposal.

Selection now prefers an exact proposal ID or kind. Otherwise it searches only the kind and displayed label, case-insensitively. A blank selector, missing match or ambiguous match does not perform a decision. Ambiguity produces the fixed diagnostic code `ambiguous_proposal`; the existing event path invalidates the run. This does not relax a scenario requirement or turn a missing proposal into a success. The accepted-card comparison against the reference arm remains enforced.

## Evidence and scope

The public regression reproduced **nine failures**, with one exclusion control already passing. The final group adds an empty-input control and is included in **111 passing tests** across the selector, C5 harness and hardening suites. Scoped Ruff and diff checks pass. Independent read-only review found no remaining issue.

Before this tooling repair, runtime `5048e13` passed the default attempt driver and shell supervisor on the unchanged public practice: **250 checks**, strict validity, 18 completed turns per arm, 24/18/18 recorded host rounds, unchanged frozen inputs and four closed service/database ports. That single-proposal practice did not cover this multi-proposal defect. Its result is retained separately from the post-repair practice.

The post-repair default-driver rehearsal also passed **250 checks** and strict validity on source `bee76ca`, with the same 18 turns per arm and 24/18/18 host-round counts. Frozen inputs remained unchanged and all four ports closed. Both runs used fresh disposable profiles, deterministic host/extractor stubs, keyword recall and a pre-existing local model cache; non-loopback connections were refused. Neither run wrote model reasoning into the returned-round journal.

[Raw failures, passing tests, frozen inputs and both complete public rehearsals](evidence/maturity-proposal-selection-2026-11-06/manifest.json) are retained with hashes. The published payloads contain none of the owned synthetic profile credential values.

These are synthetic tests and deterministic public rehearsals. They do not access hidden scenarios or make model calls. They do not establish the cause of the stopped C1 attempt, which remains sealed and incomplete. Runtime files, launchers, schema and renderer are unchanged, so the existing installed-runtime and R5 measurements keep their original scope; they are not rerun for this tooling-only change. Full final-candidate CI and new approved R4/C5 acceptance remain required before release.
