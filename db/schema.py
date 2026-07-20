"""DuckDB schema definitions for RevWatch."""

from __future__ import annotations

BUSINESSES_DDL = """
CREATE TABLE IF NOT EXISTS businesses (
    id              VARCHAR PRIMARY KEY,
    name            VARCHAR NOT NULL,
    category        VARCHAR NOT NULL,
    country         VARCHAR NOT NULL,
    city            VARCHAR NOT NULL,
    latitude        DOUBLE NOT NULL,
    longitude       DOUBLE NOT NULL,
    size_tier       VARCHAR NOT NULL,
    channels        VARCHAR[] NOT NULL,
    created_at      TIMESTAMP DEFAULT current_timestamp,
    updated_at      TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_businesses_country ON businesses(country);
CREATE INDEX IF NOT EXISTS idx_businesses_city ON businesses(city);
CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category);
"""

SIGNAL_OBSERVATIONS_DDL = """
CREATE TABLE IF NOT EXISTS signal_observations (
    id              VARCHAR DEFAULT (uuid()) PRIMARY KEY,
    business_id     VARCHAR NOT NULL REFERENCES businesses(id),
    signal_type     VARCHAR NOT NULL,
    value           DOUBLE NOT NULL,
    timestamp       TIMESTAMP NOT NULL,
    source          VARCHAR NOT NULL,
    reliability     DOUBLE NOT NULL,
    ingested_at     TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_signals_business ON signal_observations(business_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signal_observations(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signal_observations(timestamp);
"""

REVENUE_ESTIMATES_DDL = """
CREATE TABLE IF NOT EXISTS revenue_estimates (
    id                      VARCHAR DEFAULT (uuid()) PRIMARY KEY,
    business_id             VARCHAR NOT NULL REFERENCES businesses(id),
    period                  VARCHAR NOT NULL,
    point_estimate          DOUBLE NOT NULL,
    ci_low                  DOUBLE NOT NULL,
    ci_high                 DOUBLE NOT NULL,
    confidence_score        DOUBLE NOT NULL,
    signal_contributions    JSON NOT NULL,
    model_version           VARCHAR NOT NULL,
    created_at              TIMESTAMP DEFAULT current_timestamp,
    UNIQUE (business_id, period, model_version)
);

CREATE INDEX IF NOT EXISTS idx_estimates_business ON revenue_estimates(business_id);
CREATE INDEX IF NOT EXISTS idx_estimates_period ON revenue_estimates(period);
CREATE INDEX IF NOT EXISTS idx_estimates_model ON revenue_estimates(model_version);
"""

SOURCE_MAPPINGS_DDL = """
CREATE TABLE IF NOT EXISTS source_mappings (
    source          VARCHAR NOT NULL,
    source_id       VARCHAR NOT NULL,
    business_id     VARCHAR NOT NULL REFERENCES businesses(id),
    created_at      TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (source, source_id)
);
"""

TRUE_REVENUE_DDL = """
CREATE TABLE IF NOT EXISTS true_revenue (
    business_id         VARCHAR NOT NULL REFERENCES businesses(id),
    period              VARCHAR NOT NULL,
    revenue             DOUBLE NOT NULL,
    trend_factor        DOUBLE NOT NULL DEFAULT 1.0,
    seasonal_factor     DOUBLE NOT NULL DEFAULT 1.0,
    shock_factor        DOUBLE NOT NULL DEFAULT 1.0,
    created_at          TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (business_id, period)
);

CREATE INDEX IF NOT EXISTS idx_true_revenue_period ON true_revenue(period);
CREATE INDEX IF NOT EXISTS idx_true_revenue_business ON true_revenue(business_id);
"""

VALIDATION_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS validation_reports (
    id                  VARCHAR DEFAULT (uuid()) PRIMARY KEY,
    model_version       VARCHAR NOT NULL,
    n_observations      INTEGER NOT NULL,
    mape                DOUBLE NOT NULL,
    median_ape          DOUBLE NOT NULL,
    interval_coverage   DOUBLE NOT NULL,
    mean_confidence     DOUBLE NOT NULL,
    segment_metrics     JSON NOT NULL,
    calibration         JSON NOT NULL,
    promoted            BOOLEAN NOT NULL DEFAULT FALSE,
    notes               VARCHAR DEFAULT '',
    created_at          TIMESTAMP DEFAULT current_timestamp
);

CREATE INDEX IF NOT EXISTS idx_validation_model ON validation_reports(model_version);
CREATE INDEX IF NOT EXISTS idx_validation_created ON validation_reports(created_at);
"""

PIPELINE_RUNS_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                  VARCHAR DEFAULT (uuid()) PRIMARY KEY,
    job_name            VARCHAR NOT NULL,
    status              VARCHAR NOT NULL,
    started_at          TIMESTAMP NOT NULL,
    finished_at         TIMESTAMP,
    details             JSON,
    error_message       VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_job ON pipeline_runs(job_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
"""

MODEL_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS model_registry (
    model_version       VARCHAR PRIMARY KEY,
    status              VARCHAR NOT NULL,
    mape                DOUBLE,
    promoted_at         TIMESTAMP,
    notes               VARCHAR DEFAULT '',
    created_at          TIMESTAMP DEFAULT current_timestamp
);
"""

ALL_DDL = (
    BUSINESSES_DDL
    + SIGNAL_OBSERVATIONS_DDL
    + REVENUE_ESTIMATES_DDL
    + SOURCE_MAPPINGS_DDL
    + TRUE_REVENUE_DDL
    + VALIDATION_REPORTS_DDL
    + PIPELINE_RUNS_DDL
    + MODEL_REGISTRY_DDL
)
