import json
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest

from membrain.build_identity import MIGRATIONS
from membrain.config import Settings
from membrain.ephemeral_turns import context

pytestmark = pytest.mark.integration


def test_temporary_history_uses_branch_index_without_scanning_other_branches():
    settings = Settings.from_env()
    plans = []
    with psycopg.connect(settings.migration_database_url or settings.database_url,
                         row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("CREATE TEMP TABLE memory_events (tenant_id text, owner_id text, brain_id text, "
                     "conversation_id text, branch_id text, sequence bigint, is_current boolean, "
                     "deleted boolean, suppressed boolean, retired boolean, document jsonb)")
        conn.execute("CREATE INDEX memory_events_tail ON memory_events (tenant_id,brain_id,sequence)")
        conn.execute(dict(MIGRATIONS)['023_conversation_event_index.sql'].decode(), prepare=False)
        conn.execute("INSERT INTO memory_events SELECT 'tenant','owner','brain','chat',"
                     "CASE WHEN n<=6 THEN 'main' ELSE 'fork' END,n,true,false,false,false,"
                     "jsonb_build_object('observed',jsonb_build_object('event_kind','message',"
                     "'actor_role','user','content',jsonb_build_object('text',n::text))) "
                     "FROM generate_series(1,20006) n")
        conn.execute("ANALYZE memory_events")

        class MeasuredConnection:
            def execute(self, query, params):
                plans.append(conn.execute('EXPLAIN (ANALYZE, FORMAT JSON) ' + query, params).fetchone()['QUERY PLAN'][0])
                return conn.execute(query, params)

        @contextmanager
        def transaction(*args):
            yield MeasuredConnection(), {'recording_revision': 1, 'dependency_generation': 1}

        store = SimpleNamespace(
            _transaction=transaction,
            _row=lambda *args: {'ephemeral': True, 'stage': 'started', 'recording_revision': 1,
                               'context_generation': 1, 'conversation_id': 'chat', 'branch_id': 'main'},
            _lease=lambda *args: None,
        )
        principal = SimpleNamespace(tenant_id='tenant', principal_id='owner')
        result = context(store, principal, 'brain', 'turn', lease_token='lease', limit=6)
        assert [row['content'] for row in result['messages']] == [str(n) for n in range(1, 7)]
        assert len(plans) == 1
        plan = plans[0]

        def nodes(node):
            yield node
            for child in node.get('Plans', []):
                yield from nodes(child)

        filtered = sum(node.get('Rows Removed by Filter', 0) * node.get('Actual Loops', 1)
                       for node in nodes(plan['Plan']))
        assert 'memory_events_conversation_tail' in json.dumps(plan)
        assert filtered < 10, plan
        conn.rollback()
