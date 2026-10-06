"""
ask_ai.py — Ask AI tab content.

A single LangChain chain (PromptTemplate + Gemini) that takes a
natural-language question and returns a plain-English response.
This is NOT the full NL-to-SQL agent — no SQL generation, no
query execution. It demonstrates LangChain + Gemini integration
as a standalone chain; the full agent (SQL generation, validation,
self-correction loop) is a separate, later module.
"""

import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.config import GOOGLE_API_KEY

_PROMPT = PromptTemplate.from_template(
    """You are a financial data analyst assistant for FinQuery, a
banking transactions analytics platform. Answer the user's question
in 2-4 plain-English sentences. If the question requires querying
a database, explain generally what the answer would involve rather
than inventing specific numbers.

Question: {question}

Answer:"""
)


def _get_chain():
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.8-flash",
        google_api_key=GOOGLE_API_KEY,
        temperature=0.3,
    )
    return _PROMPT | llm | StrOutputParser()


def render():
    """Render the Ask AI tab: a single text box backed by a LangChain + Gemini chain."""
    st.header("Ask AI")
    st.caption(
        "Demonstrates LangChain + Gemini integration. "
        "The full NL-to-SQL agent with self-correction is in development."
    )

    question = st.text_input("Ask a question about the warehouse or financial data:")

    if st.button("Ask") and question:
        with st.spinner("Thinking..."):
            try:
                chain = _get_chain()
                answer = chain.invoke({"question": question})
                st.write(answer)
            except Exception as e:
                st.error(f"Something went wrong: {e}")