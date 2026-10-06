"""Convenience script to run both Telegram Bot and Admin Panel locally."""

import asyncio
import logging
import multiprocessing
import uvicorn
from app.config import settings
from app.db.base import async_session_factory, init_db
from app.seeds.test_data import seed_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("korshi_tap")


def start_admin():
    uvicorn.run(
        "app.admin.app:app",
        host=settings.ADMIN_HOST,
        port=settings.ADMIN_PORT,
        log_level="info",
    )


async def start_bot_async():
    from app.bot.bot import main as bot_main
    await bot_main()


def start_bot():
    asyncio.run(start_bot_async())


async def ensure_db_ready():
    await init_db()
    async with async_session_factory() as session:
        from sqlalchemy import func, select
        from app.db.models import Listing
        cnt = (await session.execute(select(func.count(Listing.id)))).scalar_one()
        if cnt == 0:
            logger.info("Database is empty. Populating with initial test data...")
            await seed_database(session)


if __name__ == "__main__":
    asyncio.run(ensure_db_ready())

    print("\n" + "=" * 60)
    print("🏔  KORSHI TAP — Сервис поиска подселения и соседей (Алматы)")
    print(f"📊  Admin Web Panel: http://{settings.ADMIN_HOST}:{settings.ADMIN_PORT}")
    print("🤖  Telegram Bot: Long polling mode (работает на вашем компьютере)")
    print("=" * 60 + "\n")

    p_admin = multiprocessing.Process(target=start_admin)
    p_admin.start()

    try:
        start_bot()
    except (KeyboardInterrupt, SystemExit):
        print("\nОстановка KORSHI TAP...")
    finally:
        p_admin.terminate()
        p_admin.join()
