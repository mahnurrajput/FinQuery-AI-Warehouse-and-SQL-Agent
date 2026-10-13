"""
sql_generator.py — Module 2.2: natural language question -> PostgreSQL query.

Builds a prompt from the schema context, the rules and the few-shot examples,
calls the model through the fallback logic, and returns the SQL, a
CANNOT_ANSWER reason, or an error when every model failed. Does not execute
anything. Execution happens after the validator (Module 2.3) and executor (Module 2.4).
"""

import re
from dataclasses import dataclass

from langchain_core.prompts import PromptTemplate

from app.llm_fallback import invoke_with_fallback
from app.schema_context import SCHEMA_CONTEXT, RULES, format_examples

# Prefix the model uses when it cannot answer
_CANNOT_PREFIX = "CANNOT_ANSWER:"

# Maximum characters of an error message kept in the result
_MAX_ERROR_CHARS = 300

# Prompt
_PROMPT = PromptTemplate.from_template(
    """You write PostgreSQL queries for the FinQuery data warehouse.

{schema}

{rules}

Examples:

{examples}

{error_context}Question: {question}
SQL:"""
)


# Result type
@dataclass
class SQLResult:
    sql: str | None            # the query, when the model could write one
    cannot_answer: str | None  # the reason, when the model said it cannot answer
    raw: str                   # the model's unedited output, for debugging
    error: str | None = None   # set when every model call failed (no output at all)


# Helpers
def _clean(raw: str) -> str:
    """Remove markdown code fences and surrounding whitespace."""
    text = raw.strip()
    text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _short_error(exc: Exception) -> str:
    """Return the exception type and a shortened message."""
    message = str(exc).strip().replace("\n", " ")
    if len(message) > _MAX_ERROR_CHARS:
        message = message[:_MAX_ERROR_CHARS] + "..."
    return f"{type(exc).__name__}: {message}"


# Public API
def generate_sql(
    question: str,
    previous_sql: str | None = None,
    error: str | None = None,
    status_placeholder=None,
) -> SQLResult:
    """
    Turn a question into SQL.

    previous_sql and error are used by the retry loop (Module 2.5): when a query
    fails, pass it back with the database error so the model can correct it.

    If every model in the fallback list fails, the result has error set and
    sql / cannot_answer are None. The caller decides what to do with that.
    """
    error_context = ""
    if previous_sql and error:
        error_context = (
            "Your previous query failed.\n"
            f"Previous SQL:\n{previous_sql}\n"
            f"Database error: {error}\n"
            "Write a corrected query.\n\n"
        )

    try:
        raw = invoke_with_fallback(
            _PROMPT,
            {
                "schema": SCHEMA_CONTEXT,
                "rules": RULES,
                "examples": format_examples(),
                "error_context": error_context,
                "question": question,
            },
            status_placeholder=status_placeholder,
        )
    except Exception as exc:
        # invoke_with_fallback already logged each failed attempt.
        # Return the failure instead of crashing the caller.
        return SQLResult(
            sql=None,
            cannot_answer=None,
            raw="",
            error=_short_error(exc),
        )

    text = _clean(raw)
    if text.upper().startswith(_CANNOT_PREFIX):
        reason = text[len(_CANNOT_PREFIX):].strip()
        return SQLResult(sql=None, cannot_answer=reason, raw=raw)

    return SQLResult(sql=text, cannot_answer=None, raw=raw)