# TypeScript companion controls: installed-service acceptance

## Result and scope

The TypeScript SDK now exposes 23 existing companion/map operations: current persona and versions, edits/restore/reset/history deletion, persona proposals and user decisions, feelings and clear, simulated mood and pin/reset, relationship support style/boundaries/familiarity cap/acknowledgements/reset, and the two bounded stored-memory projections. Previously the client could write note-linked feelings and shared moments but could not inspect or control these layers.

The change adds no model call, extraction rule, endpoint, database migration or runtime dependency. The Python runtime and all launcher pins remain `d4d71262ab1c7d76600082b9c53b10144bb08a00`. The [qualified backend evidence](maturity-private-paths-2026-11-04.md), including full CI at launcher/source candidate `53d7e32`, remains tied to those unchanged runtime bytes. It does not count as CI for the new TypeScript source. The [manifest](maturity-typescript-companion-2026-11-04/manifest.json) binds the exact SDK and test hashes exercised locally.

## Verification

- `npm test`: **50 passed, zero failures/skips**, including six new contract tests covering every new operation, explicit brain scope, authentication/recovery acknowledgement, URL encoding, immutable input, false/null/removal values, bounded commitment acknowledgement, sensitive-map opt-in and denied requests without fallback/retry.
- The existing `npm run typecheck` passed. An additional strict TypeScript compile included `index.ts`, `contract.ts` and `companion.test.ts`; exit 0.
- A separate, fresh disposable profile started through the already installed Python runtime passed **36 actual-API checks** using the modified TypeScript SDK. This was synthetic data, keyword mode, no host/extractor provider and no real-model evaluation call. Persona feedback generated actual proposals; rejection and acceptance persisted. Feelings retained their source/note identity; shared play produced an explained simulated mood trigger. Versions, rollback, reset, history erasure, commitments and both maps round-tripped. A second brain stayed isolated, an invalid card preserved the current card, and the actual service refused a wrong key.
- Service stop returned 0; both API and database ports were confirmed closed. No runtime source or SDK file changed while the installed-service check ran.

The allowlisted evidence directory contains the exact scripts, logs, check list, run result and hashes. The scripts retain this machine's absolute paths to the tested SDK and installed interpreter. Credentials, database contents, the connection file and private conversation data are excluded. The actual-API check covers transport and state transitions; it does not prove a real host model will respect boundaries or interpret feelings correctly.

[Full Verify for SDK source `78a225d`](https://github.com/chriswu727/memBrain/actions/runs/41906140459) now passes **7,000 Python tests, zero skips**, three warnings, **50 TypeScript tests**, strict types, Ruff and package builds. All four Docker journeys and the real local-model/activation cases run. The [CI result](maturity-typescript-companion-2026-11-04/ci-result.json) records the source, job, complete-log hash and Docker cases. This qualifies the SDK extension at that source; later host-context runtime repairs require their own verification.

## Documentation and remaining gates

The English and Chinese entry points and reference now describe the TypeScript controls and explicit user choice for accepting persona proposals. Current qualification replaces stale claims that the first Chromium CI and fresh Mac installation are pending, or that R5 remains above 600 ms. Historical failures remain linked. The paid acceptance draft now distinguishes implemented driver, digest and resolution enforcement from their still-open independent review.

One bounded ordinary Claude code consultation reviewed a frozen snapshot of the billing/harness/plan sources. It **timed out after 180.02 seconds without a complete response**; no retry was made. It provides no independent approval. Subscription usage is unknown. It was code consultation, not a held-out scenario author/judge or behavioural evaluation. Its source hashes and failure metadata are retained separately from the local SDK checks.

Real-model R4/C5, the final independent review and the remaining release checklist stay open. This change grants no paid/subscription evaluation approval and creates no schedule. Work continues under the active Goal; no merge to the default branch, tag or publication is authorized while those gates remain open.
