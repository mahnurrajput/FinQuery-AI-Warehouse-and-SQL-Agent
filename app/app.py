"""
app.py — Streamlit entrypoint for FinQuery.

Thin orchestration layer only: renders the sidebar health check
and delegates each tab's content to its own module. This file
should never grow chart or chain logic directly.
"""

import streamlit as st
from app.queries import check_warehouse_health
from app import dashboard, ask_ai

st.set_page_config(page_title="FinQuery", layout="wide")

# --- Sidebar: warehouse connectivity status ---
with st.sidebar:
    st.title("FinQuery")
    if check_warehouse_health():
        st.success("Warehouse: Connected")
    else:
        st.error("Warehouse: Unavailable")

# --- Main tabs ---
tab_dashboard, tab_ask_ai = st.tabs(["Dashboard", "Ask AI"])

with tab_dashboard:
    dashboard.render()

with tab_ask_ai:
    ask_ai.render()