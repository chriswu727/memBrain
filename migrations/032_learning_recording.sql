ALTER TABLE memory_jobs
    ADD COLUMN recording_revision bigint CHECK (recording_revision >= 0);
