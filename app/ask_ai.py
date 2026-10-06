"""
ask_ai.py — Ask AI tab content.

A single LangChain chain (PromptTemplate + Gemini) that takes a
natural-language question and returns a plain-English response.
Model selection and fallback-on-failure logic lives in
app.llm_fallback; this file only owns the prompt and UI.
"""

import streamlit as st
from langchain_core.prompts import PromptTemplate

from app.llm_fallback import invoke_with_fallback

_PROMPT = PromptTemplate.from_template(
    """You are a financial data analyst assistant for FinQuery, a
banking transactions analytics platform. Answer the user's question
in 2-4 plain-English sentences. If the question requires querying
a database, explain generally what the answer would involve rather
than inventing specific numbers.

Question: {question}

Answer:"""
)


def render():
    """Render the Ask AI tab: a single text box backed by a LangChain + Gemini chain."""
    st.header("Ask AI")
    st.caption(
        "Demonstrates LangChain + Gemini integration. "
        "The full NL-to-SQL agent with self-correction is in development."
    )

    question = st.text_input("Ask a question about the warehouse or financial data:")

    if st.button("Ask") and question:
        status_placeholder = st.empty()
        with st.spinner("Thinking..."):
            try:
                answer = invoke_with_fallback(
                    _PROMPT, {"question": question}, status_placeholder=status_placeholder
                )
                status_placeholder.empty()
                st.write(answer)
            except Exception as e:
                status_placeholder.empty()
                st.error(f"Something went wrong: {e}")