# Private-path reads and R5 qualification, 2026-11-04

Source/launcher candidate: `53d7e323219a40f670ef574e45c2c36e3f32d4ee`. All nine launchers pin runtime `d4d71262ab1c7d76600082b9c53b10144bb08a00`. **The fresh canonical benchmark and every canonical-size window of a completed fullscreen comparison pass the unchanged R5 recall bars.** Fresh Mac installation passes 49/49; 165 installed files match and the installed graph journey passes. Full current CI passes 7,000 Python tests with zero skips, 44 TypeScript tests, strict types, Ruff and package builds; real R4/C5 and final independent review remain unaccepted. Nothing has been merged to the default branch or published.

[Measurements, provenance, failure logs and scripts](maturity-private-paths-2026-11-04/) are retained with verified file/archive-member hashes. Larger raw comparisons and the public practice outputs are in the archive. Original local files are under `/Users/yichen/tmp/membrain-tail-attribution-20261104`. The [previous runtime's failures](maturity-bounded-recall-2026-11-04.md), including its 671.06/605.36 ms windows, remain failures. No paid provider or subscription-backed behavioural test was called.

## Finding and change

An actual HTTP service diagnostic samples Python stacks/process CPU and PostgreSQL waits during 1,440 nonempty keyword recalls. It records 824 samples, 496 unique stacks and no dropped samples/stacks. Sampler-thread CPU is 0.06465 seconds over 88.19 seconds of observed wall time; the largest sampling gap is 161.51 ms. The diagnostic p95 is 531.13 ms and maximum 1,025.21 ms, not a qualification result.

Many waiting threads are in the shared recovery-registry profile lock; active stacks also show registry opening and filesystem metadata operations. Stack counts of blocked threads are **not CPU percentages**. They identify a testable hotspot, not a sole-cause explanation for every historical stall. The existing registry opens serialize across brains, including installation/head and pending-erasure checks.

`_private` previously called `chmod` on every POSIX read even when the mode was already correct. It now reads and checks the current metadata on every invocation and writes permissions only when they differ from `0600` for a file or `0700` for a directory. Symlink/type checks, exclusive ownership, hard-link rejection and descriptor/path replacement checks remain. Windows still applies its owner ACL every time. Registry locks, SQLite transactions, activation/receipt/erasure checks, schema validation, retrieval quality and every candidate/context budget are unchanged. There is no permission, record or result cache.

Six new regression cases check repeated stable reads, repair after permissions change, foreign ownership, hard links, symlinks and the unchanged Windows ACL path. Before the fix, the two redundant-write cases fail and the four safety cases pass; the final profile/registry group passes **83**, and the recovery/erasure/lock/quarantine/backup/upgrade group passes **74**. Hook timeout/spooling guards pass seven cases; pin/matrix checks pass four; Ruff and diff checks pass. The Windows case exercises the ACL dispatch with a stub, not a new real-Windows certification.

## Controlled HTTP comparison

Four fresh services use the same settled eight-brain corpus, no visualizer and no model calls. Each worker runs 21 queries and discards its first; the remaining 160 contexts per phase are nonempty. The prototype function matches the committed runtime byte for byte. **All 640 rendered-context SHA-256 values match across phases.**

| Phase | Implementation | Median | p95 |
| --- | --- | --- | --- |
| 1 | Reference, unconditional permission writes | 466.03 ms | 528.25 ms |
| 2 | Candidate, repair permissions when needed | 464.53 ms | 502.91 ms |
| 3 | Candidate | 465.80 ms | 495.20 ms |
| 4 | Reference | 477.53 ms | 522.48 ms |

These measurements show improvement on this comparison, not a universal latency or total-memory guarantee.

## Fresh canonical R5

The unchanged public benchmark builds a new disposable installation: eight brains with 1,000 keyword messages each, 100 notes in brain zero, indexing caught up, semantic model off and no model calls. It uses one service, 21 queries per worker with the first discarded, excluding client startup/reply generation. Machine: Apple M4, 10 cores, macOS 15.7.4, Python 3.12.13, embedded PostgreSQL 16.2.

| Workload | Samples/nonempty | p95 | Unchanged bar |
| --- | --- | --- | --- |
| Serial | 20/20 | 102.66 ms | <500 ms: pass |
| One brain, eight workers | 160/160 | 491.68 ms | ≤1,000 ms: pass |
| Eight brains, eight workers | 160/160 | 538.89 ms | ≤600 ms: pass |

The benchmark exits 0; map requests at 200/500 nodes complete without errors. The completed synthetic profile and registry were cold-archived after confirming both ports closed, with all 1,463 regular files checked by SHA-256, before removing that disposable profile to recover disk space. The private archive contains fixture credentials and is deliberately excluded from Git; its hash is retained. Local embedding models were preserved.

## Strict fullscreen qualification

Headed Chromium 153 uses Apple M4/Metal at 1280×900/DPR1, with normal status polling and a fresh API process per phase. Three cycles per phase each run the unchanged serial/one-brain8/eight-brains8 workloads. **Every canonical-size cycle and every phase aggregate must pass**; the script exits nonzero for any failed window or screenshot. No samples beyond the declared first-query warmups are discarded. Animation is paused only after measurement for screenshots.

| Phase | Serial p95, 60 samples | One-brain8 p95, 480 samples | Eight-brains8 p95, 480 samples | Eight-brain window p95 values, 160 samples each |
| --- | --- | --- | --- | --- |
| Closed | 111.90 ms | 509.50 ms | 499.63 ms | 510.87 / 501.42 / 490.86 ms |
| Fullscreen open | 119.63 ms | 527.21 ms | 530.60 ms | 559.07 / 504.92 / 528.56 ms |
| Fullscreen open | 116.88 ms | 564.85 ms | 521.49 ms | 523.28 / 517.44 / 521.18 ms |
| Closed | 113.15 ms | 510.28 ms | 503.98 ms | 505.93 / 506.01 / 497.24 ms |

The comparison completes and exits 0. All **4,080 measured recalls are nonempty**; all 36 workload windows pass, including all 12 eight-brain windows. Both open phases match the API's actual 182-node/66-edge payload before/after measurement, render 2,035/2,055 frames, stay visible and observe six real status/model/recording polls each. There are no page errors, external requests, artifact failures or unexpected closes. The visualizer's contours/signals remain illustrations; memory IDs/links reflect the bounded stored-record projection.

## Installation and public rehearsal

The current pin passes **49/49** clean-home Mac checks with the unchanged frozen basic/companion baselines. The installed interpreter/API/browser checks **165 matching runtime/resource/migration files**, with no missing or unexpected files; both graph layers, fullscreen 3D, accepted persona development and 2D fallback work. Page errors and external requests are zero; cleanup exits 0. Nine task-owned profiles' API/database ports are independently confirmed closed, including the two public practice arms.

The public C5 practice runs `P`, `E` and `F` directly with deterministic host/extractor stubs, keyword recall, no model cache or provider credentials, and the harness's refusal of non-loopback sockets. All arms finish with exit 0. The checker passes **250 checks** across persona, feelings, mood, relationship, page actions, reference history, scenario clock, tools, network, recording and run completeness. Strict validity reports `valid: true`, no problems and no empty-reply retries. P2 proposals and deletion cascade are exercised. This proves rehearsal mechanics, not real model behaviour or the live frozen-manifest driver's acceptance.

## Remaining gates

[Verify 41897991336](https://github.com/chriswu727/memBrain/actions/runs/41897991336) passes on current source `53d7e32`: **7,000 Python tests, zero skips, three warnings, 1,232.10 seconds; 44 TypeScript tests, strict types, Ruff and sdist/wheel builds pass**. All four real Docker desktop/recovery/upgrade/standalone-chat journeys and real pinned local-model/activation cases pass. The full decoded log is archived; the prior runtime's 6,994-pass result remains historical. Final independent code/plan review remains pending. A bounded Claude Desktop review was attempted, but the interaction interface could not locate an operable target window; no review request was delivered, no new Claude session was opened and no review result is claimed.

R4/C5 still require a separately approved frozen real-model attempt on new held-out scenarios. The 280 CNY draft and subscription scenario-author/reviewer use remain unapproved. Current measurements do not establish semantic-recall latency, maximum storage capacity, biological equivalence or real-host interpretation of personality, feelings, boundaries and resets. Default-branch merge, tags and publication remain frozen pending the remaining acceptance and review.
