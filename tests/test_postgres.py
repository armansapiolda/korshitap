"""Runs migrations and the main flows against a real Postgres.

Skipped unless TEST_POSTGRES_URL is set, e.g.
    TEST_POSTGRES_URL=postgresql+asyncpg://postgres@127.0.0.1:5432/korshi_test .venv/bin/pytest tests/test_postgres.py
The database is wiped (all tables dropped) before the test.
"""

import os

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

PG_URL = os.environ.get("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_POSTGRES_URL is not set")


@pytest.mark.asyncio
async def test_migrations_seeds_search_and_wipe_on_postgres():
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db.base import Base, _upgrade_schema
    from app.db.models import User
    from app.matching.cold_search import perform_cold_search
    from app.seeds.test_data import seed_database, wipe_database
    from app.services.funnel_service import funnel_report, track
    from app.services.user_service import UserService

    engine = create_async_engine(PG_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    async with engine.begin() as conn:
        await conn.run_sync(_upgrade_schema)
    async with engine.connect() as conn:
        diff = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c, opts={"compare_type": True}), Base.metadata)
        )
    assert diff == []

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await seed_database(session, count=120)
        real = await UserService.get_or_create_user(session, 5550001, first_name="Real")
        await track(session, real.telegram_id, "start")
        await session.commit()

        viewer = (await session.execute(select(User).where(User.is_seed == True).limit(1))).scalar_one()
        from app.db.models import SeekerProfile
        profile = (await session.execute(select(SeekerProfile).where(SeekerProfile.user_id == viewer.id))).scalar_one_or_none()
        await perform_cold_search(session, viewer, profile)
        assert (await funnel_report(session))["steps"][0]["count"] == 1

        deleted = await wipe_database(session)
        assert deleted > 0
        remaining = (await session.execute(select(func.count(User.id)))).scalar_one()
        assert remaining == 1
    await engine.dispose()
