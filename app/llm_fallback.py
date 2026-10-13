"""
llm_fallback.py — Multi-model fallback strategy for Gemini calls.

Tries a prioritized list of Gemini models in order. If one is slow,
rate-limited or unavailable, it falls through to the next. Each attempt
logs one short line; full tracebacks are off unless SHOW_TRACEBACKS is True.
"""

import logging
import sys
import time
import warnings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from app.config import GOOGLE_API_KEY

# Debug settings
LOG_LEVEL = logging.DEBUG      # logging.INFO hides the per-attempt debug output
SHOW_TRACEBACKS = False        # True prints full tracebacks for failed attempts
MAX_ERROR_CHARS = 200          # long Google error messages are cut to this length

# Logging: send everything from this module to the terminal
logger = logging.getLogger("finquery.llm")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False  # avoid duplicate lines if root logging is also configured

# Ordered by observed speed and reliability on the free tier in testing.
# gemini-2.5-flash answered in ~3-5s in both test runs. Its SQL quality is not
# yet measured; the evaluation step (Module 4.2) decides whether it stays first.
MODEL_FALLBACK_ORDER = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",        # newest, but slow and over its free-tier daily quota today
]

_SLOW_RESPONSE_THRESHOLD_SECONDS = 60

# Per-attempt limits. A slow model fails fast so the fallback can move on.
_REQUEST_TIMEOUT_SECONDS = 25
_MAX_OUTPUT_TOKENS = 1024


def _build_chain(model_name: str, prompt: PromptTemplate):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=GOOGLE_API_KEY,
        temperature=0.3,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        max_retries=0,  # no hidden retries: failures reach this code and the fallback
    )
    # No StrOutputParser: we need the full message for finish_reason and usage.
    return prompt | llm


def _short(text: str) -> str:
    """Collapse whitespace and cut long messages so one log line stays readable."""
    text = " ".join(str(text).split())
    if len(text) > MAX_ERROR_CHARS:
        return text[:MAX_ERROR_CHARS] + "..."
    return text


def _describe(e: BaseException | None) -> str:
    """Exception type and short message, e.g. 'ResourceExhausted: 429 quota exceeded'."""
    if e is None:
        return "no error recorded"
    return _short(f"{type(e).__name__}: {e}")


def _extract_text(content) -> str:
    """Gemini can return a plain string or a list of content parts. Join the text."""
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "") if isinstance(part, dict) else str(part)
        for part in content
    )


def _log_success(model_name: str, elapsed: float, message, text_len: int) -> None:
    usage = message.usage_metadata or {}
    details = usage.get("output_token_details") or {}
    finish = message.response_metadata.get("finish_reason")

    logger.info(
        "OK %s in %.2fs | finish=%s | in=%s out=%s reasoning=%s | chars=%d",
        model_name, elapsed, finish,
        usage.get("input_tokens"), usage.get("output_tokens"),
        details.get("reasoning"), text_len,
    )
    if finish != "STOP":
        logger.warning("%s finish=%s: the answer may be truncated", model_name, finish)


def invoke_with_fallback(prompt: PromptTemplate, inputs: dict, status_placeholder=None) -> str:
    """
    Try each model in MODEL_FALLBACK_ORDER until one succeeds.
    Raises the last exception if every model fails.

    status_placeholder: an optional st.empty() the caller passes in,
    used to show a "still trying" message if this takes a while.
    """
    start_time = time.time()
    total = len(MODEL_FALLBACK_ORDER)
    last_error = None

    logger.info("Request started | models: %s", " > ".join(MODEL_FALLBACK_ORDER))

    for attempt, model_name in enumerate(MODEL_FALLBACK_ORDER, start=1):
        if status_placeholder and time.time() - start_time > _SLOW_RESPONSE_THRESHOLD_SECONDS:
            status_placeholder.info(
                "We're trying to reach the AI model — it's experiencing high demand "
                "right now. Still working on it..."
            )

        logger.info(
            "[%d/%d] Trying %s | timeout=%ss",
            attempt, total, model_name, _REQUEST_TIMEOUT_SECONDS,
        )
        attempt_start = time.time()
        caught = []  # warnings raised by the library during this attempt

        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                message = _build_chain(model_name, prompt).invoke(inputs)

            text = _extract_text(message.content)
            _log_success(model_name, time.time() - attempt_start, message, len(text))
            logger.info(
                "Answered by %s on attempt %d/%d in %.2fs total",
                model_name, attempt, total, time.time() - start_time,
            )
            return text

        except Exception as e:
            last_error = e
            logger.warning(
                "FAIL %s after %.2fs | %s",
                model_name, time.time() - attempt_start, _describe(e),
            )
            if SHOW_TRACEBACKS:
                logger.debug("Traceback for %s", model_name, exc_info=True)

        finally:
            # Log library warnings whether the attempt succeeded or failed.
            for w in caught:
                logger.warning(
                    "warning from %s | %s: %s",
                    model_name, w.category.__name__, _short(w.message),
                )

    logger.error(
        "All %d models failed after %.2fs | last error: %s",
        total, time.time() - start_time, _describe(last_error),
    )
    raise last_error