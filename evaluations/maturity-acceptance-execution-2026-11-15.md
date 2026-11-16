# Sixth maturity acceptance attempt (R4 only): execution binding

This binding fixes attempt `maturity-20261115a` before any paid call. It was completed from the
[draft](maturity-acceptance-execution-DRAFT.md) on 2026-11-15 (America/Vancouver) by the operator of the preparation,
under the lead's delegation. The attempt id was fixed by the lead's brief **before** any persona draw was computed.
**This binding authorizes no model call.** The owner's approval of the paid run (the ceiling, the subscription use
for blind scoring and the final review) is recorded separately; the lead starts the run only after it, and only
after the independent freeze review set `execution_may_start` (below). Subscription use so far: isolated scenario
authorship, review and fixing by Sonnet sessions only (no session ran the provider's largest model). There is no
recharge, no automatic additional attempt and no C5 unit in this attempt; C5 remains invalid and unscored.

## Scope decisions (taken by the lead under the owner's delegation)

1. **R4 is judged on the plugin path alone.** Arms: `P` (plugin path) and `F` (full-history reference); gated arm:
   `P`. The proxy path is not part of acceptance. Hosts whose model cannot call tools get recording and recall but
   no notes and are not covered by the gate. The rule text: `architecture/v1-acceptance.md`, R4 "Paths", amended at
   `e0f9f27d` (and `42f7f135`) before this attempt; `docs/releasing.md` records that R4 is failed and that the
   extraction path has been removed with no attempt run without it.
2. **One fixed persona in both arms.** The companion layer is always on, so the run carries a persona: the
   personality type `isfj` = `acceptance_persona.draw("maturity-20261115a")` =
   `IDS[int(sha256(attempt id), 16) % 16]` over `membrain.persona_presets.IDS` (seed `maturity-20261115a`), recorded
   in the manifest's `persona` entry. It was computed for the first time while this binding was written, after all
   scenarios were approved. The harness saves it in `P` before the first session (made by the host, action
   "preset"), so the product's random first type and its one-time announcement never occur; `F` receives the same
   product-rendered `<membrain-persona>` block. Nobody chose the type.
3. **Host model.** `deepseek-v4-pro` through the harness's emulation of the plugin hooks and MCP tools, as in
   attempts 1–5. **It is not Claude Code**: no hook subprocess, no stdio MCP, no Claude Code system prompt; the
   result says how memBrain's plugin path works with this model under this emulation, not how Claude Code behaves.
4. **One arm at a time.** For each scenario `P` runs, its installation is stopped and its ports checked closed,
   then `F` runs; only one host request is ever open against the ledger.
5. **Ceiling.** 80 CNY on the guard's conservative count, one model in the policy, one request in flight.
6. **A turn left unrecorded because the host did not resume recording stops the attempt as invalid**, as before.
   No resume call is inserted on the host's behalf.
7. **Scenario authors, reviewers and fixers** are isolated sessions started by
   `evaluations/acceptance-kit/launch.py` in directories outside every checkout, with only their brief; only
   hashes, counts and fixed codes reached the operator.

## Identities

Attempt `maturity-20261115a` (named "the sixth maturity attempt", never "attempt 6", which names
`v1-2026-11-07-final-acceptance-6.md`) uses the new execution clone
`/home/yichen/.local/state/membrain-setup/runs/r4-attempt6/clone` (Linux x86_64, WSL2, kernel
6.18.58.1-microsoft-standard-WSL2), branch `acceptance/maturity-20261115a`, cloned from integration commit
`67d2924dcee14ffcf320e49c28670229db86f395` (head of `integration/maturity-candidate` when preparation started). The
branch adds one tooling commit, `f3c0569b` (the kit's novelty check, below), and the commit of this binding; the
frozen commit is the branch head that commits this binding, recorded in the freeze review and in
`control/preparation.json`. `src/` and `migrations/` are unchanged from the integration commit. All nine launchers
pin runtime `548674ce18a147b9fae00b547eae5f50dbbcaa69` (pin commit `0b0392bc`; `src/` and `migrations/` are identical
between `548674ce` and `67d2924d`), build `db6172e467bb182f8a8de58375400c2da3f23c608a8dfbda15e86c768960256f`, schema
`3a94d7b6ea6bfba8ff8a4d920aa83001123922f4f90b0a9d6430ef1997b6166d` (`membrain.build_identity` in the clone).

Interpreter: a dedicated virtual environment `.venv` in the clone, made by `uv sync --frozen` (uv 0.13.6) from the
clone's `uv.lock`; CPython 3.12.16 managed by uv, `include-system-site-packages = false`, `membrain` imported from
the clone's `src` (editable). No other virtual environment is on its path (attempt 5's interpreter took
dependencies from another environment; this one does not).

Qualification on this source: the full suite passed in CI on the integration source (4,105 tests, reported by the
lead; not rerun locally in this preparation). In the clone, with every `*_API_KEY` and `C5_*` variable unset and under
the machine's test lock: the acceptance tooling's focused tests (driver, review hardening, review pipeline, scenario
path, kit, c5 harness and its hardening, supervisor, billing guard, proposal selection) **701 passed, 0 failed**; the
novelty check's tests 4 passed; the public stub rehearsal `r4-stub-rehearsal.py` before freezing: freeze of 430
files marked practice, driver complete with both scenarios valid, dry-run checks passed for both, gate computed
(`R4` true on the synthetic verdicts, gated `P`, frozen arms `P`, `F`), zero network events, ledger unchanged with
no request, ports closed. The three batches merged after the tooling was written (host erasure reconciliation,
persona suggestions bound to evidence, deferred-note source lifecycle) needed no tooling change. No installed-package
check was run. These checks are not real-model acceptance.

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
  body, which a host loads only when its model opens the skill (never in the 86 turns of the 2026-11-13 trial). One
  difference from Claude Code remains: Claude Code can defer tool descriptions until the model looks a tool up,
  while `P` gets every description up front. `F` receives the whole earlier history and the same persona block.
  Blinding uses labels A and B (`v1-2026-10-29-phase-b-blind.py … PF`).
- **Scenario persona.** A scenario `PERSONA` card is refused by the harness in a live run and whenever the driver
  passes the manifest's draw; validity (given the draw by the driver) requires every arm's `persona.json` to record
  `source: "seeded"` and the manifest's type.
- **Changed evaluation code** (reviewed in [no-learning-pipeline-2026-11-14.md](no-learning-pipeline-2026-11-14.md)
  and, for `f3c0569b`, in this attempt's freeze review; frozen below): two-arm harness, run script, driver and
  validity; review pipeline with frozen `ARMS = ("P", "F")` and `GATED = ("P",)`; `first.md`, `recheck.md` and
  `companion.md` worded for two replies; the persona draw; post-arm cleanup; R4 precheck mode; the stub host's
  consolidation; the rehearsal; the scenario kit; the kit's novelty check. Criteria, rubric, critical types 1–5,
  resolution rules R1–R5, attribution rules and the pass rule are unchanged.
- **Pass rule (unchanged, as coded in `acceptance_review.py gate`).** Over S1 and S2: `P`'s total ≥ `F`'s total − 1;
  no `P` reply with a standing critical error attributed to memory (two independent attributors; anything but two
  "host" answers, including a missing or invalid answer, is memory); the number of `P` replies with a host-caused
  critical error ≤ the number of `F` replies with a standing critical error. `R4 = P passes`. A tally or sealed
  mapping that does not hold exactly `P` and `F` is refused, a case id may not occur in both scenarios, and with the
  manifest every tally must be bound to its frozen scenario (key, stem, sha256) and to this manifest.

## Differences from attempt 5 that affect comparability

| Change | Attempt 5 | This attempt | Effect on comparison |
| --- | --- | --- | --- |
| Arms | `P`, `E`, `F` in parallel | `P`, then `F` | `E` results have no successor; parallel versus sequential does not change any arm's inputs |
| Gate | `P` and `E` both had to pass | `P` alone | An R4 pass here is a pass of the plugin path only |
| Persona | none in either arm | type `isfj` in both | Every prompt ≈ 250 tokens longer; tone and length of replies may change in both arms alike |
| Tools offered to `P` | 5 (recall, note, boundary, pause, resume; ≈ 7.7k characters of schemas at today's sizes) | all 14 the server lists (16,989 characters of schemas, measured on this source) | New behaviours (consolidation, manner feedback, persona, forget, the low-level tools) can occur |
| Skill text in `P`'s prompt | the whole skill body (≈ 10.4k characters at runtime `7902c16e`) in every call | none (the skill body is 16,593 characters now, 17,164 with its front matter, and a host loads it only on demand) | Guidance attempts 1–5 gave the host in every call is gone; what remains is the server's instructions and the notices |
| Server instructions | not given | in `P`'s system prompt (1,332 characters, sha256 `bb95409e…82a0`, measured on this source) | Instructions the shipped product relies on now reach the host |
| Net standing prompt of `P` | skill + 5 schemas | instructions + 14 schemas + persona block | About +0.5k characters per call besides the persona block |
| Hook path | `membrain.host.*` with default tool names | `membrain.plugin.*` with Claude Code's names | Notice wording as Claude Code's plugin gets it |
| MCP server | new per turn | one per session | A consolidation batch survives between its two calls |
| Consolidation | never requested (tool not offered) | requested when ≥ 5 messages wait; up to two tool calls in a turn | Cue writing now affects recall in `P`; more `P` host rounds |
| Runtime | `7902c16e` | `548674ce` (no extraction model, host consolidation, first-persona logic, local dates, no runtime mode, host erasure reconciliation, persona suggestions bound to evidence, deferred-note source lifecycle) | Product changes since attempt 5 |
| Scenarios | S1/S2 of attempt 5 (now public) | new held-out S1/S2 from a rewritten brief | Briefs rewritten from the public plans; their text differs from attempt 5's (hashes `7b8d8ee1…`, `0e847ff0…`), which was never recovered |
| Review instructions | three replies | two replies; same criteria and rubric; `recheck.md` now also says to ignore wording about tools or memory, as `first.md` always did | A reviewer compares two replies instead of three |
| Blinding | three replies per case | two replies per case | **Partial blinding (limitation).** Any visible sign of memory use in one reply ("Saved.", "Memory's updated.", a repeated answer after consolidation) identifies both replies of that case. Reviewers are told to ignore such wording; `acceptance_review.py remarks` counts, per arm, the case replies and all replies containing a phrase from a fixed list (`MEMORY_REMARKS`), and the record states those counts and shares |
| Ceiling | 280 CNY, two models | 80 CNY, one model | Reservation headroom: refusal once settled charges exceed 59.945984 CNY |
| Scenario sessions | Codex subscription sessions, isolation not observed | Claude Code Sonnet sessions with observed isolation (below) | Authors and reviewers are a different model family than in attempts 1–5 |

Unchanged: host model and call shape (`thinking` enabled, `max_tokens` 16,384, at most 4 rounds, tools in the first
3, at most 6 tool calls, up to 4 attempts for an empty reply, cap 5 × user turns), the billing guard, validity's
rules (plus: arms, persona agreement and no overlap), the scoring pipeline's rules, and the scenario format.

## Scenarios

**Session isolation.** Authors, reviewers and fixers ran through `evaluations/acceptance-kit/launch.py` with the
Claude Code (2.1.322) command `claude -p PROMPT --model sonnet --safe-mode --restricted --strict-mcp-config
--no-session-persistence --tools Read,Write,Edit --disallowedTools Bash,WebFetch,WebSearch,Task --permission-mode
acceptEdits` (`session-commands.json`, sha256 `906a3964…edc4`), each in a new empty directory under
`/home/yichen/.local/state/acceptance-sessions/20261115a` (outside every checkout; the path names no product, because
a session can see its own working directory's path), with `MEMBRAIN_DIRECTORY` pointing to an empty read-only
directory and only PATH, HOME, USER, LOGNAME, LANG, LC_ALL, TERM and TMPDIR in the environment (no credential). The
allowed-models file `control/allowed-models.json` is `["sonnet"]`; `launch.py` accepts a `--model` only by exact
membership, and the alias resolved to `claude-sonnet-5-5` in the probe. The Codex command is marked non-isolating
and was not used.

The isolation was observed on 2026-11-15 by a probe session with the kit's exact flags
(`/home/yichen/.local/state/membrain-setup/runs/r4-isolation-probe-20261115/probe-result.json`, sha256
`8e677e2e…4ba7`): the Sonnet session had only Read, Write and Edit; reads inside its directory were allowed; reads of
`/etc/hostname` and of a repository file were refused as outside the working directory; it saw no memory or MCP
tool, no plugin or memory context, no CLAUDE.md or project instructions; and no transcript was persisted under
`~/.claude/projects`. Its lesson (the session sees its working directory's path) set the workdir root above. What
this does not guarantee: `--restricted` confines the file tools but the model's provider still receives everything
the session reads; admin-managed policy settings still apply; and from outside, the launcher can show what a session
wrote, never prove what it did not read.

**Assignments.** Each author received the neutral brief (`author-brief.md`, sha256 `da83c11f…c108`) and one
assignment file, without source, history, previous scenarios or outcomes. The assignment files (frozen as control
files) state only the case prefix, the two languages and the size:
`control/s1-assignment.md`: prefix `S1`, mainly English, one session in German; `control/s2-assignment.md` and its
byte-identical copy `control/s2b-assignment.md`: prefix `S2`, mainly Chinese, one session in English; both 11 cases
and 60–66 user messages. **German was the operator's choice**, because the kit's brief has the assignment name the
second language and earlier English-main held-out scenarios mostly used German. Neither scenario has page actions or
a persona; both hold only literal assignments, state every weekday correctly and declare one off-the-record stretch
in the shape the harness runs (`c5-precheck.py --r4`, which `freeze.py` runs with the clone's interpreter and
requires to pass). Independent reviewers kept findings private (`reviewer-brief.md`, sha256 `6f75a6f8…f875`);
independent fixers applied corrections (`fixer-brief.md`, sha256 `af8c8fa5…f124`).

**Production, as the launcher reported it**:

| # | Session | Result (launcher's JSON) |
| --- | --- | --- |
| 1 | s1 author 1 | 21 sessions, 61 turns, 11 cases, precheck ok; `6b7203a4…4ab5` |
| 2 | s2 author 1 | 20 sessions, 65 turns, 11 cases, precheck ok; `8a7e58d0…57b7` |
| 3 | s1 reviewer 1 | not approved: 6 findings, 2 blocking |
| 4 | s2 reviewer 1 | not approved: 8 findings, 2 blocking |
| 5 | s1 fixer 1 | applied 6; 61 turns, 11 cases, precheck ok; `2ad6b209…f633` |
| 6 | s2 fixer 1 | applied 7 (of 8 findings); 65 turns, 11 cases, precheck ok; `370e2a8f…840d` |
| 7 | s1 reviewer 2 | not approved: 1 finding, 1 blocking |
| 8 | s2 reviewer 2 | not approved: 5 findings, 2 blocking |
| 9 | s1 fixer 2 | applied 1; 61 turns, 11 cases, precheck ok; `8d3ab00b…232d` |
| 10 | s2 fixer 2 | applied 5; 65 turns, 11 cases, precheck ok; `503c896e…486d` |
| 11 | s1 reviewer 3 | **approved**: 0 findings; receipt `c698ab7d…22d8` |
| 12 | s2 reviewer 3 | not approved: 4 findings, 1 blocking |
| 13 | s2 fixer 3 | applied 4; 65 turns, 11 cases, precheck ok; `7ab143a2…c473` |
| 14 | s2 reviewer 4 | not approved: 7 findings, 1 blocking |
| 15 | s2b author 1 | 19 sessions, 63 turns, 11 cases, precheck ok; `4c6c0404…5358` |
| 16 | s2b reviewer 1 | **approved**: 6 findings, 0 blocking (all minor; not applied, since a fix would need a new review); receipt `f1a0a119…bdff` |

Every session exited 0 and produced its outputs; every author and fixer version passed `c5-precheck.py --r4` with no
code (the precheck includes the weekday check, `weekday_mismatch`). Sixteen Sonnet sessions wrote, reviewed or fixed
the scenarios; with the isolation probe, seventeen Sonnet sessions were used for this attempt's preparation. The
launcher does not report cost, and the operator did not open the session logs, so their subscription cost is not
known.

**The first S2 was not approved and is unused.** S2 took **four review rounds where three were planned** (blocking
findings 2, 2, 1, 1): the limit of three was the preparation's operating limit, and the lead allowed one more
round after the third. The first S2 fixer applied 7 of its 8 findings. After the fourth reviewer did not approve, S2
was started over, as the lead had decided in advance, by a fresh author under the new key `s2b` with the byte-identical assignment (prefix `S2`: the kit
takes the case prefix only from the assignment file and ties it to no key; the first S2 never enters a manifest, so
its case ids cannot collide with the new one's). The first S2's final file (`s2/scenario_s2.py`, sha256
`7ab143a2b7055d93c9b3e251d19a508dd52950c13b04bd261ce5dfa8d9eec473`), its earlier versions, reviews, findings and fixes
stay in the private root as unused evidence; it is not frozen and is never run.

**Final scenarios** (from the receipts): S1 `8d3ab00b3b990c488f359e09468e89d75b13fd92ce146b468e27152d125e232d` (11 cases, 61 turns,
21 sessions), key `s1`, `s1/scenario_s1.py`; S2 `4c6c0404fab7de758f9592fd65b76c3d4f949761a85e52b5d3c902b214a15358` (11 cases, 63 turns,
19 sessions), key `s2b`, `s2b/scenario_s2b.py`; receipts `control/s1-review-approved.json`
`c698ab7db0ebfaf6275430900e6109286fd8ef486a9d0f893f3d053755c522d8`, `control/s2b-review-approved.json` `f1a0a119a7cd99df06e0cb51c7a0ed2fd8cab771354fc0725c49be74b3b7bdff`.

**Novelty** (`evaluations/acceptance-kit/novelty.py`, added in `f3c0569b`, prints only numbers and booleans). The
earlier scenarios are the 21 public ones at `67d2924d` (every top-level `evaluations/*scenario*.py` that assigns
`SESSIONS_LONG`, and the two scenario files of attempt 5's evidence), plus 15,571 64-hex strings recorded under
`evaluations/` there. The **stop threshold, 10% largest 8-gram overlap, was fixed before any held-out file was
measured**, from the public scenarios' largest mutual overlap (leave-one-out) of 2.64%. Measured on the final files:
S1: hash new, largest overlap 0.03% (all earlier together 0.03%, 2,895 distinct 8-grams); S2 (`s2b`): hash new,
largest 0.43% (together 0.76%, 4,612 8-grams); both within the threshold. For comparison, the unused first S2 measured
0.26% (together 0.53%); `s2b` shares 0.35% of its 8-grams with the unused first S2 and 0.00% with S1. Both final hashes
differ from every earlier scenario hash.

**Session directories.** After each session's outputs had been moved into the private root by the launcher, the
finished sessions' working directories (redundant copies outside the private root) were removed with `rm -rf`
without being opened: the twelve sessions of the first round at 2026-11-16 03:51 UTC, and every later session's
directory right after it finished. Empty directories with the same names were left so that the launcher's session
numbering (which counts directories) continues and no earlier review, findings or fixes file is overwritten. The
private root keeps its own copies and the sessions' logs, which the operator never opened.

## Order, validity and scoring

Order is `s1`, `s2b`. Strict validity is required after each scenario; both must be valid before blind scoring. First
reviews, 22 independent case rechecks, conditional R5 checks, resolutions and double attribution follow the unchanged
protocol (runbook: `evaluations/acceptance-review/companion.md`, R4 unit). No score or recording expectation is
adjusted manually.

## Billing

After the owner's approval, [official prices](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) and
[completion limits](https://api-docs.deepseek.com/api/create-chat-completion/) are revalidated on the day of the run
and recorded in `control/provider-revalidation.json`; a mismatch stops preparation. Maximum input/output rates are
9/27 CNY per million for `deepseek-v4-pro`; conservative context/output bounds 1,048,576/393,216 tokens. The policy
file `evaluations/maturity-provider-policy-2026-11-14.json` (sha256
`e7b91106b206412c608b33b0f43adc1d6f7db7c19da0c05a82a620198fb5689f`) admits only `deepseek-v4-pro` with a proposed
limit of 80 CNY and one request in flight. Search/Fetch and other provider services are excluded.

Private evidence is Git-excluded (`.git/info/exclude`) under
`/home/yichen/.local/state/membrain-setup/runs/r4-attempt6/clone/evaluations/.maturity-heldout-20261115a/` (mode
700). Its absolute `control/ledger.json` binds this attempt, the 80 CNY ceiling and the policy; it is created by the
lead after approval, from the policy exactly as the rehearsal creates its ledger, and its initial SHA-256 and bound
policy hash (`<filled in by the run: control/ledger-initial.json>`) are recorded before any completion. Every host
call and permitted malformed-response retry uses it. Each request reserves 20.054016 CNY (1,048,576 × 9 + 393,216 × 27
per million); with one request open the guard refuses once settled charges exceed 59.945984 CNY (with two open it
would refuse above 39.891968 CNY, which is why the arms run one after the other).

Expected conservative charge (guard's count; characters at about 3.7 per token, as `budget.md`):

| Item | CNY |
| --- | --- |
| `P`, attempt-5 workload (S1 + S2, 173 host rounds) | 15.63 |
| `P` standing prompt: − skill 10.4k, + 9.3k more schema characters (all 14 tools, low-level ones included), + 1.33k instructions, + 0.3k notice ≈ +0.5k characters × ≈ 210 calls | +0.3 |
| Consolidation: ≈ 9 batches per scenario, 2 calls each | +5.4 |
| Persona block, both arms (≈ 250 tokens a call) | +0.8 |
| `F`, attempt-5 workload | 11.52 |
| Billed empty-reply retries | +0.4 |
| **Expected total** | **≈ 34** (plausible 26–45) |

Headroom: about 26 CNY between the expected settled total and the 59.945984 CNY refusal point (≈ 1.76 ×). The real
bill is expected at about a fifth of the guard's count, ≈ 7–15 CNY depending on the time of day. Unknown usage stays
reserved.

## Stop rules

- Provider or transport failure (including transient 429 and 5xx), a guard refusal, invalid evidence, a reached cap,
  a degraded harness, a frozen input that changed, an existing run directory or a driver error stops further work:
  the driver (or the run script's supervisor) blocks the shared ledger, terminates the arm and closes the attempt's
  disposable services. No new scenario starts after a failed or invalid one; nothing is retried automatically.
- A turn left unrecorded because the host did not resume recording makes the scenario invalid.
- No stopped ledger is reopened, no unused allowance is transferred, and no extra attempt is included. A port wait
  that times out before any arm starts costs nothing and may be retried once its cause is found from socket state.
- An invalid scenario is preserved, unscored; `diagnose` emits only counts, event kinds and positions.
- A second refused first, second or resolution review output stops scoring for the owner. Two unusable R5 responses
  cannot clear a critical mark; missing or invalid attribution counts as memory-caused. No score is changed by hand.
- Earlier ledgers, reservations and sealed evidence are preserved separately.

## Running the attempt (for the lead, after approval; not run in preparation)

Run in one fresh bash, from the clone, with nothing else from earlier attempts in the environment. The key is read
from the main checkout's `.env` into the environment only: it is never echoed, never on a command line, never in
history, never written to a file. The `.env` line must be the plain form `DEEPSEEK_API_KEY=value` (no quotes).

```bash
set +x +v; set +H; HISTFILE=/dev/null; unset HISTFILE
CLONE=/home/yichen/.local/state/membrain-setup/runs/r4-attempt6/clone
PRIV="$CLONE/evaluations/.maturity-heldout-20261115a"
cd "$CLONE"
unset HOST_MODEL MEMBRAIN_SRC PYTHONPATH MEMBRAIN_SEMANTIC MEMBRAIN_EVALUATION_CLOCK C5_STUB
export C5_PYTHON="$CLONE/.venv/bin/python" MEMBRAIN_MODEL_CACHE="$HOME/.cache/membrain/eval-embedding-model" \
       PYTHON_DOTENV_DISABLED=1
env | grep -E '_API_KEY=|^C5_(BILLING|ATTEMPT)|^MEMORY_' | sed 's/=.*//'   # must print nothing (names only)

# 1. The ledger, from the policy exactly as r4-stub-rehearsal.py creates its own (once; it is never replaced).
"$C5_PYTHON" -I - "$PRIV/control/ledger.json" > "$PRIV/control/ledger-initial.json" <<'PY'
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("evaluation_budget", Path("evaluations/evaluation_budget.py"))
budget = importlib.util.module_from_spec(spec); spec.loader.exec_module(budget)
policy = json.loads(Path("evaluations/maturity-provider-policy-2026-11-14.json").read_text())
models = {name: {key: value for key, value in rate.items()} for name, rate in policy["models"].items()}
print(json.dumps(budget.create_ledger(sys.argv[1], run_id="maturity-20261115a", limit_cny=policy["proposed_limit_cny"],
                                      endpoint=policy["endpoint"], models=models)))
PY
cat "$PRIV/control/ledger-initial.json"   # ledger path, run id, policy_sha256, initial_sha256: record them

# 2. The attempt's binding variables.
export C5_ATTEMPT_ID=maturity-20261115a C5_BILLING_LEDGER="$PRIV/control/ledger.json"
export C5_BILLING_POLICY_SHA256="$("$C5_PYTHON" -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["policy_sha256"])' "$PRIV/control/ledger-initial.json")"

# 3. The provider key, into the environment only (the value is never printed).
IFS= read -r DEEPSEEK_API_KEY < <(sed -n 's/^DEEPSEEK_API_KEY=//p' /home/yichen/src/memBrain/.env | head -n 1)
export DEEPSEEK_API_KEY
[ -n "$DEEPSEEK_API_KEY" ] && echo "key loaded" || echo "key missing"

# 4. Record prices, the initial balance and preparation checks (control/provider-revalidation.json,
#    control/balance-initial.json), then the live driver: s1, then s2b; P then F within each.
"$C5_PYTHON" evaluations/acceptance-attempt-driver.py run --manifest "$PRIV/control/manifest.json" \
    --out "$PRIV/runs" --live > "$PRIV/control/execution-summary.out" 2> "$PRIV/control/execution-progress.err"
echo "driver exit $?"; tail -n 1 "$PRIV/control/execution-summary.out"

# 5. Afterwards, whatever the result: close everything and check.
unset DEEPSEEK_API_KEY
for run in "$PRIV"/runs/*-P "$PRIV"/runs/*-F; do [ -d "$run" ] && "$C5_PYTHON" evaluations/c5-harness.py --cleanup "$run"; done
ss -ltn | grep -E ':(8893|55533)\b' || echo "ports closed"
```

The driver refuses to start unless the manifest is the one below, every frozen hash matches, the ledger is unblocked
and bound to this attempt and policy, and the persona entry is the draw of the attempt id. Its stderr holds only
paths, keys and exit codes; the run directories hold scenario content and are never opened by the operator.

## Before spending, during and after

Before spending, record: the exact execution commit and clean status, pins, the interpreter (above), the running
service's build identity, owned-port availability (8893, 55533), free disk (≥ 5 GiB), the revalidated provider model
settings and the initial balance; the preparation's own record is `control/preparation.json`. Frozen through scoring:
runtime, launchers, harness, supervisor, driver, scoring pipeline, review instructions, persona draw, policy, this
binding, briefs, the novelty check, receipts, control files and scenarios (manifest
`evaluations/.maturity-heldout-20261115a/control/manifest.json` in the clone, with its file count, sha256 and
`persona` recorded in the freeze review and `control/preparation.json`; no `practice` mark; made by `freeze.py
--binding evaluations/maturity-acceptance-execution-2026-11-15.md --allowed-models
evaluations/.maturity-heldout-20261115a/control/allowed-models.json`, which refuses an attempt id this binding does
not name). Observe balances before S1, after S1 and after S2, separately from conservative ledger charges.
Credentials are never printed or placed on a command line. After the run, whatever its result, verify that ports
8893 and 55533 are closed and no process of the attempt's profiles remains (`c5-harness.py --cleanup` on each run
directory, then a process listing). The final independent review examines the frozen source and the gate evidence.
An R4 pass does not by itself allow merge, tag or publication: C5, the repeated R5 protocol and the final release
review remain open. Any source change requires review and qualification; this approval includes no extra attempt.

## Filled in by the run

- Owner's approval of the paid run (words, date): `<filled in after approval>`.
- Provider revalidation: `<control/provider-revalidation.json>`; balances: `<initial / after S1 / after S2>`.
- Ledger: `<initial sha256, policy sha256>`.
- Execution summary, validity, scoring, `gate.json`, memory-remark counts, final review: `<filled in by the run>`.
