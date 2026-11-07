# Affect readings keep their own evidence

A real disposable PostgreSQL reproduction found two provenance failures. An inferred feeling backed only by an assistant message was visible despite having no user-message source, and it generated an `inferred_distress` mood trigger. An unresolved reference also exposed an inferred feeling before its evidence arrived. Restoring the assistant-only record hid it, demonstrating inconsistent native/restored behavior.

Separately, replacing a source-linked note after “Clear feelings” could recreate the cleared feeling when the request omitted its sources. The note inherited the old dependencies, but affect creation checked only explicitly supplied arguments. The same failure occurred with a reference resolved after an earlier note replacement but before the reset.

## Repair

Each new reading records its own source references and dependency edges. A delayed source can resolve that reading directly, including after archive restore. Inferred feelings remain hidden from the affect API, mood and memory graph until a current, delivered user-message source exists. Assistant messages, drafts and unresolved references cannot establish a user feeling. Native and restored records use the same rule.

Explicit sources describe the current reading independently of the note's inherited history. When the caller supplies no sources, replacement falls back to inherited evidence and enforces the reset cutoff. New post-reset evidence remains valid even if the note still depends on older messages. Read-time checks also protect legacy records against pre-reset sources. Legacy records with explicit IDs retain those IDs; a record with no independent source metadata can only fall back to the evidence preserved on its note.

The existing observed-event `source_references` field identifies independently bound readings, including an empty list. No database migration or public API shape change is required. Restore preserves the event IDs and dependency edges; it does not need to resolve rewritten archive source keys again. Sources without a conversation remain supported, and a record's `note_id` must still point to a note. These rules establish provenance, not the semantic correctness of a model's emotional interpretation. They do not establish human-like emotion or pass C5.

## Verification

The first ten regression cases produced **nine failures and one passing restored-record control** on the original runtime. The final **15 regression cases pass** with real PostgreSQL, including native/restored behavior, pending references before/after restore, source deletion, reset inheritance, explicit new feelings, legacy records and sources without a conversation. The unchanged affected suites pass **195 cases** covering affect, mood, mood succession, relationship history, note workflow and both graph projections: **210 distinct cases** in total. Full-source Ruff and diff checks pass.

The initial broad run reported 154 passes and 41 service-startup errors after runtime files changed while its parent interpreter retained the earlier build identity. A serial rerun against frozen runtime files passed all 195 cases. A separate overlapping database startup was refused by the native service guard. Two regression-fixture mistakes were also retained: a low-level legacy record omitted normalized `felt_at`, and a no-conversation request supplied null instead of omitting the selector. Both fixtures were corrected before the final passing run. These failures were not counted as successful verification.

A fresh wheel matches all 187 runtime inputs. The installed wheel passes 17 checks: all 15 provenance regressions and two real-service cross-session affect/mood flows. Synthetic fixture databases were stopped, API/database ports confirmed closed, and profiles removed after preserving logs. Local logs and cleanup receipts are retained outside the repository; the final evidence manifest records their hashes and outcomes. No provider calls, hidden scenarios or user conversations were used. Full candidate CI and behavioral acceptance remain separate release gates.
