"""Database engine and base setup."""

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


async def init_db() -> None:
    """Initialize database tables and run safe column migrations."""
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN preferred_gender VARCHAR(20) DEFAULT 'any'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN city VARCHAR(100) DEFAULT 'Алматы'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN occupation VARCHAR(50) DEFAULT 'student'"))
        except Exception:
            pass
        for col_def in [
            "lease_term VARCHAR(100)",
            "preferred_age_range VARCHAR(100)",
            "utilities_status VARCHAR(50)",
            "utilities_amount INTEGER",
            "neighbor_criteria JSON",
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE listings ADD COLUMN {col_def}"))
            except Exception:
                pass
        for col_def in [
            "has_apartment BOOLEAN DEFAULT 0",
            "apartment_address VARCHAR(255)",
            "rooms_count VARCHAR(50)",
            "room_type VARCHAR(50)",
            "neighbors_needed INTEGER DEFAULT 1",
            "preferred_room_type VARCHAR(50) DEFAULT 'any'",
            "budget_range VARCHAR(100)",
            "ideal_neighbor_desc TEXT",
            "about_self_desc TEXT",
            "neighbor_criteria JSON",
            "notifications_enabled BOOLEAN DEFAULT 1",
            "last_freshness_ping_at DATETIME",
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE seeker_profiles ADD COLUMN {col_def}"))
            except Exception:
                pass
