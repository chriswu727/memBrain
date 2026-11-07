ALTER TABLE memory_embeddings ADD COLUMN document_index_version text NOT NULL DEFAULT 'single-vector-v1';

CREATE TABLE memory_embedding_passages (
    tenant_id text NOT NULL,
    owner_id text NOT NULL,
    brain_id text NOT NULL,
    memory_id text NOT NULL,
    memory_revision bigint NOT NULL,
    model text NOT NULL,
    model_version text NOT NULL,
    passage_index integer NOT NULL CHECK (passage_index >= 0),
    start_offset integer NOT NULL CHECK (start_offset >= 0),
    end_offset integer NOT NULL CHECK (end_offset > start_offset),
    embedding vector NOT NULL,
    PRIMARY KEY (tenant_id, brain_id, memory_id, memory_revision, model, model_version, passage_index),
    FOREIGN KEY (tenant_id, brain_id, memory_id, memory_revision, model, model_version)
        REFERENCES memory_embeddings (tenant_id, brain_id, memory_id, memory_revision, model, model_version)
        ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, owner_id, brain_id) REFERENCES memory_brains (tenant_id, owner_id, id)
);

ALTER TABLE memory_embedding_passages ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_embedding_passages FORCE ROW LEVEL SECURITY;
CREATE POLICY principal_isolation ON memory_embedding_passages
    USING (tenant_id = current_setting('app.tenant_id', true) AND owner_id = current_setting('app.principal_id', true))
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true) AND owner_id = current_setting('app.principal_id', true));
