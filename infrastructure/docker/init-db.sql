-- infrastructure/docker/init-db.sql
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS agriculture;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS telemetry;

-- Set search path
SET search_path TO agriculture, analytics, telemetry, public;

-- Create user if not exists (already created by docker-compose)
-- GRANT ALL PRIVILEGES ON DATABASE agriculture_ai TO agri_user;

-- Create tables (these will be created by Alembic migrations)
-- This file is just for initialization

-- Enable row level security
ALTER DATABASE agriculture_ai SET row_security = on;

-- Create indexes for performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scan_user_date ON agriculture.scans(user_id, created_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_prediction_confidence ON agriculture.predictions(confidence_score) WHERE confidence_score > 0.8;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_telemetry_device_time ON agriculture.telemetry(device_id, timestamp DESC);

-- Create materialized view for analytics
CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.daily_metrics AS
SELECT 
    DATE(s.created_at) as date,
    COUNT(DISTINCT s.user_id) as active_users,
    COUNT(s.id) as total_scans,
    AVG(p.confidence_score) as avg_confidence,
    COUNT(CASE WHEN p.inference_source = 'edge' THEN 1 END) as edge_predictions,
    COUNT(CASE WHEN p.inference_source = 'cloud' THEN 1 END) as cloud_predictions
FROM agriculture.scans s
JOIN agriculture.predictions p ON p.scan_id = s.id
GROUP BY DATE(s.created_at)
WITH DATA;

-- Refresh materialized view daily
CREATE OR REPLACE FUNCTION refresh_daily_metrics()
RETURNS trigger AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY analytics.daily_metrics;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA agriculture TO agri_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA agriculture TO agri_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO agri_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA analytics TO agri_user;