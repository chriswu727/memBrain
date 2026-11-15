-- Source arrival must bind hidden/replaced interpretations too, so later erasure reaches their bodies.
-- Include affect records and past revisions; the previous index covered only visible current notes.
DROP INDEX memory_events_note_sources;
CREATE INDEX memory_events_note_sources ON memory_events
USING gin ((document->'observed'->'source_references') jsonb_path_ops)
WHERE NOT deleted AND document->'observed'->'source_references' IS NOT NULL;
