------------------------------------------------------------------
     -- PART 2: OLAP QUERIES AND AGGREGATIONS
------------------------------------------------------------------

--  Query 1: Monthly total transaction amount and fraud count
-- =====================================================================
-- Shows total monthly transactions and how many were marked as fraud.
-- Helps monitor fraud trends and seasonal behavior.
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

--  Query 2: Top 10 customers by total spending
-- =====================================================================
-- Identifies customers with the highest spending.
-- Useful for CRM insights, loyalty analysis, and monitoring for anomalies.
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

--  Query 3: Fraud transaction ratio by merchant state
-- =====================================================================
-- Calculates the percentage of transactions that are fraudulent in each state.
-- Supports fraud detection and regional risk assessment.
-- UPDATED: joins dim_location (not dim_merchant) for merchant_state.
-- Note: 'N/A' now appears as its own row for online/international
-- transactions where state doesn't apply -- a real, reportable
-- category rather than a silently dropped or miscounted one.
SELECT 
    loc.merchant_state,
    COUNT(f.fact_id) AS total_transactions,
    COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) AS fraud_transactions,
    ROUND( (COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) * 100.0) / NULLIF(COUNT(f.fact_id), 0), 2 ) AS fraud_percentage
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
GROUP BY loc.merchant_state
ORDER BY fraud_percentage DESC;

--  Query 4: Card brand performance and fraud rate
-- =====================================================================
-- Compares total transactions and fraud rate across card brands.
-- Helps the bank identify risky or overused card types.

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

-- Query 5: Average transaction amount by merchant city
-- =====================================================================
-- Provides insight into spending behavior in different locations.
-- Helps the bank plan promotions or loyalty programs city-wise.
-- UPDATED: joins dim_location (not dim_merchant) for merchant_city.
-- This is the query most directly affected by the original dim_merchant
-- grain bug -- prior to the redesign, a merchant spanning thousands of
-- cities would have had every transaction collapsed onto one arbitrary
-- city here (see WAREHOUSE_REDESIGN_NOTES.md, Section 2). Post-redesign,
-- each city's true transaction volume is reflected independently.
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
