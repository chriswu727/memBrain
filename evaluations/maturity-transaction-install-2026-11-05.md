# Installed transaction-worker candidate

Runtime `174bc506595e9f96e4c38b0c10f737c7f98c639a` passes **49/49 real launcher acceptance checks**, zero failures, exit zero, on the reference Mac. Source head is `8a38eaca007abc7e929fc1e49474edb9c0cdc235`. Both independently installed environments match all **187 runtime inputs**, build `9029d20d74b2b7e3726e5fa6cb40c66e9ca59634a669851e7a61e8d7264a250e` and schema `e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693`.

The unchanged [installation harness](release-install-2026-11-01.py) runs both upgrade and companion parts in fresh isolated homes, using an existing download cache. Actual hooks download the published GitHub source archive and launch the installed runtime. Frozen baselines remain `d0d7a0379f7ac5f1b81dad04504601bb6606f1b0` and `19e894ca9e08cf65fa071e8019789499953478d0`; the latter's own runtime is `4f5f5278c5566e59606f1483720dc4150465ddb5`. The runtime commit was made reachable through `qualification/runtime-174bc50` without updating PR #43 and canceling its live previous-source checks.

Verified journeys cover:

- Recording on the old runtime, upgrading through current hooks, preserving installation/brain identity and recalling in a new session. Observed upgrade durations are 21 seconds and 12 seconds for the two baselines, with cached downloads.
- Real stdio startup through Claude, Codex and CodeBuddy MCP configurations, note correction, deletion and subsequent-session checks. These launch isolated MCP processes; they do not operate a user's host window.
- Cold service restart, and memory delivery on the next message when a session begins before service readiness.
- Installed HTTP proxy forwarding, memory injection and recording with a local stub upstream.
- Backup, quarantined restoration, explicit activation, preserved recall and refusal to restart the retired original installation.
- Persona card/version, pinned baseline mood, reported feelings, shared moments, support style and a topic boundary with an alias surviving upgrade and restore. The boundary suppresses its topic until the user raises it.

All four test profiles' API and database ports are closed after cleanup. Their data remain available for investigation. Two installed interpreters independently report package manifests equal to the source manifest; this is a full file comparison, not only a version-string check.

No paid or subscription-backed model behavior evaluation ran. The harness uses local semantic embedding and a stub text-model upstream; it does not establish real-agent answer quality, personality growth quality or R4/C5 acceptance. This Mac result does not substitute for current-source full CI and native qualification on every supported platform. Publication remains frozen pending those checks, remaining host behavior, R4/C5 and final review. The [current R5 and focused regression results](maturity-ci-closeout-2026-11-05.md) retain their separate scope.

The [eight-payload evidence manifest](evidence/maturity-transaction-install-2026-11-05/manifest.json) preserves the wrapper, exact run log, metadata, all results, proxy log, parity/port checker and its output. Exported bytes and compression round trips were verified. Exact scans against 12 distinct credential values from the four owned test profiles found zero matches; this is not a universal secret scan. Profiles, databases, models and backup archives are not exported. No merge, tag or release occurred.
