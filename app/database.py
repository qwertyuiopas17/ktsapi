"""
KTS API — Database Setup
SQLAlchemy engine, session factory, and base model.

The schema is owned by Alembic (`alembic upgrade head`); the app never calls
`create_all` at startup.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def normalize_db_url(url: str) -> str:
    # Render/Heroku hand out "postgres://..."; SQLAlchemy 2.x only accepts "postgresql://".
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


_db_url = normalize_db_url(settings.DATABASE_URL)
_is_sqlite = _db_url.startswith("sqlite")

_engine_kwargs: dict = {"pool_pre_ping": True, "echo": settings.DB_ECHO}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(_db_url, **_engine_kwargs)

# expire_on_commit=False prevents DetachedInstanceError after commit
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


def get_db():
    """FastAPI dependency — yields a DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
