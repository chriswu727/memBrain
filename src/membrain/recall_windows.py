from . import cognition
from .candidates import _eligible, _scope_clause
from .helpers import DomainError
from .relationship import _boundary_view, _state, kept_out

MAX_WINDOWS = 12
WINDOW_CHARACTERS = 700


def validate_request(windows, query, target):
    if not isinstance(windows, (list, tuple)) or not 1 <= len(windows) <= MAX_WINDOWS:
        raise DomainError("validation_failed", "Choose 1 to 12 exact memory windows.")
    if not isinstance(query, str) or len(query.encode()) > 65536:
        raise DomainError("validation_failed", "The current query must fit within 65536 bytes.")
    for key in ('conversation_ref', 'branch_ref'):
        value = target.get(key)
        if value is not None and (not isinstance(value, str) or not 1 <= len(value) <= 256):
            raise DomainError("validation_failed", "Window scope must use bounded identifiers.")
    seen = set()
    for item in windows:
        if (not isinstance(item, dict) or set(item) != {'memory_id', 'revision', 'span'}
                or not isinstance(item['memory_id'], str) or not 1 <= len(item['memory_id']) <= 256
                or type(item['revision']) is not int or not 1 <= item['revision'] <= 2**63 - 1):
            raise DomainError("validation_failed", "Windows require exact memory versions.")
        span = item['span']
        if (not isinstance(span, dict) or set(span) != {'start', 'end', 'unit'}
                or type(span['start']) is not int or type(span['end']) is not int
                or not 0 <= span['start'] < span['end'] <= 2**31 - 1
                or span['end'] - span['start'] > 400 or span['unit'] != 'unicode_code_point'
                or (item['memory_id'], item['revision']) in seen):
            raise DomainError("validation_failed", "Windows require distinct bounded Unicode spans.")
        seen.add((item['memory_id'], item['revision']))


def read(service, conn, principal, brain, windows, query, target):
    clause, scope_params = _scope_clause('a', target)
    rows = conn.execute(
        'SELECT a.document FROM memory_assertions a WHERE ' + _eligible(include_speech=False) + clause
        + 'AND (a.id,a.revision) IN (SELECT * FROM unnest(%s::text[],%s::bigint[]))',
        (*service._params(principal, brain['id']), *scope_params,
         [item['memory_id'] for item in windows], [item['revision'] for item in windows]),
    ).fetchall()
    memories = {(row['document']['memory_id'], row['document']['revision']): row['document'] for row in rows}
    event_ids = list({ref['event_id'] for memory in memories.values() for ref in memory['evidence_refs']})
    events = {event['event_id']: event for event in service._events(
        conn, principal, brain, event_ids=event_ids, limit=MAX_WINDOWS)} if event_ids else {}
    superseded = service._superseded_evidence(conn, principal, brain, event_ids) if event_ids else []
    boundaries = _boundary_view(_state(service, conn, principal, brain['id']))
    scope = service._scope(principal, brain, target)
    items = []
    for window in windows:
        memory = memories.get((window['memory_id'], window['revision']))
        if (memory is None or memory['derivation']['method'] != 'direct_capture'
                or memory['lifecycle'] not in ('active', 'dormant') or len(memory['evidence_refs']) != 1):
            continue
        ref = memory['evidence_refs'][0]
        if (ref['relationship'] != 'supports' or 'span' not in ref
                or not cognition._valid_ref(ref, events, scope)
                or any(cognition.evidence_overlaps(ref, old) for old in superseded)):
            continue
        source = events[ref['event_id']]
        observed = source['observed']
        if (observed['actor_role'] not in ('user', 'operator') or observed['event_kind'] != 'message'
                or observed['delivery_state'] != 'received' or observed['content']['media_type'] != 'text/plain'):
            continue
        text = observed['content']['text']
        if kept_out(text, boundaries, query):
            continue
        span = ref['span']
        literal = text[span['start']:span['end']]
        statement = memory['statement']
        prefix = len(statement) - len(literal)
        match = window['span']
        if (not statement.endswith(literal) or not 0 <= match['start'] < match['end'] <= len(statement)
                or match['end'] <= prefix):
            continue
        start = max(span['start'], span['start'] + max(0, match['start'] - prefix) - WINDOW_CHARACTERS // 3)
        end = min(span['end'], start + WINDOW_CHARACTERS)
        start = max(span['start'], end - WINDOW_CHARACTERS)
        act = next((segment['act'] for segment in cognition.evidence_segments(source)
                    if segment.get('span') == span), 'unknown')
        items.append({'memory_id': memory['memory_id'], 'revision': memory['revision'],
                      'event_id': source['event_id'], 'evidence_ref': ref,
                      'window_span': {'start': start, 'end': end, 'unit': 'unicode_code_point'},
                      'text': text[start:end], 'source_characters': len(text),
                      'actor_role': observed['actor_role'], 'world': memory['world'], 'source_act': act,
                      'recorded_at': source['system_time']['recorded_at'],
                      'conversation_id': source['scope']['conversation_id']})
    return {'items': items, 'scope_generation': brain['scope_generation'],
            'dependency_generation': brain['dependency_generation']}
