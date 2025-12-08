-- Model parameters table
CREATE TABLE model_parameters (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    parameters_json JSONB NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_model_version UNIQUE (model_name, version)
);

-- Add trigger for updated_at
CREATE TRIGGER update_model_parameters_modtime
    BEFORE UPDATE ON model_parameters
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Insert initial Wyckoff model parameters
INSERT INTO model_parameters (
    model_name,
    version,
    parameters_json,
    effective_from
) VALUES (
    'wyckoff_v2',
    '2.0.0',
    '{
        "phase_thresholds": {
            "accumulation_min_score": 0.60,
            "distribution_min_score": 0.60
        },
        "event_detection": {
            "bc_volume_multiplier": 2.0,
            "spring_recovery_threshold": 0.02,
            "sos_volume_multiplier": 1.5
        },
        "scoring": {
            "bc_signal_weights": [4, 4, 4, 4, 4, 4, 4],
            "spring_signal_weights": [3, 3, 3, 3]
        }
    }'::jsonb,
    NOW()
);
