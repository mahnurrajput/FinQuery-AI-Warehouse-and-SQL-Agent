"""
app.py — Streamlit entrypoint for FinQuery.

Thin orchestration layer only: renders the sidebar health check
and the two main tabs. All data access goes through app.queries;
this file never imports app.db directly.
"""

import streamlit as st
from app.queries import check_warehouse_health

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
    st.header("Analytics Dashboard")
    st.info("Charts will be added here next.")

with tab_ask_ai:
    st.header("Ask AI")
    st.info("LangChain + Gemini chain will be added here next.")