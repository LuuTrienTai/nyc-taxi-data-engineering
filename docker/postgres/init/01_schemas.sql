CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset TEXT NOT NULL,
    data_period TEXT,
    source_file TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','success','failed')),
    rows_read BIGINT,
    rows_loaded BIGINT,
    rows_rejected BIGINT,
    error_message TEXT
);

ALTER TABLE audit.pipeline_runs ADD COLUMN IF NOT EXISTS airflow_run_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_runs_airflow_run_id
    ON audit.pipeline_runs (airflow_run_id);
