# Source-preserving recall resolution

**Partly removed:** the short views (recall summaries) and retention priorities described here were written by background learning with a cognition model, removed after runtime `2600219b` (see [what the removed learning left behind](../docs/reference.md#what-the-removed-learning-left-behind)). Recall still reads the ones an older runtime stored, and erasure still removes them; nothing writes new ones.

Original sources and full assertion statements remain persistent. Age changes accessibility and the default detail supplied to a model; it does not delete source content. Explicit user erasure remains separate and removes dependent short expressions too.

## Encoding and verification

New cognitive jobs use `recall-resolution-v1`, inheriting source-act, citation-coverage, attribution, bounded-learning and publication checks. An optional `recall_summary` contains a shorter statement and up to eight source-backed detail cues. An optional `retention_priority` controls accessibility, not validity or truth. The configured model selects useful content, wording, cues and retention. The runtime does not infer emotional importance or require every claim to have a summary.

The existing proposal and independent verification calls handle both expressions. A separate required `recall_summary_verdict` checks the entire short statement, its qualifications and every detail cue against the same authorized positive source excerpts and limited speaker provenance. Positive full-statement support cannot override an adverse or missing summary verdict. Publication rechecks this verdict. There is no extra summarization call on reads or recurring age-based rewrite job.

Local encoding can produce an `episode_fragment`, `episode_outline` or `semantic_anchor`, but its memory kind remains episodic and its claims remain attributed reports with unknown executable validity. A concise report does not establish a current preference, universal trait or independently verified external event. Duplicate claims are not required to fill layers.

The new local proposal omits the ontology registry and relation capabilities that its restricted schema cannot use. Only reachable schema definitions are sent. Local proposal and verification instructions describe the authorized local task; full sources, citation provenance, organization fidelity and independent verification remain present. Historical comparisons are not silently skipped. Older frozen contracts retain their previous schemas, prompts and byte-level regression values.

Local claims should be self-contained and cite the complete source units establishing a pronoun's antecedent. The local verifier schema excludes historical abstraction support-selection fields, instance verdicts and current-request verdicts. If a model still returns those unauthorized fields, the result remains rejected; the runtime never strips them to turn a failed response into a pass.

## Recall and expansion

After normal source, scope, cutoff, revision and lifecycle validation, an eligible supported assertion can expose its short expression below the everyday accessibility tier. Retention and recorded external use affect that tier through the existing access policy. Pinned memories and open commitments retain full detail.

Explicit episode, quotation, timeline, procedure, commitment and cue-recovery requests use full statements. So does `detail_level="full"`. Matching omitted words or CJK bigrams in the full assertion or supporting source spans expands detail, including source details not listed in model-selected cues. This is a conservative lexical signal, not complete semantic understanding. A model recall controller's explicit selection is kept detailed.

For a safe standalone episodic summary, literal captures wholly contained in its exact positive source spans are deferred from model context. Their versions remain in the raw result with `display_mode="do_not_surface"` and `deferred_by`. Scope and world must match. Pinned captures, open commitments, counterevidence and connected belief-resolution cases are not suppressed by this rule. The summary and deferred captures form one context-budget group, so truncation cannot leave a hidden capture dependent on an omitted summary.

The compact model view uses the short statement and `recall_detail="summary_expandable"`; its memory handle resolves to the same full version. HTTP and Python callers can request `detail_level="full"` or inspect that memory. MCP exposes the same option and its source-inspection tool. An explicit `summary` request is a preference: concrete cues and evidence safeguards can still require detail. Inject `model_context`, or use SDK context helpers, rather than serializing the entire control-plane result.

The automatic text runtime reserves room for host instructions, its memory protocol and the current input before requesting memory. Its conservative byte budget accounts for escaping JSON memory inside a JSON message string. The final complete prompt is still checked against the unchanged input ceiling.

## Persistence and compatibility

`024_recall_resolution.sql` is a compatibility marker: older binaries must reject a database containing the new persisted representation. Desktop upgrade applies it through the normal migration path. No source rewrite, re-embedding, reset or automatic paid reprocessing is required. Old assertions without an eligible verified short expression retain their full rendering. Future authorized learning can propose new representations; an upgrade alone does not manufacture them.

Trusted local archive restore retains both expressions and their exact source dependencies. Untrusted imports retain existing quarantine/rebuild rules. Corrections, suppression, erasure and source invalidation apply to the whole assertion; a short expression cannot independently resurrect an invalid source.

## Long literal captures

The local embedding provider keeps the original parent vector and adds overlapping passage vectors for statements longer than 400 Unicode code points. Each passage covers at most 400 original characters and 512 model tokens, including the model prefix. Token-dense windows shrink until they fit; normalization never silently removes source coverage. Heads and passages use separate inference batches, capped at 32 vectors, 4,096 padded token positions and 1,048,576 attention positions (batch size times squared sequence width). This avoids padding short passages to a long head's width. Short statements keep their single vector. Query embeddings retain the existing model and representation.

Migration `026_embedding_passages.sql` stores these auxiliary vectors under the original assertion version with owner isolation and cascading deletion. Parent and passage vectors publish atomically after rechecking the unchanged statement and live job lease. Coverage versions enter embedding job identities so existing single-vector documents can be backfilled. Passages are indexing representations, not independent assertions, episodes or graph nodes. Retrieval takes the best head or passage score per parent before applying the existing distinct-parent candidate budget.

A raw recall item can carry `matched_statement_span`; its full assertion remains unchanged. The bounded model view can render an explicitly labeled `matched_excerpt_expandable` for a direct capture, retaining the parent's world, source speech act and qualifications. The excerpt is partial original text, not an independently supported fact. Explicit full-detail and quotation requests retain full statements.

The Python host resolves selected passages through authenticated `POST /v1/brains/{id}/recall-windows`. This endpoint accepts at most 12 distinct exact memory versions and returns at most 700 original source characters per item. It rechecks current parent eligibility, scope, exact source revision/hash/span, superseding corrections, and relationship boundaries against the entire source before cropping. A failed fresh read cannot fall back to an older timeline copy. The existing 9,000-character host-context ceiling remains unchanged. Python and TypeScript SDKs expose the endpoint; custom hosts must adopt it or implement equivalent source-window handling to receive long tails.

Extra vectors increase background encoding work and storage in proportion to long-source coverage. This mechanism does not establish better general semantic accuracy, human-like memory, or longitudinal acceptance. Full network, installation and scale qualification remain separate from source-level diagnostics.

## Host fidelity and limits

`memory-consumption-v6` and optional `answer-grounding-v3` explicitly apply source fidelity to first-person cards, captions, letters and other autobiographical drafts. Creative wording does not authorize invented remembered times, locations, sensations, actions or feelings. These instructions and optional review are fallible; they do not control arbitrary host models deterministically. An answer reviewer is not silently enabled, and no automatic paid rewrite or retry is added.

This is a cue-sensitive presentation mechanism, not evidence of biological equivalence, a full learned hierarchy, useful aging over real elapsed years, universally optimal retrieval or general token savings. Models may omit optional summaries; lexical expansion may retain more detail than necessary. Recent conversation, relation certificates and essential uncertainty remain when needed. Cost claims must distinguish measured provider tokens from deterministic wire bytes and include background encoding and historical comparisons. The longitudinal release gate remains separate from scoped diagnostics.
