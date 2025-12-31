ALTER TABLE daily_snapshots
    ADD COLUMN IF NOT EXISTS wyckoff_regime VARCHAR(20)
        CHECK (wyckoff_regime IN ('ACCUMULATION', 'MARKUP', 'DISTRIBUTION', 'MARKDOWN', 'UNKNOWN'));

ALTER TABLE daily_snapshots
    ADD COLUMN IF NOT EXISTS wyckoff_regime_confidence NUMERIC(4,3)
        CHECK (wyckoff_regime_confidence BETWEEN 0 AND 1);

ALTER TABLE daily_snapshots
    ADD COLUMN IF NOT EXISTS wyckoff_regime_set_by_event VARCHAR(20);