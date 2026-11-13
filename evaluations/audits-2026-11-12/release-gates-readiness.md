# memBrain release gates: readiness brief

Date: 2026-11-12. Branch `integration/maturity-candidate`, head `5b7ec232` (launchers pinned to runtime `fa88a4b`). Read-only review of the repository. No test, service, database, network call or model call was made. File references are relative to `/home/yichen/src/memBrain` unless absolute. Statements marked **Judgement** are mine and are not recorded in the repository.

## Summary

- **R4** has never passed. Eleven attempts exist in two numberings: the README's v1 attempts 1 to 6 (`README.md:241-252`) and the maturity attempts 1 to 5 (`evaluations/maturity-*attempt*`). Only the fifth maturity attempt produced a scored result on the current protocol in which one gated arm passed: plugin `P` 20, extraction `E` 16 with one memory-caused privacy reply, reference `F` 15.5 (`evaluations/maturity-fifth-attempt-2026-11-07.md:9-13`). That result covers runtime `7902c16e`, which is many recall changes behind the pin, so it is not evidence for the pinned runtime (`docs/releasing.md:5`).
- **Under the main-line decision**, only `P` (the host's own AI with hooks and memory tools) remains a meaningful gated arm, against `F`. The pass rule still works for one arm, but the acceptance contract, the plan and three harness/scoring files name `E` explicitly and must change, with free tests and an independent review. The harness does not yet offer `memory_consolidate`, although the session notice it injects tells the host to call it.
- **A concrete risk found by code reading:** the consolidation batch hands the host AI up to 40 earlier user messages as raw text, with no sensitivity or boundary filtering (`src/membrain/message_cues.py:164-171`, `:197-210`; `src/membrain/mcp_server.py:225-237`). Under the fixed attribution rules, a reply that repeats such content counts as memory-caused (`evaluations/acceptance-review/attribute.md:16-19`). This is untested; it should be checked with a public regression before any paid attempt.
- **C5** has never run to completion: C1 stopped twice on `page_action_failed` (third and fifth attempts) with the cause unestablished, and C2 never ran.
- **R5** needs the owner's Apple M4 Mac: the protocol uses headed Chromium with the Metal renderer and a retained fixture installation on that Mac, and the driver script exists only as gzipped evidence with hard-coded Mac paths. The plan draft makes the R5 bar (matrix gap 20) a prerequisite of a paid attempt.
- **Estimated cost of one R4 attempt (S1 and S2, arms `P` and `F` only, DeepSeek host as before):** about 6 to 15 CNY actually billed (off-peak to peak), about 30 to 40 CNY booked by the conservative guard; a ceiling of about 100 CNY is advisable because each in-flight request reserves 20.05 CNY. Plus about 65 to 75 subscription agent runs for authorship, review and scoring. Derivation in [Appendix A](#appendix-a-cost-derivation).
- **Earliest sensible attempt (Judgement):** not now. After the harness offers consolidation and passes the free dry run, the consolidation privacy question is settled, the recall path is frozen, and the Mac has run R1 and R5 on that frozen runtime.

## 1. R4 as it stands

### 1.1 What is tested

| Element | Specification | Source |
| --- | --- | --- |
| Scenarios | Two new held-out scenarios (S1, S2), each 11 cases and about 60 to 66 user turns; one mainly English with one session in another language, one mainly Chinese with one session in English. Every session states a UTC date and time, at least one hour apart | `evaluations/maturity-paid-acceptance-plan-draft.md:37-48`; `architecture/v1-acceptance.md:58` |
| Fifth attempt sizes | S1 63 turns, S2 65 turns, 11 cases each | `evaluations/maturity-fifth-attempt-2026-11-07.md:52`; freeze review in `evaluations/evidence/maturity-fifth-attempt-2026-11-07/control/freeze-review.json.gz` |
| Arms | `P` plugin path: hooks and MCP tools in process (`memory_recall`, `memory_note`, `memory_boundary`, `memory_pause`, `memory_resume`), skill text and session context in the system prompt; `E` proxy: `ChatMemory` without tools plus note extraction after every turn; `F` reference: whole history in the prompt | `evaluations/maturity-paid-acceptance-plan-draft.md:62-66`; `evaluations/c5-harness.py:12-13`, `:53`, `:950-953`, `:1018`, `:1034-1037` |
| Host model | `deepseek-v4-pro` via `https://api.deepseek.com` for all three arms; the host is a simulated agent, not a real Claude Code or Codex process | `evaluations/c5-harness.py:50`; `README.md:243` |
| Extraction model (`E` only) | `deepseek-flash` | `evaluations/c5-harness.py:950`; `evaluations/maturity-paid-acceptance-plan-draft.md:140` |
| Judge | Subscription agents, Codex in the maturity attempts: 2 first reviewers, 22 second reviewers (one per case), two R5 checkers per candidate type-4 reply, 2 resolution reviewers, two attributors per gated critical reply. The documents do not name the reviewers' model identifier | `evaluations/maturity-acceptance-execution-2026-11-07b.md:3`; `evaluations/maturity-fifth-attempt-2026-11-07.md:15`; rubrics in `evaluations/acceptance-review/first.md`, `recheck.md`, `assistant-claims.md`, `resolve.md`, `attribute.md` |
| Scoring | Per reply 0, 0.5 or 1; a reply with a standing critical error scores 0; totals out of 22. Critical types 1 to 5 (plan stated as done, privacy disclosure, corrected fact used, invented user fact, role-play treated as real) | `evaluations/acceptance-review/first.md:5-17`; `evaluations/v1-2026-11-07-final-acceptance-6.md:13` |
| Pass rule | Each gated arm: total at least `F` minus 1; no memory-caused critical error; no more host-caused critical errors than `F`. Attribution disagreement or a missing answer counts as memory | `architecture/v1-acceptance.md:60-63`; `evaluations/maturity-paid-acceptance-plan-draft.md:93`; implemented in `evaluations/acceptance_review.py:1083-1107` |

### 1.2 How an attempt is run

1. **Approval.** The owner approves a written proposal with a DeepSeek ceiling and subscription use (`evaluations/maturity-fifth-attempt-proposal-2026-11-07.md:13-20`; approval quote at `evaluations/maturity-acceptance-execution-2026-11-07b.md:3`).
2. **Fresh checkout and private root.** A new checkout and a Git-excluded private root, for the fifth attempt `/Users/yichen/tmp/membrain-acceptance-20261107b/` and `evaluations/.maturity-heldout-20261107b/` (`evaluations/maturity-acceptance-execution-2026-11-07b.md:5`, `:13`).
3. **Hidden, newly written inputs.** Fresh isolated authors write each scenario from a neutral brief that gives no product internals, earlier scenarios or results; an independent reviewer writes findings the developer never opens; another agent applies fixes; the developer sees only hashes, the precheck's last line, case prefixes and fix counts (`evaluations/maturity-paid-acceptance-plan-draft.md:54-58`). The author brief, reviewer brief, `freeze.py` and `launch.py` used in the fifth attempt are in the Mac's private root only, not in this repository (manifest entries under `evaluations/.maturity-heldout-20261107b/control/` in `evaluations/evidence/maturity-fifth-attempt-2026-11-07/control/manifest.json.gz`). They must be retrieved from the Mac or rewritten and reviewed.
4. **Pre-checks and freeze.** Revalidate provider prices; create a new ledger with `create_ledger` (`evaluations/evaluation-billing.md:7`); record pin, clean status, unset `MEMBRAIN_SRC`, bindable ports, hashes; freeze runtime, harness, driver, pipeline, review instructions, policy and scenarios (`evaluations/maturity-paid-acceptance-plan-draft.md:140`). `python evaluations/c5-precheck.py SCENARIO.py` checks each scenario by counts only (`evaluations/c5-harness.md:99-105`).
5. **Execution.** `python3 evaluations/acceptance-attempt-driver.py run --manifest M --out OUT_ROOT --live` with `C5_BILLING_LEDGER`, `C5_ATTEMPT_ID`, `C5_BILLING_POLICY_SHA256`, `DEEPSEEK_API_KEY` and `MEMBRAIN_MODEL_CACHE` set (`evaluations/acceptance-attempt-driver.md:5-28`; `evaluations/c5-run-scenario.sh:13-20`). The driver calls `evaluations/c5-run-scenario.sh SCENARIO OUT_ROOT KEY`, which runs the three arms in parallel on ports 8893/55533 (P) and 8894/55534 (E) (`evaluations/c5-run-scenario.sh:83-101`), then `acceptance_review.py validity --scenario ...` on the three run directories. Any invalid scenario stops the attempt; nothing is rerun (`evaluations/acceptance-attempt-driver.md:65-71`).
6. **Scoring.** Blinding (`evaluations/v1-2026-10-29-phase-b-blind.py`), then `validity`, `diagnose`, `verdicts`, first review, `split`, second reviews, `r5-inputs`/`r5-check`, resolution, `tally`, `attribution-inputs`, attribution and `gate` (`evaluations/maturity-paid-acceptance-plan-draft.md:72`; subcommands at `evaluations/acceptance_review.py:1138-1157`). No score is changed by hand (`:146`).
7. **Final independent review** of the frozen source and gate evidence (`evaluations/maturity-acceptance-execution-2026-11-07b.md:15`).

### 1.3 Duration and cost of past attempts

Fifth attempt timeline (UTC, 2026-11-07), from `evaluations/evidence/maturity-fifth-attempt-2026-11-07/control/`: preparation recorded 21:25:03; freeze review 21:52:48; S1 ran 21:52:55 to about 22:03; S2 to about 22:14:35; C1 stopped 22:15:55; final review completed 22:40:22. Paid execution of S1 and S2 took about 22 minutes with three arms in parallel; each arm's own turn time was 6 to 10 minutes per scenario (sum of `seconds` in the archived results). When scenario authorship started is not recorded in what I read.

Host token use in the fifth attempt's valid R4 unit (summed from `evaluations/evidence/maturity-fifth-attempt-2026-11-07/blind/s*/results_*.jsonl.gz`; extraction calls not included):

| Arm | Turns | Prompt tokens | of which cache hits | Output tokens |
| --- | --- | --- | --- | --- |
| P | 128 | 1,515,728 | 1,114,368 | 73,557 |
| E | 128 | 882,560 | 493,056 | 81,419 |
| F | 128 | 989,708 | 706,048 | 96,758 |

| Attempt | Spend | Source |
| --- | --- | --- |
| Maturity 1 (stopped, invalid) | 23.15 CNY guard-booked; balance fell 3.76 CNY | `evaluations/maturity-attempt-stop-2026-11-05.md:15` |
| Maturity 2 (stopped, invalid) | 20.45 CNY settled plus 60.16 CNY unknown reservations; balance fell 4.34 CNY | `evaluations/maturity-second-attempt-stop-2026-11-06.md:9-11` |
| Maturity 3 (R4 failed, C5 incomplete) | 48.08 CNY settled plus 20.05 unknown; balance fell 8.68 CNY | `evaluations/maturity-third-attempt-2026-11-06.md:23` |
| Maturity 4 (stopped, invalid) | 9.93 CNY settled plus 20.05 unknown; balance fell 0.97 CNY | `evaluations/maturity-fourth-attempt-2026-11-07.md:17-26` |
| Maturity 5 (R4 failed, C5 invalid) | 39.63 CNY guard-booked, 597 requests (463 Pro, 134 Flash), no unknowns; balance fell 8.31 CNY (S1 3.86, S2 3.98, C1 partial 0.47) | `evaluations/maturity-fifth-attempt-2026-11-07.md:54`; balance files above |
| v1 attempts 1 to 6 | 27.66 (1); 81.12 for 1 to 4 together; per-scenario 7.47 to 19.42; attempt 6 run 1 invalid 33.45 | `evaluations/v1-2026-11-02-final-acceptance.md:73`; `evaluations/v1-2026-11-05-final-acceptance-4.md:73`; `evaluations/maturity-paid-acceptance-plan-draft.md:100-109`; `evaluations/v1-2026-11-07-final-acceptance-6.md:76-85` |

The guard books every prompt token at the maximum uncached rate (9 CNY per million for `deepseek-v4-pro`, 27 for output) and reserves 20.054016 CNY per request in flight (`evaluations/evaluation-billing.md:16-18`; `evaluations/maturity-paid-acceptance-plan-draft.md:128-133`), so booked amounts are four to five times the billed amount. Peak-hour runs cost about twice off-peak (`evaluations/v1-2026-11-07-final-acceptance-6.md:85`). Every maturity attempt ran under a 280 CNY ceiling.

### 1.4 Why each attempt did not pass

Maturity series (the current protocol, S1/S2 for R4 and C1/C2 for C5):

| Attempt | Runtime | R4 | Reason | Source |
| --- | --- | --- | --- | --- |
| 1 (`maturity-20261105a`) | `cc2a601` | Invalid, unscored | The validity tool rebuilt the scenario path from its stem and lost the private directory (`FileNotFoundError`) after S1 finished; tooling defect, since repaired | `evaluations/maturity-attempt-stop-2026-11-05.md:3-9` |
| 2 (`maturity-20261106a`) | `cc2a601` | Invalid, unscored | S2 stopped at 8/5/5 of 63 turns on `BudgetStop` in F; three requests had unknown billing; the transport cause was not retained | `evaluations/maturity-second-attempt-stop-2026-11-06.md:5-13` |
| 3 (`maturity-20261106b`) | `cc2a601` | **Failed** | P 17.5 against a threshold of 18, with two memory-caused critical replies (type 4) and one host-caused; E 20.5 passed; F 19. C1 stopped on `page_action_failed` | `evaluations/maturity-third-attempt-2026-11-06.md:7-21` |
| 4 (`maturity-20261107`) | `86e7f1f` | Invalid, unscored | S1 session 10: the host had called `memory_pause` and never resumed, so a later turn was not recorded (`turn_not_recorded`), which stops the run | `evaluations/maturity-fourth-attempt-2026-11-07.md:3-11` |
| 5 (`maturity-20261107b`) | `7902c16e` | **Failed** | P 20 passed; E 16 meets the score bar but has one memory-caused type-2 reply (off-the-record content kept in the proxy's raw history and recalled as ordinary history); F 15.5. C1 stopped on `page_action_failed` at session 3, message 1 | `evaluations/maturity-fifth-attempt-2026-11-07.md:7-31`, `:52` |

The proxy off-record gap from attempt 5 was later repaired for direct English and Chinese opening pause commands, with the two public reproductions passing (`evaluations/backend-recording-policy-2026-11-07.md:5`); no paid run has tested it.

v1 series (`README.md:245-252`): 1 memory defects; 2 failed the first rule (20 of 22 and no critical error), which even F could not meet, so the rule was revised (`evaluations/v1-2026-11-03-gate-review.md`); 3 invalid (empty host replies); 4 P failed on one memory-caused reply, E passed; 5 P had three memory-caused replies and E fell below F minus 1 (`evaluations/v1-2026-11-06-final-acceptance-5.md:8-10`); 6 one memory-caused type-4 reply in each arm, mainly the host restating a recalled assistant suggestion as a user fact (`evaluations/v1-2026-11-07-final-acceptance-6.md:7-9`; `README.md:256`).

## 2. What an R4 attempt should now consist of

**Decision on record.** On 2026-11-11 the owner fixed that every function is exercised by the host tool's own AI and that memBrain ships no second AI and asks the user to configure none (`evaluations/host-consolidation-2026-11-11.md:9`).

**Arms that remain meaningful.**
- `P` remains the gated arm. It is the main line: the host's AI uses hooks, the session notice, the skill and the memory tools. The harness host is DeepSeek playing an agent host, which is consistent with the decision as long as it receives every tool a real host receives.
- `F` remains the reference.
- `E` as specified needs a second model (`deepseek-flash` extraction, `evaluations/c5-harness.py:950-953`) and is off the main line. **Judgement:** drop it as a gated arm. The proxy and `ChatMemory` are still listed as shipped surfaces (`architecture/v1-acceptance.md:10`), so the owner must also decide whether the proxy without extraction stays in the release scope. If it stays, it needs its own evidence; a tool-free, extraction-free proxy arm could be added as an ungated or gated arm, but that is a new design choice, not what the documents describe.

**Does the pass rule still apply?** The three conditions apply unchanged to a single gated arm. Re-scoring the fifth attempt with only `P` gated is not available: the rule would change after its result was known, the runtime it covers (`7902c16e`) is no longer pinned (`docs/releasing.md:5`), and the documents require a retry on new scenarios (`architecture/v1-acceptance.md:65`; `evaluations/maturity-paid-acceptance-plan-draft.md:96`).

**Changes required before a paid attempt** (each with a free test, per `evaluations/maturity-paid-acceptance-plan-draft.md:24`):

| Change | Where |
| --- | --- |
| Offer `memory_consolidate` to the host. `TOOLS` lacks it, yet the session context the harness injects asks the host to call it whenever five or more messages wait | `evaluations/c5-harness.py:53`; notice built in `src/membrain/host.py:85-97`, added at `:2091`, `:2107-2108`; harness reads it at `evaluations/c5-harness.py:1018` |
| `memory_recall`'s new `my_replies` parameter reaches the host automatically, because schemas are read from the server; confirm it with a test | `evaluations/c5-harness.py:425-433`; `src/membrain/mcp_server.py:76-90` |
| Review the per-turn tool cap: at most three tool rounds and six calls per turn. A consolidation takes two rounds, leaving one for recall | `evaluations/c5-harness.py:1049-1050` |
| Account for the batch staying in the session transcript: P keeps every tool result for the rest of the session, which raises prompt tokens | `evaluations/c5-harness.py:1131` |
| Remove or un-gate `E`: arm list, run script, validity, tally and gate all hard-code P/E/F | `evaluations/acceptance-attempt-driver.py:63`; `evaluations/c5-run-scenario.sh:84`; `evaluations/acceptance_review.py:1004-1019`, `:1083`, `:1096-1107` |
| Reviewer rubrics say "three replies labelled A–C"; with two arms the sheets and rubrics change | `evaluations/acceptance-review/first.md:3`; `evaluations/acceptance-review/recheck.md:1` (the blind script already takes the arm list as an argument, `evaluations/v1-2026-10-29-phase-b-blind.py:12`) |
| Extend the public practice scenario's stub host with a consolidation call and a `my_replies` recall, and rerun the zero-model dry run (250 checks last time) | `evaluations/c5-harness.md:107-118`; `evaluations/maturity-proposal-selection-2026-11-06.md:13` |
| Settle the consolidation privacy path (see below) | `src/membrain/message_cues.py:164-218` |
| Amend the contract and plan: `architecture/v1-acceptance.md:59`, `docs/releasing.md:130`, `evaluations/maturity-paid-acceptance-plan-draft.md:62-66`, `:93`, `:100-135` | |

**Consolidation privacy risk (from code reading, untested).** `pending` selects the user's unreviewed current messages with no filter for sensitive content or boundaries (`src/membrain/message_cues.py:164-171`, `:197-210`), and `memory_consolidate` returns their text to the host (`src/membrain/mcp_server.py:225-237`). The only markers removed are on the cues the host writes back (`src/membrain/message_cues.py:30`, `:43`). Ordinary recall keeps a bounded topic out of later context (`evaluations/c5-harness.md:138`). If a host then repeats a private or bounded fact it read in a batch, the attribution rule for type 2 counts it as memory-caused when memory served it without its restriction (`evaluations/acceptance-review/attribute.md:16-19`), and for C5 a type 7 error fails regardless of cause (`evaluations/maturity-paid-acceptance-plan-draft.md:94`). Paused turns are not affected: a paused brain offers nothing (`src/membrain/message_cues.py:194-195`).

**What the documents require about scenarios and review.**
- New held-out scenarios for every attempt: `docs/releasing.md:130`; `architecture/v1-acceptance.md:58`, `:65`; `evaluations/maturity-fifth-attempt-2026-11-07.md:62`.
- Written by fresh agents without access to the product; independent scenario review whose findings the developer never opens; fixes by an agent other than the developer: `evaluations/maturity-paid-acceptance-plan-draft.md:54-58`.
- A plan frozen and independently reviewed before any paid call: `architecture/v1-acceptance.md:57`; `docs/releasing.md:130`; spending control reviewed: `evaluations/maturity-paid-acceptance-plan-draft.md:31`.
- A later plan must state whether unused held-out scenarios remain eligible, and any source or scenario change needs new review: `evaluations/maturity-paid-acceptance-plan-draft.md:143`.
- A final independent source/release review: `evaluations/maturity-acceptance-execution-2026-11-07b.md:15`.

**Who authors and judges (Judgement).** The maturity attempts used Codex agents for authorship and scoring while Codex was the developer's peer. With Claude now leading development, Claude subagents launched by the developer are a weaker form of isolation, and the earlier attempts had a judge from a different vendor than the DeepSeek host. Keeping Codex for authorship and scoring, relayed by the owner, preserves the documented separation; using Claude subagents instead needs the owner's explicit decision and a written isolation rule.

## 3. C5

**Meant to measure.** Whether the companion layers behave as designed when a real host model uses them: feelings reported and referenced later, a mood that reacts and recovers, a boundary that holds, a deletion and a reset that stick, persona stability, and a long absence without guilt pressure (`architecture/phase-c-design.md:267-282`; `evaluations/maturity-paid-acceptance-plan-draft.md:39-46`). It adds critical types 6 to 9 (inferred feeling stated as fact, boundary broken, deleted emotional memory brought back, simulated mood claimed as real or used for pressure) with rules RC1 and RC2 (`:74-89`); a standing type 7 or 8 error fails C5 whatever its cause (`:94`; `evaluations/acceptance_review.py:1081-1082`).

**Why it is invalid.** It has never been scored. Attempts 1, 2 and 4 stopped before C1. In attempts 3 and 5, C1 stopped on `page_action_failed`: attempt 3 with P at 32 of 64 turns, attempt 5 at session 3, message 1 (`evaluations/maturity-third-attempt-2026-11-06.md:21`; `evaluations/maturity-fifth-attempt-2026-11-07.md:52`). A failed page action is a harness event that invalidates the run (`evaluations/c5-harness.md:54`, `:66`). The cause was not established; the run stays sealed. A selector defect found after attempt 3 was fixed (`evaluations/maturity-proposal-selection-2026-11-06.md:5-7`), and attempt 5 still failed. The event records the action kind and one of four fixed reason codes (`evaluations/c5-harness.py:205-213`, `:1001-1003`) in the sealed run on the Mac; I could not determine whether those two fields were read.

**What a valid run needs.**
- A root cause for the page-action failure on public fixtures. **Judgement:** reading only the action kind and reason code from the sealed C1 `harness-events.jsonl` is content-free by the harness's design, but the plan keeps invalid runs sealed (`evaluations/maturity-paid-acceptance-plan-draft.md:143`), so that read needs the owner's decision.
- Under the main line, `E`'s companion behaviour came from extraction ("feelings through extraction", `evaluations/maturity-paid-acceptance-plan-draft.md:65`), so `E` drops out here too.
- The consolidation privacy question above, which bears directly on types 2 and 7.
- New held-out C1/C2 with `FACTS` and `PAGE_ACTIONS` (`evaluations/maturity-paid-acceptance-plan-draft.md:50-52`), every session timed, no timed pauses (`evaluations/c5-harness.md:91-105`). The fifth attempt's C2 never ran; whether it remains eligible would have to be stated and reviewed (`evaluations/maturity-paid-acceptance-plan-draft.md:143`).
- **Judgement:** run C5 as a separately approved unit after R4, so that a C5 harness fault cannot spend R4's budget or block its scoring. The plan already keeps a valid R4 unit after a later invalid C5 unit (`evaluations/maturity-paid-acceptance-plan-draft.md:13`).

## 4. R5

**Protocol.** On the reference machine, not CI (`evaluations/maturity-test-matrix.md:290`): a 1,000-message keyword fixture per brain across eight brains plus 100 notes, semantic model off, measured after indexing settles, excluding client start-up, 20 queries per worker after one discarded warm-up, one local service (`evaluations/maturity-test-matrix.md:283-289`; `evaluations/maturity-free-checks-2026-11-03.md:53`). The installed qualification runs a closed/open/open/closed sequence with the memory page's 3D view open in headed Chromium in the open phases, a fresh API per phase and three cycles per phase; each cycle runs serial, eight clients on one brain and eight clients on eight brains: 36 windows (`evaluations/maturity-month-qualification-2026-11-07.md:15-25`; `architecture/phase-c-design.md:100`). Bars: serial p95 below 500 ms; one brain with eight clients at most 1,000 ms; eight brains at most 600 ms (`docs/releasing.md:132-133`). The last pass, on `f5e265c`: 36/36 windows, 4,080 nonempty recalls, worst 235.34/308.34/310.41 ms (`evaluations/maturity-month-qualification-2026-11-07.md:17-23`).

**What it needs.**
- **Machine:** the Apple M4 Mac. The recorded renderer is ANGLE Metal on Apple M4 (`evaluations/evidence/maturity-month-qualification-2026-11-07/visual-summary.json.gz`).
- **Fixture:** a retained installation at `/Users/yichen/tmp/membrain-xml-integration-20261105/performance/perf-recall-cache-installation`, with a persisted working-state seed from `/Users/yichen/tmp/membrain-working-map-20261105/`. The driver `compare-visual-permissions.py` and wrapper `run-visual.py` exist only gzipped under `evaluations/evidence/maturity-month-qualification-2026-11-07/visual/`, with these paths hard-coded. The base benchmark `evaluations/recall-concurrency-benchmark.py` can seed a new fixture (`:133-143`).
- **Duration:** the measurement itself takes minutes (the browser session in `visual/run.log.gz` spans 13:27:02 to 13:29:15 UTC); the total including the fresh 49-check installation (R1) is not recorded. **Judgement:** half a day of Mac time for R1 and R5 together, including fixture checks.

**Can it run here?** Not as the counting run. This WSL2 environment has 4 logical processors, 8 GiB memory and no desktop control (`evaluations/backend-host-recording-receipts-2026-11-09.md:39`), the bars were set and met on the M4, and the protocol needs a hardware-rendered headed browser. A WSL run would be a useful rehearsal of the closed phases only and would not count.

**A question for the owner (Judgement).** The fixture runs with `MEMBRAIN_SEMANTIC=0` (`run-visual.py` in the evidence above), while the product now loads the local embedding model at service start (commit `fa88a4b2`) and recall includes message-context embeddings and the cue route. R5 as written therefore does not exercise those parts of the recall path. Adding a semantic-on window would change the gate and needs a decision; repeating the unchanged protocol is still required for the item to count (`docs/releasing.md:131`). The plan draft makes matrix gap 20, which is this bar, a prerequisite of any paid attempt (`evaluations/maturity-paid-acceptance-plan-draft.md:22`).

## 5. Other unchecked or stale items

| Item | State | What it needs |
| --- | --- | --- |
| GitHub Verify | Last recorded pass covers `2ef05f3` (`docs/releasing.md:11`). Verify runs on pull requests and pushes to `main` that touch more than Markdown and `evaluations/` (`.github/workflows/verify.yml:3-14`), so the next move of `main` triggers it. Whether the push that moved `main` to `b06a98b9` ran Verify is not recorded; I could not check without network | Record the result for the frozen candidate; Actions minutes |
| Five-platform native qualification | Last pass `978312c` (`docs/releasing.md:12`); not repeated for any later runtime (`evaluations/status-audit-2026-11-10.md:41`) | `native-engine.yml` by `workflow_dispatch` (`.github/workflows/native-engine.yml:53`), runs on macOS, Linux and Windows hosted runners; Actions minutes, about an hour |
| Native Windows | Scoped checks last on `294db3d`/`2ef05f3` (`docs/releasing.md:46-48`), run on the Windows host of this WSL machine (`evaluations/backend-host-recording-receipts-2026-11-09.md:27-39`) | The owner's permission to run on the Windows side; no new purchase |
| macOS installation (R1, 49 checks) | Last pass `7902c16e` (`docs/releasing.md:13`) | The Mac, with R5 in the same session |
| R2 tests and matrix | Full local suite on `75f50fd` passed 8,533 (`docs/releasing.md:10`); the run for `fa88a4b` is in progress (the report has `FULL_SUITE_PLACEHOLDER`, `evaluations/assistant-replies-and-warm-up-2026-11-12.md`). The matrix header and content are stale (`evaluations/status-audit-2026-11-10.md:101`) and lack the consolidation and `my_replies` tests | Bring the matrix up to date; the plan requires it green with no open gap (`evaluations/maturity-paid-acceptance-plan-draft.md:22`) |
| R3 privacy and security | Security findings listed in `evaluations/status-audit-2026-11-10.md:87-93` are open; of the two withheld credential findings, one is fixed in `933f4d8a` (`docs/releasing.md:34`) and one is open. The checklist contradicts itself on the embedded-engine baseline (`evaluations/status-audit-2026-11-10.md:102`) | Fix before any publication (`evaluations/status-audit-2026-11-10.md:114`); details of the withheld finding are outside this brief |
| Independent review | Not run for any runtime since the fifth attempt's final review (`docs/releasing.md:26-42`) | A reviewer not anchored on the developer; subscription use needs the owner's approval |
| C-1 | Unchecked although its text says every step is implemented (`docs/releasing.md:137`; `evaluations/status-audit-2026-11-10.md:102`) | A decision to tick it or name what is missing |
| C-2 | Ticked, but its own text says recheck when interfaces change (`docs/releasing.md:138`); `memory_consolidate` and `my_replies` exist on some hosts only, not OpenClaw, AstrBot or the proxy (`docs/releasing.md:30`; `evaluations/assistant-replies-and-warm-up-2026-11-12.md`) | Update `docs/host-compatibility.md` |
| D-2 delivery | Not started (`docs/releasing.md:143-147`) | After every other item |

## 6. Ordered proposal

| Step | The project lead alone | Needed from the owner |
| --- | --- | --- |
| 1. Finish the current suite run and record it in the 2026-11-12 report | Yes | Nothing |
| 2. Write a public regression for the consolidation batch's handling of sensitive and boundary messages; decide and implement the policy | Yes, free | Nothing, unless the policy changes product behaviour the owner cares about |
| 3. Propose the R4/C5 contract amendment: `P` gated against `F`; `E` removed or un-gated; the proxy's release scope stated | Draft | **Decision** on arms and proxy scope |
| 4. Harness and scoring changes from section 2, the practice scenario extended, the zero-model dry run repeated, the matrix updated | Yes, free; days of work (Judgement) | Nothing |
| 5. Freeze the recall path for the candidate. Every later recall change reopens R5 and the R4 evidence (`docs/releasing.md:5`, `:131`) | Proposes the freeze point | **Agreement** that memory-quality work pauses or continues on another branch |
| 6. Optional real-host trials on longer sessions: does the host consolidate late in a long context, does it set `my_replies` when asked about its own words | Prepare | **Approval** of subscription use; the earlier 13-turn Sonnet trial cost about 0.47 USD at list prices (`evaluations/host-consolidation-trial-2026-11-11.md:75`); Judgement: 1 to 5 USD |
| 7. Mac session: R1 49-check installation and the R5 protocol on the frozen runtime | Prepare scripts and a fixture plan | **Mac access**, about half a day (Judgement); decision on a semantic-on R5 window |
| 8. Verify and five-platform Native on the frozen candidate; native Windows checks | Run | **Approval** of Actions minutes; permission for Windows-side runs |
| 9. Independent review of the amended plan and harness changes | Prepare the material, without the developer's conclusions | **Approval** of subscription reviewers (Codex via the owner, or a decision to use Claude subagents) |
| 10. R4 attempt: new author and reviewer briefs, two new held-out scenarios, freeze, run, score, final review | Operate, without seeing scenario content | **Approval** of a DeepSeek ceiling (Appendix A: about 100 CNY; expected bill 6 to 15 CNY) and of about 65 to 75 subscription agent runs; the owner relays Codex work; one day elapsed (Judgement) |
| 11. C5 as a separate unit after the page-action cause is found | Investigate on public fixtures | **Decision** on reading the sealed C1 reason code; **approval** of a ceiling (Judgement: about 100 CNY; expected bill 8 to 20 CNY) |
| 12. Security fixes, final independent review, README and Chinese README alignment, C-1/C-2, D-2 | Yes | Confirmation of the release before the tag (`docs/releasing.md:147`) |

**Earliest point for an R4 attempt (Judgement).** Consolidation reached the pinned runtime on 2026-11-11 and `my_replies` on 2026-11-12. Real-host evidence for consolidation is 26 turns on three models (`evaluations/host-consolidation-trial-2026-11-11.md:33`); whether a host sets `my_replies` is unmeasured (`evaluations/assistant-replies-and-warm-up-2026-11-12.md`). The earliest sensible attempt follows steps 2 to 5, 7, 8 and 9: the harness exercises everything a real host receives, the consolidation privacy path has a decision and a regression, the runtime is frozen, and R1, R5, Verify and Native are green on that runtime as the plan requires (`evaluations/maturity-paid-acceptance-plan-draft.md:21-31`). Running earlier would test a harness that cannot call `memory_consolidate` and a runtime likely to change again.

## What I could not determine

- The reviewers' model identifier in the maturity attempts; the documents say only "Codex subscription".
- How long scenario authorship and review took before the fifth attempt's 21:25 UTC preparation record.
- Whether the fixture installation and private acceptance roots still exist on the Mac.
- Whether Verify ran on the push that moved `main` to `b06a98b9`, and its result.
- The current DeepSeek prices and whether `deepseek-v4-pro` and `deepseek-flash` are still offered; they were last checked on 2026-11-07.
- The cause of the two C1 page-action failures.
- Whether a DeepSeek host offered `memory_consolidate` would follow the notice, and how many tokens consolidation adds per scenario.

## Appendix A. Cost derivation

All figures are for one R4 attempt with S1 and S2 and arms `P` and `F`, using the fifth attempt's token use as the workload (Section 1.3).

- **Guard-booked host cost:** P (1.516M prompt × 9 + 0.074M output × 27) / 1M = 15.6 CNY; F (0.990M × 9 + 0.097M × 27) / 1M = 11.5 CNY; together 27.1 CNY. Consolidation adds two host rounds per session with five or more waiting messages, plus a batch of up to 8,000 characters (`src/membrain/host.py:65-71`) that stays in P's context for the rest of the session. Judgement: +10% to +30% on P, so 29 to 32 CNY; with workload variation, 30 to 40 CNY.
- **Billed cost:** the fifth attempt's R4 unit fell 7.84 CNY in balance for three arms plus extraction, off-peak (21:52 UTC is 05:52 Beijing time). P and F carry about 73% of guard-booked host cost, so about 5.5 to 6 CNY, 6 to 7 with consolidation; peak hours roughly double it to 12 to 15 CNY.
- **Ceiling:** with two arms in parallel, at most two or three requests are in flight at 20.05 CNY each, and an interrupted request keeps its reservation (`evaluations/evaluation-billing.md:18`). Earlier attempts retained 20 to 60 CNY of unknown reservations. A ceiling near 100 CNY leaves room for that without inviting a stop on reservations alone. Prices must be revalidated before approval.
- **Subscription work:** 2 authors, 1 to 2 scenario reviewers and fixers, 2 first reviewers, 22 second reviewers, about 36 R5 checkers (fifth attempt), 2 resolution reviewers, 2 attributors per gated critical reply, one final reviewer: about 65 to 75 agent runs. These are not metered in CNY and need separate approval (`evaluations/maturity-paid-acceptance-plan-draft.md:135`).
- **If `E` were kept ungated for information:** about +10 CNY booked and +2 to 3 CNY billed, and it keeps a second model in the evaluation.
