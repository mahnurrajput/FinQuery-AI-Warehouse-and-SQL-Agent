"""
sql_validator.py — Module 2.3: safety checks before any SQL reaches the database.

Fails closed: if a query cannot be parsed or confirmed safe, it is rejected.
The query is parsed with sqlglot (PostgreSQL dialect), so tables, CTEs and LIMIT
are read from the syntax tree instead of from text patterns. The SQL returned on
success is regenerated from that tree, so the query that is checked is the query
that runs.

Checks:
1. Exactly one statement, and it parses as PostgreSQL.
2. Only SELECT (optionally with WITH) or UNION of SELECTs.
3. No write, DDL, admin, or locking clause anywhere in the tree.
4. Only dw_etl and molap tables, always schema-qualified, no catalog prefix.
5. No blocked functions (file access, sleep, process control, sequences, settings).
6. A top-level LIMIT is always present and no higher than MAX_ROWS.

The database role is read-only too (create_readonly_role.sql).
This validator is the first line of defence; the role is the second.
"""

import logging
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

# sqlglot logs a warning when it falls back to a generic command; the validator reports that itself
logging.getLogger("sqlglot").setLevel(logging.ERROR)

MAX_ROWS = 1000
ALLOWED_SCHEMAS = ("dw_etl", "molap")

# Node types that must never appear anywhere in a query
FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Set, exp.Into, exp.Lock,
)

BLOCKED_FUNCTIONS = {
    "pg_sleep", "pg_sleep_for", "pg_sleep_until", "pg_read_file", "pg_read_binary_file",
    "pg_ls_dir", "pg_stat_file", "pg_terminate_backend", "pg_cancel_backend",
    "pg_advisory_lock", "pg_advisory_xact_lock", "pg_notify", "pg_reload_conf",
    "lo_import", "lo_export", "lo_unlink", "dblink", "set_config", "current_setting",
    "nextval", "setval",
}

# Characters and quoting styles the parser is not asked to handle
_DOLLAR_QUOTE = re.compile(r"\$\w*\$")


@dataclass
class ValidationResult:
    ok: bool
    sql: str | None     # the safe query to execute, regenerated from the checked tree
    reason: str | None  # why it was rejected, when ok is False


# Helpers
def _reject(reason: str) -> ValidationResult:
    return ValidationResult(ok=False, sql=None, reason=reason)


def _check_tables(tree: exp.Expression) -> str | None:
    """Every table must be schema-qualified with an allowed schema, or be a CTE of this query."""
    cte_names = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not table.name:
            return "table functions are not allowed in FROM"
        full_name = ".".join(part for part in (table.catalog, table.db, table.name) if part)
        if table.catalog:
            return f"table '{full_name}' is not allowed; no database prefix is allowed"
        if not table.db and table.name.lower() in cte_names:
            continue
        if table.db.lower() not in ALLOWED_SCHEMAS:
            return f"table '{full_name}' is not allowed; use dw_etl.* or molap.* tables"
    return None


def _check_functions(tree: exp.Expression) -> str | None:
    for func in tree.find_all(exp.Func):
        if isinstance(func, exp.Anonymous):
            name = func.name.lower()  # functions sqlglot does not know, e.g. pg_read_file
        else:
            name = func.sql_name().lower()
        if name in BLOCKED_FUNCTIONS:
            return f"blocked function: {name}"
    return None


def _check_limit(tree: exp.Expression) -> tuple[str | None, exp.Expression]:
    """Return (reason, tree). Adds LIMIT MAX_ROWS when the query has none."""
    limit = tree.args.get("limit")

    if limit is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(MAX_ROWS)))
        return None, tree

    if isinstance(limit, exp.Fetch):
        return "use LIMIT instead of FETCH", tree

    if isinstance(limit, exp.Limit):
        value = limit.expression
        if not (isinstance(value, exp.Literal) and value.is_int):
            return "unsupported LIMIT clause", tree
        if int(value.name) > MAX_ROWS:
            return f"LIMIT above the maximum of {MAX_ROWS} rows", tree
        return None, tree

    return "unsupported LIMIT clause", tree


# Public API
def validate_sql(raw_sql: str) -> ValidationResult:
    if not raw_sql or not raw_sql.strip():
        return _reject("empty query")

    if "\\" in raw_sql:
        return _reject("backslashes are not allowed")
    if _DOLLAR_QUOTE.search(raw_sql):
        return _reject("dollar-quoted strings are not allowed")

    # 1. Exactly one statement that parses as PostgreSQL
    try:
        statements = [s for s in sqlglot.parse(raw_sql, read="postgres") if s is not None]
    except Exception:
        return _reject("could not parse the query as PostgreSQL")

    if not statements:
        return _reject("empty query")
    if len(statements) > 1:
        return _reject("multiple statements are not allowed")

    tree = statements[0]

    # 2. Read-only shape
    if not isinstance(tree, (exp.Select, exp.Union)):
        return _reject("only SELECT queries are allowed")

    # 3. No write, DDL, admin or locking nodes anywhere in the tree
    for node in tree.find_all(*FORBIDDEN_NODES):
        return _reject(f"forbidden statement or clause: {type(node).__name__.upper()}")

    # 4. Tables
    reason = _check_tables(tree)
    if reason:
        return _reject(reason)

    # 5. Functions
    reason = _check_functions(tree)
    if reason:
        return _reject(reason)

    # 6. LIMIT
    reason, tree = _check_limit(tree)
    if reason:
        return _reject(reason)

    return ValidationResult(ok=True, sql=tree.sql(dialect="postgres"), reason=None)