-- Job runs table
CREATE TABLE job_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,
    tickers_processed INTEGER DEFAULT 0,
    errors_json JSONB,
    duration_seconds INTEGER,
    metadata JSONB
);

-- Indexes for job runs
CREATE INDEX idx_job_runs_job_name ON job_runs(job_name);
CREATE INDEX idx_job_runs_started_at ON job_runs(started_at DESC);
CREATE INDEX idx_job_runs_status ON job_runs(status);
