# Interrupted host-erasure work: completion and boundaries

## Scope

Continues Claude's local integration head 8259e41e3a50e36cce6ba2bb1441b828f9ea5613. Eighteen existing commits
follow remote integration d585437f0676e77aa3a6d3f52fb13ae646759970; they are preserved, not recreated or reset.
Those commits retire the bundled turn runtime and finish server-side digest erasure. Their existing local full-run
evidence is 4,050 passed, three Docker journey skips and three fork warnings. That result predates these fixes.

## Changes

- An observation whose replay response was invalidated by an unrelated source edit is revalidated against current
  recording permission and stored source events. An identical source is acknowledged as duplicate; a changed
  idempotency payload or source revision still conflicts. Erased/stale captures remain excluded.
- A bounded authenticated read confirms erasure by event ID or retained source identity. Host contacts reconcile
  confirmed copies in the pending/refused journals and session ledgers. No absent source is guessed to be erased.
- The replay/session/journal locks serialize cleanup with capture admission. Persistent guards contain stable source
  identities, never message fingerprints. Current owner and recording target are checked separately.
- Single reply erasure preserves its input. Whole-user erasure clears fingerprints as well as bodies. Retired desktop
  pending/recovery evidence loses its input fingerprint once erasure is observed for the matching profile.
- The shared path serves CLI hooks (Claude, Codex, OpenClaw), ChatMemory/AstrBot and Hermes. Host/provider transcripts,
  Hermes USER.md, external backups and exports remain outside this filesystem cleanup.

## Verification

Runtime files were frozen during each service-test batch, using task-owned synthetic databases in WSL Ubuntu.
Ruff over src/tests/examples and git diff whitespace checks passed.

- Related host, queue, receipt, outcome, isolation and adapter regression batch: **278 passed**, 121.29 seconds.
- After the final reply-only/legacy-metadata refinements: **107 passed**, 63.44 seconds, covering the new erasure
  tests, recording fences, retained outcomes, database digest erasure and legacy installation backup/restore.
- Both runners reported database_stopped=true. Earlier failure logs are retained alongside the successful logs;
  they include the first test-fixture correction, generator-consumption bug and malformed-record compatibility fix.
- These batch counts overlap; they are not a count of distinct tests. Full PR Verify is reported separately.

No model calls or behavioural acceptance were started. R4 remains failed; C5 remains invalid/unscored. This WSL
verification does not replace native Windows/macOS or multi-platform qualification.

## Limits and cost

Cleanup follows the next authenticated host/tool/policy contact, not an all-device push. Failed or unsupported
contacts leave cleanup pending. Historical content-derived source keys erased on the server require a retained event
receipt for precise matching. Without one, completed legacy metadata can be discarded conservatively, but unrelated
unsent messages must survive: queued copies use the existing stale-capture replay fence, and unresolved historical
refused copies need explicit whole-user cleanup. This does not claim instantaneous erasure of every old local file.

Stable-source guards survive process restarts. Content-derived identities are never retained as deletion guards.
A bounded identity read uses existing event indexes; filesystem reconciliation occurs on a newly observed recording
revision. Opening a host connection also reads current recording policy. No latency, recall-quality or throughput
improvement is claimed: a same-fixture performance benchmark was not run.
