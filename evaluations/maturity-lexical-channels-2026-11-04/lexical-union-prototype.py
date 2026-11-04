from membrain import cognition
from membrain.lexical_candidates import MAX_QUERY_TERMS, MAX_TERM_LENGTH, _prefixes, historical_support_filter


def lexical_rows(conn, params, target, text, *, limit, through_sequence=None, excluded_versions=(),
                 independent_of_event_ids=()):
    from membrain.candidates import _eligible, _scope_clause
    from membrain.service import _vector

    clause, scope_params = _scope_clause('a', target)
    where = _eligible() + clause
    where += "AND a.embedding_model='lexical-feature-hash' AND a.embedding_version='v1-d256-blake2s' "
    values = (*params, *scope_params)
    support_clause, support_params = historical_support_filter(independent_of_event_ids)
    where += support_clause
    values += support_params
    if excluded_versions:
        where += 'AND (a.id,a.revision) NOT IN (SELECT * FROM unnest(%s::text[],%s::bigint[])) '
        values += ([key[0] for key in excluded_versions], [key[1] for key in excluded_versions])
    if through_sequence is not None:
        where += (
            'AND NOT EXISTS (SELECT 1 FROM memory_events future WHERE future.tenant_id=a.tenant_id '
            'AND future.owner_id=a.owner_id AND future.brain_id=a.brain_id AND future.id=ANY(a.event_ids) '
            'AND future.is_current AND future.sequence>%s) '
        )
        values += (through_sequence,)
    vector = _vector(text)
    words = sorted(cognition._terms(text)[0])
    terms = [word for word in words if len(word) <= MAX_TERM_LENGTH][:MAX_QUERY_TERMS]
    if not terms:
        rows = conn.execute('SELECT a.document,a.event_ids,a.is_current FROM memory_assertions a WHERE ' + where
                            + 'ORDER BY a.embedding <=> %s::vector NULLS LAST,a.id,a.revision LIMIT %s',
                            (*values, vector, limit + 1)).fetchall()
        return rows[:limit], len(rows) > limit or len(terms) != len(words)
    select = 'SELECT a.document,a.event_ids,a.is_current,a.id,a.revision,a.embedding <=> %s::vector AS distance FROM memory_assertions a WHERE '
    order = 'ORDER BY distance NULLS LAST,a.id,a.revision LIMIT %s'
    rows = conn.execute(
        'WITH hashed AS MATERIALIZED (' + select + where + order + '), '
        'exact AS MATERIALIZED (' + select + where
        + "AND to_tsvector('simple',a.search_text) @@ to_tsquery('simple',%s) " + order + '), '
        'ranked AS (SELECT *,0 AS channel,row_number() OVER (ORDER BY distance NULLS LAST,id,revision) AS position FROM exact '
        'UNION ALL SELECT *,1 AS channel,row_number() OVER (ORDER BY distance NULLS LAST,id,revision) AS position FROM hashed), '
        'selected AS (SELECT DISTINCT ON (document->>\'memory_id\',document->\'revision\') '
        'document,event_ids,is_current,channel,position FROM ranked WHERE position<=%s '
        'ORDER BY document->>\'memory_id\',document->\'revision\',channel,position) '
        'SELECT document,event_ids,is_current,((SELECT count(*) FROM hashed)>%s OR (SELECT count(*) FROM exact)>%s) AS truncated '
        'FROM selected ORDER BY channel,position',
        (vector, *values, limit + 1, vector, *values, ' | '.join(_prefixes(terms)), limit + 1,
         limit, limit, limit),
    ).fetchall()
    truncated = len(terms) != len(words)
    for row in rows:
        truncated |= row.pop('truncated')
    return rows, truncated
