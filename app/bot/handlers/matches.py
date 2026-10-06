"""Matches view, accept/decline callbacks, and direct chat connection."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.bot_instance import get_bot
from app.bot.keyboards.reply import MENU_MATCHES_KZ, MENU_MATCHES_RU
from app.bot.notifications import get_chat_url, send_mutual_match_celebration
from app.db.base import async_session_factory
from app.db.models import Listing, User
from app.i18n import get_district_name
from app.services.match_service import MatchService
from app.services.user_service import UserService

router = Router(name="matches_router")


@router.message(F.text.in_([MENU_MATCHES_RU, MENU_MATCHES_KZ]))
async def menu_matches_click(message: Message):
    """View all mutual matches."""
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, message.from_user.id)
        user = await UserService.get_or_create_user(session, message.from_user.id)
        matches = await MatchService.get_user_matches(session, user.id)

    if not matches:
        empty_text = (
            "❤️ **Әзірге сәйкестіктер (Match) жоқ.**\n\n"
            "**🔍 Іздеу** бөлімінен пәтерлерді қарап, ❤️ қой. "
            "Бір-біріңізге ұнаған кезде осы жерде жеке контакт шығады!"
            if lang == "kz"
            else
            "❤️ **Пока нет активных совпадений (Match).**\n\n"
            "Листай варианты в **🔍 Поиск** и ставь ❤️. "
            "Как только интерес совпадёт — здесь сразу появится контакт для связи!"
        )
        await message.answer(empty_text, parse_mode="Markdown")
        return

    header = (
        f"🎉 **Сенің сәйкестіктерің ({len(matches)}):**\n"
        if lang == "kz"
        else f"🎉 **Твои взаимные совпадения ({len(matches)}):**\n"
    )
    await message.answer(header, parse_mode="Markdown")

    for m in matches:
        is_seeker = (m.seeker_user_id == user.id)
        partner = m.owner_user if is_seeker else m.seeker_user
        partner_name = partner.first_name or ("Көрші" if lang == "kz" else "Пользователь")

        lst = m.listing
        dist_name = get_district_name(lst.district, lang) if lst else "Алматы"
        price = f"{lst.price_per_person:,} ₸" if lst else ""
        chat_url = get_chat_url(partner)

        if lang == "kz":
            card = (
                f"🤝 **{partner_name} екеуіңде MATCH!**\n"
                f"📍 Аудан: **{dist_name}**\n"
                f"💰 Бағасы: **{price}**\n"
                f"📅 Күні: {m.matched_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            btn_text = f"💬 {partner_name}-мен сөйлесу (Telegram)"
        else:
            card = (
                f"🤝 **Match с {partner_name}!**\n"
                f"📍 Район: **{dist_name}**\n"
                f"💰 Цена: **{price}**\n"
                f"📅 Дата: {m.matched_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            btn_text = f"💬 Написать {partner_name} в Telegram"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=btn_text, url=chat_url)]]
        )
        await message.answer(card, reply_markup=kb, parse_mode="Markdown")


# --- Accept / Decline Applicant Callbacks ---

@router.callback_query(F.data.startswith("match_accept:"))
async def cb_match_accept(callback: CallbackQuery):
    """When a user clicks [❤️ Принять (Match!)] on an applicant notification."""
    parts = callback.data.split(":")
    seeker_id = int(parts[1])
    listing_id = int(parts[2])

    bot = get_bot()
    match_id = None

    async with async_session_factory() as session:
        cur_user = await UserService.get_or_create_user(session, callback.from_user.id)
        lang = cur_user.language or "ru"

        # Determine owner and seeker
        lst_stmt = select(Listing).where(Listing.id == listing_id)
        res = await session.execute(lst_stmt)
        listing = res.scalar_one_or_none()

        if listing:
            owner_id = listing.owner_id
            match = await MatchService.create_direct_match(
                session=session,
                seeker_user_id=seeker_id,
                listing_id=listing_id,
                owner_user_id=owner_id,
            )
            await session.commit()
            match_id = match.id

            # Send instant push notification to BOTH users with direct chat button!
            await send_mutual_match_celebration(bot, session, match_id)

    await callback.answer("🎉 MATCH!")
    confirm_text = (
        "✅ **MATCH қабылданды!**\nЧатқа өту туралы хабарлама жіберілді."
        if lang == "kz"
        else
        "✅ **MATCH принят!**\nОбоим участникам отправлены кнопки для начала диалога."
    )
    await callback.message.edit_text(confirm_text, parse_mode="Markdown")


@router.callback_query(F.data.startswith("match_decline:"))
async def cb_match_decline(callback: CallbackQuery):
    """When a user declines an applicant."""
    async with async_session_factory() as session:
        cur_user = await UserService.get_or_create_user(session, callback.from_user.id)
        lang = cur_user.language or "ru"

    await callback.answer("Өткізілді / Пропущено")
    text = "❌ Өткізілді." if lang == "kz" else "❌ Пропущено."
    await callback.message.edit_text(text, parse_mode="Markdown")
