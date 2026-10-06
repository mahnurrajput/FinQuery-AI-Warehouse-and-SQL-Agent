"""
dashboard.py — Dashboard tab content.

Owns all chart rendering for the Dashboard tab. Pulls data via
app.queries only; app.app.py never touches chart logic directly —
it just calls render().
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from app.queries import (
    get_monthly_transactions,
    get_top_customers,
    get_fraud_by_state,
    get_card_brand_performance,
    get_transactions_by_city,
)


def render():
    """Render the full Dashboard tab: 5 charts from MOLAP tables."""
    st.header("Analytics Dashboard")

    # --- Chart 1: Monthly transaction trend ---
    monthly = pd.DataFrame(get_monthly_transactions())
    monthly["period"] = monthly["year"].astype(str) + "-" + monthly["month"].astype(str).str.zfill(2)
    fig1 = px.line(
        monthly, x="period", y="total_transaction_amount",
        title="Monthly Transaction Amount", markers=True
    )
    st.plotly_chart(fig1, width='stretch')

    col1, col2 = st.columns(2)

    with col1:
        # --- Chart 2: Top customers ---
        top_customers = pd.DataFrame(get_top_customers())
        fig2 = px.bar(
            top_customers, x="customer_id", y="total_spent",
            title="Top 10 Customers by Spending"
        )
        st.plotly_chart(fig2, width='stretch')

        # --- Chart 3: Fraud by state ---
        fraud_state = pd.DataFrame(get_fraud_by_state())
        fig3 = px.bar(
            fraud_state.head(15), x="merchant_state", y="fraud_percentage",
            title="Fraud Percentage by State (Top 15)"
        )
        st.plotly_chart(fig3, width='stretch')

    with col2:
        # --- Chart 4: Card brand performance ---
        card_brand = pd.DataFrame(get_card_brand_performance())
        fig4 = px.bar(
            card_brand, x="card_brand", y="total_transactions",
            title="Transactions by Card Brand"
        )
        st.plotly_chart(fig4, width='stretch')

        # --- Chart 5: Avg transaction by city ---
        city = pd.DataFrame(get_transactions_by_city())
        fig5 = px.bar(
            city, x="merchant_city", y="avg_transaction_amount",
            title="Top 10 Cities by Avg Transaction Amount"
        )
        st.plotly_chart(fig5, width='stretch')