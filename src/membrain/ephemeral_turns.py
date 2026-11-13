from .helpers import DomainError, _hash, _identifier, _integer


def require_current(brain, row):
    if (row["recording_revision"] != brain["recording_revision"]
            or row["context_generation"] != brain["dependency_generation"]):
        raise DomainError("context_stale", "Temporary conversation context changed.")


def begin(store, principal, brain_id, *, turn_id, conversation_id, branch_id, expected_recording_revision,
          review_policy=None, off_record=False):
    """Reserve a content-free temporary turn at the caller's recording revision.

    A temporary turn needs a reason: the brain's recording is paused, or the caller explicitly asks for one turn to
    stay off the record (``off_record``) while recording remains enabled. The explicit form never changes the
    brain's recording controls and binds the same revision, deletion and scope dependencies as a paused one.
    """
    from .turn_scopes import require_new_scope

    if type(off_record) is not bool:
        raise DomainError('validation_failed', 'off_record must be a boolean.')
    for value in (turn_id, conversation_id, branch_id):
        _identifier(value)
    _integer(expected_recording_revision, 0)
    if review_policy is not None:
        _hash(review_policy)
    with store._transaction(principal, brain_id) as (conn, brain):
        row = conn.execute(
            "SELECT *,clock_timestamp() AS db_now FROM memory_runtime_turns "
            "WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND turn_id=%s FOR UPDATE",
            store._params(principal, brain_id, turn_id),
        ).fetchone()
        if row is not None:
            if not row['ephemeral'] or (row['conversation_id'], row['branch_id']) != (conversation_id, branch_id):
                raise DomainError('idempotency_conflict', 'Turn identity belongs to another operation.')
            return store._public(conn, principal, row)
        if (brain['recording_revision'] != expected_recording_revision
                or not (brain['recording_paused'] or off_record)):
            raise DomainError('context_stale', 'Recording policy changed before the temporary turn began.')
        require_new_scope(conn, principal, brain_id, conversation_id, branch_id)
        row = conn.execute(
            "INSERT INTO memory_runtime_turns(tenant_id,owner_id,brain_id,turn_id,conversation_id,branch_id,"
            "input_fingerprint,scope_reserved,recording_revision,context_generation,ephemeral,response_review_policy) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,true,%s,%s,true,%s) RETURNING *,clock_timestamp() AS db_now",
            (*store._params(principal, brain_id, turn_id), conversation_id, branch_id, '0' * 64,
             brain['recording_revision'], brain['dependency_generation'], review_policy),
        ).fetchone()
        store._record(conn, row, 'begin')
        return store._public(conn, principal, row)


def advance(store, principal, brain_id, turn_id, *, lease_token, expected_revision, stage, delivery_state=None):
    previous = {'generating': 'started', 'generated': 'generating', 'delivering': 'generated', 'completed': 'delivering'}
    if (stage not in previous or (stage == 'completed' and delivery_state not in {
            'delivered', 'partially_delivered', 'cancelled', 'unknown', 'returned',
    }) or (stage != 'completed' and delivery_state is not None)):
        raise DomainError('validation_failed', 'Invalid temporary turn stage or delivery state.')
    with store._transaction(principal, brain_id) as (conn, brain):
        row = store._row(conn, principal, brain_id, turn_id)
        if not row['ephemeral']:
            raise DomainError('stage_conflict', 'A durable turn cannot become temporary.')
        store._lease(row, lease_token, expected_revision)
        if stage != 'completed' or delivery_state == 'returned':
            require_current(brain, row)
        if row['stage'] != previous[stage]:
            raise DomainError('stage_conflict', 'Temporary stages cannot be repeated or recovered.')
        failure = None
        if stage == 'completed':
            failure = {'cancelled': 'cancelled', 'unknown': 'delivery_uncertain'}.get(delivery_state)
            if failure is None and (row['recording_revision'] != brain['recording_revision']
                                    or row['context_generation'] != brain['dependency_generation']):
                failure = 'context_stale'
        ending = ',worker_id=NULL,lease_token_digest=NULL,lease_expires_at=NULL,recovery_required=NULL' if stage == 'completed' else ''
        row = conn.execute(
            "UPDATE memory_runtime_turns SET stage=%s,revision=revision+1,updated_at=clock_timestamp(),"
            "generation_count=generation_count+%s,scope_reserved=%s,response_review_calls=response_review_calls+%s,"
            "ephemeral_delivery_state=%s,failure_code=%s"
            + ending + " WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s AND turn_id=%s "
            "RETURNING *,clock_timestamp() AS db_now",
            ('failed' if failure else stage, int(stage == 'generating'), stage != 'completed',
             int(stage == 'generated' and row['response_review_policy'] is not None), delivery_state, failure,
             *store._params(principal, brain_id, turn_id)),
        ).fetchone()
        store._record(conn, row, 'advance')
        return store._public(conn, principal, row)


def context(store, principal, brain_id, turn_id, *, lease_token, limit=6, max_bytes=4000):
    _integer(limit, 0, 8)
    _integer(max_bytes, 1, 32000)
    with store._transaction(principal, brain_id) as (conn, brain):
        row = store._row(conn, principal, brain_id, turn_id)
        if not row['ephemeral'] or row['stage'] != 'started':
            raise DomainError('stage_conflict', 'Temporary context is only available before generation.')
        store._lease(row, lease_token)
        require_current(brain, row)
        records = conn.execute(
            "SELECT document FROM memory_events WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
            "AND conversation_id=%s AND COALESCE('value:' || branch_id,'null')=COALESCE('value:' || %s,'null') "
            "AND is_current AND NOT deleted AND NOT suppressed "
            "AND NOT retired AND document IS NOT NULL AND document->'observed'->>'event_kind'='message' "
            "AND document->'observed'->>'actor_role' IN ('user','assistant') ORDER BY sequence DESC LIMIT %s",
            (principal.tenant_id, principal.principal_id, brain_id, row['conversation_id'], row['branch_id'], limit),
        ).fetchall()
        items, used = [], 0
        for record in records:
            document = record['document']
            text = document['observed']['content'].get('text') or ''
            size = len(text.encode())
            if used + size > max_bytes:
                break
            used += size
            items.append({'role': document['observed']['actor_role'], 'content': text})
        return {'messages': list(reversed(items)), 'recording_revision': row['recording_revision'],
                'context_generation': row['context_generation']}
