"""Database connection and session management."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import DATABASE_URL, SQLITE_URL, USE_SQLITE_FALLBACK

Base = declarative_base()

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
_active_url: str | None = None


def _create_engine_with_fallback() -> tuple[Engine, str]:
    """Try PostgreSQL first; fall back to SQLite when configured."""
    global _active_url

    if not USE_SQLITE_FALLBACK:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        _active_url = DATABASE_URL
        return engine, DATABASE_URL

    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _active_url = DATABASE_URL
        return engine, DATABASE_URL
    except Exception:
        engine = create_engine(
            SQLITE_URL,
            connect_args={"check_same_thread": False},
        )
        _active_url = SQLITE_URL
        return engine, SQLITE_URL


def get_engine() -> Engine:
    """Return the shared SQLAlchemy engine."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine, _ = _create_engine_with_fallback()
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_active_database_url() -> str:
    """Return the URL of the database currently in use."""
    get_engine()
    return _active_url or SQLITE_URL


def get_session_factory() -> sessionmaker:
    """Return the session factory bound to the active engine."""
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def execute_sql_file(sql_path: str) -> None:
    """Execute a SQL script file against the active database."""
    from pathlib import Path

    path = Path(sql_path)
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    sql_content = path.read_text(encoding="utf-8")
    engine = get_engine()

    # Split statements for databases that do not support multi-statement execution
    statements = [s.strip() for s in sql_content.split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
