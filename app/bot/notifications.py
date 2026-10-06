"""Real-time match and applicant notifications with direct Telegram chat links."""

import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Listing, Match, SeekerProfile, User
from app.i18n import get_district_name

logger = logging.getLogger(__name__)


def get_chat_url(user: User) -> str:
    """Generate direct Telegram chat URL for any account (with or without username)."""
    if user.username:
        return f"https://t.me/{user.username}"
    return f"tg://user?id={user.telegram_id}"


async def notify_owner_about_applicant(
    bot: Bot,
    session: AsyncSession,
    seeker_user: User,
    listing: Listing,
):
    """Notify apartment owner when a seeker likes their listing."""
    stmt = select(User).where(User.id == listing.owner_id)
    res = await session.execute(stmt)
    owner = res.scalar_one_or_none()
    if not owner or owner.is_blocked:
        return

    lang = owner.language or "ru"
    dist_name = get_district_name(listing.district, lang)

    # Get seeker profile info
    prof_stmt = select(SeekerProfile).where(SeekerProfile.user_id == seeker_user.id)
    prof_res = await session.execute(prof_stmt)
    profile = prof_res.scalar_one_or_none()

    seeker_name = seeker_user.first_name or "Соискатель"
    budget_val = f"{profile.budget_max:,} ₸" if profile and profile.budget_max else "по договоренности"

    if lang == "kz":
        text = (
            f"🔔 **Жаңа үміткер! / Новый отклик!**\n\n"
            f"👤 **{seeker_name}** сенің мына пәтеріңді ұнатты:\n"
            f"📍 **{dist_name}** ({listing.address_landmark or 'Алматы'})\n"
            f"💰 Оның бюджеті: **{budget_val} дейін**\n\n"
            f"Бұл адам саған сәйкес келе ме?"
        )
        btn_accept = "❤️ Қабылдау (Match!)"
        btn_pass = "❌ Өткізу"
    else:
        text = (
            f"🔔 **Новый отклик на твоё жильё!**\n\n"
            f"👤 **{seeker_name}** хочет заселиться к тебе:\n"
            f"📍 **{dist_name}** ({listing.address_landmark or 'Алматы'})\n"
            f"💰 Бюджет соискателя: **до {budget_val}**\n\n"
            f"Принять этого соседа?"
        )
        btn_accept = "❤️ Принять (Match!)"
        btn_pass = "❌ Пропустить"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=btn_accept,
                    callback_data=f"match_accept:{seeker_user.id}:{listing.id}",
                ),
                InlineKeyboardButton(
                    text=btn_pass,
                    callback_data=f"match_decline:{seeker_user.id}:{listing.id}",
                ),
            ]
        ]
    )

    try:
        await bot.send_message(
            chat_id=owner.telegram_id,
            text=text,
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning("Could not send notification to owner %s: %s", owner.telegram_id, e)


async def notify_seeker_about_owner_interest(
    bot: Bot,
    session: AsyncSession,
    owner_user: User,
    listing: Listing,
    seeker_user: User,
):
    """Notify seeker when owner likes them in 'Кто ищет'."""
    lang = seeker_user.language or "ru"
    dist_name = get_district_name(listing.district, lang)
    owner_name = owner_user.first_name or "Владелец"

    if lang == "kz":
        text = (
            f"🔔 **Сені пәтер иесі таңдады!**\n\n"
            f"👤 **{owner_name}** саған пәтер ұсынуда:\n"
            f"📍 **{dist_name}** ({listing.address_landmark or 'Алматы'})\n"
            f"💰 Бағасы: **{listing.price_per_person:,} ₸/ай**\n\n"
            f"Бұл нұсқа саған ұнай ма?"
        )
        btn_accept = "❤️ Қабылдау (Match!)"
        btn_pass = "❌ Өткізу"
    else:
        text = (
            f"🔔 **Тебя выбрал владелец жилья!**\n\n"
            f"👤 **{owner_name}** предлагает тебе свободное место:\n"
            f"📍 **{dist_name}** ({listing.address_landmark or 'Алматы'})\n"
            f"💰 Цена: **{listing.price_per_person:,} ₸/мес**\n\n"
            f"Принять предложение?"
        )
        btn_accept = "❤️ Принять (Match!)"
        btn_pass = "❌ Пропустить"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=btn_accept,
                    callback_data=f"match_accept:{seeker_user.id}:{listing.id}",
                ),
                InlineKeyboardButton(
                    text=btn_pass,
                    callback_data=f"match_decline:{seeker_user.id}:{listing.id}",
                ),
            ]
        ]
    )

    try:
        await bot.send_message(
            chat_id=seeker_user.telegram_id,
            text=text,
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning("Could not send notification to seeker %s: %s", seeker_user.telegram_id, e)


async def send_mutual_match_celebration(
    bot: Bot,
    session: AsyncSession,
    match_id: int,
):
    """Send mutual match celebration and direct chat buttons to BOTH users."""
    stmt = (
        select(Match)
        .options(
            selectinload(Match.seeker_user),
            selectinload(Match.owner_user),
            selectinload(Match.listing),
        )
        .where(Match.id == match_id)
    )
    res = await session.execute(stmt)
    match = res.scalar_one_or_none()
    if not match:
        return

    seeker = match.seeker_user
    owner = match.owner_user
    lst = match.listing

    # 1. Message for Seeker
    s_lang = seeker.language or "ru"
    s_dist = get_district_name(lst.district, s_lang)
    owner_chat_url = get_chat_url(owner)

    if s_lang == "kz":
        s_text = (
            f"🎉 **СІЗДЕРДЕ MATCH!**\n\n"
            f"Пәтер иесі **{owner.first_name}** сені таңдады!\n"
            f"📍 Аудан: **{s_dist}**\n"
            f"💰 Бағасы: **{lst.price_per_person:,} ₸/ай**\n\n"
            f"💬 Бір-біріңізбен сөйлесіп, пәтерді көруге келісіңіздер:"
        )
        s_btn = f"💬 {owner.first_name}-мен сөйлесу (Telegram)"
    else:
        s_text = (
            f"🎉 **У ТЕБЯ MATCH!**\n\n"
            f"Владелец жилья **{owner.first_name}** одобрил твою анкету!\n"
            f"📍 Район: **{s_dist}**\n"
            f"💰 Цена: **{lst.price_per_person:,} ₸/мес**\n\n"
            f"💬 Начните общение прямо сейчас, чтобы договориться о просмотре:"
        )
        s_btn = f"💬 Начать диалог с {owner.first_name}"

    s_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=s_btn, url=owner_chat_url)]]
    )

    try:
        await bot.send_message(
            chat_id=seeker.telegram_id,
            text=s_text,
            reply_markup=s_kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning("Could not notify seeker: %s", e)

    # 2. Message for Owner
    o_lang = owner.language or "ru"
    o_dist = get_district_name(lst.district, o_lang)
    seeker_chat_url = get_chat_url(seeker)

    if o_lang == "kz":
        o_text = (
            f"🎉 **СІЗДЕРДЕ MATCH!**\n\n"
            f"Сен және **{seeker.first_name}** бір-біріңізге сәйкес келдіңіздер!\n"
            f"📍 Аудан: **{o_dist}**\n"
            f"💰 Бағасы: **{lst.price_per_person:,} ₸/ай**\n\n"
            f"💬 Танысып, пәтерге қоныстану шарттарын талқылаңыздар:"
        )
        o_btn = f"💬 {seeker.first_name}-мен сөйлесу (Telegram)"
    else:
        o_text = (
            f"🎉 **У ТЕБЯ MATCH!**\n\n"
            f"Ты и соискатель **{seeker.first_name}** подошли друг другу!\n"
            f"📍 Район: **{o_dist}**\n"
            f"💰 Цена: **{lst.price_per_person:,} ₸/мес**\n\n"
            f"💬 Напиши соискателю в Telegram, чтобы договориться о заселении:"
        )
        o_btn = f"💬 Начать диалог с {seeker.first_name}"

    o_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=o_btn, url=seeker_chat_url)]]
    )

    try:
        await bot.send_message(
            chat_id=owner.telegram_id,
            text=o_text,
            reply_markup=o_kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning("Could not notify owner: %s", e)
