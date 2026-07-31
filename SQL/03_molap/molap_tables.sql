------------------------------------------------------------------
     --              MOLAP SUMMARY TABLES
------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS molap;

-- MOLAP Table for Query 1: Monthly total transaction, amount and fraud count
-- =====================================================================
-- Precomputes monthly totals and fraud counts for faster OLAP reporting.
-- Unaffected by the merchant/location redesign (no merchant/location join).

DROP TABLE IF EXISTS molap.molap_monthly_transactions CASCADE;
CREATE TABLE molap.molap_monthly_transactions AS
SELECT 
    d.year,
    d.month,
    COUNT(f.fact_id) AS total_transactions,
    ROUND(SUM(f.amount), 2) AS total_transaction_amount,
    COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) AS fraud_transactions
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

SELECT * FROM molap.molap_monthly_transactions;


-- MOLAP Table for Query 2: Top 10 customers by total spending
-- =====================================================================
-- Precomputes total spending per customer for CRM dashboards.
-- Unaffected by the merchant/location redesign.

DROP TABLE IF EXISTS molap.molap_top_customers CASCADE;
CREATE TABLE molap.molap_top_customers AS
SELECT 
    c.customer_id,
    c.gender,
    c.current_age,
    ROUND(SUM(f.amount), 2) AS total_spent
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_id, c.gender, c.current_age
ORDER BY total_spent DESC
LIMIT 10;

SELECT * FROM molap.molap_top_customers;


-- MOLAP Table for Query 3: Fraud transaction ratio by merchant state
-- =====================================================================
-- Precomputes fraud percentage per state for risk monitoring.
-- UPDATED: joins dim_location (not dim_merchant) for merchant_state,
-- since state/city/zip moved off dim_merchant in the redesign.
-- This also means the -1/'N/A' and 'Online'/international sentinel
-- rows in dim_location now surface here as their own reportable
-- rows/categories rather than silently corrupting a real state's count.

DROP TABLE IF EXISTS molap.molap_fraud_by_state CASCADE;
CREATE TABLE molap.molap_fraud_by_state AS
SELECT 
    loc.merchant_state,
    COUNT(f.fact_id) AS total_transactions,
    COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) AS fraud_transactions,
    ROUND( (COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) * 100.0) / NULLIF(COUNT(f.fact_id), 0), 2 ) AS fraud_percentage
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
GROUP BY loc.merchant_state
ORDER BY fraud_percentage DESC;

SELECT * FROM molap.molap_fraud_by_state;


-- MOLAP Table for Query 4: Card brand performance and fraud rate
-- =====================================================================
-- Precomputes transaction counts, total amounts, and fraud rates by card brand.
-- Unaffected by the merchant/location redesign.

DROP TABLE IF EXISTS molap.molap_card_brand_performance CASCADE;
CREATE TABLE molap.molap_card_brand_performance AS
SELECT 
    cd.card_brand,
    COUNT(f.fact_id) AS total_transactions,
    ROUND(SUM(f.amount), 2) AS total_amount,
    COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) AS fraud_transactions,
    ROUND( (COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) * 100.0) / NULLIF(COUNT(f.fact_id), 0), 2 ) AS fraud_rate_percentage
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_card cd ON f.card_key = cd.card_key
GROUP BY cd.card_brand
ORDER BY total_transactions DESC;

SELECT * FROM molap.molap_card_brand_performance;


-- MOLAP Table for Query 5: Average transaction amount by merchant city
-- =====================================================================
-- Precomputes average, min, max, and count of transactions per city.
-- UPDATED: joins dim_location (not dim_merchant) for merchant_city.
-- This is also the query most directly affected by the original
-- dim_merchant grain bug -- prior to the redesign, a merchant spanning
-- thousands of cities would have had all its transactions collapsed
-- onto one arbitrary city here. Post-redesign, each city's true
-- transaction volume is reflected independently.

DROP TABLE IF EXISTS molap.molap_transactions_by_city CASCADE;
CREATE TABLE molap.molap_transactions_by_city AS
SELECT
    loc.merchant_city,
    COUNT(f.fact_id) AS num_transactions,
    ROUND(AVG(f.amount), 2) AS avg_transaction_amount,
    ROUND(MAX(f.amount), 2) AS max_transaction_amount,
    ROUND(MIN(f.amount), 2) AS min_transaction_amount
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
GROUP BY loc.merchant_city
ORDER BY avg_transaction_amount DESC
LIMIT 10;

SELECT * FROM molap.molap_transactions_by_city;
