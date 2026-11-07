# Persona decisions consume earlier feedback

Two real-database reproductions showed that existing withdrawn proposals could bypass later user decisions:

- Accept a newer request for a more formal persona, then erase the feedback behind it: an older casual proposal reopened and could change the card back.
- Withdraw an older proposal by editing one source, create and reject a newer proposal of the same kind, then restore the old source's feedback text: the old proposal reopened during the 30-day rejection pause.

Proposal status and proposal creation now use one feedback cutoff, covering decisions of the same kind and accepted changes in the opposite direction. Old proposal IDs cannot reopen after those decisions. Fresh proposals require three eligible sources after the cutoff, and rejection still imposes the 30-day pause. Revising one old source does not authorize a proposal backed by older feedback; three eligible revisions can support a new proposal. Accepted/rejected decisions remain historical records even after their feedback is erased. Deleting personality history removes those records as documented.

The Companion page explains consumed same-kind feedback with `feedback_used` in English and Chinese. Opposite-direction decisions retain the `contradicted` reason. The real companion graph reports the same withdrawn/accepted statuses and retains only the actual accepted-version link; no decorative acceptance state is invented. Archive restore preserves the boundary.

## Validation

The original opposite-direction regression produced three failures and one passing control. The subsequent same-kind regression failed before its repair. The final six-case real-database regression suite passes, covering source revisions, new feedback, the rejection pause, reset, restore and companion-map state.

The existing persona/growth/map suite initially reported 147 passes and two missing-translation failures, with two real-host tests intentionally reserved for a separate interpreter. The missing translation was added. Both localization checks and both real-host flows then passed: cross-session feedback/acceptance/rollback, and persona updates/reset across turns. Together, **157 distinct affected cases pass across these runs**. The direct-service portion uses an isolated database fixture in place of starting a detached API; the two host tests use the actual service. An anyio import/assertion-rewriting warning remains in the first direct-service log. Full-source Ruff, JavaScript syntax checks and diff checks pass.

The direct-service test databases were stopped and removed after capturing their results. No paid model, hidden scenario or user conversation was used. These deterministic tests do not establish human-like personality behavior or pass C5. Runtime `4748818bc0e78bdbf4b82589313fb7fc2d0d0db2` is pinned by all nine launchers in `a39c9913555e799141946793dbf4899debb5b352`; both pin checks pass. A fresh wheel matches all 187 runtime inputs and passes eight installed cases (the six lifecycle regressions and two real-host flows). [Validation and package evidence](evidence/maturity-persona-decisions-2026-11-06/manifest.json) retain the initial failures and subsequent results. The preceding memory-grounding candidate passed all 7,583 Python tests, 50 TypeScript tests and five native platforms. This persona candidate adds runtime changes, so its own full CI remains pending before delivery is complete.
