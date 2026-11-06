# Second maturity attempt stopped during S2

The owner-approved `maturity-20261106a` attempt stopped on November 6 at 18:44:34 UTC (10:44:34 Vancouver time). The frozen candidate was `1a0083d419512920e354eeeb8e972fdffd73a171`, runtime `cc2a601`, with manifest SHA-256 `51a7653b6b5a37245461932b44e26f71a20cf449be35b9f60745ab83a3737626`. All four new scenarios had passed independent review and structural/date checks before execution: 254 user turns and 44 scored cases. This was a real host/extractor run with local semantic recall, not the public stub rehearsal.

S1 completed and passed validity with no problems or retried empty replies. S2 stopped with P/E/F completing 8/5/5 of their 63 turns. The safe diagnosis reports `BudgetStop` in F; the shared ledger is blocked, and the supervisor stopped the remaining arms. C1 and C2 never started. Neither acceptance pair is eligible: S1 alone cannot establish R4, and C5 has no execution evidence. No replies have been graded and no behavioral pass or failure is inferred from this execution failure.

## Billing and diagnosis limits

Of 325 reserved requests, 322 settled with **20.445113 CNY** conservative accounting. Three have unknown billing and retain **60.162048 CNY** in reservations. The total accounted amount, **80.607161 CNY**, is below the approved 280 CNY ceiling. This was not exhaustion of that monetary ceiling. No reservation has been reclaimed, no stopped ledger reopened, and no new paid attempt started.

The account snapshot moved from **195.22 to 190.88 CNY**, an observed decrease of **4.34 CNY**. This is not a final invoice: account snapshots can include unrelated activity and delayed billing. The unknown requests remain conservatively reserved regardless of the balance snapshot.

The old guard retained only the supervisor's generic `arm_failed` reason and exposed `BudgetStop`. It did not retain the underlying transport class, HTTP status or response-validation category. Although requests waited for a prolonged period, the evidence does **not** establish a timeout or a provider-wide incident. The [official provider status page](https://status.deepseek.com/) reported normal operation when checked after the stop; that also does not prove the individual requests succeeded. Hidden logs, scenarios and replies remain sealed; no diagnostic is invented from their contents.

No test API listener remained after termination. An immediate bind check found the two API ports temporarily unavailable, while database ports were already free; a later bind check confirmed all four ports (8893, 55533, 8894, 55534) closed. Both execution and balance-observer sessions terminated. [Safe counts, budget state and private evidence hashes](maturity-second-attempt-stop-2026-11-06.json) are retained.

## Prospective diagnostic repair

The original checkout and all attempt inputs remain unchanged. A separate worktree adds content-free failure categories to the evaluation billing guard: transport failure with an allowlisted class, HTTP failure with a numeric status, or rejected response billing evidence. The first global cause survives sibling cancellation and supervisor cleanup. Budgets, retained reservations, stop behavior, model bounds and no-retry rules are unchanged. This repair cannot recover the missing cause of the stopped attempt or make it valid.

Six new regression cases failed before the repair. The final billing suite passes **52 tests**, including body-read interruption, HTTP failure, malformed/unapproved billing responses, a sensitive custom exception class, and concurrent shutdown preserving both reservations and the first cause. The broader overlapping billing/attempt-driver/harness-hardening group passes **240 tests**; two additional billing cases were subsequently verified in the final 52-test run. These counts overlap and are not added together. Scoped Ruff and diff checks pass. All verification uses synthetic data and makes no model calls.

Candidate CI for the diagnostic repair must be recorded separately. R4/C5 and final release review remain incomplete. Any further paid attempt requires its own explicit approval and frozen inputs; this attempt and the earlier invalid attempt stay closed. No merge, tag or release is authorized.
