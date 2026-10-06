"""Periodic "are you still searching?" reminders that keep the base free of dead profiles.

- A profile not updated for LISTING_FRESHNESS_DAYS gets a reminder with two buttons.
- No answer for another LISTING_FRESHNESS_DAYS -> the profile is hidden automatically.
- A user who blocked the bot is hidden right away.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.profile import set_profile_active
from app.config import settings
from app.db.base import async_session_factory
from app.db.models import SeekerProfile, User
from app.services.user_service import UserService

logger = logging.getLogger(__name__)
router = Router(name="freshness_router")

CHECK_INTERVAL_SECONDS = 6 * 60 * 60

ACTION_PING = "ping"
ACTION_HIDE = "hide"


async def find_stale_profiles(
    session: AsyncSession,
    now: Optional[datetime] = None,
    days: Optional[int] = None,
) -> List[Tuple[str, User, SeekerProfile]]:
    """Return (action, user, profile) for profiles that need a reminder or should be hidden."""
    now = now or datetime.utcnow()
    days = days or settings.LISTING_FRESHNESS_DAYS
    threshold = now - timedelta(days=days)

    rows = (
        await session.execute(
            select(SeekerProfile, User)
            .join(User, SeekerProfile.user_id == User.id)
            .where(
                SeekerProfile.is_active == True,
                User.is_blocked == False,
                User.is_seed == False,
                SeekerProfile.updated_at < threshold,
                or_(
                    SeekerProfile.last_freshness_ping_at.is_(None),
                    SeekerProfile.last_freshness_ping_at < threshold,
                ),
            )
        )
    ).all()

    result = []
    for profile, user in rows:
        pinged = profile.last_freshness_ping_at
        if pinged is not None and profile.updated_at <= pinged:
            # Reminder was sent and ignored for `days` days
            result.append((ACTION_HIDE, user, profile))
        else:
            result.append((ACTION_PING, user, profile))
    return result


async def _mark_pinged(session: AsyncSession, profile_id: int, when: datetime) -> None:
    # Keep updated_at untouched: it is the "last confirmed by the user" timestamp.
    await session.execute(
        update(SeekerProfile)
        .where(SeekerProfile.id == profile_id)
        .values(last_freshness_ping_at=when, updated_at=SeekerProfile.updated_at)
    )


def _reminder(lang: str) -> Tuple[str, InlineKeyboardMarkup]:
    if lang == "kz":
        text = "👋 Сәлем! Әлі де көрші іздеп жүрсің бе? Жауап бермесең, сауалнаманы бір аптадан кейін жасырамын."
        yes, no = "✅ Иә, іздеп жүрмін", "⏸ Жоқ, таптым"
    else:
        text = "👋 Привет! Ты ещё ищешь соседа? Если не ответишь, через неделю я скрою анкету."
        yes, no = "✅ Да, ищу", "⏸ Нет, уже нашёл"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=yes, callback_data="fresh:yes")],
            [InlineKeyboardButton(text=no, callback_data="fresh:no")],
        ]
    )
    return text, kb


async def run_freshness_check(bot: Bot) -> None:
    """One pass: send reminders and hide abandoned profiles."""
    now = datetime.utcnow()
    async with async_session_factory() as session:
        stale = await find_stale_profiles(session, now=now)

        for action, user, profile in stale:
            lang = user.language or "kz"
            if action == ACTION_HIDE:
                await set_profile_active(session, user.id, False)
                text = (
                    "⏸ Сауалнамаңды жасырдым. Қайта іздегің келсе — «👤 Профиль» бөлімінде қос."
                    if lang == "kz"
                    else
                    "⏸ Я скрыл твою анкету. Если снова будешь искать — включи её в «👤 Профиль»."
                )
                try:
                    await bot.send_message(user.telegram_id, text)
                except Exception:
                    pass
                continue

            text, kb = _reminder(lang)
            try:
                await bot.send_message(user.telegram_id, text, reply_markup=kb)
                await _mark_pinged(session, profile.id, now)
            except TelegramForbiddenError:
                # User blocked the bot: nobody can reach them anyway
                await set_profile_active(session, user.id, False)
            except Exception as e:
                logger.info("Freshness reminder to %s failed: %s", user.telegram_id, e)
            await asyncio.sleep(0.05)

        await session.commit()


async def freshness_loop(bot: Bot) -> None:
    while True:
        try:
            await run_freshness_check(bot)
        except Exception:
            logger.exception("Freshness check failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@router.callback_query(F.data.startswith("fresh:"))
async def cb_freshness_answer(callback: CallbackQuery):
    answer = callback.data.split(":")[1]
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer()
            return
        lang = user.language or "kz"
        if answer == "yes":
            profile = await UserService.get_or_create_seeker_profile(session, user.id)
            profile.updated_at = datetime.utcnow()
            profile.last_freshness_ping_at = None
            text = "Керемет, іздеуді жалғастырамыз! 🔎" if lang == "kz" else "Отлично, продолжаем поиск! 🔎"
        else:
            await set_profile_active(session, user.id, False)
            text = (
                "Құттықтаймын! 🎉 Сауалнама жасырылды, оны «👤 Профиль» бөлімінде қайта қоса аласың."
                if lang == "kz"
                else
                "Поздравляю! 🎉 Анкета скрыта, включить её снова можно в «👤 Профиль»."
            )
        await session.commit()

    await callback.answer()
    try:
        await callback.message.edit_text(text)
    except Exception:
        await callback.message.answer(text)
