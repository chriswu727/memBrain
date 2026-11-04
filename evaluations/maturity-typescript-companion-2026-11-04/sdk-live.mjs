import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { MemoryClient, MemoryHttpError } from '/Users/yichen/tmp/membrain-review-20261029/sdk/typescript/index.ts';

const config = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const client = new MemoryClient(config);
const checks = [];
function check(value, label) { assert.ok(value, label); checks.push(label); }
const baseline = { name: 'Aster', voice: { register: 'formal' },
  baseline_mood: { label: 'calm', valence: 0, energy: 1 } };
check((await client.persona()).version === 0, 'empty persona is explicit');
check((await client.setPersona(baseline, { hostDefault: true })).version === 1, 'save host default');
check((await client.setPersona({ ...baseline, name: 'Aster edited' }, { madeBy: 'user' })).version === 2,
  'user edit creates version');
check((await client.personaVersions()).versions.length === 2, 'version history retained');
check((await client.restorePersona(1, { madeBy: 'user', reason: 'Rollback.' })).version === 3,
  'restore creates new version');
check((await client.resetPersona({ madeBy: 'user' })).card.name === 'Aster', 'reset restores host default');
for (let index = 0; index < 3; index++) {
  await client.observe("You're too formal. Please be more casual.", {
    conversationId: 'sdk-feedback', branchId: 'main', sourceEventKey: `casual-${index}` });
}
let proposal = (await client.personaProposals()).proposals.find(p => p.status === 'open');
check(Boolean(proposal), 'explicit feedback makes proposal');
await client.rejectPersonaProposal(proposal.id);
check((await client.personaProposals()).proposals.find(p => p.id === proposal.id).status === 'rejected',
  'rejection persists');
for (let index = 0; index < 3; index++) {
  await client.observe('Replies are too long. Please be shorter.', {
    conversationId: 'sdk-feedback', branchId: 'main', sourceEventKey: `shorter-${index}` });
}
proposal = (await client.personaProposals()).proposals.find(p => p.status === 'open');
check(Boolean(proposal), 'another feedback kind remains independent');
const before = (await client.persona()).version;
await client.acceptPersonaProposal(proposal.id);
check((await client.persona()).version === before + 1, 'acceptance changes current persona');
check((await client.personaProposals()).proposals.find(p => p.id === proposal.id).status === 'accepted',
  'accepted proposal remains inspectable');
await client.observe('I am nervous about an interview.', {
  conversationId: 'sdk-feelings', branchId: 'main', sourceEventKey: 'feeling-source' });
const source = (await client.timeline({ conversationId: 'sdk-feelings', roles: ['user'] })).items[0].event_id;
const note = await client.writeNote('The user is nervous about an interview.', {
  kind: 'other', sourceEventIds: [source],
  affect: { label: 'nervous', valence: -1, intensity: 2, basis: 'reported' } });
check((await client.affectRecords()).records.some(p => p.note_id === note.note_id), 'feeling keeps note identity');
await client.clearAffect();
check((await client.affectRecords()).records.length === 0, 'clear feelings persists');
await client.setSupportStyle('Listen first; advice only when asked.');
check((await client.relationship()).support_style.text.includes('Listen first'), 'support style round trips');
const result = await client.addBoundary('old workplace', ['former office', '旧单位']);
const boundary = result.boundaries.find(p => p.topic === 'old workplace');
check(boundary.aliases.includes('旧单位'), 'boundary aliases round trip');
await client.removeBoundary(boundary.id);
check((await client.relationship()).boundaries.length === 0, 'boundary removal persists');
await client.capFamiliarity('new');
check((await client.relationship()).familiarity.cap === 'new', 'familiarity cap is applied');
await client.capFamiliarity(null);
check((await client.relationship()).familiarity.cap === null, 'familiarity cap can be removed');
const shared = await client.writeNote('We laughed together at a shared joke.', { kind: 'milestone', shared: true });
check((await client.relationship()).shared_moments.some(p => p.id === shared.note_id), 'shared moment is preserved');
check((await client.mood()).triggers.some(p => p.rule === 'shared_play'), 'shared play has an explained mood trigger');
await client.pinMood();
check((await client.mood()).pinned === true, 'mood pin round trips');
await client.pinMood(false);
check((await client.mood()).pinned === false, 'mood can be unpinned');
await client.resetMood();
check((await client.mood()).at_baseline === true, 'mood reset reaches baseline');
const due = new Date(Date.now() - 2 * 86400000).toISOString().slice(0, 10);
const promise = await client.writeNote('Bring a map to our meeting.', { kind: 'agent_commitment', status: 'intended', due });
check((await client.relationship()).commitments.missed.some(p => p.note_id === promise.note_id), 'missed promise is inspectable');
await client.acknowledgeCommitments([promise.note_id]);
check(!(await client.relationship()).once.includes(promise.note_id), 'acknowledgement prevents repeat delivery');
for (const graph of [await client.memoryMap({ structure: true, trace: true }), await client.companionMap()]) {
  const ids = new Set(graph.nodes.map(p => p.id));
  check(ids.size > 0 && graph.edges.every(e => ids.has(e.source) && ids.has(e.target)), 'map edges have real returned endpoints');
}
await client.ensureBrain('sdk-peer', 'SDK peer');
await client.setPersona({ name: 'Other persona' }, { brainId: 'sdk-peer' });
check((await client.persona('sdk-peer')).card.name === 'Other persona', 'explicit brain override writes there');
check((await client.persona()).card.name === 'Aster', 'another brain does not replace the owner persona');
await client.addBoundary('other topic', [], 'sdk-peer');
check((await client.relationship()).boundaries.length === 0, 'boundary does not cross brains');
await assert.rejects(client.setPersona({ name: 'x'.repeat(61) }), error =>
  error instanceof MemoryHttpError && [400, 422].includes(error.status));
check((await client.persona()).card.name === 'Aster', 'invalid card leaves current persona intact');
const denied = new MemoryClient({ ...config, apiKey: 'wrong-key' });
await assert.rejects(denied.persona(), error => error instanceof MemoryHttpError && error.status === 401);
checks.push('wrong key is refused by the actual service');
await client.resetRelationship();
const reset = await client.relationship();
check(reset.familiarity.level === 'new' && reset.boundaries.length === 0 && reset.shared_moments.length === 0,
  'relationship reset clears only its layer');
check((await client.persona()).version === before + 1, 'relationship reset preserves persona');
await client.deletePersonaHistory();
check((await client.personaVersions()).versions.length === 0, 'persona history is erased');
check((await client.personaProposals()).proposals.length === 0, 'persona history deletion removes proposals');
writeFileSync(process.argv[3], JSON.stringify({ passed: true, checks, count: checks.length,
  real_model_calls: 0, scope: 'TypeScript SDK against installed Python API, synthetic data only' }, null, 2) + '\n');
console.log(JSON.stringify({ passed: true, checks: checks.length, real_model_calls: 0 }));
