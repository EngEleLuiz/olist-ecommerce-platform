-- Olist dev database bootstrap
-- Runs automatically on first `docker compose up` (postgres init scripts).
-- Safe to rerun — all statements use IF NOT EXISTS.

-- ── Schemas (mirror dbt target schemas) ──────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS raw;        -- landing zone for CSV imports
CREATE SCHEMA IF NOT EXISTS staging;    -- dbt staging views
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;      -- dbt mart tables (facts + dims)
CREATE SCHEMA IF NOT EXISTS ml;         -- ML prediction outputs

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- ── Grant privileges to app user ─────────────────────────────────────────────
-- (user already exists — created by POSTGRES_USER env var)
GRANT ALL PRIVILEGES ON SCHEMA raw          TO olist;
GRANT ALL PRIVILEGES ON SCHEMA staging      TO olist;
GRANT ALL PRIVILEGES ON SCHEMA intermediate TO olist;
GRANT ALL PRIVILEGES ON SCHEMA marts        TO olist;
GRANT ALL PRIVILEGES ON SCHEMA ml           TO olist;

-- ── Pipeline run log ──────────────────────────────────────────────────────────
-- Lightweight audit table — Step Functions writes here on each run.
CREATE TABLE IF NOT EXISTS raw.pipeline_runs (
    run_id          UUID        DEFAULT uuid_generate_v4() PRIMARY KEY,
    pipeline_name   TEXT        NOT NULL,
    status          TEXT        NOT NULL CHECK (status IN ('started','succeeded','failed')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    rows_processed  BIGINT,
    error_message   TEXT,
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_name_started
    ON raw.pipeline_runs (pipeline_name, started_at DESC);

-- ── LTV prediction cache ──────────────────────────────────────────────────────
-- Mirrors dbt_project/seeds/ltv_predictions.csv for SQL querying in pgAdmin.
CREATE TABLE IF NOT EXISTS ml.ltv_predictions (
    customer_unique_id      TEXT        NOT NULL,
    predicted_ltv_90d       NUMERIC(12,4),
    predicted_ltv_365d      NUMERIC(12,4),
    predicted_purchases_90d NUMERIC(12,4),
    predicted_at            DATE,
    loaded_at               TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (customer_unique_id, predicted_at)
);

COMMENT ON TABLE raw.pipeline_runs    IS 'Pipeline execution audit log';
COMMENT ON TABLE ml.ltv_predictions   IS 'BG/NBD + Gamma-Gamma LTV predictions';
