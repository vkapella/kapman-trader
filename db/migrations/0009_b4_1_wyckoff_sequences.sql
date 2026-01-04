CREATE SCHEMA IF NOT EXISTS b4_1;

CREATE TABLE IF NOT EXISTS b4_1.wyckoff_sequences (
    sequence_id UUID PRIMARY KEY,
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    sequence_type VARCHAR(40) NOT NULL,
    start_date DATE NOT NULL,
    terminal_date DATE NOT NULL,
    prior_regime VARCHAR(20) NOT NULL,
    terminal_event VARCHAR(10) NOT NULL,
    confidence NUMERIC(6, 4) NOT NULL,
    invalidated BOOLEAN NOT NULL DEFAULT FALSE,
    invalidated_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (ticker_id, terminal_date, terminal_event)
);

CREATE TABLE IF NOT EXISTS b4_1.wyckoff_sequence_events (
    sequence_id UUID NOT NULL
        REFERENCES b4_1.wyckoff_sequences(sequence_id)
        ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL,
    event_date DATE NOT NULL,
    event_role VARCHAR(12) NOT NULL,
    event_order INTEGER NOT NULL
);
