DROP INDEX memory_assertions_search;

ALTER TABLE memory_assertions ADD COLUMN search_lexemes tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_text)) STORED;

CREATE INDEX memory_assertions_search ON memory_assertions USING gin (search_lexemes);
