--				ETL
-- Schema Already Created.

-- Transformed Data into tables

-- users 
TRUNCATE etl.users_clean;

INSERT INTO etl.users_clean
SELECT DISTINCT
  u.id::TEXT AS customer_id,
  NULLIF(u.current_age,'')::INT,
  NULLIF(u.retirement_age,'')::INT,
  NULLIF(u.birth_year,'')::INT,
  NULLIF(u.birth_month,'')::INT,
  INITCAP(TRIM(u.gender)) AS gender,
  TRIM(u.address),
  NULLIF(u.latitude,'')::NUMERIC(9,6),
  NULLIF(u.longitude,'')::NUMERIC(9,6),
  NULLIF(REGEXP_REPLACE(u.per_capita_income, '[^\d\.]', '', 'g'), '')::NUMERIC(14,2),
  NULLIF(REGEXP_REPLACE(u.yearly_income, '[^\d\.]', '', 'g'), '')::NUMERIC(14,2),
  NULLIF(REGEXP_REPLACE(u.total_debt, '[^\d\.]', '', 'g'), '')::NUMERIC(18,2),
  NULLIF(u.credit_score,'')::INT,
  NULLIF(u.num_credit_cards,'')::INT
FROM staging.stg_users u
WHERE u.id IS NOT NULL;


-- cards
TRUNCATE etl.cards_clean;

INSERT INTO etl.cards_clean
SELECT DISTINCT
  c.id::TEXT AS card_id,
  c.client_id::TEXT,
  INITCAP(TRIM(c.card_brand)) AS card_brand,
  INITCAP(TRIM(c.card_type)) AS card_type,
  CONCAT('XXXX-XXXX-XXXX-', RIGHT(LPAD(REGEXP_REPLACE(c.card_number_raw::TEXT, '\D', '', 'g'), 16, '0'), 4)) AS card_number_masked,
  CASE WHEN UPPER(TRIM(c.has_chip_raw)) = 'YES' THEN TRUE ELSE FALSE END AS has_chip,
  NULLIF(REGEXP_REPLACE(c.credit_limit_raw, '[^\d\.]', '', 'g'), '')::NUMERIC(14,2) AS credit_limit,

  CASE 
    WHEN TRIM(c.acct_open_date_raw) ~ '^[0-9]{1,2}/[0-9]{4}$' THEN
      TO_DATE(TRIM(c.acct_open_date_raw), 'MM/YYYY')
    ELSE NULL
  END AS acct_open_date,

  CASE 
    WHEN TRIM(c.expires_raw) ~ '^[0-9]{1,2}/[0-9]{4}$' THEN
      TO_DATE(TRIM(c.expires_raw), 'MM/YYYY')
    ELSE NULL
  END AS expires,

  NULLIF(c.num_cards_issued, '')::INT AS num_cards_issued,
  NULLIF(c.year_pin_last_changed, '')::INT AS year_pin_last_changed,
  CASE WHEN UPPER(TRIM(c.card_on_dark_web)) = 'YES' THEN TRUE ELSE FALSE END AS card_on_dark_web
FROM staging.stg_cards c
WHERE c.id IS NOT NULL;

-- mcc 

TRUNCATE etl.mcc_clean;

INSERT INTO etl.mcc_clean (mcc_code, description)
SELECT DISTINCT TRIM(mcc_code)::TEXT, INITCAP(TRIM(description))
FROM staging.stg_mcc
WHERE mcc_code IS NOT NULL AND TRIM(mcc_code) <> '';


-- fraud
TRUNCATE etl.fraud_clean;

INSERT INTO etl.fraud_clean (transaction_id, fraud_label)
SELECT transaction_id, TRIM(fraud_label) FROM staging.stg_fraud_labels;


-- transactions
TRUNCATE etl.transactions_clean;

INSERT INTO etl.transactions_clean (
  transaction_id, transaction_date, client_id, card_id, amount,
  use_chip, merchant_id, merchant_city, merchant_state, merchant_zip, mcc_code, errors
)
SELECT
  t.id::BIGINT AS transaction_id,
  CASE
    WHEN t.raw_date ~ '^\d{4}-\d{2}-\d{2}' THEN TO_DATE(SPLIT_PART(t.raw_date,' ',1), 'YYYY-MM-DD')
    WHEN t.raw_date ~ '^\d{1,2}/\d{1,2}/\d{4}' THEN TO_DATE(SPLIT_PART(t.raw_date,' ',1), 'MM/DD/YYYY')
    ELSE NULL
  END AS transaction_date,
  t.client_id::TEXT,
  t.card_id::TEXT,
  NULLIF(REGEXP_REPLACE(t.amount_raw, '[^\d\.\-()]', '', 'g'), '')::numeric(18,2) * 
    CASE WHEN t.amount_raw ~ '^\(' THEN -1 ELSE 1 END AS amount,
  CASE WHEN UPPER(TRIM(t.use_chip_raw)) LIKE '%CHIP%' THEN TRUE
       WHEN UPPER(TRIM(t.use_chip_raw)) LIKE '%SWIPE%' THEN FALSE
       ELSE NULL END AS use_chip,
  REGEXP_REPLACE(TRIM(t.merchant_id), '[^0-9A-Za-z]', '', 'g') AS merchant_id,
  INITCAP(TRIM(t.merchant_city)) AS merchant_city,
  UPPER(TRIM(t.merchant_state)) AS merchant_state,
  TRIM(t.merchant_zip) AS merchant_zip,
  TRIM(t.mcc) AS mcc_code,
  t.errors
FROM staging.stg_transactions t
WHERE t.id IS NOT NULL;


-- errors
TRUNCATE etl.errors_clean;

INSERT INTO etl.errors_clean (error_desc)
SELECT DISTINCT
    CASE 
        WHEN TRIM(errors) = '' OR errors IS NULL THEN 'NO_ERROR'
        ELSE INITCAP(TRIM(errors))
    END AS error_desc
FROM etl.transactions_clean;


-- Load data into dw_etl dimensions 

TRUNCATE TABLE dw_etl.fact_transactions RESTART IDENTITY;

-- dim date
-- Truncate and reset dim_date
TRUNCATE TABLE dw_etl.dim_date CASCADE;

-- Step 1: Insert Standard Unknown / Default Fallback Row (1900-01-01)
INSERT INTO dw_etl.dim_date (
    date_key,
    full_date,
    year,
    quarter,
    month,
    month_name,
    day_of_month,
    day_of_week,
    day_name,
    is_weekend
) VALUES (
    19000101,
    '1900-01-01'::DATE,
    1900,
    1,
    1,
    'January',
    1,
    1, -- Monday (ISO standard)
    'Monday',
    FALSE
);

-- Step 2: Dynamically calculate boundaries with +1 year padding and generate calendar series
WITH date_bounds AS (
    SELECT 
        -- Start: Jan 01 of the earliest year in source data
        -- (Falls back to CURRENT_DATE if source table is empty)
        DATE_TRUNC('year', COALESCE(MIN(transaction_date), CURRENT_DATE))::DATE AS min_date,
        
        -- End: Dec 31 of MAX(year) + 1 year (Padding Strategy)
        -- e.g., MAX date in 2023 -> Pad through Dec 31, 2024
        (DATE_TRUNC('year', COALESCE(MAX(transaction_date), CURRENT_DATE)) + INTERVAL '2 years - 1 day')::DATE AS max_date
    FROM etl.transactions_clean
),
date_series AS (
    SELECT 
        generate_series(
            (SELECT min_date FROM date_bounds), 
            (SELECT max_date FROM date_bounds), 
            INTERVAL '1 day'
        )::DATE AS d
)
INSERT INTO dw_etl.dim_date (
    date_key,
    full_date,
    year,
    quarter,
    month,
    month_name,
    day_of_month,
    day_of_week,
    day_name,
    is_weekend
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
    d AS full_date,
    EXTRACT(YEAR FROM d)::INT AS year,
    EXTRACT(QUARTER FROM d)::INT AS quarter,
    EXTRACT(MONTH FROM d)::INT AS month,
    TRIM(TO_CHAR(d, 'Month')) AS month_name,
    EXTRACT(DAY FROM d)::INT AS day_of_month,
    EXTRACT(ISODOW FROM d)::INT AS day_of_week,
    TRIM(TO_CHAR(d, 'Day')) AS day_name,
    CASE WHEN EXTRACT(ISODOW FROM d) IN (6, 7) THEN TRUE ELSE FALSE END AS is_weekend
FROM date_series;



-- dim customer
TRUNCATE dw_etl.dim_customer RESTART IDENTITY CASCADE;

INSERT INTO dw_etl.dim_customer (customer_key, customer_id, gender, address)
VALUES (-1, 'N/A', 'N/A', 'N/A');

INSERT INTO dw_etl.dim_customer (
  customer_id, current_age, birth_year, birth_month,
  gender, address, latitude, longitude, per_capita_income, yearly_income,
  total_debt, credit_score, num_credit_cards
)
SELECT customer_id, current_age,birth_year, birth_month,
  gender, address, latitude, longitude, per_capita_income, yearly_income,
  total_debt, credit_score, num_credit_cards
FROM etl.users_clean;


-- dim card
TRUNCATE dw_etl.dim_card RESTART IDENTITY CASCADE;

INSERT INTO dw_etl.dim_card (card_key, card_id, card_brand, card_type, card_number_masked)
VALUES (-1, 'N/A', 'N/A', 'N/A', 'N/A');

INSERT INTO dw_etl.dim_card (
  card_id, client_id, card_brand, card_type, card_number_masked,
  has_chip, credit_limit, acct_open_date, expires, num_cards_issued,
  year_pin_last_changed, card_on_dark_web
)
SELECT 
  card_id, client_id, card_brand, card_type, card_number_masked,
  has_chip, credit_limit, acct_open_date, expires, num_cards_issued,
  year_pin_last_changed, card_on_dark_web
FROM etl.cards_clean;



-- dim merchant 
TRUNCATE dw_etl.dim_merchant RESTART IDENTITY CASCADE;

INSERT INTO dw_etl.dim_merchant (merchant_key, merchant_id)
VALUES (-1, 'N/A');

INSERT INTO dw_etl.dim_merchant (merchant_id)
SELECT DISTINCT merchant_id
FROM etl.transactions_clean
WHERE merchant_id IS NOT NULL AND TRIM(merchant_id) <> '';



-- dim location
TRUNCATE dw_etl.dim_location RESTART IDENTITY CASCADE;

INSERT INTO dw_etl.dim_location (location_key, merchant_city, merchant_state, merchant_zip, location)
VALUES (-1, 'N/A', 'N/A', 'N/A', 'N/A');

INSERT INTO dw_etl.dim_location (merchant_city, merchant_state, merchant_zip, location)
SELECT DISTINCT
  COALESCE(INITCAP(TRIM(merchant_city)), 'N/A')   AS merchant_city,
  COALESCE(UPPER(TRIM(merchant_state)), 'N/A')    AS merchant_state,
  COALESCE(TRIM(merchant_zip), 'N/A')             AS merchant_zip,
  CASE 
    WHEN UPPER(TRIM(merchant_city)) = 'ONLINE' THEN 'Online / No Physical Location'
    ELSE CONCAT(
      INITCAP(TRIM(merchant_city)), ', ',
      UPPER(TRIM(merchant_state))
    )
  END AS location
FROM etl.transactions_clean;



-- dim mcc
TRUNCATE dw_etl.dim_mcc RESTART IDENTITY CASCADE;

INSERT INTO dw_etl.dim_mcc (mcc_key, mcc_code, description)
VALUES (-1, 'N/A', 'N/A');

INSERT INTO dw_etl.dim_mcc (mcc_code, description)
SELECT mcc_code, description FROM etl.mcc_clean;


-- dim error
TRUNCATE dw_etl.dim_error RESTART IDENTITY CASCADE;

INSERT INTO dw_etl.dim_error (error_key, error_desc)
VALUES (-1, 'N/A');

INSERT INTO dw_etl.dim_error (error_desc)
SELECT error_desc
FROM etl.errors_clean;



-- Fact Table
INSERT INTO dw_etl.fact_transactions (
    transaction_id, date_key, customer_key, card_key,
    merchant_key, location_key, mcc_key,
    amount, use_chip, fraud_label, anomaly_flag, error_key
)
SELECT
    tx.transaction_id,
    COALESCE(d.date_key, 19000101)      AS date_key,
    COALESCE(cu.customer_key, -1)       AS customer_key,
    COALESCE(ca.card_key, -1)           AS card_key,
    COALESCE(m.merchant_key, -1)        AS merchant_key,
    COALESCE(loc.location_key, -1)      AS location_key,
    COALESCE(mm.mcc_key, -1)            AS mcc_key,
    tx.amount,
    tx.use_chip,
    CASE WHEN LOWER(TRIM(fc.fraud_label)) IN ('yes','y','true','fraud','1') THEN TRUE ELSE FALSE END AS fraud_label,
    FALSE AS anomaly_flag,
    COALESCE(e.error_key, -1)           AS error_key
FROM etl.transactions_clean tx
LEFT JOIN dw_etl.dim_date d ON d.full_date = tx.transaction_date::date
LEFT JOIN dw_etl.dim_customer cu ON cu.customer_id = tx.client_id
LEFT JOIN dw_etl.dim_card ca ON ca.card_id = tx.card_id
LEFT JOIN dw_etl.dim_merchant m ON m.merchant_id = tx.merchant_id
LEFT JOIN dw_etl.dim_location loc
       ON loc.merchant_city  = COALESCE(INITCAP(TRIM(tx.merchant_city)), 'N/A')
      AND loc.merchant_state = COALESCE(UPPER(TRIM(tx.merchant_state)), 'N/A')
      AND loc.merchant_zip   = COALESCE(TRIM(tx.merchant_zip), 'N/A')
LEFT JOIN dw_etl.dim_mcc mm ON mm.mcc_code = tx.mcc_code
LEFT JOIN etl.fraud_clean fc ON fc.transaction_id = tx.transaction_id
LEFT JOIN dw_etl.dim_error e
       ON (CASE WHEN tx.errors IS NULL OR TRIM(tx.errors) = '' THEN 'NO_ERROR'
                ELSE INITCAP(TRIM(tx.errors)) END) = e.error_desc;




-- ============================================================================
--              Data Integrity & Row-Count Validation Script
-- Note: Dimension tables include +1 for the unknown/default fallback record (-1)
-- ============================================================================

-- 1. Fact Transactions Count Check (Expecting exact 1:1 match)
SELECT
  (SELECT COUNT(*) FROM staging.stg_transactions WHERE id IS NOT NULL) AS staging_valid_transactions,
  (SELECT COUNT(*) FROM dw_etl.fact_transactions) AS dw_etl_fact_count;


-- 2. Customer Dimension Check (Staging distinct IDs vs Dimension count - 1)
SELECT
  (SELECT COUNT(DISTINCT id::TEXT) FROM staging.stg_users WHERE id IS NOT NULL) AS staging_distinct_users,
  (SELECT COUNT(*) - 1 FROM dw_etl.dim_customer) AS dw_etl_customers_excl_unknown;


-- 3. Card Dimension Check (Staging distinct IDs vs Dimension count - 1)
SELECT
  (SELECT COUNT(DISTINCT id::TEXT) FROM staging.stg_cards WHERE id IS NOT NULL) AS staging_distinct_cards,
  (SELECT COUNT(*) - 1 FROM dw_etl.dim_card) AS dw_etl_cards_excl_unknown;


-- 4. Merchant Dimension Check (Cleaned merchant IDs vs Dimension count - 1)
SELECT
  (SELECT COUNT(DISTINCT REGEXP_REPLACE(TRIM(merchant_id), '[^0-9A-Za-z]', '', 'g'))
     FROM staging.stg_transactions
     WHERE merchant_id IS NOT NULL AND TRIM(merchant_id) <> '') AS staging_distinct_merchants,
  (SELECT COUNT(*) - 1 FROM dw_etl.dim_merchant) AS dw_etl_merchants_excl_unknown;


-- 5. Location Dimension Check (Spatial combinations vs Dimension count - 1)
SELECT
  (SELECT COUNT(DISTINCT (
      COALESCE(INITCAP(TRIM(merchant_city)), 'N/A'),
      COALESCE(UPPER(TRIM(merchant_state)), 'N/A'),
      COALESCE(TRIM(merchant_zip), 'N/A')
   ))
   FROM staging.stg_transactions) AS staging_distinct_locations,
  (SELECT COUNT(*) - 1 FROM dw_etl.dim_location) AS dw_etl_locations_excl_unknown;


-- 6. MCC Dimension Check (Cleaned MCC codes vs Dimension count - 1)
SELECT
  (SELECT COUNT(DISTINCT TRIM(mcc_code)::TEXT) 
     FROM staging.stg_mcc
     WHERE mcc_code IS NOT NULL AND TRIM(mcc_code) <> '') AS staging_distinct_mcc,
  (SELECT COUNT(*) - 1 FROM dw_etl.dim_mcc) AS dw_etl_mcc_excl_unknown;


-- 7. Error Dimension Check (Unique parsed errors vs Dimension count - 1)
SELECT
  (SELECT COUNT(DISTINCT 
      CASE 
        WHEN TRIM(errors) = '' OR errors IS NULL THEN 'NO_ERROR'
        ELSE INITCAP(TRIM(errors))
      END)
   FROM staging.stg_transactions) AS staging_distinct_errors,
  (SELECT COUNT(*) - 1 FROM dw_etl.dim_error) AS dw_etl_errors_excl_unknown;


-- 8. Fraud Label Integrity Check
SELECT
  (SELECT COUNT(*) 
     FROM staging.stg_fraud_labels 
     WHERE LOWER(TRIM(fraud_label)) IN ('yes','y','true','fraud','1')) AS staging_fraud_count,
  (SELECT COUNT(*) 
     FROM dw_etl.fact_transactions 
     WHERE fraud_label IS TRUE) AS dw_etl_fact_fraud_count;
  