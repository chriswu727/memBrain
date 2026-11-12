-- How far a brain's messages have been reviewed for cues: whoever writes cues reads messages in recording order and
-- says how far it got, so a message that needs no cue is not offered again.
CREATE TABLE memory_cue_progress (
    tenant_id text NOT NULL,
    owner_id text NOT NULL,
    brain_id text NOT NULL,
    reviewed_through_sequence bigint NOT NULL CHECK (reviewed_through_sequence >= 0),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, brain_id),
    FOREIGN KEY (tenant_id, owner_id, brain_id) REFERENCES memory_brains (tenant_id, owner_id, id)
);

ALTER TABLE memory_cue_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_cue_progress FORCE ROW LEVEL SECURITY;
CREATE POLICY principal_isolation ON memory_cue_progress
    USING (tenant_id = current_setting('app.tenant_id', true) AND owner_id = current_setting('app.principal_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)
                AND owner_id = current_setting('app.principal_id', true));
