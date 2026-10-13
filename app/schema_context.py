"""
schema_context.py — Schema description and few-shot examples for the
NL-to-SQL agent (Layer 2, Module 2.1).

The SQL generator (Module 2.2) puts SCHEMA_CONTEXT and the examples into its
prompt so the model writes SQL against the real warehouse, not guessed names.
Keep this file in sync with SQL/01_schema/schema.sql and SQL/03_molap/molap_tables.sql.
"""

SCHEMA_CONTEXT = """
DATABASE: PostgreSQL. Two schemas are queryable: dw_etl (star schema) and molap (precomputed summaries).
Always use fully qualified names, for example dw_etl.fact_transactions.
Data covers calendar years 2010 to 2019 only.

=== dw_etl.fact_transactions (fact table, one row per transaction) ===
  fact_id        BIGINT    primary key
  transaction_id BIGINT    original transaction id from the source data
  date_key       INT       FK -> dim_date.date_key
  customer_key   BIGINT    FK -> dim_customer.customer_key
  card_key       BIGINT    FK -> dim_card.card_key
  merchant_key   BIGINT    FK -> dim_merchant.merchant_key
  location_key   BIGINT    FK -> dim_location.location_key
  mcc_key        BIGINT    FK -> dim_mcc.mcc_key
  error_key      BIGINT    FK -> dim_error.error_key
  amount         NUMERIC(18,2)  transaction amount
  use_chip       BOOLEAN   TRUE if the transaction used a chip
  fraud_label    BOOLEAN   TRUE if the transaction is fraudulent
  anomaly_flag   BOOLEAN   always FALSE (not implemented yet). Do not use it.

=== dw_etl.dim_date (one row per calendar day) ===
  date_key     INT      YYYYMMDD integer, the join key from the fact table
  full_date    DATE
  year         INT
  quarter      INT
  month        INT      1 to 12
  month_name   VARCHAR  e.g. 'July'
  day_of_month INT
  day_of_week  INT      ISO: 1 = Monday ... 7 = Sunday
  day_name     VARCHAR
  is_weekend   BOOLEAN

=== dw_etl.dim_customer (one row per customer) ===
  customer_key      BIGINT   primary key
  customer_id       TEXT     natural key
  current_age       INT
  birth_year        INT
  birth_month       INT
  gender            TEXT
  address           TEXT
  latitude          NUMERIC
  longitude         NUMERIC
  per_capita_income NUMERIC
  yearly_income     NUMERIC
  total_debt        NUMERIC
  credit_score      INT
  num_credit_cards  INT

=== dw_etl.dim_card (one row per card) ===
  card_key              BIGINT   primary key
  card_id               TEXT     natural key
  client_id             TEXT
  card_brand            TEXT     values: 'Visa', 'Mastercard', 'Amex', 'Discover', 'N/A'
  card_type             TEXT     values: 'Debit', 'Credit', 'Debit (Prepaid)', 'N/A'
  card_number_masked    TEXT     masked number. Never query raw card numbers.
  has_chip              BOOLEAN
  credit_limit          NUMERIC
  acct_open_date        DATE
  expires               DATE
  num_cards_issued      INT
  year_pin_last_changed INT
  card_on_dark_web      BOOLEAN

=== dw_etl.dim_merchant (one row per merchant_id) ===
  merchant_key  BIGINT   primary key
  merchant_id   TEXT     merchant identifier. This is a brand/chain id, NOT a location.
                         One merchant_id can appear in many cities.

=== dw_etl.dim_location (one row per distinct city/state/zip) ===
  location_key   BIGINT   primary key
  merchant_city  TEXT     title case, e.g. 'Houston', 'Miami', 'New York', 'Dallas', 'Los Angeles'
  merchant_state TEXT     upper case state code. Outside the US this can hold a country name.
  merchant_zip   TEXT     zip code, or 'N/A' when none applies
  location       TEXT     display string, e.g. 'Houston, TX' or 'Online / No Physical Location'
  Use merchant_city, merchant_state and merchant_zip for location filters.
  Do not filter on the location column.

=== dw_etl.dim_mcc (merchant category codes) ===
  mcc_key      BIGINT   primary key
  mcc_code     TEXT     e.g. '5411'
  description  TEXT     e.g. 'Grocery Stores, Supermarkets'

=== dw_etl.dim_error (transaction error types) ===
  error_key   BIGINT   primary key
  error_desc  TEXT     one error label, or several labels joined by commas,
                       e.g. 'Bad Pin' or 'Bad Pin,Insufficient Balance'
  Special values:
    'NO_ERROR'  the transaction had no error
    'N/A'       the unknown-member row (error_key -1)
  Labels include: 'Bad Card Number', 'Bad Expiration', 'Bad Cvv', 'Bad Pin',
  'Bad Zipcode', 'Insufficient Balance', 'Technical Glitch'.
  To match one error type, use LIKE, for example error_desc LIKE '%Insufficient Balance%'.
  Do not use = for one error type, because combined labels exist.

=== Unknown member rows ===
Every dimension has a fallback row with key -1 and 'N/A' values. Facts with unmatched
dimensions point at -1. Do not filter on these keys unless the question asks for unknown values.

=== molap schema (precomputed summary tables, prefer these for overall KPIs) ===
  molap.molap_monthly_transactions     (year, month, total_transactions, total_transaction_amount, fraud_transactions)
  molap.molap_top_customers            (customer_id, gender, current_age, total_spent)  -- top 10 only
  molap.molap_fraud_by_state           (merchant_state, total_transactions, fraud_transactions, fraud_percentage)
  molap.molap_card_brand_performance   (card_brand, total_transactions, total_amount, fraud_transactions, fraud_rate_percentage)
  molap.molap_transactions_by_city     (merchant_city, num_transactions, avg_transaction_amount,
                                        max_transaction_amount, min_transaction_amount)  -- top 10 only

=== Join paths ===
  fact -> date:      fact_transactions f JOIN dim_date d ON f.date_key = d.date_key
  fact -> city:      fact_transactions f JOIN dim_location l ON f.location_key = l.location_key
  fact -> merchant:  fact_transactions f JOIN dim_merchant m ON f.merchant_key = m.merchant_key
  fact -> card:      fact_transactions f JOIN dim_card c ON f.card_key = c.card_key
  fact -> customer:  fact_transactions f JOIN dim_customer cu ON f.customer_key = cu.customer_key
  fact -> mcc:       fact_transactions f JOIN dim_mcc mc ON f.mcc_key = mc.mcc_key
  fact -> error:     fact_transactions f JOIN dim_error e ON f.error_key = e.error_key
"""

RULES = """
RULES FOR SQL GENERATION
1. Output a single SELECT statement only. No INSERT, UPDATE, DELETE, DROP, ALTER or other writes.
2. Use only tables and columns listed above. Never invent a table or column name.
3. Use fully qualified names: dw_etl.fact_transactions, molap.molap_monthly_transactions.
4. Filter years and months through dim_date (d.year, d.month), not by parsing dates.
5. Filter cities through dim_location.merchant_city, using title case, e.g. 'Houston'.
6. Use merchant_id for merchant questions. Never treat merchant_id as a city or location.
7. For error types, use LIKE because one error_desc can hold several labels.
8. For overall totals or monthly trends, prefer the molap tables when they answer the question.
9. Always include LIMIT for queries that return many rows (default LIMIT 100).
10. If the question asks for data outside 2010-2019, or needs a column that is not listed,
    do not guess. Reply with exactly one line: CANNOT_ANSWER: <short reason>
11. Output only the SQL, with no explanation and no markdown fences.
12. Do not return card_brand 'N/A' or error_desc 'N/A' in rankings or totals unless the question asks about unknown values.
"""

FEW_SHOT_EXAMPLES = [
    {
        "question": "What is the total number of transactions?",
        "sql": "SELECT COUNT(*) AS total_transactions FROM dw_etl.fact_transactions;",
    },
    {
        "question": "Show monthly total transaction amount and fraud count.",
        "sql": """SELECT d.year, d.month,
       COUNT(f.fact_id) AS total_transactions,
       ROUND(SUM(f.amount), 2) AS total_transaction_amount,
       COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) AS fraud_transactions
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
GROUP BY d.year, d.month
ORDER BY d.year, d.month;""",
    },
    {
        "question": "Who are the top 10 customers by total spending?",
        "sql": """SELECT c.customer_id, c.gender, c.current_age,
       ROUND(SUM(f.amount), 2) AS total_spent
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_customer c ON f.customer_key = c.customer_key
GROUP BY c.customer_id, c.gender, c.current_age
ORDER BY total_spent DESC
LIMIT 10;""",
    },
    {
        "question": "What percentage of transactions are fraudulent in each state?",
        "sql": """SELECT loc.merchant_state,
       COUNT(f.fact_id) AS total_transactions,
       COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) AS fraud_transactions,
       ROUND(COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) * 100.0
             / NULLIF(COUNT(f.fact_id), 0), 2) AS fraud_percentage
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
GROUP BY loc.merchant_state
ORDER BY fraud_percentage DESC;""",
    },
    {
        "question": "Compare card brands by number of transactions and fraud rate.",
        "sql": """SELECT cd.card_brand,
       COUNT(f.fact_id) AS total_transactions,
       ROUND(SUM(f.amount), 2) AS total_amount,
       ROUND(COUNT(f.fact_id) FILTER (WHERE f.fraud_label = TRUE) * 100.0
             / NULLIF(COUNT(f.fact_id), 0), 2) AS fraud_rate_percentage
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_card cd ON f.card_key = cd.card_key
GROUP BY cd.card_brand
ORDER BY total_transactions DESC;""",
    },
    {
        "question": "What is the average transaction amount per city? Show the top 10.",
        "sql": """SELECT loc.merchant_city,
       COUNT(f.fact_id) AS num_transactions,
       ROUND(AVG(f.amount), 2) AS avg_transaction_amount
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
GROUP BY loc.merchant_city
ORDER BY avg_transaction_amount DESC
LIMIT 10;""",
    },
    {
        "question": "What are the 5 highest transactions in July 2019 in Houston?",
        "sql": """SELECT f.transaction_id, f.amount, d.full_date
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
WHERE d.year = 2019 AND d.month = 7
  AND loc.merchant_city = 'Houston'
ORDER BY f.amount DESC
LIMIT 5;""",
    },
    {
        "question": "How many fraud transactions happened in 2018?",
        "sql": """SELECT COUNT(*) AS fraud_transactions
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
WHERE d.year = 2018 AND f.fraud_label = TRUE;""",
    },
    {
        "question": "How many transactions had an insufficient balance error?",
        "sql": """SELECT COUNT(*) AS insufficient_balance_transactions
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_error e ON f.error_key = e.error_key
WHERE e.error_desc LIKE '%Insufficient Balance%';""",
    },
    {
        "question": "Show the transactions for merchant 59935.",
        "sql": """SELECT f.transaction_id, f.amount, d.full_date, loc.merchant_city
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_merchant m ON f.merchant_key = m.merchant_key
JOIN dw_etl.dim_date d ON f.date_key = d.date_key
JOIN dw_etl.dim_location loc ON f.location_key = loc.location_key
WHERE m.merchant_id = '59935'
ORDER BY d.full_date
LIMIT 100;""",
    },
    {
        "question": "Total spending in grocery stores.",
        "sql": """SELECT ROUND(SUM(f.amount), 2) AS total_grocery_spending
FROM dw_etl.fact_transactions f
JOIN dw_etl.dim_mcc mc ON f.mcc_key = mc.mcc_key
WHERE mc.description ILIKE '%grocer%';""",
    },
    {
        "question": "How many transactions happened in July 2024?",
        "sql": "CANNOT_ANSWER: the warehouse only covers calendar years 2010 to 2019.",
    },
]


def format_examples() -> str:
    """Render the few-shot examples as text for the generator prompt."""
    blocks = []
    for ex in FEW_SHOT_EXAMPLES:
        blocks.append(f"Question: {ex['question']}\nSQL:\n{ex['sql']}")
    return "\n\n".join(blocks)