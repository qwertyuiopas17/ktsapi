"""
KTS API — Database Setup
SQLAlchemy engine, session factory, and base model.

Connection priority (ported from Aethel):
  1. DATABASE_URL env var (PostgreSQL in prod)
  2. Fallback: SQLite for local dev

Safety patterns applied from aethel-backend-v3:
  - expire_on_commit=False for detached object safety
  - check_same_thread=False for SQLite + FastAPI threadpool
  - postgres:// → postgresql:// normalization for Render/Heroku
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Render/Heroku hand out "postgres://..." — SQLAlchemy 2.x
# only accepts "postgresql://...". Normalise silently.
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)

_is_sqlite = _db_url.startswith("sqlite")

# Engine kwargs — SQLite needs check_same_thread=False for FastAPI
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": settings.APP_DEBUG}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(_db_url, **_engine_kwargs)

# expire_on_commit=False prevents DetachedInstanceError when
# accessing attributes on objects after db.commit()
# (ported from aethel-backend-v3/database.py)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

