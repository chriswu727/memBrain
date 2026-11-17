# A hard time got through together is a shared moment; a provider's transient failure no longer ends an attempt

Runtime `3afc0dda`; launcher pin `e82ad9d6`; acceptance tooling at `3b3c32ef`. No migration, no new dependency. It closes no release gate: **C5 remains unscored.** Both changes come from the [first two-arm companion attempt](maturity-c5-attempt-stop-2026-11-17.md), which stopped on a provider timeout.

## 1. The hard shared moment (product)

**The defect.** In the attempt's second scenario the user wrote, in Chinese, that the two of them had got through a bad night together and thanked the agent; the host answered warmly and saved no shared moment. The tool server's standing instructions defined a hard moment only as "a difficult time between you (the user upset with you, a mistake of yours you sorted out together)". The design is wider: a hard time counts toward familiarity and mellows with time and company, and the skill text already says "a difficult time the two of you went through".

**The change.** The instructions now say: "hard is for a hard time you got through together (a bad night you sat with them through, or the user upset with you)". They are 1,388 characters of a budget of 1,400 (1,398 with OpenClaw's tool names). Nothing else changed in the product.

**Tried on the host model** (`deepseek-v4-pro`, the plugin path's standing prompt on this source, public messages written for the probe, three trials each; [script](evidence/hard-moment-and-provider-retry-2026-11-17/hard-moment-probe.py), [results](evidence/hard-moment-and-provider-retry-2026-11-17/hard-moment-probe-results.json)):

| Situation | Saved as a hard shared moment |
| --- | --- |
| A bad night told in Chinese, then thanks for staying through it | 3 of 3 |
| The same kind of night in English | 3 of 3 |
| The user upset with the agent over a mistake, then reconciled | 3 of 3 |
| A long day with a small consolation (control) | 0 of 3 |

In all six "bad night" trials the host saved the moment at the message that told of the night, before the user said they had got through it together. A bad day confided in earnest is therefore likely to become a hard shared moment; whether that is too eager has not been measured, and no real plugin host was tried. The probe's conservative count is 2.32 CNY.

## 2. A transient failure of the provider is retried (acceptance tooling)

**What happened.** The attempt ended at turn 54 of 63 of its second scenario because one request got no answer in 600 seconds. The rule bound in every attempt so far stopped on any provider or transport failure and kept that request's whole reservation of 20.05 CNY, the model's full context and output limits, because the guard cannot know what an interrupted request cost.

**The change.** An interrupted request is settled at a bound that is true for that request and the run goes on: the prompt bounded from the bytes actually sent (`min(context limit, 2 × request bytes + 4 × tool-schema bytes + 16,384)` tokens at the input price) plus the request's own `max_tokens` at the output price. The harness sends the same request again after 30 and then 120 seconds, three sends at most for one host call; a third failure stops the arm as before. Interrupted are: timeouts, connection and protocol errors, HTTP 429, 500, 502, 503 and 504, and a complete 2xx body that holds no billing data (the provider documents empty lines under load). Still fatal: any other status, usage that is present but inconsistent, an unexpected response model, a guard refusal. Each interrupted send is written, with position and code only, to a file validity reads; a run whose interruptions were all retried is valid, and the driver checks after each scenario that the ledger's interrupted entries match those lines.

**What an interruption costs on the guard's count**: about 0.59 CNY plus 0.018 CNY per kilobyte of request, plus 0.59 CNY when the plugin arm's tool schemas are sent; typically 1.3 to 3.3 CNY, at most 9.88. An attempt expected to cost 30 to 50 CNY has room for roughly three to nine interruptions before the guard refuses for lack of headroom.

**Independent review of billing safety** ([review](evidence/hard-moment-and-provider-retry-2026-11-17/provider-retry-review.md)): safe to use in a paid attempt; the ceiling holds with any number of interruptions. It rests on two assumptions. That a prompt never has more tokens than bytes was checked by the reviewer against the provider's published tokenizer. That `max_tokens` also caps reasoning tokens is implied by the provider's documentation and not stated; the repository's own records support it (runs that ended exactly at the bound with all of it reasoning, and 265 settled requests of the stopped attempt within it). If it were false, up to 10.17 CNY per interrupted send would be uncounted. The review's findings were all addressed: the empty-body case above, retrying only statuses that are transient, sequence numbers and times in the ledger with the driver's cross-check, a signal handler that could wait on its own lock, the per-session delay caused by interruptions reported by validity, and the texts.

**Limits.**
- No interruption has occurred under the new rule: it is tested with a fake transport only (the stub rehearsals run without the guard).
- A reply produced on a retry is not distinguished in scoring.
- A retried call can take up to about 33 minutes; in the plugin arm that runs on the scenario clock, which the reference arm does not have.
- The provider's guide says that when tools are sent the model's reasoning must be passed back in later requests; the harness passes it back within a turn and not for earlier turns, as in every attempt so far. If the provider began to enforce that, the first request after a turn with a tool call would be refused, early in the first scenario, and the attempt would stop there.

## Also

The host-diligence table of the companion evaluation now says when a turn was not reached by a stopped run; before, it read as a call the host had not made.

## Verification

- The guard and retry: 68 new tests of the interruption path and the tests added for the review's findings, with a fake transport and no network (a property test of the bound over English, German, Chinese and mixed prompts against a tokenizer that counts one token per byte; two processes sharing a ledger; the refusal-point arithmetic; a signal during a guarded section); focused runs of the acceptance tooling: 1,035 passed and 1 failed (a test double missing the new argument, fixed), then 1,086 passed after the review's fixes; both stub rehearsals pass.
- **Full local suite on `3b3c32ef`: 4,576 passed, none failed, 3 skipped** (the desktop end-to-end tests that need Docker), 7 fork warnings (4 tests), 38 min 44 s; the source was unchanged during the run and the database stopped.
- Not run: GitHub Verify, the native platform jobs, the R5 overhead protocol, a real plugin host, any acceptance attempt on this runtime.

Sub-sessions implemented the retry and the review's fixes and ran the suites; another reviewed billing safety without being told what to conclude; the lead set the decisions, made the product change and the probe, and integrated everything.
