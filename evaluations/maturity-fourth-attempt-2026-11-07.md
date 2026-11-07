# Fourth maturity attempt: stopped during S1

The owner-authorized single attempt `maturity-20261107` stopped automatically during its first scenario. S1 completed 40/30/39 of 64 turns in plugin/extraction/full-history arms. S2, C1 and C2 did not run. Neither R4 nor C5 is eligible for scoring; no new behavioral score or pass is claimed. The [previous scored R4 failure and incomplete C5](maturity-third-attempt-2026-11-06.md) remain unresolved.

The frozen execution commit was `8b0e1caa75df7e3db31e6b59b2a4a77cb276b07f`, runtime `86e7f1fed2ba00d08b3cb9509beb50e4cf811f4b`. Its [engineering qualification](maturity-sensitive-structure-2026-11-07.md) passed 7,840 Python/53 TypeScript tests, all five native platforms, fresh installation and public rehearsal. Those passes do not establish real-agent behavior. The independent source review's graph privacy finding was fixed before this attempt, with an explicitly reviewed successor binding.

## Stop and diagnostic limits

At S1 session 10, message 4, the plugin arm reported `turn_not_recorded`. The supervisor stopped the shared ledger with `harness_degraded`; the driver exited 1 with `runner_failed`. The extraction and reference arms stopped under the shared budget guard.

Content-free control metadata shows that the preceding plugin message called `memory_pause` and was not recorded. The failing message produced a nonempty reply without any tool call, and was also not recorded; the pause file remained present. The operator did not read the hidden user's wording, criteria, assistant replies or tool arguments/results. This identifies a missing resume invocation at the stop, but does not establish the semantic adequacy of the hidden request or a database outage. A public-fixture investigation of recording-state visibility can follow without altering or rescoring this run.

One interrupted in-flight request retains a `provider_transport` / `SystemExit` failure record after the shared stop. That is not evidence of a provider outage. Its usage remains unknown and its full reservation remains held.

## Cost and preservation

| Ledger measure | Result |
| --- | --- |
| Shared authorized ceiling | 280 CNY |
| Reserved requests | 163 |
| Requests with settled usage | 162 |
| Settled amount at conservative policy rates | 9.933585 CNY |
| Unknown-usage reservation retained | 20.054016 CNY |
| Ledger state | Blocked; not reopened or replaced |

The observed account-balance decrease was 0.97 CNY between the before/final snapshots. This observation is separate from the guard's conservative uncached/maximum-rate accounting; it is not attributed as a final invoice and does not release the unknown reservation or authorize more spending.

All 656 frozen execution files and four scenario hashes remained unchanged. The four owned API/database ports were closed after cleanup. The invalid private run remains sealed and is not published or repurposed as accepted evidence. The [content-free summary](maturity-fourth-attempt-2026-11-07.json) records status, counts, billing aggregates, hash continuity and port checks.

There is no automatic retry or additional authorized round. Further source work uses separate public fixtures and preserves this failure. A new paid or subscription-backed behavioral attempt would require its own concrete plan and explicit approval. Main merge, tag and publication remain blocked by missing valid R4/C5 results and the final release disposition.

The [completed final independent review](maturity-fourth-attempt-final-review-2026-11-07.json) confirms SRC-01 is fixed and qualified, with no new concrete source finding inferred from the aggregate. Its release disposition is blocked because eligible R4/C5 acceptance is absent. Completion of that review is not release approval.
