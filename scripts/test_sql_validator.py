"""
test_sql_validator.py — Offline tests for the SQL validator. No model calls.

Run from the project root:
    python -m scripts.test_sql_validator
"""

from app.sql_validator import validate_sql

CASES = [
    # (description, sql, should_pass)

    # Real queries produced by the generator
    ("generator: total count",
     "SELECT COUNT(*) AS total_transactions FROM dw_etl.fact_transactions;", True),
    ("generator: top 5 in Houston",
     """SELECT f.transaction_id, f.amount, d.full_date
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
WHERE d.year = 2019 AND d.month = 7
  AND loc.merchant_city = 'Houston'
ORDER BY f.amount DESC
LIMIT 5;""", True),
    ("generator: insufficient balance",
     """SELECT COUNT(*) AS insufficient_balance_transactions
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_error e ON f.error_key = e.error_key
WHERE e.error_desc LIKE '%Insufficient Balance%';""", True),
    ("generator: card brand from molap",
     """SELECT card_brand, fraud_rate_percentage
FROM molap.molap_card_brand_performance
ORDER BY fraud_rate_percentage DESC
LIMIT 1;""", True),
    ("generator: merchant transactions",
     """SELECT f.transaction_id, f.amount, d.full_date, loc.merchant_city
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_merchant m ON f.merchant_key = m.merchant_key
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
WHERE m.merchant_id = '59935'
ORDER BY d.full_date
LIMIT 100;""", True),
    ("generator: grocery total",
     """SELECT ROUND(SUM(f.amount), 2) AS total_grocery_spending
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_mcc mc ON f.mcc_key = mc.mcc_key
WHERE mc.description ILIKE '%grocery%';""", True),

    # Should pass
    ("EXTRACT with FROM inside is allowed",
     "SELECT EXTRACT(YEAR FROM d.full_date) AS y, COUNT(*) FROM dw_etl.dim_date d GROUP BY y LIMIT 10;", True),
    ("keyword inside a string literal is allowed",
     "SELECT COUNT(*) FROM dw_etl.dim_error WHERE error_desc = 'DROP TABLE users';", True),
    ("no LIMIT: one is added",
     "SELECT COUNT(*) FROM dw_etl.fact_transactions", True),
    ("WITH query on schema tables",
     "WITH t AS (SELECT amount FROM dw_etl.fact_transactions) SELECT SUM(amount) FROM t LIMIT 10;", True),
    ("UNION of two schema tables",
     "SELECT year FROM dw_etl.dim_date UNION SELECT year FROM molap.molap_monthly_transactions", True),
    ("subquery with its own LIMIT, outer query gets one",
     "SELECT * FROM dw_etl.fact_transactions WHERE transaction_id IN (SELECT transaction_id FROM dw_etl.fact_transactions LIMIT 5)", True),

    # Should fail: writes and statement types
    ("DROP table",
     "DROP TABLE dw_etl.fact_transactions;", False),
    ("DELETE rows",
     "DELETE FROM dw_etl.fact_transactions;", False),
    ("UPDATE rows",
     "UPDATE dw_etl.fact_transactions SET amount = 0;", False),
    ("write inside a CTE",
     "WITH d AS (DELETE FROM dw_etl.fact_transactions RETURNING *) SELECT * FROM d LIMIT 1;", False),
    ("SELECT INTO creates a table",
     "SELECT * INTO dw_etl.copy_table FROM dw_etl.dim_date LIMIT 1;", False),
    ("locking read",
     "SELECT * FROM dw_etl.dim_date LIMIT 1 FOR UPDATE;", False),
    ("SET statement",
     "SET search_path = staging;", False),
    ("multiple statements",
     "SELECT 1 FROM dw_etl.dim_date LIMIT 1; DROP TABLE dw_etl.dim_date;", False),
    ("write hidden after a comment still checked",
     "SELECT COUNT(*) FROM dw_etl.fact_transactions; -- harmless\nDELETE FROM dw_etl.fact_transactions;", False),
    ("EXPLAIN is not a SELECT",
     "EXPLAIN SELECT * FROM dw_etl.fact_transactions;", False),

    # Should fail: table access
    ("staging table not allowed",
     "SELECT * FROM staging.stg_transactions LIMIT 10;", False),
    ("etl table not allowed",
     "SELECT * FROM etl.transactions_clean LIMIT 10;", False),
    ("unqualified table name",
     "SELECT * FROM fact_transactions LIMIT 10;", False),
    ("system catalog not allowed",
     "SELECT * FROM pg_catalog.pg_tables LIMIT 10;", False),
    ("comma join to a forbidden schema",
     "SELECT COUNT(*) FROM dw_etl.fact_transactions f, staging.stg_transactions s LIMIT 10;", False),
    ("quoted forbidden schema",
     'SELECT * FROM "staging"."stg_transactions" LIMIT 10;', False),
    ("forbidden table inside a subquery's comma join",
     "SELECT * FROM (SELECT 1 FROM dw_etl.dim_date, etl.users_clean LIMIT 1) t LIMIT 5;", False),
    ("database-qualified name",
     "SELECT * FROM otherdb.dw_etl.dim_date LIMIT 5;", False),
    ("table function in FROM",
     "SELECT * FROM generate_series(1, 10) LIMIT 5;", False),

    # Should fail: functions
    ("file read function blocked",
     "SELECT pg_read_file('/etc/passwd') LIMIT 1;", False),
    ("sleep function blocked",
     "SELECT pg_sleep(100) FROM dw_etl.dim_date LIMIT 1;", False),
    ("sequence write blocked",
     "SELECT nextval('dw_etl.fact_transactions_fact_id_seq') LIMIT 1;", False),

    # Should fail: LIMIT and input
    ("LIMIT above maximum",
     "SELECT * FROM dw_etl.fact_transactions LIMIT 50000;", False),
    ("LIMIT ALL",
     "SELECT * FROM dw_etl.dim_date LIMIT ALL;", False),
    ("FETCH instead of LIMIT",
     "SELECT * FROM dw_etl.dim_date FETCH FIRST 5 ROWS ONLY;", False),
    ("backslash escape string",
     "SELECT E'\\'' FROM dw_etl.dim_date LIMIT 1;", False),
    ("dollar-quoted string",
     "SELECT $$ x $$ FROM dw_etl.dim_date LIMIT 1;", False),
    ("empty query",
     "   ", False),
]


# Runner
def main() -> None:
    failures = 0
    for description, sql, should_pass in CASES:
        result = validate_sql(sql)
        passed = result.ok == should_pass
        if not passed:
            failures += 1
        status = "PASS" if passed else "FAIL"
        detail = "accepted" if result.ok else f"rejected: {result.reason}"
        print(f"[{status}] {description} -> {detail}")

    print()
    print(f"{len(CASES) - failures}/{len(CASES)} passed")


if __name__ == "__main__":
    main()