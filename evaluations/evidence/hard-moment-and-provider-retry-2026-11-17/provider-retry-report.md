# Provider-interruption retry: report (2026-11-17)

## Branch and commits

Worktree `/home/yichen/src/memBrain/.claude/worktrees/agent-a19bb7ce86c07be8f`, branch `worktree-agent-a19bb7ce86c07be8f`, based on `integration/maturity-candidate` `4936e6bb`. Two commits (not pushed):

- `e8a1d98f` Retry a transient provider failure at a charged bound instead of ending the attempt
- `92769cf1` Pass a replaced host call's position on in the persona test
- `bbc1401f` Describe the escape example in the billing text without the escape itself (documentation only, made after the rehearsals)

Commits were allowed, so no patch file was written. Rehearsals ran on the committed tree `92769cf1` (clean). The only later commit changes one phrase in `evaluation-billing.md`, which no test or rehearsal reads, so nothing has to be rerun unless you change these files. Nothing under `src/` changed.

Files: `evaluations/evaluation_budget.py`, `evaluations/c5-harness.py`, `evaluations/acceptance_review.py`, `evaluations/evaluation-billing.md`, `evaluations/c5-harness.md`, `evaluations/acceptance-attempt-driver.md`, `evaluations/maturity-c5-execution-DRAFT.md`, `tests/test_evaluation_billing_guard.py`, `tests/test_c5_harness_hardening.py`, new `tests/test_provider_interruption_retry.py`.

## Read this first (for a billing-safety reviewer)

The guard used to keep an interrupted request's whole 20.054016 CNY reservation. It now settles that request at `min(context, 2 × body bytes + 4 × tool-schema bytes + 16,384)` input tokens plus the request's own `max_tokens` output tokens, at the policy's maximum rates. It also leaves the ledger open. The prompt side rests on two things. First, a byte-level BPE token is at least one UTF-8 byte. Second, the provider renders message text as sent and re-serializes at most the tool schemas, and JSON escaping writes at most 6 bytes for each byte. The 16,384-token allowance has to cover the provider's own template text.

**The completion side adds a dependence that the full reservation deliberately avoided.** It assumes `max_tokens` bounds every completion token, reasoning included. The repository's records support this: `deepseek-v4-pro` with thinking on stopped with `finish_reason=length` exactly at `max_tokens` while spending it all on reasoning (`v1-2026-10-25-longitudinal-followup.md`, `v1-2026-10-25-longitudinal-harness.md`). Every successful settlement also refuses `completion_tokens > max_tokens`. But it is a provider behaviour, not something the guard can enforce. Re-check it, and the byte-level tokenizer, against the provider's documentation before approval. If either is doubted, the nearest sound variant is to charge the policy's `max_output_tokens` instead of the request's `max_tokens`. That costs 10.6 CNY per interruption and still releases the 9.4 CNY context part.

Where the bound cannot be computed, the old behaviour applies:
- no recorded sizes (an older ledger)
- a value that fails validation
- a bound above the reservation

While a request is in flight it still holds its full reservation, so the refusal point counts it in full until it settles. Between an interruption and its retry the ledger is unblocked for up to 150 s. A harness crash in that window exits nonzero, and the run script's `--stop` then blocks the ledger. A SIGKILL of the whole tree would leave the ledger unblocked with no sender. After a failed runner the driver never starts another scenario.

## Decisions: what each became and where

1. **Interrupted settlement** (`evaluation_budget.py`: `INTERRUPTED_CLASSES`, `retriable_status`, `tools_bytes`, `interruption_bound`, `ProviderInterrupted`, `GuardedTransport._interrupted`, `_retain`, `handle_request`).
   - **What counts as an interruption:**
     - the transport classes `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `PoolTimeout`, `TimeoutException`, `ConnectError`, `ReadError`, `WriteError`, `CloseError` and `RemoteProtocolError`;
     - any of those raised while reading the body after a 2xx, 429 or 5xx status;
     - HTTP 429 and 500–599.
   - **What is recorded:** `_reserve` stores two sizes on each entry, `request_bytes` (`len(request.content)`) and `tools_bytes` (the shortest JSON form of `tools`).
   - **On an interruption:** the entry gets `actual_micros` set to the bound and an `interrupted` object holding:
     - `kind`;
     - `error_class` or `http_status`;
     - `prompt_tokens_bound`;
     - `completion_tokens_bound`.
   - **Then:** the ledger stays open and `ProviderInterrupted` (a subclass of `BudgetStop`) is raised. It is raised outside the `except` block, so no provider exception text is chained into it.
   - **Fallbacks:** the old retain-and-block applies when the bound cannot be computed, when the entry has no sizes, or when the bound would exceed the reservation. A request without a usable `max_tokens` is refused before HTTP, as before (`request_refused`).
2. **Bounded retry** (`c5-harness.py`: `INTERRUPTION_WAITS = (30, 120)`, `Host.call`, `Host._interrupted`).
   - After an interruption the client waits 30 s, then 120 s, and sends the identical body again: three sends at most per host call.
   - Each send reserves and settles under the guard and increments `Host.calls` against the cap.
   - These retries are separate from the four tries for an empty reply.
   - **When there is no retry left:** a third interruption, or a cap that leaves no send. The host then blocks the ledger with the interruption's kind (`provider_transport` or `provider_http_status`). It raises a `BudgetStop` after a third interruption, or `RuntimeError("host call cap reached")` when the cap was the reason. The arm then ends with a traceback, as before.
   - The third request's own entry is settled at its bound rather than kept at its full reservation. The bound is true for that request too, so this is still safe. It differs slightly from "as today".
   - `run()` passes `guard=BILLING`, `out=out` and `at={session, turn, round, where}`.
   - The no-resume check also refuses an existing `provider-interruptions.jsonl`.
3. **Still fatal:**
   - any other HTTP status (400, 401, 403, 422 tested);
   - a body cut short after a final 4xx;
   - a response the guard cannot settle (malformed usage, an unapproved response model);
   - a guard refusal for lack of headroom or for a malformed request;
   - `SystemExit`, `KeyboardInterrupt`;
   - `DecodingError`, `LocalProtocolError`, `ProxyError`, `UnsupportedProtocol`;
   - any unrecognised class (`other`).

   All of these keep the reservation, block the ledger and are never retried.
4. **Recording and reports.**
   - **Ledger:** the `interrupted` object above.
   - **Log:** one content-free line per interrupted send, for example `provider interrupted ReadTimeout at session 1 of 3, message 3, round 2: send 1 of 3, retry in 30 s`. The final send's line ends `no retry left: the ledger is blocked and the arm stops`. It carries no message, URL or session id.
   - **No harness event** is written.
   - **`acceptance_review.py`:**
     - `_provider_interruptions` and `_interruption_report` read the new file;
     - `validity` gains `provider_interruptions` per run directory;
     - `validity` refuses a malformed file, or an interruption with `retried: false`;
     - `diagnose` prints counts, positions, send numbers and codes;
     - the log counter gains `provider interrupted <code>`, where the code must be an allowlisted class or `http_429`/`http_5xx`, otherwise `other`;
     - `ProviderInterrupted` was added to the known class names.
   - A run with only retried interruptions is valid.
5. **Timeout.** Kept at 600 s; I found no reason in the code to change it. httpx applies it to each connect, write and read wait, not to a whole send.
   - **Worst case for one call:** three sends that each hang for a full read timeout take 3 × 600 + 30 + 120 = 1,950 s, about 33 minutes. It is longer if bytes trickle in.
   - **Effect on the clock:** in `P` that time runs on the scenario clock (the clock runs in wall time from each session start). A session that outlasts its gap to the next session still ends the run as `clock_already_past`.
   - **Margin:** with sessions at least 3 h apart, the margin is 3 h minus the session's normal duration. One or two such calls fit; about five would use the whole gap by themselves; only the call cap limits their number. `F` has no clock.
   - **Driver:** it has no overall timeout.
6. **Texts.**
   - `maturity-c5-execution-DRAFT.md`: Stop rules rewritten; the closing "no retry" sentence qualified; Billing notes that interruptions count at their bound; a row in "Differences that affect comparability"; a first bullet in "Limits" saying a retried reply is not distinguished in scoring.
   - `evaluation-billing.md`: the old "transient 429/503 stops" sentences replaced by an "Interrupted requests" section (formula, safety argument, example charges, the new dependence) and a "Still fatal" paragraph.
   - `c5-harness.md`: a new bullet under "Harness events, stops and the log", with the time analysis; the no-resume list and the billing sentence updated.
   - `acceptance-attempt-driver.md`: one sentence.
   - `c5-harness.py`: module docstring updated.
   - Not edited: `architecture/v1-acceptance.md`, which does not state this rule. No past binding or record was edited, including `maturity-acceptance-execution-2026-11-16.md`.

## The bound, exactly

```
prompt_tokens_bound = min(context_tokens, 2 × request_bytes + 4 × tools_bytes + 16,384)
completion_bound    = the request's max_tokens (0 < max_tokens ≤ max_output_tokens, else no bound)
charge (micro-CNY)  = ceil(prompt_tokens_bound × input_cny_per_million)
                      + ceil(max_tokens × output_cny_per_million)
```

- `request_bytes` is the body's length as sent.
- `tools_bytes` is `json.dumps(tools, ensure_ascii=False, separators=(",", ":"))` in UTF-8, or 0 without tools. It must not exceed `request_bytes`.

Why the prompt side cannot undercount, for mixed English, German and Chinese:

- **Tokens never exceed bytes.** In byte-level BPE every token encodes at least one UTF-8 byte, and merges only join bytes. That holds whatever the script: about 1 byte per English character, 2 per umlaut, 3 per Chinese character, 4 per emoji.
- **Message text is covered twice over.** The provider renders it as sent, and the JSON body contains every byte of it; escaping only lengthens it. The factor 2 doubles that.
- **Tool schemas are covered up to sixfold.** A template may re-serialize them, and the worst JSON escape is 6 bytes per byte (a six-character backslash-u escape for a one-byte `<`). `2 + 4 = 6` × their shortest form covers it.
- **The allowance covers the template.** 16,384 tokens for the template text, role markers and any tool or reasoning preamble. Each message's JSON framing (at least 29 bytes) already exceeds its few markers.
- **The cap is safe.** A prompt above `context_tokens` is refused by the provider.

I did not use plain "bytes as tokens" because a template that re-serializes the schemas with ASCII-only or HTML-safe escaping could exceed it.

Charges at the frozen rates (9 and 27 CNY per million tokens, `max_tokens` 16,384):

| Request | Charge |
| --- | --- |
| 40 KB body, no tools | 1.31 CNY |
| 20 KB body with `P`'s 17,217 bytes of schemas | 1.57 CNY |
| 60 KB body with those schemas | 2.29 CNY |
| 150 KB body (a late `F` prompt) | 3.29 CNY |

The previous charge was 20.054016 CNY each. This is more than the "about half a yuan" in the brief. Those 0.44 CNY are the output side alone; the rest is the safety margin on the prompt.

## New file formats

**`provider-interruptions.jsonl`** (run directory, format 1): one JSON object per interrupted send, with exactly these keys:

- `format` (1);
- `time` (epoch seconds);
- `session` (the scenario's session id, as in `harness-events.jsonl`);
- `turn` (0-based);
- `round` (0–3);
- `kind` (`provider_transport` or `provider_http_status`);
- either `error_class` (an allowlisted class name) or `http_status` (429 or 5xx);
- `send` (1–3);
- `retried` (bool; it may only be true for sends 1 and 2).

**`validity` → `"provider_interruptions"`:**

```
{"<run> (<arm>)": {"interrupted_sends": n, "retried_host_calls": m, "not_retried": k,
                   "at": [{"session": i, "message": j, "round": r, "send": s,
                           "code": "ReadTimeout" | "http_503", "retried": true}]}}
```

Positions count from 1; there are no session ids.

**Ledger entries** gain `request_bytes` and `tools_bytes`, plus `interrupted` on an interrupted request. The ledger version stays 1, and the policy hash is unchanged.

## Existing tests changed, and why

- `tests/test_evaluation_billing_guard.py::test_provider_failures_never_release_money_for_an_automatic_retry`: the `timeout` and `http` (503) parameters became `http_400` and `http_401`. Timeouts and 503 no longer block, by design; they are now covered in the new file.
- `tests/test_evaluation_billing_guard.py::test_provider_stop_records_safe_cause_without_releasing_reservation`: `timeout`, `body_timeout` (after a 200) and `http` 503 were removed, because they are now interruptions. Added: `body_timeout_after_400`, `decoding` and `keyboard`. `http` now uses 400.
- `tests/test_evaluation_billing_guard.py::test_concurrent_shutdown_keeps_the_first_provider_failure_and_both_reservations`: the first arm's 503 became 400, so the first fatal cause is still preserved.
- `tests/test_c5_harness_hardening.py::test_both_arms_carry_the_seeded_persona_and_p_gets_the_shipped_tools_and_instructions`: its `Host.call` wrapper takes and passes on `at` (the new signature). This was the one failure in the first run.

Added in `tests/test_c5_harness_hardening.py`: `test_a_live_arm_retries_a_transient_provider_failure_and_finishes_valid_evidence`. It is an end-to-end `F` arm on a fake live provider behind the real guard: a timeout on the second send, then all four turns done, the ledger open, one line in the interruptions file, no harness event.

New file `tests/test_provider_interruption_retry.py` (68 tests), covering:
- a timeout followed by success;
- two interruptions followed by success, in three combinations;
- three interruptions, for timeout, 503 and 429;
- the call cap counting retries;
- retries kept separate from empty-reply retries;
- 14 fatal causes;
- a headroom refusal;
- a request without `max_tokens`;
- an unusable `max_tokens`;
- the fallback when no bound can be computed;
- an old reservation without sizes;
- 17 interruption causes at guard level;
- a property test: 400 seeded random prompts in English, German, Chinese, emoji and mixed text, with and without schemas, against a one-token-per-byte tokenizer with the most expansive schema renderings, plus a check that the bound never exceeds the reservation;
- per-language checks;
- the context cap;
- the exact refusal-point arithmetic with an interrupted settlement;
- an in-flight interrupted reservation counting in full;
- two forked arm processes on one ledger, one of them interrupted;
- `validity` valid with counts, nine malformed variants, and an unretried interruption refused;
- `diagnose` content-free, with a planted secret;
- the class allowlists agreeing.

## Test runs (focused runner, under the lock)

| Run | Tests | Result |
| --- | --- | --- |
| `focused-1` | `test_evaluation_billing_guard`, `test_provider_interruption_retry`, every `test_acceptance_*`, every `test_c5_*`, `test_companion_acceptance` | 1035 passed, 1 failed (the wrapper signature above), 679.7 s |
| `focused-2` | after the fix, `tests/test_c5_harness_hardening.py` alone | 80 passed, 362.2 s |

Before the lock I ran two files I had read and that start no service: `test_evaluation_billing_guard.py`, 56 passed, and the new file, 68 passed. `ruff check` on all changed Python files passed, and `git diff --check` is clean.

Logs and JUnit are in `/home/yichen/.local/state/membrain-setup/runs/provider-retry-20261117/` (`focused-1.log`, `focused-1-junit.xml`, `focused-2.log`, `focused-2-junit.xml`). The stopped `database`, `pytest` and `.agent-memory-recovery` folders were removed. No process was left running, and the lock was released.

## Rehearsals (committed tree `92769cf1`, under the lock)

Both ran once each and exited 0.

| Rehearsal | Validity | Gate | Ledger | Ports and network |
| --- | --- | --- | --- | --- |
| `c5-stub-rehearsal.py` | both practice scenarios valid (16 page actions per arm: 14 done, 2 not applicable; persona mirroring 34 of 34) | C5 true | unchanged, 0 requests | closed; 0 network events |
| `r4-stub-rehearsal.py` | valid | R4 true | unchanged, 0 requests | closed; 0 network events |

The rehearsals cannot exercise interruptions (the stub has no guard). Logs: `c5-rehearsal.log` and `r4-rehearsal.log` in the same folder. The rehearsals deleted their own synthetic databases.

## Disagreements, limits, not done

- **The bound is more conservative than the brief's estimate:** about 1.3–3.3 CNY per interrupted send, against the brief's 0.5. Several interruptions eat into the roughly 23–30 CNY of headroom. The draft binding says so.
- **New dependence:** the completion bound relies on `max_tokens` including reasoning (see "Read this first").
- **A deterministic 5xx is retried too.** A 5xx such as 501 would get its two retries before stopping, costing at most three bounds.
- **Connection failures are charged.** `ConnectError` and `ConnectTimeout` are charged their bound even though the request was probably never sent.
- **No cross-check against the ledger.** Validity reads no ledger, so it does not compare the interruptions file with the ledger's `interrupted` entries. A reviewer can compare the counts by hand.
- **One old log line still carries error text.** The existing `host error …` log line for an empty reply still prints `str(error)[:300]`. I left it untouched as out of scope; the new interruption lines carry no text.
- **No real provider was contacted.** The provider's tokenizer and its `max_tokens` semantics are taken from the repository's records and must be re-checked before approval.
