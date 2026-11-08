ALTER TABLE memory_brains
    ADD COLUMN recording_paused boolean NOT NULL DEFAULT false,
    ADD COLUMN recording_revision bigint NOT NULL DEFAULT 0 CHECK (recording_revision >= 0);
