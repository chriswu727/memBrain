# Installed candidate: upgrade, host transport and recovery

The real launcher acceptance harness completed **49 checks passed, zero failed**, exit zero, against pinned runtime `47fcb96684b367dd2f6e30d4cdc6cb5657b5fa58` on the reference Mac. The installed build was `30da9f98a0144b0a88fdb754adb7a4f214e654333ed95245406277506533e0dd`, matching the current source build. Source head was `99d3133fd0d9fd7a020a70575f4ca083e696357f`.

The unchanged [release installation harness](release-install-2026-11-01.py) ran both `upgrade` and `companion` parts in fresh isolated homes, with a shared download cache. The wrapper changes the cache location and records the current runtime identity. It uses actual published-source archives and installed tools, not the development environment's service. Both frozen baselines are unchanged: `d0d7a0379f7ac5f1b81dad04504601bb6606f1b0` for ordinary memory and `19e894ca9e08cf65fa071e8019789499953478d0` for companion state (whose own launcher pins runtime `4f5f5278c5566e59606f1483720dc4150465ddb5`).

Verified journeys include:

- Old-runtime recording, upgrade through current hooks, unchanged installation/brain identity, and recall in a new session. Observed upgrade durations were 31 seconds for the ordinary baseline and 12 seconds for the companion baseline.
- Real stdio startup through Claude, Codex and CodeBuddy MCP configurations, including tool discovery, note correction and deletion with subsequent session checks.
- Cold service restart through hooks, plus a session created before service readiness receiving memory on its next message.
- The installed HTTP proxy recalling an earlier bot-user turn, forwarding to a local stub upstream, returning its reply, and recording both sides. This verifies transport and memory injection, not real model answer quality.
- Backup, restoration into quarantine, explicit activation, preserved memory, and refusal to restart the retired original installation.
- Persona card/version, baseline mood pin, reported feeling, shared moment, support style, and a topic boundary with an alias surviving both upgrade and restore. The boundary suppresses the topic until the user raises it.

All four created installation profiles were inspected after cleanup; each API and database port was closed. Profiles, databases and reports remain available for investigation. No model API key, paid text-model evaluation or subscription-backed agent test was used. This harness does not establish R4/C5 behavior, autonomous personality growth quality, every supported operating system, or release readiness. The current [R5 failure](maturity-familiarity-map-2026-11-05.md) remains open, as does the [cold first-recall failure observed during diagnostic profiling](maturity-performance-attribution-2026-11-05.md).

The [six-payload evidence manifest](evidence/maturity-installed-candidate-2026-11-05/manifest.json) includes the wrapper, exact run log, all 49 results, metadata, proxy log and closed-port inspection. Compressed payloads round-trip exactly and both hashes are recorded. Exported bytes were checked against the distinct credentials from the four owned installation profiles, with zero matches; this is not a universal secret scan. No merge, tag or release occurred.
