"""Session factory — each call to SessionLocal() returns a new, isolated session."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from db.engine import get_engine


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def SessionLocal() -> Session:
    """Create a new database session. Caller must close it (or use db_session())."""
    return _session_factory()()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
