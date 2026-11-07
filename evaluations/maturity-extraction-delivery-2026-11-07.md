# Confirmed extraction delivery and bounded retries

Runtime `0c8ea88ad61e782ce03628195f8758fc395726b6` fixes silent note-delivery failures. Previously, the extraction loop caught a failed write, continued, and finally recorded a successful turn with zero saves. An earlier confirmed save was also omitted from the cumulative count if a later source conflict or pause ended the turn. Seven public fault regressions failed against candidate `341f4e8` before this repair.

Each proposed note now receives one request ID, reused with the same payload and dependency generation for up to two transient delivery retries. HTTP 429/5xx and transport failures retry the memory service, never the extraction model. A committed write whose response was lost replays its existing result, including after a replacement or a feeling was saved. Deletion or correction invalidates the request response, so a retry fails closed rather than recreating erased content. Generation advances for the next proposal only after a valid response confirms the write.

Known local validation failures and explicit service validation rejections can leave other valid proposals to be saved, while preserving the turn's incomplete status. Permission, source, version and idempotency conflicts stop later writes. Malformed HTTP 200 data and otherwise unconfirmed outcomes also stop; a generic `ValueError` is not treated as proof that the server rejected the write. `NoteValidationError`, a `ValueError` subclass, identifies only checks performed before network delivery. Pausing is checked again before each delivery attempt.

A failed or partially successful turn reports degraded extraction and retains its confirmed-save count. A commit whose response cannot be confirmed is not counted as a confirmed save, even if the note is present. Diagnostics describe incomplete extraction rather than incorrectly saying the model never read the turn. Error status and logs expose error classes or codes, not response bodies. This adds bounded in-process delivery recovery, not a durable extraction queue or crash replay; raw conversation capture remains separate.

## Verification

The final local group passed **92 tests**, covering delivery faults, source deletion/correction guards, note formatting and legacy helper compatibility, diagnostics and companion dependency boundaries. The initial repaired subset passed 25 checks before the explicit 403/idempotency-409 cases were added. The final four launcher-pin/matrix guards, Ruff and diff checks pass. An independent read-only review found no remaining issue in the frozen request identity, partial accounting or uncertain-response handling.

The real HTTP tests cover transient 429/503, timeout before and after commit, lost replacement responses without duplicate feelings, erasure before retry, malformed successful JSON/shape, lost responses on every attempt, partial success followed by exhaustion, pause between attempts, local validation, explicit API rejection and permission/idempotency rejection. Each asserts the provider call count where applicable; note delivery does not issue another provider request. All provider responses in these checks are deterministic in-process stubs; there are no paid or subscription evaluation calls.

## Exact-runtime installation and fullscreen qualification

Fresh launcher installation, upgrade, restart, MCP, proxy, companion preservation and backup/restore passed **49/49 checks**. Both installed homes match all **187 runtime inputs**, with build `ccab88610a3fdabeb8f127a14b140c93d1a43e41d6c0c47f89c6b384d0fb4928` and unchanged schema `e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`. Four profiles and eight ports closed. An interpreter bound to the actual installed package then passed **42 delivery, notes, typed-note and architecture tests**; its database stopped and temporary profile was removed.

The unchanged closed/open/open/closed R5 protocol passed **36/36 windows**, with **4,080 nonempty measured recalls**. Worst individual-window p95 was **250.06 ms serial, 299.14 ms for eight workers on one brain and 345.90 ms for eight brains**, below the existing 500/1,000/600 ms limits. The retained keyword fixture, three cycles per phase, 21 queries per worker with the first discarded, fresh API per phase and normal polling were unchanged.

Chromium 153.0.8010.12 used Apple M4 Metal rendering at 1,280 × 900, DPR 1. Both visible open phases matched **187 nodes and 71 edges** against the structural API before and after measurement. Animation advanced 981 and 996 frames; there were no page errors or external requests. Source and driver hashes stayed unchanged and all ports closed. These measurements qualify reference-fixture overhead; they do not establish a speedup from this reliability repair, model quality or arbitrary memory capacity.

[Retained failures, tests, installed results, screenshots and predecessor CI](evidence/maturity-extraction-delivery-2026-11-07/manifest.json) preserve exact source identities in 123 hashed payloads, with zero owned-profile credential matches. Completed synthetic test profiles were removed only after their processes and ports stopped; raw logs remain archived. No paid provider or subscription evaluation ran.

## CI and release status

Current integration candidate `341f4e8`, runtime `6c47349`, remains frozen while its existing CI finishes. Its native run `42352865258` has passed all five platforms; full Verify `42352865220` is still running. This new repair is on its isolated personal branch until qualification and prior CI closeout are complete. No CI was cancelled to obtain a passing result.

The previous [source-fence qualification](maturity-extraction-sources-2026-11-07.md) keeps its own exact runtime and retained architecture-guard failure. R4 still fails and C5 is incomplete after the [third behavioral attempt](maturity-third-attempt-2026-11-06.md). Fresh provider/subscription behavioral acceptance requires a new authorization. Main merge, tagging and release remain frozen.
