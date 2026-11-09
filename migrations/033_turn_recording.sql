ALTER TABLE memory_runtime_turns
    ADD COLUMN recording_revision bigint NOT NULL DEFAULT 0 CHECK (recording_revision >= 0);
