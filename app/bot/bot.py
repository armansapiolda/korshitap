"""Bot application setup and long-polling runner."""

import asyncio
import logging
from aiogram import Dispatcher

from app.bot.bot_instance import get_bot, get_dispatcher
from app.bot.handlers import (
    district_search,
    matches,
    owner_flow,
    profile,
    recommendations,
    reports,
    seeker_flow,
    start,
    swipe,
    who_is_looking,
)
from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import Update
from app.db.base import init_db

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        if event.message:
            logger.info("INCOMING MESSAGE: user_id=%s, text=%r", event.message.from_user.id, event.message.text)
        elif event.callback_query:
            logger.info("INCOMING CALLBACK: user_id=%s, data=%r", event.callback_query.from_user.id, event.callback_query.data)
        return await handler(event, data)


def setup_routers(dispatcher: Dispatcher):
    """Register all handler routers."""
    dispatcher.update.outer_middleware(LoggingMiddleware())
    dispatcher.include_router(owner_flow.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(recommendations.router)
    dispatcher.include_router(district_search.router)
    dispatcher.include_router(seeker_flow.router)
    dispatcher.include_router(swipe.router)
    dispatcher.include_router(who_is_looking.router)
    dispatcher.include_router(matches.router)
    dispatcher.include_router(profile.router)
    dispatcher.include_router(reports.router)


async def main():
    """Main startup for Telegram bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Initializing database...")
    await init_db()

    bot = get_bot()
    dp = get_dispatcher()

    logger.info("Setting up Telegram routers...")
    setup_routers(dp)

    logger.info("Starting Telegram Bot long-polling (Local Machine)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
