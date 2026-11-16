# Seventh maturity attempt (maturity-20261116a): preparation report

Prepared and frozen on 2026-11-16 (06:24–06:55 UTC). No paid call, no API key read, no push, no PR. Nothing changed
in `/home/yichen/src/memBrain` or in the sixth attempt's directories. `control/freeze-review.json` was not written.

## Frozen state

- SOURCE `f20a074a6f95ab0da42fb2e8080663f4aea7a96e` = local and GitHub head of `integration/maturity-candidate`; main
  tree clean; no test running at start; 57 GB free.
- Clone `/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/clone`, branch `acceptance/maturity-20261116a`.
  **Frozen head `c5232a043d650824c7d12982893d876e88d57877`** (one commit on SOURCE: the binding
  `evaluations/maturity-acceptance-execution-2026-11-16.md`, sha256
  `f3dddd14af8c63fb184280bc30d44f9cd5e1488e406a905c6cc9b866317f007c`). Tree clean; private root
  `evaluations/.maturity-heldout-20261116a/` mode 700, git-excluded, 0 tracked files.
- **Manifest** `evaluations/.maturity-heldout-20261116a/control/manifest.json`: sha256
  **`a27d7ca878cd86483b79e0e682fb788847bafa4f41647b98b44304216aa534de`**, **437 files** (430 tracked + 7 private:
  allowed-models, two assignments, two receipts, two scenarios), **persona `estj`** (seed `maturity-20261116a`),
  **order `s1b`, `s2b`**, no practice mark. All 437 hashes re-verified (0 mismatches). freeze.py: `--binding` and
  `--allowed-models` given, exit 0.
- `control/preparation.json` sha256 `f4e40a7f5ef67c8f22256c140536448e1c1dcf2abe369975ca06c7f4e8656dfe` (mode 600).
- Runtime pin `a85ca152` (pin commit `4513d133`), 9 launchers; `src/` and `migrations/` identical to SOURCE. Build
  `6ad5f2fbb4bb7e078a53b38e9ff0c9cea92343f3b964b381f6303f75aca0bf9d`, schema
  `3a94d7b6ea6bfba8ff8a4d920aa83001123922f4f90b0a9d6430ef1997b6166d` (same schema as the sixth attempt). CPython 3.12.16
  (binary `23bc148d…82b5`), uv 0.13.6, `uv sync --frozen`, 79 packages, no system site-packages; `uv.lock`
  `0bc566ca…7e92`. Embedding model digests and ONNX Runtime 1.31.1 are the same as the sixth attempt's.
- Measured on this source (rehearsal `tools.json`): 14 tools offered (same names and order as the sixth attempt),
  17,217 schema characters (sixth: 16,989), server instructions 1,332 characters, sha256 `bb95409e…82a0` (unchanged),
  skill not in the prompt; SKILL.md 17,488 characters with front matter, 16,919 without (sixth by the same method:
  17,164 / 16,595).
- Free disk 60.2 GB; ports 8893 and 55533 free and bindable.

## Sessions (launcher JSON only): 6 Sonnet sessions, no probe

| # | Session | Launcher JSON |
| --- | --- | --- |
| 1 | s1b author 1 | `{"cases": 11, "key": "s1b", "loads": true, "precheck": {"codes": [], "ok": true}, "produced": true, "role": "author", "session": 1, "session_exit": 0, "sessions": 17, "sha256": "e08a4f4aa1106c7a637fc88604dcbc4def9d2d503a36bcff5576b99bc57fd38a", "turns": 61}` |
| 2 | s1b reviewer 1 | `{"approved": false, "blocking": 1, "findings": 6, "findings_sha256": "dda46dd1…a103c", "key": "s1b", "produced": true, "review_sha256": "daa811a7…2838", "reviewed_sha256": "e08a4f4a…d38a", "role": "reviewer", "session": 1, "session_exit": 0}` |
| 3 | s1b fixer 1 | `{"applied": 6, "cases": 11, …, "precheck": {"codes": [], "ok": true}, "session": 1, "session_exit": 0, "sessions": 17, "sha256": "c3feb22af4d00aa35b1775287681185fdb4e4ba0dc258470a3d0aea28b94b8cf", "turns": 61}` |
| 4 | s1b reviewer 2 | `{"approved": false, "blocking": 1, "findings": 7, "findings_sha256": "f33dc208…493f", "review_sha256": "d1a7e72f…af6", "reviewed_sha256": "c3feb22a…b8cf", "session": 2, "session_exit": 0}` |
| 5 | s1b fixer 2 | `{"applied": 7, "cases": 11, …, "precheck": {"codes": [], "ok": true}, "session": 2, "session_exit": 0, "sessions": 17, "sha256": "aec260c21694c4a9c10fde3825fbe04e1fba5998894fc572449875140c8beab6", "turns": 61}` |
| 6 | s1b reviewer 3 | `{"approved": true, "blocking": 0, "findings": 4, "findings_sha256": "a170bcf3…70cd6", "receipt_sha256": "8b304844c36fbfa328ed30d9a9682e0c582dd3402eab74317fa56f91e5eaef36", "review_sha256": "f780dcf7…c086b", "reviewed_sha256": "aec260c2…eab6", "session": 3, "session_exit": 0}` |

Full lines: `launch-s1b-*.out` in the run root and in `preparation.json` (`session_table`). Approved in the third
and last allowed round; no `s1c` restart. The 4 minor findings of reviewer 3 were not applied (a fix would need a new
review), as with `s2b`'s 6 minor findings in the sixth attempt. Every working directory was emptied with `find
-mindepth 1 -delete` right after its session, unopened; empty directories kept. The six session logs (35–56 bytes
each by size) were never opened.

## Scenarios and receipts

- **S1 `s1b`** (new): `aec260c21694c4a9c10fde3825fbe04e1fba5998894fc572449875140c8beab6`, 17 sessions, 61 turns, 11
  cases; receipt `control/s1b-review-approved.json` `8b304844c36fbfa328ed30d9a9682e0c582dd3402eab74317fa56f91e5eaef36`;
  assignment `control/s1b-assignment.md` byte-identical to the sixth's `s1-assignment.md` (`4ea5bc56…e634`).
- **S2 `s2b`** (reused): `4c6c0404fab7de758f9592fd65b76c3d4f949761a85e52b5d3c902b214a15358`, 19 sessions, 63 turns,
  11 cases; receipt `f1a0a119a7cd99df06e0cb51c7a0ed2fd8cab771354fc0725c49be74b3b7bdff`; both match the sixth binding.
  Copied by path (`s2b/` with its review-1.json and findings-1.md, the receipt, the assignment) with `cp -a`, never
  displayed. The receipt binds only key, sha256, counts and review session (no attempt or private root), so freeze.py
  accepted it unchanged and **no new reviewer session was needed**.
- Both pass `c5-precheck.py --r4` on this source with no code.

## Novelty (threshold 10% largest 8-gram overlap, as in the sixth binding)

- `s1b` vs the 21 public scenarios at SOURCE (15,589 recorded hashes): `sha256_new` true, largest 0.07%, union 0.07%,
  2,811 8-grams, ok.
- `s1b` with the sixth attempt's `s1`, unused `s2` and `s2b` added as earlier files: largest 0.28%, union of all 24
  0.36%, new, ok; alone 0.28% (`s1`), 0.00% (`s2`), 0.00% (`s2b`).
- `s2b` vs the public set at SOURCE: largest 0.43%, union 0.76%, 4,612 8-grams (unchanged from the sixth), within
  the threshold, but **`sha256_new` false and `ok` false**: its hash is recorded at SOURCE in the sixth binding (the
  only file that records it). Expected and stated in the binding.

## Tests and rehearsals (clone, keys and `C5_*` unset, under the shared lock)

- Focused tests: **760 passed, 0 failed, 0 skipped**, 2 existing fork warnings, 500 s (driver 152, review hardening
  157, review pipeline 128, scenario path 18, kit 71, c5 harness 47, hardening 76, supervisor 7, billing guard 55,
  proposal selection 11, pause request 34, novelty 4). Database stopped; database, pytest and recovery directories
  removed; logs and junit kept.
- Stub rehearsal before freezing: ok; freeze 432 files (practice); driver complete, both valid; dry-run checks 138/138
  each; gate R4 true, gated `P`, arms `P`,`F`; 0 network events; ledger unchanged, 0 requests; ports closed; 2
  databases removed; stderr empty.
- Stub rehearsal on the frozen head (extra, as in the sixth attempt): the same results with 433 files; its 430
  tracked hashes equal the real manifest's (430/430); tree clean afterwards.

## Deviations from the brief, refusals, content exposure

- **Order:** the s1b author was started while the focused tests and the pre-freeze rehearsal were still running (they
  do not depend on each other). Every pytest ran under the lock.
- **Novelty with extra earlier files:** `novelty.py` has no option for earlier files by path, so a wrapper outside the
  repository (`novelty_with_extras.py`, sha256 `3ce86983…40f4`) imports the kit's functions unchanged and prints only
  numbers and booleans. No tooling was changed.
- **Not repeated:** the isolation probe (same CLI 2.1.322, command and kit); the full suite (the lead's 4,140-pass run
  on `4513d133` is cited).
- **Run script additions** beyond the brief's list: refuse unless `control/freeze-review.json` has
  `execution_may_start: true`, the owned ports are free, at least 5 GiB is free, and no `runs/` exists. The expected
  head and manifest hash are read from `control/preparation.json` instead of being hard-coded, so the binding could
  include the script verbatim before freezing (verified identical by diff). `run-live.sh` sha256 `ffd12b2f…9d27`,
  `balance.py` `b34790e6…ad7a1` (tested only without a key: it printed `{"error": "KeyError"}`, no request).
- **Binding:** the manifest's mode was set to 600 after freezing (bytes unchanged). The sixth binding's misprinted
  fixer-brief hash end (`f124`, really `f114`) is corrected in the new one.
- **Refusals:** none. **Content printed that should not have been:** none. Only hashes, counts, codes, the
  neutral assignment files (read in the sixth attempt's control directory, as allowed) and public practice output were
  seen.

## Before the paid run

1. Independent freeze review writes `control/freeze-review.json` with `execution_may_start` (the run script refuses
   without it).
2. Owner's approval of this paid run (80 CNY ceiling, subscription use for blind scoring and the final review),
   recorded separately.
3. Provider revalidation on the day of the run (`control/provider-revalidation.json`).
4. Start `run-live.sh` detached as the binding shows. It creates the ledger, reads the balances, runs the driver,
   cleans up and checks the ports. Then do validity per scenario (and report `host-pauses.jsonl` and tool-call-markup
   counts), scoring, the gate and the final review.
