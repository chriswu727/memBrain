CREATE TABLE memory_read_cache (
    tenant_id text NOT NULL,
    owner_id text NOT NULL,
    brain_id text NOT NULL,
    action text NOT NULL CHECK (action IN ('recall', 'inspect')),
    key text NOT NULL,
    response jsonb NOT NULL,
    response_bytes bigint NOT NULL CHECK (response_bytes > 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, brain_id, action, key),
    FOREIGN KEY (tenant_id, brain_id, action, key)
        REFERENCES memory_requests (tenant_id, brain_id, action, key) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, owner_id, brain_id) REFERENCES memory_brains (tenant_id, owner_id, id)
);

CREATE TABLE memory_cache_maintenance (
    tenant_id text NOT NULL,
    owner_id text NOT NULL,
    brain_id text NOT NULL,
    request_action text NOT NULL DEFAULT '',
    request_key text NOT NULL DEFAULT '',
    trace_id text NOT NULL DEFAULT '',
    requests_complete boolean NOT NULL DEFAULT false,
    traces_complete boolean NOT NULL DEFAULT false,
    PRIMARY KEY (tenant_id, brain_id),
    FOREIGN KEY (tenant_id, owner_id, brain_id) REFERENCES memory_brains (tenant_id, owner_id, id)
);

DO $$
DECLARE relation text;
BEGIN
    FOREACH relation IN ARRAY ARRAY['memory_read_cache', 'memory_cache_maintenance'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', relation);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', relation);
        EXECUTE format(
            'CREATE POLICY principal_isolation ON %I USING (tenant_id = current_setting(''app.tenant_id'', true) AND owner_id = current_setting(''app.principal_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true) AND owner_id = current_setting(''app.principal_id'', true))', relation
        );
    END LOOP;
END $$;
