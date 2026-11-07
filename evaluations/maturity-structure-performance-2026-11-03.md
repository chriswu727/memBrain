# Stored topology and performance follow-up, 2026-11-03

Publication remains frozen. This change projects actual stored memory structure into the 2D/3D views and removes redundant relation queries from recall. Eight-brain R5 still fails. No paid or subscription-backed model evaluation was run.

Runtime: `84e973a8686ee6716bcf11123498a914a28db804`; all nine launchers use that pin. Source/pin commit `9bc9893c8d0129425d486b000e486a49712130df` was measured. An experimental validation memo was subsequently introduced at `20bca13`/pin `488d297`, then **reverted** through `5874e91a5606d3347c27c27325e31081d5bc91a4`. A file diff confirms that `5874e91` has exactly the runtime source and `pyproject.toml` of `84e973a`. The later installation-runner fix changes no runtime or launcher pin.

Raw JSON, hashes and compressed logs/reproduction harnesses: [evidence directory](maturity-structure-2026-11-03/). Local originals remain under `/Users/yichen/tmp/membrain-neural-evidence-20261103`.

## What the visualization represents

The opt-in authenticated `GET /v1/brains/{brain_id}/memory-map?structure=true` and Python `memory_map(structure=True)` return `memory-structure-v1`. Legacy callers retain the original default response. The memory page requests the structural graph by default.

Nodes include notes, original messages, attached feelings, current learned assertion versions, directly referenced older assertion versions, consolidated episodes and cross-episode patterns. Edges come from recorded evidence/derivation references, episode membership, pattern sources, associations and belief relations. Revision IDs and relation kinds are preserved. Dependency/scope generations and durable sequence identify the read snapshot.

The inspector, hologram and 2D fallback use the same bounded payload identities and layout. Structural layout uses deterministic adjacency passes over actual returned edges; changing recorded links changes placement. Decorative per-node dendritic branches are disabled for structural payloads. Brain shell, cortical filaments and projector remain presentation geometry. Travelling signals are simulated; neither these signals nor positions claim to be biological anatomy or live agent execution telemetry.

Reads reuse one transaction and brain lock, preserve ownership/deletion/recovery rules, and perform no learning or reinforcement. Sensitivity is resolved against surviving source dependencies before visible source nodes are bounded, including sensitive notes outside the returned sample. Source content and dependent records are masked by default. Existing companion development remains a separate graph. Working state and complete familiarity aggregates are not projected. The map is a bounded sample (at most 500 nodes/1,000 edges), not the entire database or a capacity claim.

## Recall optimization and its limits

The belief loader probes the selected endpoint hashes once to identify unlinked candidates. It skips the former per-seed relation query only for candidates proven unlinked in that transaction. Linked and newly discovered closure endpoints retain full checks. There is no cross-request cache and no reduction in validation, retrieval budget or candidate semantics.

On the same retained 1k fixture, a direct core profile fell from 450 to 145 `Connection.execute` calls over five recalls (90 to 29 per recall). That is a scoped SQL-call observation, not an end-to-end latency guarantee.

The unchanged public R5 harness seeded eight brains with 1,000 keyword messages each and 100 notes in brain zero. Indexing settled first; semantic recall was off; model calls were zero; visualization was unloaded. Each worker ran 21 queries and discarded its first. All 340 measured recalls were nonempty. [Active runtime samples](maturity-structure-2026-11-03/recall-active.json):

| Operation | Median | p95 | Unchanged target |
| --- | --- | --- | --- |
| Serial recall, 20 samples | 113.62 ms | 127.57 ms | <500 ms: pass |
| Same brain, eight workers, 160 samples | 683.16 ms | 757.01 ms | ≤1,000 ms: pass |
| Eight brains, eight workers, 160 samples | 688.28 ms | 728.24 ms | ≤600 ms: **fail** |

The benchmark exited 1. These random-fixture results alone do not establish a stable end-to-end improvement over earlier source runs. Open-versus-closed visualization recall remains unmeasured.

### Rejected validation memo

The memo candidate passed correctness checks and improved an isolated validation microbenchmark, but its separate canonical R5 run still failed: serial/same-brain/eight-brain p95 126.75/774.95/801.29 ms. A fixed-corpus HTTP ABBA comparison also showed worse tails:

| Phase | Variant | Samples | Median | p95 |
| --- | --- | --- | --- | --- |
| 1 | Reference | 160 | 687.65 ms | 729.00 ms |
| 2 | Memo | 160 | 653.37 ms | 792.92 ms |
| 3 | Memo | 160 | 669.39 ms | 816.17 ms |
| 4 | Reference | 160 | 705.74 ms | 773.07 ms |

The isolated child reference switched back to `Draft202012Validator` using the same linked schema; corpus, protocol and service setup were otherwise held fixed. The memo was reverted, rather than shipping a microbenchmark improvement that worsened observed HTTP tail latency. [Raw comparison](maturity-structure-2026-11-03/validation-abba-rejected.json) and [rejected patch](contract-property-memo-rejected.patch) are retained. The patch is historical evidence, not an instruction to apply it.

## Structural API and actual topology rendering

The structural API used the same fictional 1k-message database fixture after indexing settled. Each size used 21 public requests, discarding its first; no retry or model call. All 40 measured requests succeeded and every returned edge endpoint was present.

| Requested node/edge limit | Actual nodes/edges | Median | p95 | Maximum |
| --- | --- | --- | --- | --- |
| 200/400 | 185/66 | 22.25 ms | 31.80 ms | **301.88 ms** |
| 500/1,000 | 416/166 | 27.85 ms | 28.76 ms | 37.60 ms |

The outlier is retained. These are settled-index samples, not indexing-active or maximum-capacity acceptance. [API samples](maturity-structure-2026-11-03/structure-api.json).

Headed Chromium 153 on Apple M4/Metal, 1280×900/DPR1, rendered those exact API payloads under the real CSP. Input-to-frame p95 was 29.9/28.6 ms; pick-to-detail p95 2.0/5.7 ms. Inspector idle for ten seconds and hidden for two seconds produced zero frames/callbacks. The animated hologram ran at 27.58/27.38 fps over five seconds, paused with zero frames and released its renderer on close. IDs/edges matched the API; no page errors. This is **not** a dense 500-node/1,000-edge test or a 60-fps claim. [Hardware report](maturity-structure-2026-11-03/structure-render-mac.json).

## Functional and installation verification

- Active runtime: **190 passed**, zero failed/skipped (68.94 s), covering real PostgreSQL structural graphs, privacy/deletion, exact browser parity, existing memory/companion pages, hologram, locking, belief loading and static/matrix checks. Earlier failed authoring runs are retained: two backend fixture mistakes, then one stale unavailable-layer UI expectation. They were corrected without reducing runtime checks.
- Post-revert contracts, release-install runner, installation pins and maturity matrix: **38 passed**, zero failed/skipped. A preceding command used the nonexistent plural filename `test_installation_pins.py`, exited 4 and ran no tests; the corrected command used `test_installation_pin.py`.
- TypeScript: **44 passed**, strict typecheck clean. Ruff and JavaScript syntax clean; sdist/wheel built locally, not published. The 229-pass experimental-memo run in the archive is historical and is not the active-runtime test claim.
- First clean-home install attempt: **29 passed, one failed, incomplete**. The frozen companion baseline restarts after its asynchronous model download. Its fixture writes hit that restart window. Current runtime already activates in place. The runner now waits for the baseline's own download marker to disappear **and** service readiness before writing state; timeout remains an error. Both old baselines and all existing checks are unchanged. The runner group passed **22 checks**. [Original failure](maturity-structure-2026-11-03/install-first-failed.json).
- Fresh rerun: **49/49 passed, completed**. Upgrade, cross-session recall, MCP corrections/deletion, restart, stub proxy and companion backup/restore/activation passed at the active runtime pin. [Full result](maturity-structure-2026-11-03/install-settled.json).
- Independent installed interpreter/API/browser smoke completed. **165 package/resource/migration files matched byte for byte**, with no missing, mismatched or unexpected files. Both graph layers, exact API/3D identities and 2D fallback worked; no page errors or external requests. The fixture service stopped with exit 0. [Installed-package proof](maturity-structure-2026-11-03/installed-package.json).

Earlier GitHub Verify run [41772764696](https://github.com/chriswu727/memBrain/actions/runs/41772764696) failed with 6,583 passed, six skipped and one warning. Its privacy assertion searched `9932` anywhere in JSON and matched those digits in a random recall UUID while `items` was empty. The fixture now checks `erase-sensitive-content-9932`, preserving the privacy assertion without UUID collisions. This failure is not relabeled as a passing run. At the final observation, full CI [41781489080](https://github.com/chriswu727/memBrain/actions/runs/41781489080) at `5874e91` was still running, and the runner/test follow-up `6da38bce3630341f1646c65076c0fd80a02abec4` had [41783419996](https://github.com/chriswu727/memBrain/actions/runs/41783419996) pending. Local scoped checks do not substitute for a completed full CI result.

## Remaining release gates

Eight-brain R5, visualization-open recall comparison, a final combined full run/review and real R4/C5 behavioural acceptance remain open. Six historical R4 failures remain failures. Paid/subscription-backed evaluations remain unapproved; the 280 CNY proposal is a draft. The separate C5 bookkeeping patch handoff remains pending integration. No main merge, release tag, GitHub release or PyPI publication is authorized by this evidence.
