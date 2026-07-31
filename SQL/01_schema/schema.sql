-- Drop schemas
DROP SCHEMA IF EXISTS staging CASCADE;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS staging;

-- STAGING TABLES

-- Staging table: transactions (keep raw text columns)
DROP TABLE IF EXISTS staging.stg_transactions;
CREATE TABLE staging.stg_transactions (
  id              BIGINT,
  raw_date        TEXT,
  client_id       TEXT,
  card_id         TEXT,
  amount_raw      TEXT,
  use_chip_raw    TEXT,
  merchant_id     TEXT,
  merchant_city   TEXT,
  merchant_state  TEXT,
  merchant_zip    TEXT,
  mcc             TEXT,
  errors          TEXT
);

-- Staging table: users
DROP TABLE IF EXISTS staging.stg_users;
CREATE TABLE staging.stg_users (
  id                TEXT,
  current_age       TEXT,
  retirement_age    TEXT,
  birth_year        TEXT,
  birth_month       TEXT,
  gender            TEXT,
  address           TEXT,
  latitude          TEXT,
  longitude         TEXT,
  per_capita_income TEXT,
  yearly_income     TEXT,
  total_debt        TEXT,
  credit_score      TEXT,
  num_credit_cards  TEXT
);

-- Staging table: cards
DROP TABLE IF EXISTS staging.stg_cards;
CREATE TABLE staging.stg_cards (
  id                 TEXT,
  client_id          TEXT,
  card_brand         TEXT,
  card_type          TEXT,
  card_number_raw    TEXT,
  expires_raw        TEXT,
  cvv                TEXT,
  has_chip_raw       TEXT,
  num_cards_issued   TEXT,
  credit_limit_raw   TEXT,
  acct_open_date_raw TEXT,
  year_pin_last_changed TEXT,
  card_on_dark_web   TEXT
);

-- Staging table: mcc codes
DROP TABLE IF EXISTS staging.stg_mcc;
CREATE TABLE staging.stg_mcc (
  mcc_code TEXT PRIMARY KEY,
  description TEXT
);

-- Staging table: fraud labels
DROP TABLE IF EXISTS staging.stg_fraud_labels;
CREATE TABLE staging.stg_fraud_labels (
  transaction_id BIGINT PRIMARY KEY,
  fraud_label TEXT
);


--			ETL Schema

--  create schemas for ETL
CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS dw_etl;

-- create cleaned tables
DROP TABLE IF EXISTS etl.transactions_clean;
CREATE TABLE etl.transactions_clean (
  transaction_id BIGINT PRIMARY KEY,
  transaction_date DATE,
  client_id TEXT,
  card_id TEXT,
  amount NUMERIC(18,2),
  use_chip BOOLEAN,
  merchant_id TEXT,
  merchant_city TEXT,
  merchant_state TEXT,
  merchant_zip TEXT,
  mcc_code TEXT,
  errors TEXT
);

DROP TABLE IF EXISTS etl.users_clean;
CREATE TABLE etl.users_clean (
  customer_id TEXT PRIMARY KEY,
  current_age INT,
  retirement_age INT,
  birth_year INT,
  birth_month INT,
  gender TEXT,
  address TEXT,
  latitude NUMERIC(9,6),
  longitude NUMERIC(9,6),
  per_capita_income NUMERIC(14,2),
  yearly_income NUMERIC(14,2),
  total_debt NUMERIC(18,2),
  credit_score INT,
  num_credit_cards INT
);

DROP TABLE IF EXISTS etl.cards_clean;
CREATE TABLE etl.cards_clean (
  card_id TEXT PRIMARY KEY,
  client_id TEXT,
  card_brand TEXT,
  card_type TEXT,
  card_number_masked TEXT,
  has_chip BOOLEAN,
  credit_limit NUMERIC(14,2),
  acct_open_date DATE,           
  expires DATE,               
  num_cards_issued INT,
  year_pin_last_changed INT,
  card_on_dark_web BOOLEAN
);

DROP TABLE IF EXISTS etl.mcc_clean;
CREATE TABLE etl.mcc_clean (
  mcc_code TEXT PRIMARY KEY,
  description TEXT
);

DROP TABLE IF EXISTS etl.fraud_clean;
CREATE TABLE etl.fraud_clean (
  transaction_id BIGINT PRIMARY KEY,
  fraud_label TEXT
);

DROP TABLE IF EXISTS etl.errors_clean;
CREATE TABLE etl.errors_clean (
    error_desc TEXT PRIMARY KEY
);

--  create dw_etl star schema (Actual data warehouse)

DROP TABLE IF EXISTS dw_etl.dim_date CASCADE;
CREATE TABLE dw_etl.dim_date (
    date_key INT PRIMARY KEY,               -- e.g., 20231015 or 19000101 (NOT auto-increment)
    full_date DATE UNIQUE,                  -- e.g., '2023-10-15'
    year INT NOT NULL,
    quarter INT NOT NULL,
    month INT NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day_of_month INT NOT NULL,
    day_of_week INT NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

DROP TABLE IF EXISTS dw_etl.dim_customer CASCADE;
CREATE TABLE dw_etl.dim_customer (
  customer_key BIGSERIAL PRIMARY KEY,
  customer_id TEXT UNIQUE,
  current_age INT,
  birth_year INT,
  birth_month INT,
  gender TEXT,
  address TEXT,
  latitude NUMERIC(9,6),
  longitude NUMERIC(9,6),
  per_capita_income NUMERIC(14,2),
  yearly_income NUMERIC(14,2),
  total_debt NUMERIC(18,2),
  credit_score INT,
  num_credit_cards INT
);

DROP TABLE IF EXISTS dw_etl.dim_card CASCADE;
CREATE TABLE dw_etl.dim_card (
  card_key BIGSERIAL PRIMARY KEY,
  card_id TEXT UNIQUE,
  client_id TEXT,
  card_brand TEXT,
  card_type TEXT,
  card_number_masked TEXT,
  has_chip BOOLEAN,
  credit_limit NUMERIC(14,2),
  acct_open_date DATE,   
  expires DATE,               
  num_cards_issued INT,
  year_pin_last_changed INT,
  card_on_dark_web BOOLEAN
);


DROP TABLE IF EXISTS dw_etl.dim_merchant CASCADE;
CREATE TABLE dw_etl.dim_merchant (
  merchant_key BIGSERIAL PRIMARY KEY,
  merchant_id  TEXT UNIQUE NOT NULL       -- true 1:1 natural key restored
);

DROP TABLE IF EXISTS dw_etl.dim_location CASCADE;
CREATE TABLE dw_etl.dim_location (
  location_key   BIGSERIAL PRIMARY KEY,
  merchant_city  TEXT NOT NULL DEFAULT 'N/A',
  merchant_state TEXT NOT NULL DEFAULT 'N/A',
  merchant_zip   TEXT NOT NULL DEFAULT 'N/A',
  location       TEXT,
  UNIQUE (merchant_city, merchant_state, merchant_zip)
);

DROP TABLE IF EXISTS dw_etl.dim_mcc CASCADE;
CREATE TABLE dw_etl.dim_mcc (
  mcc_key BIGSERIAL PRIMARY KEY,
  mcc_code TEXT UNIQUE,
  description TEXT
);

DROP TABLE IF EXISTS dw_etl.dim_error CASCADE;
CREATE TABLE dw_etl.dim_error (
    error_key BIGSERIAL PRIMARY KEY,
    error_desc TEXT UNIQUE
);

-- Fact Table

DROP TABLE IF EXISTS dw_etl.fact_transactions CASCADE;
CREATE TABLE dw_etl.fact_transactions (
  fact_id BIGSERIAL PRIMARY KEY,
  transaction_id BIGINT UNIQUE,
  date_key INT REFERENCES dw_etl.dim_date(date_key),
  customer_key BIGINT REFERENCES dw_etl.dim_customer(customer_key),
  card_key BIGINT REFERENCES dw_etl.dim_card(card_key),
  merchant_key BIGINT REFERENCES dw_etl.dim_merchant(merchant_key),
  location_key BIGINT REFERENCES dw_etl.dim_location(location_key),   -- NEW
  mcc_key BIGINT REFERENCES dw_etl.dim_mcc(mcc_key),
  amount NUMERIC(18,2),
  use_chip BOOLEAN,
  fraud_label BOOLEAN,
  anomaly_flag BOOLEAN DEFAULT FALSE,
  error_key BIGINT REFERENCES dw_etl.dim_error(error_key)
);
