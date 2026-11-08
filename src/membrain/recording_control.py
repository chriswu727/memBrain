from .helpers import DomainError


def require_recording(brain, expected_revision=None):
    if brain["recording_paused"]:
        raise DomainError("recording_paused", "Recording is paused for this brain.")
    if expected_revision is not None and expected_revision != brain["recording_revision"]:
        raise DomainError("recording_stale", "Recording policy changed after this input was captured.")


def _status(brain):
    return {"paused": brain["recording_paused"], "revision": brain["recording_revision"]}


def recording_status(service, principal, brain_id):
    from .service import reading

    with service.database.transaction(principal) as conn, reading():
        conn.execute("SET LOCAL lock_timeout = '5s'")
        return _status(service._brain(conn, principal, brain_id))


def set_recording(service, principal, brain_id, *, paused, expected_revision):
    if type(paused) is not bool or type(expected_revision) is not int or not 0 <= expected_revision < 2**63 - 1:
        raise DomainError("validation_failed", "Recording needs a boolean and a bounded policy revision.")
    with service.database.transaction(principal) as conn:
        conn.execute("SET LOCAL lock_timeout = '5s'")
        brain = service._brain(conn, principal, brain_id)
        if expected_revision != brain["recording_revision"]:
            raise DomainError("version_conflict", "Recording policy changed. Read it before changing it again.",
                              current_revision=brain["recording_revision"])
        if paused == brain["recording_paused"]:
            return _status(brain)
        params = service._params(principal, brain_id)
        brain = conn.execute(
            "UPDATE memory_brains SET recording_paused=%s,recording_revision=recording_revision+1 "
            "WHERE tenant_id=%s AND owner_id=%s AND id=%s RETURNING *", (paused, *params),
        ).fetchone()
        if paused:
            # A callback already executing outside the database cannot be recalled or presumed cancelled.
            conn.execute(
                "WITH stopped AS (UPDATE memory_runtime_turns SET stage='failed',"
                "failure_code=CASE stage WHEN 'delivering' THEN 'delivery_uncertain' "
                "WHEN 'generating' THEN 'generation_uncertain' ELSE 'cancelled' END,"
                "revision=revision+1,fence=fence+1,worker_id=NULL,lease_token_digest=NULL,"
                "lease_expires_at=NULL,scope_reserved=false,last_transition_hash=NULL,"
                "updated_at=clock_timestamp() WHERE tenant_id=%s AND owner_id=%s AND brain_id=%s "
                "AND stage NOT IN ('delivered','committed','completed','failed') RETURNING *) "
                "INSERT INTO memory_runtime_turn_transitions(tenant_id,owner_id,brain_id,turn_id,"
                "revision,stage,operation,fence,failure_code) SELECT tenant_id,owner_id,brain_id,turn_id,"
                "revision,stage,'fail',fence,failure_code FROM stopped", params,
            )
        return _status(brain)
