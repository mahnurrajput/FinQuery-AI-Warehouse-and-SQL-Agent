"""
llm_fallback.py — Multi-provider fallback strategy for LLM calls.

Tries a prioritized list of (provider, model) entries in order. If one is slow,
rate-limited or unavailable, it falls through to the next. Each attempt logs one
short line; full tracebacks are off unless SHOW_TRACEBACKS is True.
"""

import logging
import sys
import time
import warnings

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

from app.config import GOOGLE_API_KEY, GROQ_API_KEY


# Debug settings
LOG_LEVEL = logging.DEBUG      # logging.INFO hides the per-attempt debug output
SHOW_TRACEBACKS = False        # True prints full tracebacks for failed attempts
MAX_ERROR_CHARS = 200          # long provider error messages are cut to this length


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


# Models
# (provider, model) pairs, tried in this order.
# gemini-2.5-flash is first: it was the fastest reliable model in testing while its quota lasts.
# Groq is second, so it answers when Gemini is slow or over its daily quota.
MODEL_FALLBACK_ORDER = [
    ("gemini", "gemini-2.5-flash"),
    ("groq", "openai/gpt-oss-120b"),
    ("gemini", "gemini-3.5-flash"),
    ("gemini", "gemini-3.5-flash-lite"),
    ("gemini", "gemini-3.1-flash-lite"),
    ("gemini", "gemini-3.8-flash"),
]

# Gemini models that ignore the temperature setting. Passing it only creates library warnings.
_FIXED_SAMPLING_MODELS = {"gemini-3.5-flash-lite"}

_SLOW_RESPONSE_THRESHOLD_SECONDS = 60

# Per-attempt limits. A slow model fails fast so the fallback can move on.
_REQUEST_TIMEOUT_SECONDS = 25
_MAX_OUTPUT_TOKENS = 2048


# Helpers
def _label(provider: str, model_name: str) -> str:
    return f"{provider}:{model_name}"


def _build_llm(provider: str, model_name: str):
    if provider == "gemini":
        sampling = {} if model_name in _FIXED_SAMPLING_MODELS else {"temperature": 0.3}
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=GOOGLE_API_KEY,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,  # no hidden retries: failures reach this code and the fallback
            **sampling,
        )
    if provider == "groq":
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in .env")
        return ChatGroq(
            model=model_name,
            api_key=GROQ_API_KEY,
            temperature=0.3,
            max_tokens=_MAX_OUTPUT_TOKENS,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            max_retries=0,
        )
    raise ValueError(f"unknown provider: {provider}")


def _build_chain(provider: str, model_name: str, prompt: PromptTemplate):
    # No output parser: we need the full message for finish_reason and usage.
    return prompt | _build_llm(provider, model_name)


def _short(text: str) -> str:
    """Collapse whitespace and cut long messages so one log line stays readable."""
    text = " ".join(str(text).split())
    if len(text) > MAX_ERROR_CHARS:
        return text[:MAX_ERROR_CHARS] + "..."
    return text


def _describe(e: BaseException | None) -> str:
    """Exception type and short message, e.g. 'RateLimitError: 429 quota exceeded'."""
    if e is None:
        return "no error recorded"
    return _short(f"{type(e).__name__}: {e}")


def _extract_text(content) -> str:
    """Some providers return a plain string, others a list of content parts. Join the text."""
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "") if isinstance(part, dict) else str(part)
        for part in content
    )


def _log_success(label: str, elapsed: float, message, text_len: int) -> None:
    usage = message.usage_metadata or {}
    details = usage.get("output_token_details") or {}
    finish = message.response_metadata.get("finish_reason")

    logger.info(
        "OK %s in %.2fs | finish=%s | in=%s out=%s reasoning=%s | chars=%d",
        label, elapsed, finish,
        usage.get("input_tokens"), usage.get("output_tokens"),
        details.get("reasoning"), text_len,
    )
    # Gemini reports "STOP", Groq reports "stop". Compare case-insensitively.
    if str(finish).upper() != "STOP":
        logger.warning("%s finish=%s: the answer may be truncated", label, finish)


# Public API
def invoke_with_fallback(prompt: PromptTemplate, inputs: dict, status_placeholder=None) -> str:
    """
    Try each (provider, model) in MODEL_FALLBACK_ORDER until one succeeds.
    Raises the last exception if every model fails.

    status_placeholder: an optional st.empty() the caller passes in,
    used to show a "still trying" message if this takes a while.
    """
    start_time = time.time()
    total = len(MODEL_FALLBACK_ORDER)
    last_error = None

    names = " > ".join(_label(p, m) for p, m in MODEL_FALLBACK_ORDER)
    logger.info("Request started | models: %s", names)

    for attempt, (provider, model_name) in enumerate(MODEL_FALLBACK_ORDER, start=1):
        label = _label(provider, model_name)

        if status_placeholder and time.time() - start_time > _SLOW_RESPONSE_THRESHOLD_SECONDS:
            status_placeholder.info(
                "We're trying to reach the AI model — it's experiencing high demand "
                "right now. Still working on it..."
            )

        logger.info(
            "[%d/%d] Trying %s | timeout=%ss",
            attempt, total, label, _REQUEST_TIMEOUT_SECONDS,
        )
        attempt_start = time.time()
        caught = []  # warnings raised by the library during this attempt

        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                message = _build_chain(provider, model_name, prompt).invoke(inputs)

            text = _extract_text(message.content)
            _log_success(label, time.time() - attempt_start, message, len(text))
            logger.info(
                "Answered by %s on attempt %d/%d in %.2fs total",
                label, attempt, total, time.time() - start_time,
            )
            return text

        except Exception as e:
            last_error = e
            logger.warning(
                "FAIL %s after %.2fs | %s",
                label, time.time() - attempt_start, _describe(e),
            )
            if SHOW_TRACEBACKS:
                logger.debug("Traceback for %s", label, exc_info=True)

        finally:
            # Log library warnings whether the attempt succeeded or failed.
            for w in caught:
                logger.warning(
                    "warning from %s | %s: %s",
                    label, w.category.__name__, _short(w.message),
                )

    logger.error(
        "All %d models failed after %.2fs | last error: %s",
        total, time.time() - start_time, _describe(last_error),
    )
    raise last_error