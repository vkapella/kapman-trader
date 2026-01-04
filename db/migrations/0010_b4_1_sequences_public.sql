CREATE TABLE IF NOT EXISTS wyckoff_sequence_events (
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    sequence_id VARCHAR(50) NOT NULL,
    completion_date DATE NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    event_date DATE NOT NULL,
    event_role VARCHAR(12) NOT NULL,
    event_order INTEGER NOT NULL,
    PRIMARY KEY (ticker_id, sequence_id, completion_date, event_order),
    FOREIGN KEY (ticker_id, sequence_id, completion_date)
        REFERENCES wyckoff_sequences(ticker_id, sequence_id, completion_date)
        ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.schemata
        WHERE schema_name = 'b4_1'
    ) THEN
        IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'b4_1'
              AND table_name = 'wyckoff_sequences'
        ) THEN
            WITH seqs AS (
                SELECT
                    sequence_id,
                    ticker_id,
                    sequence_type,
                    start_date,
                    terminal_date,
                    prior_regime,
                    terminal_event,
                    confidence,
                    invalidated,
                    invalidated_reason
                FROM b4_1.wyckoff_sequences
            ),
            events AS (
                SELECT
                    e.sequence_id,
                    jsonb_agg(
                        jsonb_build_object(
                            'event_type', e.event_type,
                            'event_date', e.event_date,
                            'event_role', e.event_role,
                            'event_order', e.event_order
                        )
                        ORDER BY e.event_order
                    ) AS events_json
                FROM b4_1.wyckoff_sequence_events e
                GROUP BY e.sequence_id
            )
            INSERT INTO wyckoff_sequences (
                ticker_id,
                sequence_id,
                start_date,
                completion_date,
                events_in_sequence
            )
            SELECT
                s.ticker_id,
                s.sequence_type,
                s.start_date,
                s.terminal_date,
                jsonb_build_object(
                    'sequence_type', s.sequence_type,
                    'terminal_event', s.terminal_event,
                    'prior_regime', s.prior_regime,
                    'confidence', s.confidence,
                    'invalidated', s.invalidated,
                    'invalidated_reason', s.invalidated_reason,
                    'events', COALESCE(e.events_json, '[]'::jsonb)
                )
            FROM seqs s
            LEFT JOIN events e ON e.sequence_id = s.sequence_id
            ON CONFLICT (ticker_id, sequence_id, completion_date)
            DO NOTHING;

            INSERT INTO wyckoff_sequence_events (
                ticker_id,
                sequence_id,
                completion_date,
                event_type,
                event_date,
                event_role,
                event_order
            )
            SELECT
                s.ticker_id,
                s.sequence_type,
                s.terminal_date,
                e.event_type,
                e.event_date,
                e.event_role,
                e.event_order
            FROM b4_1.wyckoff_sequence_events e
            JOIN b4_1.wyckoff_sequences s ON s.sequence_id = e.sequence_id
            ON CONFLICT DO NOTHING;
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'b4_1'
              AND table_name NOT IN ('wyckoff_sequences', 'wyckoff_sequence_events')
        ) THEN
            DROP SCHEMA IF EXISTS b4_1 CASCADE;
        END IF;
    END IF;
END $$;
