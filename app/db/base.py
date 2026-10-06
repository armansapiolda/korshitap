"""Database engine and base setup."""

from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Columns that the pre-migration init_db() added with ALTER TABLE. A database
# created by an old version may lack some of them; they are part of the
# 0001_baseline revision, so they are added before stamping it.
_LEGACY_COLUMNS = {
    "users": [
        ("preferred_gender", "VARCHAR(20) DEFAULT 'any'"),
        ("city", "VARCHAR(100) DEFAULT 'Алматы'"),
        ("occupation", "VARCHAR(50) DEFAULT 'student'"),
    ],
    "listings": [
        ("lease_term", "VARCHAR(100)"),
        ("preferred_age_range", "VARCHAR(100)"),
        ("utilities_status", "VARCHAR(50)"),
        ("utilities_amount", "INTEGER"),
        ("neighbor_criteria", "JSON"),
    ],
    "seeker_profiles": [
        ("has_apartment", "BOOLEAN DEFAULT FALSE"),
        ("apartment_address", "VARCHAR(255)"),
        ("rooms_count", "VARCHAR(50)"),
        ("room_type", "VARCHAR(50)"),
        ("neighbors_needed", "INTEGER DEFAULT 1"),
        ("preferred_room_type", "VARCHAR(50) DEFAULT 'any'"),
        ("budget_range", "VARCHAR(100)"),
        ("ideal_neighbor_desc", "TEXT"),
        ("about_self_desc", "TEXT"),
        ("neighbor_criteria", "JSON"),
        ("notifications_enabled", "BOOLEAN DEFAULT TRUE"),
    ],
}

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _upgrade_schema(sync_conn) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect, text

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "migrations"))
    cfg.attributes["connection"] = sync_conn
    cfg.attributes["configure_logger"] = False

    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    if "users" in tables and "alembic_version" not in tables:
        # Database created before migrations existed: bring it to the baseline, then stamp it.
        for table, columns in _LEGACY_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        command.stamp(cfg, "0001_baseline")
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """Create or upgrade the database schema with Alembic migrations (SQLite or Postgres)."""
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade_schema)
