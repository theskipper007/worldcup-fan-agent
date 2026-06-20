"""Database engine, session factory, and schema initialisation.

The canonical schema is schema.sql (see ../../docs/data-model.md); ``init_db`` executes it so the
SQL file stays the single source of truth. The ORM models in models.py map onto those same tables
for reads/writes.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def make_engine(settings: Settings | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the configured SQLite database."""
    settings = settings or get_settings()
    return create_engine(f"sqlite:///{settings.db_path}", echo=echo, future=True)


def init_db(engine: Engine) -> None:
    """Create tables from schema.sql (idempotent — uses CREATE TABLE IF NOT EXISTS)."""
    raw = engine.raw_connection()
    try:
        raw.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        raw.commit()
    finally:
        raw.close()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]):
    """Transactional scope: commit on success, roll back on error, always close."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
