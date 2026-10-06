"""
queries.py — Named query functions for the dashboard.

Wraps db.run_query() with specific, pre-written SELECTs against
the molap schema. app.py never writes raw SQL — it only calls
these functions.
"""

from app.db import run_query, health_check, DatabaseUnavailableError

# Re-exported so app.py can import everything DB-related from one place
__all__ = [
    "health_check",
    "DatabaseUnavailableError",
    "get_monthly_transactions",
    "get_top_customers",
    "get_fraud_by_state",
    "get_card_brand_performance",
    "get_transactions_by_city",
]


def check_warehouse_health() -> bool:
    """Wraps db.health_check() for the dashboard sidebar indicator."""
    return health_check()


def get_monthly_transactions():
    return run_query("""
        SELECT year, month, total_transactions, total_transaction_amount, fraud_transactions
        FROM molap.molap_monthly_transactions
        ORDER BY year, month
    """)


def get_top_customers():
    return run_query("""
        SELECT customer_id, gender, current_age, total_spent
        FROM molap.molap_top_customers
        ORDER BY total_spent DESC
    """)


def get_fraud_by_state():
    return run_query("""
        SELECT merchant_state, total_transactions, fraud_transactions, fraud_percentage
        FROM molap.molap_fraud_by_state
        ORDER BY fraud_percentage DESC
    """)


def get_card_brand_performance():
    return run_query("""
        SELECT card_brand, total_transactions, total_amount, fraud_transactions, fraud_rate_percentage
        FROM molap.molap_card_brand_performance
        ORDER BY total_transactions DESC
    """)


def get_transactions_by_city():
    return run_query("""
        SELECT merchant_city, num_transactions, avg_transaction_amount, max_transaction_amount, min_transaction_amount
        FROM molap.molap_transactions_by_city
        ORDER BY avg_transaction_amount DESC
    """)