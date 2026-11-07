ALTER TABLE memory_assertions ADD COLUMN source_han_majority boolean;

CREATE INDEX memory_assertions_pending_script ON memory_assertions (tenant_id,owner_id,brain_id,id,revision)
    WHERE source_han_majority IS NULL AND is_current AND NOT invalidated AND NOT deleted AND NOT suppressed
    AND document IS NOT NULL;
