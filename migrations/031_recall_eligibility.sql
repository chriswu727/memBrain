ALTER TABLE memory_assertions ADD COLUMN recall_non_speech boolean
    GENERATED ALWAYS AS (
        coalesce(document->>'claim_kind','') NOT IN
            ('agent_said','proposal_offered','commitment_expressed')
        AND NOT (coalesce(document #>> '{derivation,method}','')='direct_capture'
                 AND left(document->>'statement',10)='assistant ')
    ) STORED;
