"""Pytest fixtures for KORSHI TAP."""

import asyncio
import os
import tempfile

# Configure the app BEFORE any `app.*` import: tests must never touch the real
# korshi_tap.db, call Vertex AI, or depend on the developer's .env.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="korshi_tap_tests_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{os.path.join(_TEST_DB_DIR, 'test.db')}"
os.environ["AI_PROVIDER"] = "mock"
os.environ["ADMIN_USERNAME"] = "test-admin"
os.environ["ADMIN_PASSWORD"] = "test-password"

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base, engine, init_db
from app.seeds.test_data import seed_database


async def _prepare_app_db():
    """Create tables in the temporary app database used by code that opens its own sessions."""
    await init_db()
    await engine.dispose()


asyncio.run(_prepare_app_db())


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_session():
    """Provides an isolated in-memory SQLite async database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Seed initial test data
        await seed_database(session)
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
