"""
llm_fallback.py — Multi-model fallback strategy for Gemini calls.

Tries a prioritized list of Gemini models in order. If one is
rate-limited or unavailable (429/503), falls through to the next.
Keeps this logic out of ask_ai.py so the chain-building code stays
clean and this list can be tuned independently.
"""

import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import streamlit as st

from app.config import GOOGLE_API_KEY

# Ordered by preference: fastest/newest first, most reliable fallback last.
MODEL_FALLBACK_ORDER = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

_SLOW_RESPONSE_THRESHOLD_SECONDS = 60


def _build_chain(model_name: str, prompt: PromptTemplate):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.3,
        max_output_tokens=512,
    )
    return prompt | llm | StrOutputParser()


def invoke_with_fallback(prompt: PromptTemplate, inputs: dict, status_placeholder=None) -> str:
    """
    Try each model in MODEL_FALLBACK_ORDER until one succeeds.
    Raises the last exception if every model fails.

    status_placeholder: an optional st.empty() the caller passes in,
    used to show a "still trying" message if this takes a while.
    """
    start_time = time.time()
    last_error = None

    for i, model_name in enumerate(MODEL_FALLBACK_ORDER):
        elapsed = time.time() - start_time
        if status_placeholder and elapsed > _SLOW_RESPONSE_THRESHOLD_SECONDS:
            status_placeholder.info(
                "We're trying to reach the AI model — it's experiencing high demand "
                "right now. Still working on it..."
            )

        try:
            chain = _build_chain(model_name, prompt)
            return chain.invoke(inputs)
        except Exception as e:
            last_error = e
            is_last_model = i == len(MODEL_FALLBACK_ORDER) - 1
            if not is_last_model:
                continue  # try next model
            raise last_error from None

    raise last_error