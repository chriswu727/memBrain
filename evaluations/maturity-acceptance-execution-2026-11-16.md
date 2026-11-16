# Seventh maturity acceptance attempt (R4 only): execution binding

This binding fixes attempt `maturity-20261116a` ("the seventh maturity attempt") before any paid call. It was
written on 2026-11-16 from the [sixth attempt's binding](maturity-acceptance-execution-2026-11-15.md) by the operator
of the preparation, under the lead's delegation; every section was revised for this attempt, and every number below
was measured on this source. The attempt id was fixed by the lead's brief **before** any persona draw was computed.
**This binding authorizes no model call.** The owner's approval of the paid run (the ceiling, the subscription use
for blind scoring and the final review) is recorded separately; the lead starts the run only after it, and only
after the independent freeze review has set `execution_may_start` (below). Subscription use so far: isolated
scenario authorship, review and fixing by Sonnet sessions only (no session ran the provider's largest model). There
is no recharge, no retry, no automatic additional attempt and no C5 unit in this attempt; C5 remains invalid and
unscored.

The [sixth attempt](maturity-sixth-attempt-stop-2026-11-16.md) stopped as invalid after 8 of 61 turns of its first
scenario, when the host paused recording with no arguments after its answer was written. Two things changed for this
attempt because of it: the runtime ([a host AI's pause needs the user's words](pause-request-2026-11-16.md)) and one
stop rule (scope decision 6 below).

## Scope decisions (taken by the lead under the owner's delegation)

1. **R4 is judged on the plugin path alone.** Arms: `P` (plugin path) and `F` (full-history reference); gated arm:
   `P`. The proxy path is not part of acceptance. Hosts whose model cannot call tools get recording and recall but
   no notes and are not covered by the gate. The rule text: `architecture/v1-acceptance.md`, R4 "Paths", amended at
   `e0f9f27d` (and `42f7f135`) before the sixth attempt; `docs/releasing.md` records that R4 is failed and that the
   extraction path has been removed.
2. **One fixed persona in both arms.** The companion layer is always on, so the run carries a persona: the
   personality type `estj` = `acceptance_persona.draw("maturity-20261116a")` =
   `IDS[int(sha256(attempt id), 16) % 16]` over `membrain.persona_presets.IDS` (seed `maturity-20261116a`), recorded
   in the manifest's `persona` entry. It was computed for the first time while this binding was written, after both
   scenarios were final (the first approved, the second copied and verified). The harness saves it in `P` before the
   first session (made by the host, action "preset"), so the product's random first type and its one-time
   announcement never occur; `F` receives the same product-rendered `<membrain-persona>` block. Nobody chose the type.
   It differs from the sixth attempt's `isfj` because the attempt id differs.
3. **Host model.** `deepseek-v4-pro` through the harness's emulation of the plugin hooks and MCP tools, as in
   attempts 1–6. **It is not Claude Code**: no hook subprocess, no stdio MCP, no Claude Code system prompt; the
   result says how memBrain's plugin path works with this model under this emulation, not how Claude Code behaves.
4. **One arm at a time.** For each scenario `P` runs, its installation is stopped and its ports checked closed,
   then `F` runs; only one host request is ever open against the ledger.
5. **Ceiling.** 80 CNY on the guard's conservative count, one model in the policy, one request in flight. A new
   ledger is created by the lead at run time (below); the sixth attempt's blocked ledger is never reopened.
6. **Replaced in this attempt: a turn that arm `P` leaves unrecorded because of the host's own accepted pause no
   longer stops the attempt.** In attempts 1 to 6 any turn of `P` left unrecorded that the scenario meant to be
   recorded stopped the attempt as invalid ("a turn left unrecorded because the host did not resume recording stops
   the attempt as invalid"); the sixth attempt stopped on such a turn. **This changes a stop rule that was bound in
   attempts 1 to 6.** Why: in the sixth attempt the stop came from a real behaviour of the plugin path (the host
   paused on its own), not from a fault of the harness, and stopping there left the plugin path's behaviour unscored
   while a host that fails to pause when asked was already scored. From this attempt on:
   - When the host's own accepted pause explains the unrecorded turn (an unexpected pause accepted in that turn, or
     a pause in force as the turn began that the host did not end when asked: no `memory_resume` naming the
     conversation in that turn), the run goes on. The turn is listed in the run's `host-pauses.jsonl` (kind
     `unrecorded_by_host_pause`; time and position only), validity reports the count and positions without
     refusing, and the consequences are scored with the arm: the later cases are scored as `P` answers them.
   - Attribution reviewers get no extra information about such turns. A critical reply is attributed by the
     unchanged rule: anything but two "host" answers, including a missing or invalid answer, is memory-caused.
   - An unrecorded turn that no accepted pause of the host explains still records `turn_not_recorded`, stops the live
     arm and makes the attempt invalid. This includes a turn left unrecorded by a pause the product itself makes on
     the user's words (with no accepted host pause), and a turn after a pause the product refused.
   - This cannot make arm `P` score better on the turns lost: a turn that is not stored is never recalled, `F` keeps
     the whole history, no case is dropped or excused, and no score is adjusted by hand. It can only let a run that
     would have stopped be scored, with whatever losses the pause caused.
   - No resume call is inserted on the host's behalf.
7. **Scenario authors, reviewers and fixers** are isolated sessions started by
   `evaluations/acceptance-kit/launch.py` in directories outside every checkout, with only their brief; only
   hashes, counts and fixed codes reached the operator.

## Identities

Attempt `maturity-20261116a` (named "the seventh maturity attempt", never "attempt 7") uses the new execution clone
`/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/clone` (Linux x86_64, WSL2, kernel
6.18.58.1-microsoft-standard-WSL2), branch `acceptance/maturity-20261116a`, cloned from integration commit
`f20a074a6f95ab0da42fb2e8080663f4aea7a96e` (head of `integration/maturity-candidate` locally and on GitHub when
preparation started). The branch adds only the commit of this binding; the frozen commit is that branch head,
recorded in the freeze review and in `control/preparation.json`. No tooling was changed in preparation. `src/` and
`migrations/` are unchanged from the integration commit. All nine launchers pin runtime
`a85ca152033651c2041159ace5c26e9e1a6388b4` (pin commit `4513d133`; `src/` and `migrations/` are identical between
`a85ca152`, `4513d133` and `f20a074a`), build `6ad5f2fbb4bb7e078a53b38e9ff0c9cea92343f3b964b381f6303f75aca0bf9d`,
schema `3a94d7b6ea6bfba8ff8a4d920aa83001123922f4f90b0a9d6430ef1997b6166d` (`membrain.build_identity` in the clone; the
schema is the sixth attempt's, as the runtime change has no migration).

Interpreter: a dedicated virtual environment `.venv` in the clone, made by `uv sync --frozen` (uv 0.13.6; 79
packages installed) from the clone's `uv.lock` (sha256 `0bc566ca…7e92`, unchanged from the sixth attempt); CPython
3.12.16 managed by uv (binary sha256 `23bc148d…82b5`), `include-system-site-packages = false`, `membrain` imported
from the clone's `src` (editable). No other virtual environment is on its path. Embedding model cache
`$HOME/.cache/membrain/eval-embedding-model` (`model_quantized.onnx` `f80102d3…c193`, `tokenizer.json`
`0b44a9d7…4c39`), ONNX Runtime 1.31.1, all as in the sixth attempt.

Qualification on this source: the full local suite passed on the pinned source `4513d133` (4,140 passed, 3 skipped,
reported in the [pause-request record](pause-request-2026-11-16.md); not rerun in this preparation; `src/` and
`migrations/` are identical at this source). The two evaluation-tooling commits after the pin (`51e39787`,
`f20a074a`: host-pause scoring and tool-call markup) changed no runtime file; they are covered by the focused tests
below, not by a full run. In the clone, with every `*_API_KEY` and `C5_*` variable unset and under
the machine's shared database-test lock: the acceptance tooling's focused tests **760 passed, 0 failed** (driver 152,
review hardening 157, review pipeline 128, scenario path 18, kit 71, c5 harness 47 and its hardening 76, supervisor 7,
billing guard 55, proposal selection 11, the pause request 34, the novelty check 4; 2 existing fork warnings; 8 min 20
s on a fresh task-owned database, stopped afterwards). The public stub rehearsal `r4-stub-rehearsal.py` before
freezing: freeze of 432 files marked practice, driver complete with both scenarios valid, dry-run checks 138 of 138
for both, gate computed (`R4` true on the synthetic verdicts, gated `P`, frozen arms `P`, `F`), zero network events,
ledger unchanged with no request, ports closed, two stopped synthetic databases removed. No installed-package check
was run. These checks are not real-model acceptance.

## What governs the run

The [reviewed acceptance plan](maturity-paid-acceptance-plan-draft.md) governs isolation, review, scoring and stopping,
except where this binding says otherwise. Where that plan names arm `E`, its extraction model, three parallel host
reservations plus an extractor reservation, or "each gated arm" including `E`, this binding supersedes it: two arms,
no extractor, one model, sequential arms, gated arm `P`.

- **Arms.** `P` and `F`, each in a fresh directory, run one after the other per scenario (`c5-run-scenario.sh`).
  `P` drives the plugin's own hook functions (`membrain.plugin.session_start`, `user_prompt`, `stop`, Claude Code's
  tool names), offers every tool the plugin's MCP server lists with its own schemas (14: `memory_capabilities`,
  `memory_recall`, `memory_inspect`, `memory_observe`, `memory_note`, `memory_consolidate`, `memory_boundary`,
  `memory_pause`, `memory_resume`, `memory_manner_feedback`, `memory_persona`, `memory_prepare`,
  `memory_checkpoint`, `memory_forget`, as the rehearsal's `tools.json` lists them on this source), keeps one tool
  server per session, and receives what an MCP host gives its model without the model choosing to open anything:
  the server's instructions, the session context and the per-message context. It does **not** receive the skill
  body, which a host loads only when its model opens the skill. One difference from Claude Code remains: Claude Code
  can defer tool descriptions until the model looks a tool up, while `P` gets every description up front. `F`
  receives the whole earlier history and the same persona block. Blinding uses labels A and B
  (`v1-2026-10-29-phase-b-blind.py … PF`).
- **The host's pause.** `memory_pause` now requires `request`, the user's own words asking not to be remembered,
  checked against the message staged for the turn; a call without them, or with words not in the message, is
  refused and pauses nothing. An accepted pause's answer asks the host to tell the user. Consolidation's last answer
  tells a host whose answer is already written that it is finished. Timed pauses stay refused by the harness
  (`timed_pause_refused`, a harness event).
- **Scenario persona.** A scenario `PERSONA` card is refused by the harness in a live run and whenever the driver
  passes the manifest's draw; validity (given the draw by the driver) requires every arm's `persona.json` to record
  `source: "seeded"` and the manifest's type.
- **Changed evaluation code since the sixth attempt's freeze** (in this attempt's freeze review; frozen below): the
  harness lists a turn left unrecorded by the host's own accepted pause in `host-pauses.jsonl` instead of stopping
  (decision 6); validity and `acceptance_review.py diagnose` report, per run, the count and positions of such turns
  and of replies containing raw tool-call markup (`TOOL_CALL_MARKUP`; count only), and refuse a malformed
  `host-pauses.jsonl`; `diagnose` prints the host's tool calls as fixed codes (a name only when the plugin lists
  it, timed or until-resumed pauses, whether a resume named its session, whether the tool answered with an error);
  the stub host's scripted pause quotes the turn's words as `request`. Criteria, rubric, critical types 1–5,
  resolution rules R1–R5, attribution rules and the pass rule are unchanged.
- **Pass rule (unchanged, as coded in `acceptance_review.py gate`).** Over S1 and S2: `P`'s total ≥ `F`'s total − 1;
  no `P` reply with a standing critical error attributed to memory (two independent attributors; anything but two
  "host" answers, including a missing or invalid answer, is memory); the number of `P` replies with a host-caused
  critical error ≤ the number of `F` replies with a standing critical error. `R4 = P passes`. A tally or sealed
  mapping that does not hold exactly `P` and `F` is refused, a case id may not occur in both scenarios, and with the
  manifest every tally must be bound to its frozen scenario (key, stem, sha256) and to this manifest.

## Differences that affect comparability

The sixth attempt's column describes what it bound; it ran 8 turns and was not scored, so no result of it is
compared with this one. "Same" means the same as the sixth attempt.

| Change | Attempt 5 | Sixth attempt | This attempt | Effect on comparison |
| --- | --- | --- | --- | --- |
| Arms | `P`, `E`, `F` in parallel | `P`, then `F` | same | `E` results have no successor; parallel versus sequential does not change any arm's inputs |
| Gate | `P` and `E` both had to pass | `P` alone | same | An R4 pass here is a pass of the plugin path only |
| Persona | none in either arm | type `isfj` in both | type `estj` in both (the draw of this attempt id) | Every prompt ≈ 250 tokens longer than in attempt 5; tone and length of replies may differ in both arms alike, and differ from the sixth attempt's type |
| Tools offered to `P` | 5 (recall, note, boundary, pause, resume; ≈ 7.7k characters of schemas at the sixth attempt's sizes) | all 14 the server lists (16,989 characters of schemas) | all 14 (17,217 characters of schemas, measured on this source; the pause schema now has a required `request`) | New behaviours (consolidation, manner feedback, persona, forget, the low-level tools) can occur since the sixth attempt |
| Skill text in `P`'s prompt | the whole skill body (≈ 10.4k characters at runtime `7902c16e`) in every call | none (skill 17,164 characters with front matter) | none (skill 17,488 characters with its front matter, 16,919 without, measured on this source) | Guidance attempts 1–5 gave the host in every call is gone; what remains is the server's instructions and the notices |
| Server instructions | not given | in `P`'s system prompt (1,332 characters, sha256 `bb95409e…82a0`) | same: 1,332 characters, sha256 `bb95409e6d91e02776bdfc1c89e77cf5a66ec115db3ab45a5afc714a17c682a0`, measured on this source | Unchanged since the sixth attempt; they do not mention pausing |
| Net standing prompt of `P` | skill + 5 schemas | instructions + 14 schemas + persona block | same, with 228 more schema characters | About +0.7k characters per call against attempt 5 besides the persona block |
| Hook path | `membrain.host.*` with default tool names | `membrain.plugin.*` with Claude Code's names | same | Notice wording as Claude Code's plugin gets it; the session notice now says to pause "with their words" |
| MCP server | new per turn | one per session | same | A consolidation batch survives between its two calls |
| Consolidation | never requested (tool not offered) | requested when ≥ 5 messages wait; up to two tool calls in a turn | same; the last answer adds "If it is already written, you are finished: call no other tool." | Cue writing affects recall in `P`; more `P` host rounds than attempt 5 |
| The host's pause | any call accepted | any call accepted, including one with no arguments; the answer did not ask the host to tell the user | refused unless `request` holds the user's words from the staged message; an accepted pause's answer asks the host to tell the user | The slip that stopped the sixth attempt (a pause with no arguments) is refused; a pause that quotes the user wrongly is not |
| A turn left unrecorded by the host's own accepted pause | stopped the attempt as invalid | stopped the attempt as invalid (it did, after 8 turns) | scored with the arm, listed in `host-pauses.jsonl`, reported by validity and `diagnose` (decision 6) | A run that would have stopped is scored; `P` can only lose from such turns |
| Replies with raw tool-call markup | not counted | not counted | counted per run (count and positions only), never refusing | Reported as a limitation of the frozen call shape: the last round offers no tools |
| Runtime | `7902c16e` | `548674ce` (no extraction model, host consolidation, first-persona logic, local dates, no runtime mode, host erasure reconciliation, persona suggestions bound to evidence, deferred-note source lifecycle) | `a85ca152` (the pause request, the pause note, the consolidation note) | Product changes since attempt 5 |
| Scenarios | S1/S2 of attempt 5 (now public) | new held-out S1 (`s1`) and S2 (`s2b`) | new held-out S1 (`s1b`, from the same assignment as the sixth attempt's S1); S2 is the sixth attempt's `s2b`, unchanged | The sixth attempt's S1 ran 8 turns and one of its turns is public, so it is not used; `s2b` was frozen and never run: no host model has seen it |
| Review instructions | three replies | two replies; same criteria and rubric; `recheck.md` also says to ignore wording about tools or memory | same | A reviewer compares two replies instead of three |
| Blinding | three replies per case | two replies per case | same | **Partial blinding (limitation).** Any visible sign of memory use in one reply ("Saved.", "Memory's updated.", a repeated answer after consolidation, a pause notice told to the user) identifies both replies of that case. Reviewers are told to ignore such wording; `acceptance_review.py remarks` counts, per arm, the case replies and all replies containing a phrase from a fixed list (`MEMORY_REMARKS`), and the record states those counts and shares |
| Ceiling | 280 CNY, two models | 80 CNY, one model | same, on a new ledger | Reservation headroom: refusal once settled charges exceed 59.945984 CNY |
| Scenario sessions | Codex subscription sessions, isolation not observed | Claude Code Sonnet sessions with observed isolation | same command and kit (below) | Authors and reviewers are a different model family than in attempts 1–5 |

Unchanged since the sixth attempt: host model and call shape (`thinking` enabled, `max_tokens` 16,384, at most 4
rounds, tools in the first 3, at most 6 tool calls, up to 4 attempts for an empty reply, cap 5 × user turns), the
billing guard, validity's rules other than those named above, the scoring pipeline's rules, and the scenario format.

## Scenarios

**Session isolation.** Authors, reviewers and fixers ran through `evaluations/acceptance-kit/launch.py` (sha256
`7eef3abc…0138`, unchanged since the sixth attempt) with the Claude Code (2.1.322) command `claude -p PROMPT --model
sonnet --safe-mode --restricted --strict-mcp-config --no-session-persistence --tools Read,Write,Edit
--disallowedTools Bash,WebFetch,WebSearch,Task --permission-mode acceptEdits` (`session-commands.json`, sha256
`906a3964…edc4`), each in a new empty directory under `/home/yichen/.local/state/acceptance-sessions/20261116a`
(outside every checkout; the path names no product, because a session can see its own working directory's path),
with `MEMBRAIN_DIRECTORY` pointing to an empty read-only directory and only PATH, HOME, USER, LOGNAME, LANG, LC_ALL,
TERM and TMPDIR in the environment (no credential). The allowed-models file `control/allowed-models.json` is
`["sonnet"]` (sha256 `1a1e8da4…eaf4`, a byte copy of the sixth attempt's); `launch.py` accepts a `--model` only by
exact membership. The Codex command is marked non-isolating and was not used.

The isolation was observed on 2026-11-15 by the sixth attempt's probe session with the kit's exact flags
(`/home/yichen/.local/state/membrain-setup/runs/r4-isolation-probe-20261115/probe-result.json`, sha256
`8e677e2e…4ba7`): only Read, Write and Edit; reads outside the working directory refused; no memory or MCP tool, no
plugin or memory context, no CLAUDE.md or project instructions; no transcript persisted. The probe was **not
repeated** for this attempt: the Claude Code version, the command and the kit are the same. What this does not
guarantee: `--restricted` confines the file tools but the model's provider still receives everything the session
reads; admin-managed policy settings still apply; and from outside, the launcher can show what a session wrote,
never prove what it did not read.

**Assignments.** Each author received the neutral brief (`author-brief.md`, sha256 `da83c11f…c108`) and one
assignment file, without source, history, previous scenarios or outcomes. The assignment files (frozen as control
files) state only the case prefix, the two languages and the size: `control/s1b-assignment.md` (sha256
`4ea5bc56…e634`), a byte-identical copy of the sixth attempt's `control/s1-assignment.md`: prefix `S1`, mainly English,
one session in German; `control/s2b-assignment.md` (sha256 `7664be01…a7ff`), copied with `s2b`: prefix `S2`, mainly
Chinese, one session in English; both 11 cases and 60–66 user messages. German was the sixth attempt's operator's
choice and is kept by copying the assignment. Neither scenario has page actions or a persona; both hold only literal
assignments, state every weekday correctly and declare one off-the-record stretch in the shape the harness runs
(`c5-precheck.py --r4`, which `freeze.py` runs with the clone's interpreter and requires to pass; both pass on this
source). Independent reviewers kept findings private (`reviewer-brief.md`, sha256 `6f75a6f8…f875`); independent
fixers applied corrections (`fixer-brief.md`, sha256 `af8c8fa5…f114`; the sixth binding misprinted its end as
`f124`).

**Production of the first scenario, as the launcher reported it** (key `s1b`; 2026-11-16, 06:30–06:46 UTC):

| # | Session | Result (launcher's JSON) |
| --- | --- | --- |
| 1 | s1b author 1 | 17 sessions, 61 turns, 11 cases, precheck ok; `e08a4f4a…d38a` |
| 2 | s1b reviewer 1 | not approved: 6 findings, 1 blocking |
| 3 | s1b fixer 1 | applied 6; 17 sessions, 61 turns, 11 cases, precheck ok; `c3feb22a…b8cf` |
| 4 | s1b reviewer 2 | not approved: 7 findings, 1 blocking |
| 5 | s1b fixer 2 | applied 7; 17 sessions, 61 turns, 11 cases, precheck ok; `aec260c2…eab6` |
| 6 | s1b reviewer 3 | **approved**: 4 findings, 0 blocking (all minor; not applied, since a fix would need a new review); receipt `8b304844…ef36` |

Every session exited 0 and produced its outputs; every author and fixer version passed `c5-precheck.py --r4` with no
code (the precheck includes the weekday check, `weekday_mismatch`). The first scenario was approved in the third and
last allowed review round; no restart under `s1c` was needed. Six Sonnet sessions were used for this attempt's
preparation; no isolation probe was run. The launcher does not report cost, and the operator did not open the
session logs, so their subscription cost is not known. The two earlier versions (`scenario_s1b.v1.py`,
`scenario_s1b.v2.py`), the three reviews, findings and the two fix counts stay in the private root as evidence.

**The second scenario is the sixth attempt's `s2b`, reused unchanged.** It was approved there by an independent
reviewer (6 findings, 0 blocking, all minor and not applied), frozen in the sixth attempt's manifest, and never run:
that attempt stopped in its first scenario, so no host model has seen `s2b`. Its scenario directory, its receipt and
its assignment were copied by path into this attempt's private root without being displayed, and their sha256 values
verified against the sixth binding: scenario `4c6c0404fab7de758f9592fd65b76c3d4f949761a85e52b5d3c902b214a15358`,
receipt `f1a0a119a7cd99df06e0cb51c7a0ed2fd8cab771354fc0725c49be74b3b7bdff`. The receipt names the key, the scenario's
sha256, its counts and the review session; it is bound to no attempt id or private root, so `freeze.py` accepts it
unchanged, and no new review was run. The sixth attempt's directories were not changed.

**Final scenarios** (from the receipts): S1 `aec260c21694c4a9c10fde3825fbe04e1fba5998894fc572449875140c8beab6` (11
cases, 61 turns, 17 sessions), key `s1b`, `s1b/scenario_s1b.py`; S2
`4c6c0404fab7de758f9592fd65b76c3d4f949761a85e52b5d3c902b214a15358` (11 cases, 63 turns, 19 sessions), key `s2b`,
`s2b/scenario_s2b.py`; receipts `control/s1b-review-approved.json`
`8b304844c36fbfa328ed30d9a9682e0c582dd3402eab74317fa56f91e5eaef36`, `control/s2b-review-approved.json`
`f1a0a119a7cd99df06e0cb51c7a0ed2fd8cab771354fc0725c49be74b3b7bdff`.

**Novelty** (`evaluations/acceptance-kit/novelty.py`, prints only numbers and booleans). The stop threshold is the
sixth binding's, **10% largest 8-gram overlap**, fixed there before any held-out file was measured from the public
scenarios' largest mutual overlap (leave-one-out) of 2.64%. The earlier scenarios are the 21 public ones at
`f20a074a` (every top-level `evaluations/*scenario*.py` that assigns `SESSIONS_LONG`, and the two scenario files of
attempt 5's evidence), plus 15,589 64-hex strings recorded under `evaluations/` there.
- **S1 (`s1b`)** against the public set: hash new, largest overlap 0.07% (all earlier together 0.07%, 2,811 distinct
  8-grams). With the sixth attempt's three scenario files (`s1`, the unused first `s2`, and `s2b`) added as earlier
  files by path (a wrapper outside the repository that imports the kit's functions unchanged and prints numbers
  only): hash new, largest overlap 0.28%, all 24 together 0.36%; alone, 0.28% with the sixth attempt's `s1`, 0.00%
  with the first `s2` and 0.00% with `s2b`. Within the threshold.
- **S2 (`s2b`)** against the public set at `f20a074a`: largest overlap 0.43% (together 0.76%, 4,612 8-grams), the
  same as measured for the sixth attempt; `sha256_new` is **false**, so the tool's `ok` is false, because its hash is
  now recorded under `evaluations/` (in the sixth binding, the only file at `f20a074a` that records it). That is the
  record of its freezing for the sixth attempt, not a publication of its content; it measured new at `67d2924d`.

**Session directories.** After each session's outputs had been moved into the private root by the launcher, the
finished session's working directory (a redundant copy outside the private root) was emptied with `find DIR
-mindepth 1 -delete` without being opened, right after that session finished. The empty directories were left so that
the launcher's session numbering (which counts directories) continues and no earlier review, findings or fixes file
is overwritten. The private root keeps its own copies and the sessions' logs, which the operator never opened.

## Order, validity and scoring

Order is `s1b`, `s2b`. Strict validity is required after each scenario; both must be valid before blind scoring. A
turn listed in `host-pauses.jsonl` does not make a run invalid (decision 6); validity reports, per run, the count
and positions of such turns and of replies with tool-call markup, and the record states them. First reviews, 22
independent case rechecks, conditional R5 checks, resolutions and double attribution follow the unchanged protocol
(runbook: `evaluations/acceptance-review/companion.md`, R4 unit). No score or recording expectation is adjusted
manually.

## Billing

After the owner's approval, [official prices](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) and
[completion limits](https://api-docs.deepseek.com/api/create-chat-completion/) are revalidated on the day of the run
and recorded in `control/provider-revalidation.json`; a mismatch stops preparation. Maximum input/output rates are
9/27 CNY per million for `deepseek-v4-pro`; conservative context/output bounds 1,048,576/393,216 tokens. The policy
file `evaluations/maturity-provider-policy-2026-11-14.json` (sha256
`e7b91106b206412c608b33b0f43adc1d6f7db7c19da0c05a82a620198fb5689f`, unchanged) admits only `deepseek-v4-pro` with a
proposed limit of 80 CNY and one request in flight. Search/Fetch and other provider services are excluded.

Private evidence is Git-excluded (`.git/info/exclude`) under
`/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/clone/evaluations/.maturity-heldout-20261116a/` (mode
700). Its absolute `control/ledger.json` binds this attempt, the 80 CNY ceiling and the policy; it is created by the
lead's run script after approval, from the policy exactly as the rehearsal creates its ledger, and its initial
SHA-256 and bound policy hash are recorded in `control/ledger-initial.json` before any completion. Every host call
and permitted malformed-response retry uses it. Each request reserves 20.054016 CNY (1,048,576 × 9 + 393,216 × 27
per million); with one request open the guard refuses once settled charges exceed 59.945984 CNY (with two open it
would refuse above 39.891968 CNY, which is why the arms run one after the other).

Expected conservative charge (guard's count; characters at about 3.7 per token, as `budget.md`):

| Item | CNY |
| --- | --- |
| `P`, attempt-5 workload (S1 + S2, 173 host rounds) | 15.63 |
| `P` standing prompt: − skill 10.4k, + 9.5k more schema characters (all 14 tools), + 1.33k instructions, + 0.3k notice ≈ +0.7k characters × ≈ 210 calls | +0.4 |
| Consolidation: ≈ 9 batches per scenario, 2 calls each | +5.4 |
| Persona block, both arms (≈ 250 tokens a call) | +0.8 |
| `F`, attempt-5 workload | 11.52 |
| Billed empty-reply retries | +0.4 |
| **Expected total** | **≈ 34** (plausible 26–45) |

For scale: the sixth attempt's 8 turns of `P` made 19 requests at a conservative count of 1.533573 CNY, and the
account's balance moved by 0.26 CNY. A refused pause adds a host round when the host retries. Headroom: about 26 CNY
between the expected settled total and the 59.945984 CNY refusal point (≈ 1.76 ×). The real bill is expected at
about a fifth of the guard's count, ≈ 7–15 CNY depending on the time of day. Unknown usage stays reserved.

## Stop rules

- Provider or transport failure (including transient 429 and 5xx), a guard refusal, invalid evidence, a reached cap,
  a degraded harness, a frozen input that changed, an existing run directory or a driver error stops further work:
  the driver (or the run script's supervisor) blocks the shared ledger, terminates the arm and closes the attempt's
  disposable services. No new scenario starts after a failed or invalid one; nothing is retried automatically.
- **Changed from attempts 1 to 6 (decision 6):** a turn left unrecorded by the host's own accepted pause does not
  stop the run; it is listed and scored with the arm. A turn left unrecorded that no accepted pause of the host
  explains (`turn_not_recorded`, including one left unrecorded by a pause the product itself makes on the user's
  words) makes the scenario invalid and stops the attempt.
- No stopped ledger is reopened, no unused allowance is transferred, and no extra attempt is included. A port wait
  that times out before any arm starts costs nothing and may be retried once its cause is found from socket state.
- An invalid scenario is preserved, unscored; `diagnose` emits only counts, event kinds, positions and fixed codes.
- A second refused first, second or resolution review output stops scoring for the owner. Two unusable R5 responses
  cannot clear a critical mark; missing or invalid attribution counts as memory-caused. No score is changed by hand.
- Earlier ledgers, reservations and sealed evidence (the sixth attempt's included) are preserved separately.
- No C5, no retry, no automatic further attempt, no recharge.

## Running the attempt (for the lead, after approval; not run in preparation)

The run is one script, `/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/run-live.sh` (sha256
`ffd12b2f47c5d1c31e4521933b313cacab665f4258a92f383fcfc67322aa9d27`), with
`/home/yichen/.local/state/membrain-setup/runs/r4-attempt7/balance.py` (sha256
`b34790e6e43f37d4050538e563f56acc83e6fb1114374fcda534be28e61ad7a1`) beside it. Both lie outside the clone and the
manifest; the freeze review compares them with this section. The script is the sixth binding's block with the
corrections of the sixth attempt's freeze review and run built in:
- the key line strips a trailing carriage return and validates the key's characters (`^[A-Za-z0-9_-]+$`) before
  exporting it, and refuses otherwise; the key is read from the main checkout's `.env` into the environment only:
  never echoed, never on a command line, never in history, never written to a file;
- balances are read in-process by `balance.py` (no curl), which prints only the HTTP status, currency codes and
  amounts, and on an error only the exception's type: before the first scenario, after the first scenario (a watcher
  waits for the second scenario's `P` run directory, `runs/s2b-P`, by name) and after the run;
- before the ledger is created it checks the clone's head and the manifest's sha256 against
  `control/preparation.json` (which the freeze review confirms), a clean tree, a freeze review that sets
  `execution_may_start`, free owned ports, at least 5 GiB free, and that no ledger and no run directory exist;
- it is started detached, because a background shell is killed after two hours:

```bash
setsid nohup bash /home/yichen/.local/state/membrain-setup/runs/r4-attempt7/run-live.sh \
  > /home/yichen/.local/state/membrain-setup/runs/r4-attempt7/run-live.out 2>&1 < /dev/null &
```

The script, verbatim:

```bash
#!/bin/bash
# The seventh maturity attempt's live run (maturity-20261116a), as the binding's "Running the attempt" block
# prescribes. For the lead, after the owner's approval and the independent freeze review; not run in preparation.
# Start it detached (a background shell is killed after two hours):
#   setsid nohup bash /home/yichen/.local/state/membrain-setup/runs/r4-attempt7/run-live.sh \
#     > /home/yichen/.local/state/membrain-setup/runs/r4-attempt7/run-live.out 2>&1 < /dev/null &
# It writes progress to control files only and prints no key, no scenario text and no exception text.
set +x +v; set +H; HISTFILE=/dev/null; unset HISTFILE
R=/home/yichen/.local/state/membrain-setup/runs/r4-attempt7
CLONE=$R/clone
PRIV="$CLONE/evaluations/.maturity-heldout-20261116a"
cd "$CLONE" || exit 90
unset HOST_MODEL MEMBRAIN_SRC PYTHONPATH MEMBRAIN_SEMANTIC MEMBRAIN_EVALUATION_CLOCK C5_STUB
export C5_PYTHON="$CLONE/.venv/bin/python" MEMBRAIN_MODEL_CACHE="$HOME/.cache/membrain/eval-embedding-model" PYTHON_DOTENV_DISABLED=1
leftover=$(env | grep -E '_API_KEY=|^C5_(BILLING|ATTEMPT)|^MEMORY_' | sed 's/=.*//')
[ -z "$leftover" ] || { echo "refused: variables set: $leftover"; exit 91; }

# Frozen state, before the ledger exists: the head and the manifest as control/preparation.json records them (the
# freeze review confirms both), a clean tree, free ports and disk.
want_head=$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["head"])' "$PRIV/control/preparation.json") || exit 92
want_manifest=$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["manifest_sha256"])' "$PRIV/control/preparation.json") || exit 92
[[ $want_head =~ ^[0-9a-f]{40}$ && $want_manifest =~ ^[0-9a-f]{64}$ ]] || { echo "refused: preparation record"; exit 92; }
[ "$(git rev-parse HEAD)" = "$want_head" ] || { echo "refused: head"; exit 92; }
[ -z "$(git status --porcelain --untracked-files=all)" ] || { echo "refused: tree not clean"; exit 93; }
[ "$(sha256sum "$PRIV/control/manifest.json" | cut -c1-64)" = "$want_manifest" ] || { echo "refused: manifest"; exit 94; }
[ -e "$PRIV/control/freeze-review.json" ] || { echo "refused: no freeze review"; exit 94; }
"$C5_PYTHON" -I -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("execution_may_start") is True else 1)' \
    "$PRIV/control/freeze-review.json" || { echo "refused: freeze review does not allow execution"; exit 94; }
! ss -ltn | grep -qE ':(8893|55533)\b' || { echo "refused: an owned port is in use"; exit 94; }
[ "$(df --output=avail -B1 "$CLONE" | tail -n 1)" -ge 5368709120 ] || { echo "refused: less than 5 GiB free"; exit 94; }
[ ! -e "$PRIV/control/ledger.json" ] || { echo "refused: ledger exists"; exit 95; }
[ ! -e "$PRIV/runs" ] || { echo "refused: runs exist"; exit 95; }

# 1. The ledger, from the policy exactly as r4-stub-rehearsal.py creates its own (once; it is never replaced).
"$C5_PYTHON" -I - "$PRIV/control/ledger.json" > "$PRIV/control/ledger-initial.json" <<'PY'
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("evaluation_budget", Path("evaluations/evaluation_budget.py"))
budget = importlib.util.module_from_spec(spec); spec.loader.exec_module(budget)
policy = json.loads(Path("evaluations/maturity-provider-policy-2026-11-14.json").read_text())
models = {name: {key: value for key, value in rate.items()} for name, rate in policy["models"].items()}
print(json.dumps(budget.create_ledger(sys.argv[1], run_id="maturity-20261116a", limit_cny=policy["proposed_limit_cny"],
                                      endpoint=policy["endpoint"], models=models)))
PY
[ -s "$PRIV/control/ledger-initial.json" ] || { echo "refused: ledger not created"; exit 96; }

# 2. The attempt's binding variables.
export C5_ATTEMPT_ID=maturity-20261116a C5_BILLING_LEDGER="$PRIV/control/ledger.json"
export C5_BILLING_POLICY_SHA256="$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["policy_sha256"])' "$PRIV/control/ledger-initial.json")"

# 3. The provider key, into the environment only: a trailing carriage return is stripped and the characters are
#    checked before it is exported; it is never printed, never on a command line, never written to a file.
IFS= read -r DEEPSEEK_API_KEY < <(sed -n 's/^DEEPSEEK_API_KEY=//p' /home/yichen/src/memBrain/.env | head -n 1)
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY%$'\r'}
if [[ $DEEPSEEK_API_KEY =~ ^[A-Za-z0-9_-]+$ ]]; then export DEEPSEEK_API_KEY; echo "key ok"; else unset DEEPSEEK_API_KEY; echo "key refused"; exit 97; fi

# 4. Balance before the first scenario (in-process; status and amounts only).
"$C5_PYTHON" -I "$R/balance.py" > "$PRIV/control/balance-initial.json" || { unset DEEPSEEK_API_KEY; echo "refused: balance"; exit 98; }
# Balance after the first scenario: once the second scenario's P run directory exists (its name only is checked).
( while [ ! -e "$PRIV/control/execution-done" ]; do
    if [ -d "$PRIV/runs/s2b-P" ]; then "$C5_PYTHON" -I "$R/balance.py" > "$PRIV/control/balance-after-s1b.json"; break; fi
    sleep 10
  done ) &
watcher=$!

# 5. The live driver: s1b, then s2b; P then F within each.
date -u +%FT%TZ > "$PRIV/control/execution-started"
"$C5_PYTHON" evaluations/acceptance-attempt-driver.py run --manifest "$PRIV/control/manifest.json" \
    --out "$PRIV/runs" --live > "$PRIV/control/execution-summary.out" 2> "$PRIV/control/execution-progress.err"
code=$?
echo "driver exit $code" > "$PRIV/control/execution-done"

# 6. Afterwards, whatever the result: the balance after the run, then close everything and check.
"$C5_PYTHON" -I "$R/balance.py" > "$PRIV/control/balance-final.json"
unset DEEPSEEK_API_KEY
kill "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null
for run in "$PRIV"/runs/*-P "$PRIV"/runs/*-F; do [ -d "$run" ] && "$C5_PYTHON" evaluations/c5-harness.py --cleanup "$run" >> "$PRIV/control/cleanup.out" 2>&1; done
(ss -ltn | grep -E ':(8893|55533)\b' || echo "ports closed") >> "$PRIV/control/execution-done"
date -u +%FT%TZ >> "$PRIV/control/execution-done"
```

The `.env` line must be the plain form `DEEPSEEK_API_KEY=value` (no quotes). Prices and the provider revalidation
are recorded by the lead before the script starts (`control/provider-revalidation.json`). The driver refuses to start
unless the manifest is the one below, every frozen hash matches, the ledger is unblocked and bound to this attempt and
policy, and the persona entry is the draw of the attempt id. Its stderr holds only paths, keys and exit codes; the run
directories hold scenario content and are never opened by the operator.

## Before spending, during and after

Before spending, record: the exact execution commit and clean status, pins, the interpreter (above), the running
service's build identity, owned-port availability (8893, 55533), free disk (≥ 5 GiB), the revalidated provider model
settings and the initial balance; the preparation's own record is `control/preparation.json`. Frozen through scoring:
runtime, launchers, harness, supervisor, driver, scoring pipeline, review instructions, persona draw, policy, this
binding, briefs, the novelty check, receipts, control files and scenarios (manifest
`evaluations/.maturity-heldout-20261116a/control/manifest.json` in the clone, with its file count, sha256 and
`persona` recorded in the freeze review and `control/preparation.json`; no `practice` mark; made by `freeze.py
--binding evaluations/maturity-acceptance-execution-2026-11-16.md --allowed-models
evaluations/.maturity-heldout-20261116a/control/allowed-models.json`, which refuses an attempt id this binding does
not name). Observe balances before S1, after S1 and after S2, separately from conservative ledger charges.
Credentials are never printed or placed on a command line. After the run, whatever its result, verify that ports
8893 and 55533 are closed and no process of the attempt's profiles remains (`c5-harness.py --cleanup` on each run
directory, then a process listing). Report the turns listed in each run's `host-pauses.jsonl` and the replies with
tool-call markup by count and position. The final independent review examines the frozen source and the gate
evidence. An R4 pass does not by itself allow merge, tag or publication: C5, the repeated R5 protocol and the final
release review remain open. Any source change requires review and qualification; this approval includes no extra
attempt.

## Filled in by the run

Nothing above this section changes after freezing. The frozen copy in the execution clone keeps these placeholders.

- Owner's approval of the paid run (words, date): `<filled in by the run>`
- Provider revalidation and balances (before S1, after S1, after S2): `<filled in by the run>`
- Ledger: initial sha256 and policy sha256 (`control/ledger-initial.json`): `<filled in by the run>`
- Execution summary, validity per scenario, turns listed in `host-pauses.jsonl` and replies with tool-call markup
  (counts and positions): `<filled in by the run>`
- Scores, attribution, memory-remark counts, `gate.json` and the final review: `<filled in by the run>`
