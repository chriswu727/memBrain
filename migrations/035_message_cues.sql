-- Retrieval cues attached to stored messages: who a message is about and what kind of fact it holds. They are an
-- index over the original messages, read only when recall gathers candidates, and never shown as memory content.
CREATE TABLE memory_message_cues (
    tenant_id text NOT NULL,
    owner_id text NOT NULL,
    brain_id text NOT NULL,
    event_id text NOT NULL,
    event_revision bigint NOT NULL CHECK (event_revision > 0),
    cue_text text NOT NULL CHECK (cue_text <> '' AND char_length(cue_text) <= 600),
    cue_lexemes tsvector GENERATED ALWAYS AS (to_tsvector('simple', cue_text)) STORED,
    rule_version text NOT NULL,
    model_version text,
    embedding vector,
    embedding_model text,
    embedding_model_version text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, brain_id, event_id),
    FOREIGN KEY (tenant_id, owner_id, brain_id) REFERENCES memory_brains (tenant_id, owner_id, id),
    CHECK ((embedding IS NULL) = (embedding_model IS NULL)
           AND (embedding IS NULL) = (embedding_model_version IS NULL))
);

CREATE INDEX memory_message_cues_search ON memory_message_cues USING gin (cue_lexemes);

ALTER TABLE memory_message_cues ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_message_cues FORCE ROW LEVEL SECURITY;
CREATE POLICY principal_isolation ON memory_message_cues
    USING (tenant_id = current_setting('app.tenant_id', true) AND owner_id = current_setting('app.principal_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)
                AND owner_id = current_setting('app.principal_id', true));
