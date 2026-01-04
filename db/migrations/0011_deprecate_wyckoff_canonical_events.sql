DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'wyckoff_canonical_events'
    ) THEN
        COMMENT ON TABLE public.wyckoff_canonical_events IS
        'DEPRECATED: Do not use. Structural events are persisted in wyckoff_context_events.';
    END IF;
END $$;
