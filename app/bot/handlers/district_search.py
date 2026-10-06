"""District-by-district search handler showing seekers count and smart gender filtering.
Supports all cities (Алматы, Астана, Шымкент) and sends each candidate as an individual card.
"""

from __future__ import annotations

from typing import Optional, Union
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.handlers.recommendations import format_candidate_card
from app.bot.keyboards.reply import MENU_DISTRICTS_KZ, MENU_DISTRICTS_RU
from app.bot.cards import person_keyboard, safety_tip, send_card
from app.constants import CITIES, CITY_DISTRICTS, DEFAULT_CITY
from app.db.base import async_session_factory
from app.db.models import Listing, SeekerProfile, User
from app.i18n import get_district_name
from app.services.user_service import UserService

router = Router(name="district_search_router")


async def render_district_list(
    event: Union[Message, CallbackQuery],
    user_id: int,
    active_filter: Optional[str] = None,
    city_override: Optional[str] = None,
):
    """Render the list of districts in the user's city with seeker counts and gender filter."""
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, user_id)
        lang = user.language if user and user.language else "ru"

        profile = (
            await session.execute(
                select(SeekerProfile).where(SeekerProfile.user_id == user.id)
            )
        ).scalar_one_or_none()

        city = city_override or (profile.city if profile and profile.city else getattr(user, "city", None)) or DEFAULT_CITY

        # If no explicit filter passed, use user's saved preference
        if active_filter is None:
            user_pref = getattr(user, "preferred_gender", None) or (profile.preferred_gender if profile else None) or "any"
            active_filter = user_pref if user_pref in ("female", "male") else "all"

        # Fetch all active seekers in the same city
        stmt = (
            select(SeekerProfile, User)
            .join(User, SeekerProfile.user_id == User.id)
            .where(SeekerProfile.is_active == True, User.is_blocked == False, User.id != user.id)
        )
        all_rows = (await session.execute(stmt)).all()

    # Filter seekers by city
    city_rows = [
        (sp, u) for sp, u in all_rows
        if ((sp.city if sp and sp.city else getattr(u, "city", None)) or DEFAULT_CITY) == city
    ]

    # Filter seekers based on active_filter
    if active_filter == "female":
        filtered_rows = [
            (sp, u) for sp, u in city_rows
            if sp.gender == "female" or u.gender == "female"
        ]
    elif active_filter == "male":
        filtered_rows = [
            (sp, u) for sp, u in city_rows
            if sp.gender == "male" or u.gender == "male"
        ]
    else:
        filtered_rows = city_rows

    districts = CITY_DISTRICTS.get(city, CITY_DISTRICTS[DEFAULT_CITY])

    # Build district buttons with counts
    kb_rows = []
    current_pair = []
    for district in districts:
        cnt = sum(1 for sp, u in filtered_rows if sp.districts and district in sp.districts)
        dist_name = get_district_name(district, lang)
        suffix = "адам" if lang == "kz" else "чел."
        btn_text = f"📍 {dist_name} ({cnt} {suffix})"
        current_pair.append(
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"dist_pick:{district}:{active_filter}:0:{city}",
            )
        )
        if len(current_pair) == 2:
            kb_rows.append(current_pair)
            current_pair = []
    if current_pair:
        kb_rows.append(current_pair)

    # City switch button
    kb_rows.append([
        InlineKeyboardButton(
            text=f"🏙 Қала: {city} (өзгерту)" if lang == "kz" else f"🏙 Город: {city} (сменить)",
            callback_data=f"dist_city_picker:{active_filter}",
        )
    ])

    # Gender filter toggle buttons and notice
    if active_filter == "female":
        if lang == "kz":
            msg_text = (
                f"📍 **{city} бойынша іздеу**\n\n"
                "ℹ️ *Сен қыз баланы таңдағандықтан, тек қыздар көрсетілуде.*\n"
                "Барлығын көргің келе ме?"
            )
            toggle_btn = InlineKeyboardButton(
                text="👥 Барлығын көрсету",
                callback_data=f"dist_filter:all:{city}",
            )
        else:
            msg_text = (
                f"📍 **Поиск по районам ({city})**\n\n"
                "ℹ️ *Мы показываем только девушек, так как ты выбрал(а) девушку.*\n"
                "Хочешь увидеть всех?"
            )
            toggle_btn = InlineKeyboardButton(
                text="👥 Показать всех",
                callback_data=f"dist_filter:all:{city}",
            )
        kb_rows.append([toggle_btn])
    elif active_filter == "male":
        if lang == "kz":
            msg_text = (
                f"📍 **{city} бойынша іздеу**\n\n"
                "ℹ️ *Сен ер баланы таңдағандықтан, тек жігіттер көрсетілуде.*\n"
                "Барлығын көргің келе ме?"
            )
            toggle_btn = InlineKeyboardButton(
                text="👥 Барлығын көрсету",
                callback_data=f"dist_filter:all:{city}",
            )
        else:
            msg_text = (
                f"📍 **Поиск по районам ({city})**\n\n"
                "ℹ️ *Мы показываем только парней, так как ты выбрал(а) парня.*\n"
                "Хочешь увидеть всех?"
            )
            toggle_btn = InlineKeyboardButton(
                text="👥 Показать всех",
                callback_data=f"dist_filter:all:{city}",
            )
        kb_rows.append([toggle_btn])
    else:
        if lang == "kz":
            msg_text = (
                f"📍 **{city} аудандары бойынша іздеу**\n\n"
                "Төмендегі аудандар бойынша іздеушілер саны:\n"
                "Қажетті ауданды таңда 👇"
            )
            filter_buttons = [
                InlineKeyboardButton(text="👩 Тек қыздар", callback_data=f"dist_filter:female:{city}"),
                InlineKeyboardButton(text="👨 Тек жігіттер", callback_data=f"dist_filter:male:{city}"),
            ]
        else:
            msg_text = (
                f"📍 **Поиск по районам ({city})**\n\n"
                "Количество соискателей по районам:\n"
                "Выбери нужный район 👇"
            )
            filter_buttons = [
                InlineKeyboardButton(text="👩 Только девушки", callback_data=f"dist_filter:female:{city}"),
                InlineKeyboardButton(text="👨 Только парни", callback_data=f"dist_filter:male:{city}"),
            ]
        kb_rows.append(filter_buttons)

    reply_markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if isinstance(event, Message):
        await event.answer(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        try:
            await event.message.edit_text(msg_text, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception:
            await event.message.answer(msg_text, reply_markup=reply_markup, parse_mode="Markdown")


@router.message(
    StateFilter("*"),
    F.text.in_([
        MENU_DISTRICTS_RU,
        MENU_DISTRICTS_KZ,
        "📍 Район бойынша іздеу",
        "📍 Поиск по районам",
        "Район бойынша іздеу",
        "Поиск по районам",
        "/districts",
        "/dist",
    ]),
)
async def cmd_district_search(message: Message, state: FSMContext):
    """Handle bottom menu district search button."""
    await state.clear()
    await render_district_list(message, message.from_user.id)


@router.callback_query(F.data.startswith("dist_city_picker:"))
async def cb_dist_city_picker(callback: CallbackQuery):
    """Show city options to switch district view."""
    await callback.answer()
    active_filter = callback.data.split(":")[1]
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user and user.language else "ru"

    text = "Қай қаланың аудандарын көргің келеді? 📍" if lang == "kz" else "Районы какого города показать? 📍"
    buttons = [
        [InlineKeyboardButton(text=c, callback_data=f"dist_set_city:{c}:{active_filter}")]
        for c in CITIES
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")


@router.callback_query(F.data.startswith("dist_set_city:"))
async def cb_dist_set_city(callback: CallbackQuery):
    """Handle city switch for district search."""
    await callback.answer()
    parts = callback.data.split(":")
    city = parts[1]
    active_filter = parts[2] if len(parts) > 2 else "all"

    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        profile = (
            await session.execute(
                select(SeekerProfile).where(SeekerProfile.user_id == user.id)
            )
        ).scalar_one_or_none() if user else None
        if profile:
            profile.city = city
            await session.commit()

    await render_district_list(callback, callback.from_user.id, active_filter=active_filter, city_override=city)


@router.callback_query(F.data.startswith("dist_filter:"))
async def cb_dist_filter(callback: CallbackQuery):
    """Toggle gender filter between all/female/male."""
    await callback.answer()
    parts = callback.data.split(":")
    active_filter = parts[1]
    city = parts[2] if len(parts) > 2 else None
    await render_district_list(callback, callback.from_user.id, active_filter=active_filter, city_override=city)


@router.callback_query(F.data.startswith("dist_back:"))
async def cb_dist_back(callback: CallbackQuery):
    """Return to districts list."""
    await callback.answer()
    parts = callback.data.split(":")
    active_filter = parts[1] if len(parts) > 1 else "all"
    city = parts[2] if len(parts) > 2 else None
    await render_district_list(callback, callback.from_user.id, active_filter=active_filter, city_override=city)


@router.callback_query(F.data.startswith("dist_pick:"))
async def cb_dist_pick(callback: CallbackQuery):
    """Display seekers in selected district - EACH PERSON INDIVIDUALLY WITH 'Сөйлесу' BUTTON."""
    await callback.answer()
    parts = callback.data.split(":")
    district = parts[1]
    active_filter = parts[2] if len(parts) > 2 else "all"
    offset = int(parts[3]) if len(parts) > 3 else 0
    city = parts[4] if len(parts) > 4 else DEFAULT_CITY

    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user and user.language else "ru"
        my_prof = (
            await session.execute(
                select(SeekerProfile).where(SeekerProfile.user_id == user.id)
            )
        ).scalar_one_or_none()

        my_listing = (
            await session.execute(
                select(Listing).where(Listing.owner_id == user.id).order_by(Listing.id.desc())
            )
        ).scalars().first()
        my_criteria = my_listing.neighbor_criteria if my_listing and my_listing.neighbor_criteria else {}

        stmt = (
            select(SeekerProfile, User)
            .join(User, SeekerProfile.user_id == User.id)
            .where(SeekerProfile.is_active == True, User.is_blocked == False, User.id != user.id)
        )
        all_rows = (await session.execute(stmt)).all()

    # Filter by city, district and gender
    seekers_in_dist = []
    for sp, u in all_rows:
        cand_city = (sp.city if sp and sp.city else getattr(u, "city", None)) or DEFAULT_CITY
        if cand_city != city:
            continue
        if sp.districts and district in sp.districts:
            if active_filter == "female" and sp.gender != "female" and u.gender != "female":
                continue
            if active_filter == "male" and sp.gender != "male" and u.gender != "male":
                continue
            seekers_in_dist.append((sp, u))

    dist_name = get_district_name(district, lang)

    if not seekers_in_dist:
        empty_text = (
            f"📍 **{dist_name} ауданы**\n\n"
            "Бұл ауданда әзірге кандидаттар жоқ."
            if lang == "kz"
            else
            f"📍 **{dist_name}**\n\n"
            "В этом районе пока нет подходящих кандидатов."
        )
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="⬅️ Барлық аудандар" if lang == "kz" else "⬅️ Все районы",
                    callback_data=f"dist_back:{active_filter}:{city}",
                )
            ]]
        )
        await callback.message.edit_text(empty_text, reply_markup=back_kb, parse_mode="Markdown")
        return

    # Header text
    count_suffix = "адам" if lang == "kz" else "чел."
    if active_filter == "female":
        notice_line = (
            "\nℹ️ *Сен қыз баланы таңдағандықтан, тек қыздар көрсетілуде.*"
            if lang == "kz"
            else
            "\nℹ️ *Показаны только девушки по твоему выбору.*"
        )
    elif active_filter == "male":
        notice_line = (
            "\nℹ️ *Сен ер баланы таңдағандықтан, тек жігіттер көрсетілуде.*"
            if lang == "kz"
            else
            "\nℹ️ *Показаны только парни по твоему выбору.*"
        )
    else:
        notice_line = ""

    header_text = (
        f"📍 **{dist_name} ауданы** ({len(seekers_in_dist)} {count_suffix}){notice_line}\n\n"
        f"Төменде әр кандидат жеке көрсетілген 👇"
        if lang == "kz"
        else
        f"📍 **{dist_name}** ({len(seekers_in_dist)} {count_suffix}){notice_line}\n\n"
        f"Ниже каждый кандидат показан отдельно 👇"
    )

    try:
        await callback.message.edit_text(header_text, parse_mode="Markdown")
    except Exception:
        await callback.message.answer(header_text, parse_mode="Markdown")

    PAGE_SIZE = 4
    page_seekers = seekers_in_dist[offset:offset + PAGE_SIZE]

    for sp, u in page_seekers:
        card_text = format_candidate_card(sp, u, user, my_prof, lang, my_criteria, show_reason=False)
        await send_card(callback.message.answer, card_text, reply_markup=person_keyboard(u, lang))

    # Footer navigation controls
    control_buttons = []
    next_offset = offset + PAGE_SIZE

    if next_offset < len(seekers_in_dist):
        control_buttons.append([
            InlineKeyboardButton(
                text="Тағы көрсету ➡️" if lang == "kz" else "Показать еще ➡️",
                callback_data=f"dist_pick:{district}:{active_filter}:{next_offset}:{city}",
            )
        ])

    filter_row = []
    if active_filter in ("female", "male"):
        filter_row.append(
            InlineKeyboardButton(
                text="👥 Барлығын көрсету" if lang == "kz" else "👥 Показать всех",
                callback_data=f"dist_pick:{district}:all:0:{city}",
            )
        )
    filter_row.append(
        InlineKeyboardButton(
            text="📍 Басқа аудандар" if lang == "kz" else "📍 Другие районы",
            callback_data=f"dist_back:{active_filter}:{city}",
        )
    )
    control_buttons.append(filter_row)

    shown_count = min(next_offset, len(seekers_in_dist))
    footer_text = (
        f"🏁 **{dist_name}**: {shown_count} / {len(seekers_in_dist)} адам көрсетілді."
        if lang == "kz"
        else
        f"🏁 **{dist_name}**: показано {shown_count} из {len(seekers_in_dist)} чел."
    ) + "\n\n" + safety_tip(lang)

    await callback.message.answer(
        footer_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=control_buttons),
        parse_mode="Markdown",
    )
