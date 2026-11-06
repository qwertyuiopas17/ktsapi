from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.database import Base, engine


def test_migrations_match_models():
    """Alembic is the only source of the schema, so it must match the models."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], diff
