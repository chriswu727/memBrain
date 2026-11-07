# Companion source privacy and cold affect reads

Seventeen real-database regressions reproduced automatic companion context using content from a source that the user had marked private on another note. The mood path could raise that source through a feeling, a completed plan or a shared moment, even while the graph masked it. Shared-moment context and missed-commitment reminders independently inherited only the derived note's own flag and could expose the same source.

## Repair

Mood candidates now check the sensitive-source dependency closure in bounded batches. Private feelings remain in succession processing so a later private reading can end an earlier public mood, but they cannot create a new trigger, reason or `superseded_by` reference. Completed plans and shared moments with private sources cannot drive automatic mood either.

Relationship reads check sources in batches of at most 256 notes through the existing streaming cursor. Shared moments and commitments retain their stored text for authorized inspection and report effective `sensitive` metadata. Their real counts and familiarity remain unchanged. Automatic context omits them, and a hidden missed commitment is not acknowledged as if it had been shown. Removing the privacy note allows the normal visibility/one-time reminder rules to apply again. Archive restore and the graph's explicit protection set preserve these rules.

The companion graph no longer invents a mood trigger for the protected reading; the ordinary memory graph still shows the underlying stored feeling with privacy masking and authorized opt-in. This closes automatic companion prompts based on known sensitive sources. It does not classify arbitrary unmarked text as private, prove emotional interpretation, or establish human-like feelings.

## Validation

The mood regressions failed **7/7** before repair, and the relationship regressions failed **10/10**. After repair, all 17 pass, including privacy marked before/after the derived record, a private successor ending a public feeling, archive round trips, management visibility, unchanged totals/familiarity, reminder acknowledgement and a protected moment outside the display window across a 256-record batch boundary.

The final combined affected suites pass **228 cases**, including the earlier affect-provenance regressions, mood succession, relationship history, note workflow and both graph projections. Before the cold-read repair, the privacy-only package passed 20 installed checks. The final rebuilt wheel matches all **187 runtime inputs** and passes **36 installed cases**, including all affect-source and companion-privacy regressions plus actual host mood, boundary and commitment flows. All 16 synthetic service fixture profiles were stopped, their API/database ports confirmed closed, and the profiles removed after logs were preserved. Full-source Ruff and diff checks pass. These local and installed results are distinct from full CI and from R4/C5 behavioral acceptance. No model calls or hidden evaluation data were used.

## Cold-read performance repair

Before candidate delivery, a synthetic fixture with 500 affect readings, 200 completed plans, 200 shared moments and every tenth source marked private exposed a slow correlated dependency lookup carried by the preceding affect repair. The fixture contains 2,390 events. An active, non-lock-waiting SELECT was observed at **150.44 seconds**. The completed warm benchmark reported much smaller p95 values because its first read was discarded; those values did not establish acceptable cold behavior.

A separate disposable control disabled autovacuum only for its event/dependency tables and imposed a three-second statement deadline. Both the preceding affect package and the privacy-only package timed out on the mood read. The query now fetches current related records, dependency edges and current visible sources in batches, preserving scope, deletion checks, explicit/legacy source rules and source-sequence order. A new 502-reading regression checks the 501-record lookahead, 500-record API window and completeness flag under a two-second per-statement deadline.

The final controlled comparison uses identical synthetic data and two installed packages whose 187 runtime-input manifests differ **only in `affect.py`**. The old query still times out at 3,033.58 ms. The repaired mood read completes in **130.99 ms on its first call**, followed by **126.35 ms p95** over 20 subsequent calls. Relationship reads complete in 35.59 ms first / 35.18 ms warm p95. No private mood reason appears. Both fixture database ports close and temporary profiles are removed after measurement.

These are direct-service reads on one reference machine under a deliberately unanalysed fixture, not network latency, semantic quality, the canonical recall benchmark or fullscreen R5 qualification. The original slow-query observation and failed controls remain in the evidence; no completed benchmark was restarted merely because an observation timed out.

[Raw logs, failed cold controls, installed manifests, measurement scripts and cleanup receipts](evidence/maturity-companion-source-privacy-2026-11-06/manifest.json) retain the full local evidence. Runtime `004a0f17d30f6627a093bb301978ad4fb80f2dd8` is pinned by all nine launchers in `d3dbe888fec7ddbf7a72664458d05bc1a9bef0f3`; both launcher-pin checks pass. Full combined-candidate CI remains pending.
