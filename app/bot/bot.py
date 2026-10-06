"""Bot application setup and long-polling runner."""

import asyncio
import logging
from aiogram import Dispatcher

from app.bot.bot_instance import get_bot, get_dispatcher
from app.bot.handlers import (
    district_search,
    freshness,
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
from sqlalchemy import select

from app.db.base import async_session_factory, init_db
from app.db.models import User
from app.services.funnel_service import track_now

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data):
        if event.message:
            logger.info("INCOMING MESSAGE: user_id=%s, text=%r", event.message.from_user.id, event.message.text)
        elif event.callback_query:
            logger.info("INCOMING CALLBACK: user_id=%s, data=%r", event.callback_query.from_user.id, event.callback_query.data)
        return await handler(event, data)


class BlockedUserMiddleware(BaseMiddleware):
    """Users blocked in the admin panel cannot use the bot at all."""

    async def __call__(self, handler, event: Update, data):
        from_user = None
        if event.message:
            from_user = event.message.from_user
        elif event.callback_query:
            from_user = event.callback_query.from_user
        if from_user is not None:
            async with async_session_factory() as session:
                is_blocked = (
                    await session.execute(select(User.is_blocked).where(User.telegram_id == from_user.id))
                ).scalar_one_or_none()
            if is_blocked:
                text = "⛔️ Аккаунтың бұғатталған. / Твой аккаунт заблокирован."
                if event.callback_query:
                    await event.callback_query.answer(text, show_alert=True)
                else:
                    await event.message.answer(text)
                return None
        return await handler(event, data)


class FunnelMiddleware(BaseMiddleware):
    """Record the first time a user reaches each questionnaire step (admin funnel)."""

    async def __call__(self, handler, event: Update, data):
        state = data.get("state")
        before = await state.get_state() if state else None
        result = await handler(event, data)
        if state:
            after = await state.get_state()
            if after and after != before and after.startswith("QuestionnaireState:"):
                from_user = data.get("event_from_user")
                if from_user:
                    await track_now(from_user.id, "q:" + after.split(":", 1)[1])
        return result


def setup_routers(dispatcher: Dispatcher):
    """Register all handler routers."""
    dispatcher.update.outer_middleware(LoggingMiddleware())
    dispatcher.update.outer_middleware(BlockedUserMiddleware())
    dispatcher.update.outer_middleware(FunnelMiddleware())
    # Main menu routers go first: pressing a menu button in the middle of the
    # questionnaire must open that section, not be saved as a questionnaire answer.
    dispatcher.include_router(recommendations.router)
    dispatcher.include_router(district_search.router)
    dispatcher.include_router(profile.router)
    dispatcher.include_router(owner_flow.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(seeker_flow.router)
    dispatcher.include_router(swipe.router)
    dispatcher.include_router(who_is_looking.router)
    dispatcher.include_router(matches.router)
    dispatcher.include_router(reports.router)
    dispatcher.include_router(freshness.router)


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
    freshness_task = asyncio.create_task(freshness.freshness_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        freshness_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
