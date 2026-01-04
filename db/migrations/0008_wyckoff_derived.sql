CREATE TABLE IF NOT EXISTS wyckoff_regime_transitions (
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    date DATE NOT NULL,
    prior_regime VARCHAR(20),
    new_regime VARCHAR(20),
    duration_bars INTEGER,
    PRIMARY KEY (ticker_id, date, new_regime)
);

CREATE TABLE IF NOT EXISTS wyckoff_sequences (
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    sequence_id VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    completion_date DATE NOT NULL,
    events_in_sequence JSONB NOT NULL,
    PRIMARY KEY (ticker_id, sequence_id, completion_date)
);

CREATE TABLE IF NOT EXISTS wyckoff_context_events (
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    event_date DATE NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    prior_regime VARCHAR(20) NOT NULL,
    context_label VARCHAR(60) NOT NULL,
    PRIMARY KEY (ticker_id, event_date, event_type, prior_regime)
);

CREATE TABLE IF NOT EXISTS wyckoff_snapshot_evidence (
    ticker_id UUID NOT NULL
        REFERENCES tickers(id)
        ON DELETE CASCADE,
    date DATE NOT NULL,
    evidence_json JSONB NOT NULL,
    PRIMARY KEY (ticker_id, date)
);
