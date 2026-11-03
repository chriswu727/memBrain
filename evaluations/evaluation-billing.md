# Billing control for a prospective evaluation

This control grants no permission to call a model. The release remains frozen, and no real R4/C5 run has been approved. The guard has offline tests; its policy and implementation still need independent review before execution approval is requested.

`evaluation_budget.py` wraps the C5 host and extractor transports. All four scenarios, every arm and every retry use the same absolute `C5_BILLING_LEDGER` path, `C5_ATTEMPT_ID` and `C5_BILLING_POLICY_SHA256`. The policy hash binds the run ID, ledger path, limit, endpoint and model bounds/rates. A switched ledger, attempt or policy is refused before HTTP. Live harness runs refuse a missing ledger; the public stub mode needs none and still refuses external sockets.

Before an approved run, the operator calls `create_ledger(path, run_id=..., limit_cny=..., endpoint=..., models=...)` with the frozen policy. The file must be new. The returned metadata includes the initial ledger hash; freeze it, the absolute path and the policy hash in the attempt pre-checks. Never delete, reset or replace that ledger during an attempt. It contains no API key, messages, replies or scenario contents. It records integer micro-CNY, per-request reservations, conservative settled charges and token counts. The policy for each request model has:

- `context_tokens`: the provider's complete supported context bound, not an estimated prompt length;
- `max_output_tokens`: the provider's complete published maximum output bound, including reasoning; this can exceed the smaller per-request limit;
- `input_cny_per_million` and `output_cny_per_million`: decimal strings for the maximum applicable rates;
- optional `response_models`: exact reviewed response model identifiers, if the provider returns a version rather than the request alias.

The endpoint is the exact HTTPS chat-completions URL. Only text, non-streaming completions and client function tools are permitted. Provider search/fetch tools, multimodal content, unknown request options and alternate endpoints are refused.

For each request, the guard reserves the full context bound at the maximum uncached input rate plus the complete published output bound at the maximum output rate. It does not rely on a thinking model applying the requested `max_tokens` only to final-answer tokens. A response beyond the requested limit is still invalid and retains the complete reservation. It does not predict tokenization, cache hits or discount windows. A POSIX file lock coordinates separate processes; atomic replacement and file/directory sync preserve reservations across restarts. This evaluation utility supports the Mac/Linux acceptance runners, not Windows.

A successful response can reduce its reservation only when its model and integer token accounting match the frozen bounds. Cache hits are still charged at the conservative maximum input rate. HTTP errors, interruptions, malformed usage or out-of-bound responses retain their reservations and block all subsequent requests. Already reserved requests may complete and settle. An unaccounted request left by a crashed process retains its full reservation; it is never automatically reclaimed. A refusal or uncertain bill invalidates the attempt and never authorizes a retry, including a transient 429 or 503. Full-bound reservations can stop an attempt before its actual spend reaches the approved cap; leave enough headroom in the reviewed plan.

Live pre-flight refuses unrelated provider/memory configuration. Local service startup gets an allowlist of system variables and the scenario clock, without provider credentials, and cannot reload dotenv configuration. The scenario creates a fresh profile without configured remote cognition or embedding providers.

The monetary bound depends on the reviewed provider rates and token limits actually holding. Re-check the provider's [pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) and [completion limits](https://api-docs.deepseek.com/api/create-chat-completion/) immediately before approval. Freeze them with the plan and code; do not rely on historical balance estimates. The account balance is a separate reconciliation check and includes any unrelated account use. Subscription scenario authors and judges are outside this API ledger and require their own explicit approval.

`tests/test_evaluation_billing_guard.py` exercises thread/process contention, unknown requests after a crash, failure retention, accounting validation, cache conservatism and protocol rejection using only mock transports. `tests/test_c5_harness.py` covers the live-ledger prerequisite and shared-stop check. A stub or unit result is not a real billing or behavioural acceptance result.
