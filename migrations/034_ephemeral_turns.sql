ALTER TABLE memory_runtime_turns ADD COLUMN ephemeral boolean NOT NULL DEFAULT false;
ALTER TABLE memory_runtime_turns ADD COLUMN ephemeral_delivery_state text CHECK (
    ephemeral_delivery_state IS NULL OR (ephemeral AND ephemeral_delivery_state IN (
        'delivered', 'partially_delivered', 'cancelled', 'unknown', 'returned'
    ))
);
ALTER TABLE memory_runtime_turns ADD CONSTRAINT ephemeral_without_content CHECK (
    NOT ephemeral OR (
        input_fingerprint = repeat('0', 64)
        AND input_event_refs = '[]'::jsonb AND output_event_refs = '[]'::jsonb
        AND context_event_refs = '[]'::jsonb AND context_fingerprint IS NULL
        AND recall_plan IS NULL AND orientation_job_id IS NULL AND orientation_route IS NULL
        AND response_review IS NULL AND prepared_memory_selection IS NULL
        AND delivery_receipt IS NULL
    )
);
