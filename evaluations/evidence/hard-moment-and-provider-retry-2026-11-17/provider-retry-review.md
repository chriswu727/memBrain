# Provider-interruption retry: independent billing-safety review (2026-11-17)

Reviewed: `0967fa49`, `b3ce0f12` and `ff6aed99` on `integration/maturity-candidate`, plus the files named in the brief and the implementer's report. No file in the repository was changed. I made no model call, sent no request to the provider's API, used no key, and ran no pytest. I read the provider's public documentation pages (pricing, chat-completion reference, thinking mode, token usage, error codes, rate limit). I also downloaded the provider's published V4 tokenizer archive (`cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip`, linked from the token-usage page) into my scratchpad. I inspected its JSON and ran it offline with the repository venv's `tokenizers` 0.23.3, without executing the archive's own script.

## Verdict

**Yes, on billing safety: it is safe to use in a paid attempt as committed.** I found no case where the guard's count is lower than the provider's bill while the two stated assumptions hold. I verified one of them, the tokenizer (see Q1). The other, that `max_tokens` bounds reasoning tokens, has strong evidence in the repository's records but the provider's documentation does not state it. The ceiling also holds with any number of interruptions.

I recommend fixing F1 (availability) and F5 (the texts) before the binding is frozen. Neither fix is needed to keep the ceiling. The other findings are minor.

## Findings

### F1. Major (availability; fails safe). A 2xx without complete billing JSON still loses the attempt at the full 20.05 CNY

- **Where:** `evaluations/evaluation_budget.py` `_settle`, lines 231–236 and 244–249, reached from `handle_request` line 315.
- **What:** A 2xx response whose body is read completely but is not a usable completion stays fatal. That covers three cases:
  - a body that is only whitespace;
  - JSON without `usage`;
  - JSON cut short, but ended cleanly.

  The guard settles such a response as `response_billing`: it keeps the whole reservation and blocks the ledger.
- **Why it matters:** The provider documents that a non-streaming request under load "continuously return[s] empty lines" while it waits. It also documents that "if the request has not started inference after 10 minutes, the server will close the connection". The 200 status and the blank lines are sent first. If the server then gives up by ending the body cleanly (blank lines only, or an error object), the attempt is lost exactly as on 2026-11-17. Only an abrupt close gives a `RemoteProtocolError`, which is now retried. The documentation does not say which of the two happens.

  Billing is not the obstacle. This response's cost is bounded by the same request bound as a timeout, because nothing more than a full completion of this request can have been billed.
- **Smallest fix I would accept:** In `_settle`, call `_interrupted` instead of failing in either of these cases:
  - the status is 2xx and `response.json()` raises `ValueError`;
  - the JSON object has no `usage` key.

  Use a new fixed kind such as `provider_incomplete_body`. Add that kind to the validity allowlist and the log code allowlist. Keep everything else fatal: usage present but inconsistent, a wrong response model, and `completion_tokens > max_tokens`.

### F2. Minor (residual assumption; I accept it). The completion bound rests on behaviour the documentation implies but never states

- **Where:**
  - `evaluation_budget.py` `interruption_bound`, lines 61–77 (the request's `max_tokens`, not the policy's `max_output_tokens`);
  - `evaluation-billing.md` line 27.
- **What the provider documents:**
  - `max_tokens` is "the maximum number of tokens that can be generated in the chat completion".
  - Its default is "8K in non-thinking mode, 64K in thinking mode (128K with `reasoning_effort` set to `max`)". A larger default in thinking mode only makes sense if reasoning counts toward it.
  - `completion_tokens_details.reasoning_tokens` is a "breakdown of tokens used in a completion", so `completion_tokens` includes reasoning.
  - `finish_reason=length` means "the maximum number of tokens specified in the request was reached".
  - No page says in words that reasoning counts toward `max_tokens`. The thinking-mode guide does not mention `max_tokens` at all.
- **What the repository shows:**
  - `v1-2026-10-25-longitudinal-pilot.json` records `reasoning_tokens: 4096` at a 4,096 bound.
  - `v1-2026-10-25-longitudinal-followup.md` records 16,384 reasoning tokens at a 16,384 bound with `finish_reason=length`. Its two calls total 17,629 completion tokens against 20,480 reserved; the per-call split is not recorded.
  - On every success the guard refuses `completion_tokens > max_tokens` (line 238). The 265 requests settled on 2026-11-17 all passed that check.
- **Exposure if it is wrong:** at most (393,216 − 16,384) × 27 / 10⁶ = 10.174464 CNY uncounted per interrupted send.
- **Smallest fix:** No code change. State the documentation's exact wording and the 265-request evidence in `evaluation-billing.md`, so the "re-check before approval" has a concrete answer. The alternative of charging `max_output_tokens` costs 10.6 CNY or more per interruption. At this headroom that would let only one to three interruptions fit, and I would not choose it.

### F3. Minor. Deterministic 5xx codes are retried and burn three bounds

- **Where:** `evaluation_budget.py` `retriable_status`, lines 51–53.
- **What:** Every status from 500 to 599 is an interruption, including 501 and 505, which a resend will not change. The provider documents 500 ("retry … after a brief wait"), 503 ("retry … after a brief wait") and 504.
- **Cost:** at most three bounds (about 4 to 10 CNY in this harness), then the stop. That is less than the old 20.05, so it is bounded.
- **Smallest fix:** retry only 429, 500, 502, 503 and 504.

### F4. Minor (evidence). The ledger cannot be lined up with the interruption files

- **Where:**
  - `evaluation_budget.py` `_reserve`, lines 215–219: an entry has no time, sequence or caller position, and `_write` sorts the keys, so the dict of uuid4 ids loses all order;
  - `acceptance_review.py` `_provider_interruptions` (line 979) and `validity` (lines 1258–1263): neither reads the ledger.
- **What an auditor can do today:**
  - count the ledger entries carrying `interrupted` per cause against the lines of every run directory's `provider-interruptions.jsonl`;
  - pair each interrupted entry with a later entry that has the same `request_bytes` and `tools_bytes`, which are the retry's;
  - match `host-rounds.jsonl` usage `(prompt_tokens, completion_tokens)` as a multiset against the settled entries.

  The auditor cannot prove which send was charged what, or in what order.
- **Why it matters:** Not for the ceiling. The ledger alone bounds spend. But a harness defect that retried without writing its line would go unnoticed.
- **Smallest fix:**
  - Add a content-free monotonic `seq` and `reserved_at`/`settled_at` epoch seconds to each entry.
  - Add `request_bytes` to each interruption line.
  - Have the driver (or a one-off audit script) check after each scenario that, per code, the cumulative count of interrupted ledger entries equals the cumulative count of lines across the run directories so far.

### F5. Minor (texts). The worst case and two arguments are stated loosely

- **`maturity-c5-execution-DRAFT.md` lines 248–256:**
  - "A few CNY each" and the examples 1.57 and 3.29 are examples, not a maximum. For this harness an interrupted send costs 0.442368 CNY of output plus 18 × body-KB/1000 CNY of prompt, plus 0.147 CNY (plus 0.62 CNY with `P`'s schemas). Its absolute ceiling is 9.879552 CNY, reached at a body of about 516 KB.
  - A host call that fails three times costs up to three bounds.
  - The billing section keeps "Headroom to the refusal point about 1.6×" without saying what interruptions do to it. At the expected 30–50 CNY on the guard's count, the free headroom to 59.945984 is about 10–30 CNY: roughly 3 to 9 interruptions at 3.3 CNY, and only about 3 at the upper end.
  - It should also say that exhausting the headroom ends the attempt with `reservation_limit`.
- **`evaluation-billing.md` line 27:**
  - "JSON escaping writes at most six bytes for each byte … `2 + 4 = 6` covers that" does not cover a template that pretty-prints schemas. Indentation is not escaping, and with deep nesting of short values it can exceed six bytes per byte. The bound still holds, but for another reason: whitespace runs merge into few tokens (5,000 spaces are 40 tokens; see Q1), and the factor 2 leaves a whole spare body of slack. Say that instead.
  - "Message text is rendered into the prompt as sent" is not documented for the V4 service. The tokenizer archive's `chat_template` is the old V3-style template, which renders neither tool schemas nor reasoning, so it says nothing about what the service adds. Label it an assumption covered by the slack and the 16,384 allowance.
- **`evaluation-billing.md` line 5** (pre-existing): "wraps the C5 host and extractor transports". The harness wraps only the host; the extraction arm E no longer exists.

### F6. Minor (comparability). Scenario-clock drift in `P` is not flagged

- **Where:** `c5-harness.py` `Host.call` lines 543–557. The waits plus up to 3 × 600 s of hangs run on `P`'s wall-time scenario clock.
- **What:** Validity flags only `clock_already_past` at the next session. Inside a session, `P`'s scenario time can move up to about 33 minutes per affected call while `F` has none. Companion items such as "mood within hours" are time-sensitive.
- **Fix:** In validity's `provider_interruptions` report, give each session's total interruption delay (from the line times). Name the affected sessions in the record. A threshold is optional.

### F7. Minor (pre-existing; fails safe). A SIGTERM can deadlock the process on its own lock

- **Where:** `c5-harness.py` `interrupted()` line 1850, together with `evaluation_budget._locked` line 119.
- **What:** The SIGTERM handler calls `BILLING.stop()`, which opens the lock file again and takes `flock`. If the signal lands while the main thread is inside a `_locked` block (now also `_interrupted`), the process blocks on a lock it already holds on another descriptor, until the driver's SIGKILL. The in-flight entry keeps its full reservation, so no money is at risk.
- **Fix:** Keep a module flag set while `_locked` is held. When the flag is set, the handler raises `SystemExit` without calling `stop`; the run script's `--stop` blocks the ledger.

### Observation (outside this change)

The thinking-mode guide now says that with `tools`, "`reasoning_content` must be fully passed back to the API in all subsequent requests … the API will return a 400 error". The harness drops `reasoning_content` from earlier turns (`c5-harness.py` lines 1738 and 1767). Past runs got no 400, so the service evidently tolerates this today. If it is enforced, every `P` turn after a tool call becomes a fatal 400 that keeps 20.05 CNY. Worth a look before the run.

## Answers to the six questions

**1. Can the guard's count be lower than the bill?**

Not while the two assumptions hold.

- **Each failure case:** The bound charges the request's whole possible prompt plus its whole `max_tokens` at the peak miss rates. It therefore covers each case in the brief at full cost:
  - a send that timed out on our side but completed and was billed in full by the provider;
  - a 5xx after generation started;
  - a connection reset mid-body;
  - a 429, which is probably not billed at all.
- **Rates:** The pricing page (read today) gives `deepseek-v4-pro` peak rates of 9 (miss) and 27 per million, off-peak half that, cache hits 0.30. It lists no tier by context length, 1M context and 384K (= 393,216) output, matching the policy. Cached input only lowers the bill, and the pricing page lists no other charge for a chat completion without web tools. The guard refuses web tools, which use their own `type`.
- **Tokenizer:** I verified "tokens ≤ bytes" on the published V4 tokenizer:
  - it has a ByteLevel pre-tokenizer and decoder, BPE with 128,000 entries, no empty vocabulary entries and an empty normalizer, so no Unicode expansion;
  - 3,000 random mixed-script strings plus adversarial ones (CJK, emoji, `<`, the six-character backslash-u escape of `<`, whitespace runs, JSON punctuation, single digits) all gave at most 1.0 token per byte.
- **Template:** The service's own template is unpublished. It would have to add more than one extra copy of the body plus 16,384 tokens plus 4 × the schemas to break the prompt bound, which I consider implausible. Pretty-printing is covered by token merging and the slack, not by the escape argument (F5).
- **Completion side:** `max_tokens` covering reasoning is implied but not stated by the documentation, and strongly supported by the records (F2).
- **Where the bound could fail:** a service-side preamble larger than a body plus 16K tokens, or reasoning not counted against `max_tokens`. Nothing else.

**2. The ceiling.**

A request is admitted only if S + Σᵢ₌₁ᵏ bᵢ + 20.054016 ≤ 80, where:

- S is the settled successes;
- bᵢ is the bound of each of k interruptions, with bᵢ ≤ 9.879552 and realistically 1.3–3.3.

So successes can reach at most 59.945984 − Σbᵢ before `reservation_limit`.

- **Possible spend:** While the bounds hold, total possible spend never exceeds 80 CNY: in-flight requests count at full reservation, each retry reserves before it is sent, and the arms and scenarios run strictly one after another.
- **Two processes on one ledger:** they are serialized by `flock` and each reserves in full.
- **The window between an interruption and its retry:** nothing is in flight, so there is no money at risk.
- **A crash or SIGKILL in that window:** it leaves the ledger unblocked with nothing reserved. That is a process-integrity gap, not a spend gap, and the driver never starts another scenario after a failed runner.
- **The third failure:** settled at its bound, then `guard.stop`.
- **Worst case:** 80 CNY if the bounds hold. If F2's assumption fails: 80 + k × 10.174464 CNY.

**3. What a retry can do besides cost.**

- **Side effects:** An abandoned send's reply is never used, because the guard raises before returning a response. Tool calls are executed only from the reply `Host.call` returns, and the prompt hook ran once, before the call. So there is no duplicate side effect. The provider is stateless.
- **Loop bounds:** The loop is bounded: at most 3 interrupted sends and 4 empty-reply tries per host call (at most 6 sends), each counted against the cap. `deferred_stop` is not involved: it covers bookkeeping after a call.
- **Clock:** A retried call can take up to about 1,950 s (longer if bytes trickle in, since there is no total timeout per send). It moves `P`'s scenario clock. That is not silent (the interruption lines have times and `seconds` is in the row), but it is not flagged within a session (F6).

**4. What still stops an attempt, and should it?**

- **Correctly fatal:** 400, 401, 402, 422 and other 4xx (deterministic or account problems), malformed usage, an unexpected response model, and the classes `LocalProtocolError`, `UnsupportedProtocol` and `other`.
- **`ProxyError`:** it cannot occur, because the client gets an explicit transport and httpx then ignores environment proxies.
- **`DecodingError`:** arguably transient, but rare without compression.
- **Retried although deterministic:** 501, 505 and the like (F3). The cost is bounded.
- **Fatal although plausibly transient:** a 2xx that ends without complete JSON or `usage`. This is the most likely remaining way to lose an attempt to load (F1).
- **408:** fatal. The provider documents it only for uploads.

**5. Evidence.**

- **Partly reconstructable:** counts per cause, retry chains via equal `request_bytes`/`tools_bytes`, and used replies via usage multisets.
- **Not exactly reconstructable:** the ledger has no order, time or position (F4).
- **"Every used reply came from a settled request":** this holds by construction (a response is returned only after `_settle` succeeded). It can be checked only statistically from the files.
- **The missing cross-check:** it does not matter for the ceiling. It matters for catching a harness defect, so add the count check.

**6. The texts.**

- **What is accurate:** Both texts state the rule, the formula, the fallback, the still-fatal list and the new completion-side dependence truthfully, and both preserve the 2026-11-17 failure. `evaluation-billing.md` and the implementer's report correctly drop "about half a yuan" (the stop record keeps it as the original estimate, which is fine).
- **What is missing or loose** (F5):
  - the draft gives only examples, not the per-send maximum for this harness;
  - it does not quantify what interruptions do to the 1.6× headroom (about 3–9 interruptions fit, about 3 at a 50 CNY count);
  - the escape argument is not the real reason the schema term is safe;
  - "rendered as sent" is an assumption, not documented.

## What I could not verify

- **Reasoning and `max_tokens`:** whether the service counts reasoning tokens against `max_tokens` in every case. The documentation implies it but does not say it.
- **Billing of abandoned requests:** whether the provider bills a request the client abandoned or a 5xx'd request, and whether a 429 is ever billed. Not documented; the bound charges as if billed in full.
- **The service-side template:** the V4 service's prompt template (tool-schema rendering, reasoning preamble, any hidden system text). The downloadable template is V3-style, so the 16,384-token allowance and the factor 2 are covered by argument, not by documentation.
- **The server's 10-minute close:** how the server ends a response it closes after 10 minutes without inference (clean end or abrupt close), which decides whether F1 bites.
- **Same tokenizer:** whether the service uses exactly the tokenizer it publishes (dated 2026-08-28; the model version listed is DeepSeek-V4-Pro-0813).
- **Tests:** I did not run the tests. I read the test names and the bound property test (`tests/test_provider_interruption_retry.py` lines 374–416), whose worst-case model I find sound.
