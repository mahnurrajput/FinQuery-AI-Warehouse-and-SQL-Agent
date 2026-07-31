-- ============================================================================
-- SCHEMA JUSTIFICATION
-- Banking Transactions Data Warehouse (dw_etl)
-- ============================================================================
-- Purpose: This file documents the dimensional modeling decisions behind
-- dw_etl, inline with the schema itself. It is a companion to schema.sql /
-- etl.sql, not a replacement — see WAREHOUSE_REDESIGN_NOTES.md for the full
-- narrative (issues found, data verified, alternatives considered).
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. GRAIN DECLARATION
-- ----------------------------------------------------------------------------
-- Fact grain: one row per transaction (fact_transactions.transaction_id).
-- This is the lowest available grain in the source data — no pre-aggregation
-- at the fact level. All MOLAP summary tables are derived FROM this grain,
-- never the reverse.


-- ----------------------------------------------------------------------------
-- 2. DIMENSION DESIGN DECISIONS
-- ----------------------------------------------------------------------------

-- dim_date
--   Natural key: full_date. Surrogate: date_key (INT, YYYYMMDD format).
--   Justification: Smart key chosen over BIGSERIAL so date_key is human-
--   readable and independently derivable (TO_CHAR(d,'YYYYMMDD')) without a
--   dimension lookup — a standard Kimball convention for date dimensions.
--   Populated via generate_series() to guarantee a DENSE calendar (no gaps
--   on days with zero transactions), padded +1 year past MAX(transaction_date)
--   to absorb future-dated data without FK violations.
--   Fallback: date_key = 19000101 for any transaction with an unparseable
--   or missing date.

-- dim_customer, dim_card, dim_mcc, dim_error
--   Natural key: customer_id / card_id / mcc_code / error_desc respectively.
--   Verified 1:1 against staging via GROUP BY ... HAVING COUNT(*) > 1
--   (zero rows returned for all four — see WAREHOUSE_REDESIGN_NOTES.md).
--   Standard BIGSERIAL surrogate keys. No further grain concerns.

-- dim_merchant  *** REDESIGNED ***
--   Natural key: merchant_id ONLY.
--   Originally this dimension also carried merchant_city/state/zip, deduped
--   with DISTINCT ON (merchant_id) ORDER BY merchant_id, merchant_city.
--   This was WRONG: empirical testing showed merchant_id is a chain/brand
--   identifier, not a physical-location identifier — 21.6% of merchant_ids
--   (16,164 of 74,831) span more than one city, some spanning 1,000+ distinct
--   cities. The old design silently collapsed every transaction for a given
--   merchant_id onto whichever city sorted alphabetically first, corrupting
--   any city/state-level aggregation for those merchants.
--   Fix: dim_merchant was stripped back to a pure identity dimension
--   (merchant_id only). Location was extracted into its own dimension
--   (see dim_location below) rather than folded into a composite
--   (merchant_id, city, state, zip) key — see dim_location justification
--   for why the two-dimension split was chosen over a composite key.

-- dim_location  *** NEW ***
--   Natural key: (merchant_city, merchant_state, merchant_zip).
--   Introduced to correctly model the merchant/location relationship, which
--   is many-to-many at the city level (a merchant_id operates in many
--   locations; a given location is shared by many merchant_ids — confirmed
--   empirically: 91,000+ merchant-location pairs collapse to only 25,425
--   truly unique locations, i.e. each location is reused by ~3.6 merchants
--   on average).
--   Design choice — separate dimension vs. composite key on dim_merchant:
--     A composite (merchant_id, city, state, zip) key on a single table
--     would have repeated city/state/zip text once per merchant at that
--     location (~91K rows' worth of repeated text). A conformed dim_location,
--     deduped globally, stores each unique location exactly once (25,425
--     rows) and is reusable by any future fact table needing location
--     context — the standard Kimball answer once repeat/reuse is confirmed
--     empirically rather than assumed.
--   Special values (not raw NULL, to keep every join deterministic):
--     - city = 'Online', state/zip = 'N/A'   -> genuine card-not-present
--       transactions (1,563,700 rows) with no physical location at all.
--     - city = real city, state = country name, zip = 'N/A' -> legitimate
--       international in-person transactions (~89,000 rows) that simply
--       have no US-style zip code. NOT a data quality gap.
--   These two categories were verified distinct via source-data breakdown
--   before choosing a sentinel value, specifically to avoid conflating
--   "no data" with "not applicable by design" (see notes doc).

-- ----------------------------------------------------------------------------
-- 3. FALLBACK / "UNKNOWN" ROWS — APPLIED UNIFORMLY
-- ----------------------------------------------------------------------------
-- Every dimension (except dim_date, which uses 19000101) has an explicit
-- surrogate key = -1, natural key = 'N/A' fallback row, inserted before the
-- real data load. The fact table load COALESCEs every FK to this fallback
-- instead of allowing a raw NULL, so:
--   - No fact row can silently vanish from an INNER JOIN aggregation.
--   - Every dimension attribute on the fact table has a guaranteed,
--     queryable value.
--   - "Unmatched during ETL" (-1 / 'N/A') is explicitly distinguishable from
--     both a genuine dimension value and from dim_location's 'Online' /
--     international sentinels, which represent known-and-modeled states,
--     not ETL failures.
-- Sentinel vocabulary is standardized to 'N/A' warehouse-wide (not 'UNKNOWN'
--     in some places and 'N/A' in others) for consistent downstream filtering.


-- ----------------------------------------------------------------------------
-- 4. SECURITY / COMPLIANCE
-- ----------------------------------------------------------------------------
-- cvv is dropped at the staging boundary and never enters etl or dw_etl.
-- card_number is masked to XXXX-XXXX-XXXX-1234 format before dw_etl load.


-- ----------------------------------------------------------------------------
-- 5. KEY REFERENCE TABLE
-- ----------------------------------------------------------------------------
-- Dimension     | Natural Key                              | Surrogate PK   | Fallback
-- --------------|-------------------------------------------|----------------|----------
-- dim_date      | full_date                                 | date_key (INT) | 19000101
-- dim_customer  | customer_id                                | customer_key   | -1 / 'N/A'
-- dim_card      | card_id                                    | card_key       | -1 / 'N/A'
-- dim_merchant  | merchant_id                                | merchant_key   | -1 / 'N/A'
-- dim_location  | (merchant_city, merchant_state, merchant_zip) | location_key | -1 / 'N/A'
-- dim_mcc       | mcc_code                                   | mcc_key        | -1 / 'N/A'
-- dim_error     | error_desc                                 | error_key      | -1 / 'N/A'
-- fact_transactions | transaction_id                         | fact_id        | n/a


-- ----------------------------------------------------------------------------
-- 6. KNOWN SCOPE LIMITATIONS (deliberate, not oversights)
-- ----------------------------------------------------------------------------
-- - anomaly_flag is hardcoded FALSE at load time — reserved for a future
--   anomaly-detection pass, not currently populated by any model.
-- - use_chip is NULL for transaction rows where the source string matched
--   neither '%CHIP%' nor '%SWIPE%' (e.g. genuine online transactions) —
--   an intentional three-state modeling choice (chip / swipe / not
--   applicable), not a data defect.
-- - Indexing and partitioning strategy is intentionally out of scope for
--   this file — tracked separately as its own deliverable against dw_etl.
