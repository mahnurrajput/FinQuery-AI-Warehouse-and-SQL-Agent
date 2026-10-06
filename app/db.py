"""
db.py — Database engine and query execution layer.

Exposes exactly three public functions: get_engine, run_query,
health_check. No other module should construct a SQLAlchemy
engine or connection directly — app.py and queries.py always
go through these three.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


class DatabaseUnavailableError(Exception):
    """Raised when the database cannot be reached."""
    pass


_engine = None


def get_engine():
    """Lazily create and cache a single SQLAlchemy engine for the app."""
    global _engine
    if _engine is None:
        connection_url = URL.create(
            drivername="postgresql+psycopg2",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=int(DB_PORT),
            database=DB_NAME,
            query={"sslmode": "require"},
        )
        _engine = create_engine(connection_url, pool_pre_ping=True)
    return _engine


def run_query(sql: str, params: dict | None = None):
    """
    Execute a read-only SQL statement and return rows as a list of dicts.
    Raises DatabaseUnavailableError on connection failure.
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    except OperationalError as e:
        raise DatabaseUnavailableError(f"Could not reach database: {e}") from e


def health_check() -> bool:
    """Lightweight connectivity check for the dashboard sidebar."""
    try:
        run_query("SELECT 1")
        return True
    except DatabaseUnavailableError:
        return False