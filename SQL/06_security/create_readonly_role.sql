-- Create read-only role
CREATE ROLE finquery_readonly WITH LOGIN PASSWORD 'readonly_password';

-- Grant connection
GRANT CONNECT ON DATABASE finquery_dw_ai TO finquery_readonly;

-- Grant schema access
GRANT USAGE ON SCHEMA dw_etl, molap TO finquery_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA dw_etl, molap TO finquery_readonly;

-- Auto-grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA dw_etl, molap GRANT SELECT ON TABLES TO finquery_readonly;

-- Verification:
-- Test: Connect as finquery_readonly (should work)
SELECT COUNT(*) FROM dw_etl.fact_transactions;

-- Test: Try to drop a table (should fail)
DROP TABLE dw_etl.fact_transactions;