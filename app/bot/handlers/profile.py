"""Profile and settings management handler with bilingual support and survey edit."""

from typing import Union
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, update

from app.bot.keyboards.reply import (
    MENU_PROFILE_KZ,
    MENU_PROFILE_RU,
    get_main_menu_keyboard,
)
from app.bot.states import QuestionnaireState
from app.constants import DEFAULT_CITY, LISTING_STATUS_ACTIVE, LISTING_STATUS_PAUSED
from app.db.base import async_session_factory
from app.db.models import Listing, SeekerProfile, User
from app.i18n import get_district_name
from app.services.funnel_service import EVENT_PROFILE_HIDDEN, track
from app.services.user_service import UserService

router = Router(name="profile_router")


async def render_profile_view(event: Union[Message, CallbackQuery], user_id: int):
    """Display user's complete profile card with clean aesthetics and options."""
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, user_id)
        if not user:
            user = await UserService.get_or_create_user(session, user_id)
        lang = user.language or "kz"

        profile = (
            await session.execute(
                select(SeekerProfile).where(SeekerProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if not profile:
            profile = await UserService.get_or_create_seeker_profile(session, user.id)

    name = profile.name or user.first_name or ("Қолданушы" if lang == "kz" else "Пользователь")
    age = profile.age or user.age or 22
    city = profile.city or getattr(user, "city", None) or DEFAULT_CITY
    dist_name = ", ".join(get_district_name(d, lang) for d in (profile.districts or ["Бостандыкский"]))

    gender_val = profile.gender or user.gender
    if lang == "kz":
        gender_str = "Қыз бала 👩" if gender_val == "female" else ("Жігіт 👨" if gender_val == "male" else "Көрсетілмеген")
    else:
        gender_str = "Девушка 👩" if gender_val == "female" else ("Парень 👨" if gender_val == "male" else "Не указан")

    occ_val = profile.occupation or getattr(user, "occupation", "working") or "working"
    if lang == "kz":
        if occ_val in ("student", "учусь"):
            occ_str = "Студент 🎓"
        elif occ_val in ("work_study", "Работаю и учусь"):
            occ_str = "Жұмыс істейді және оқиды 💼🎓"
        elif occ_val in ("unemployed", "Пока не работаю"):
            occ_str = "Оқымайды және жұмыс істемейді ✨"
        else:
            occ_str = "Жұмыс істейді 💼"
    else:
        if occ_val in ("student", "учусь"):
            occ_str = "Студент 🎓"
        elif occ_val in ("work_study", "Работаю и учусь"):
            occ_str = "Работает и учится 💼🎓"
        elif occ_val in ("unemployed", "Пока не работаю"):
            occ_str = "В поиске себя ✨"
        else:
            occ_str = "Работает 💼"

    budget_str = profile.budget_range or (f"{profile.budget_max:,} ₸" if profile.budget_max else ("Келісімді" if lang == "kz" else "По договорённости"))
    move_date = profile.move_in_date or ("Жақын арада" if lang == "kz" else "В ближайшее время")

    about_self = profile.about_self_desc or profile.raw_bio or ("Толтырылмаған" if lang == "kz" else "Не заполнено")
    ideal_roommate = profile.ideal_neighbor_desc or profile.neighbor_preferences or ("Толтырылмаған" if lang == "kz" else "Не заполнено")

    notif_enabled = getattr(profile, "notifications_enabled", True)
    if lang == "kz":
        notif_str = "Қосулы 🔔" if notif_enabled else "Өшірулі 🔕"
    else:
        notif_str = "Включены 🔔" if notif_enabled else "Выключены 🔕"

    if lang == "kz":
        if profile.has_apartment:
            housing_block = (
                f"🏠 **Пәтер:** Бар (көрші іздеймін)\n"
                f"🚪 **Бөлме саны:** {profile.rooms_count or 'Көрсетілмеген'}\n"
                f"🛏 **Бөлме түрі:** {profile.room_type or 'Жеке бөлме'}\n"
                f"👥 **Қанша көрші керек:** {profile.neighbors_needed or '1'}\n"
                f"📍 **Мекенжай:** {profile.apartment_address or 'Көрсетілмеген'}\n"
                f"💰 **Бір көршіге бағасы:** {budget_str}\n"
            )
        else:
            housing_block = (
                f"🔍 **Пәтер:** Әлі таппадым (іздеп жүрмін)\n"
                f"🛏 **Қалаған бөлме:** {profile.preferred_room_type or 'Тек жеке бөлме'}\n"
                f"💰 **Бюджет:** {budget_str}\n"
            )

        text = (
            f"👤 **Сенің сауалнамаң**\n\n"
            f"Есімің: **{name}**, {age} жаста\n"
            f"Жынысы: **{gender_str}**\n"
            f"Қала және аудан: **{city} · {dist_name}**\n"
            f"Қызметі: **{occ_str}**\n"
            f"Көшу мерзімі: **{move_date}**\n\n"
            f"{housing_block}\n"
            f"📝 **Өзің туралы:**\n«{about_self}»\n\n"
            f"🎯 **Идеал көршің:**\n«{ideal_roommate}»\n\n"
            f"🔔 Хабарламалар: **{notif_str}**"
        )
        if not profile.is_active:
            text = "⏸ **Сауалнама жасырылған — сені ешкім көрмейді.**\n\n" + text
        btn_pause = "▶️ Қайта іздеу" if not profile.is_active else "⏸ Көрші таптым — жасыру"
        btn_edit = "✏️ Сауалнаманы өзгерту"
        btn_notif = "🔕 Хабарламаны өшіру" if notif_enabled else "🔔 Хабарламаны қосу"
        btn_lang = "🌐 Тілді ауыстыру / Сменить язык"
    else:
        if profile.has_apartment:
            housing_block = (
                f"🏠 **Жильё:** Квартира уже есть (ищу соседа)\n"
                f"🚪 **Количество комнат:** {profile.rooms_count or 'Не указано'}\n"
                f"🛏 **Тип комнаты:** {profile.room_type or 'Отдельная комната'}\n"
                f"👥 **Сколько соседей нужно:** {profile.neighbors_needed or '1'}\n"
                f"📍 **Адрес / ориентир:** {profile.apartment_address or 'Не указан'}\n"
                f"💰 **Стоимость на одного соседа:** {budget_str}\n"
            )
        else:
            housing_block = (
                f"🔍 **Жильё:** Квартиру пока не нашёл\n"
                f"🛏 **Предпочтение по комнате:** {profile.preferred_room_type or 'Отдельная комната'}\n"
                f"💰 **Бюджет:** {budget_str}\n"
            )

        text = (
            f"👤 **Твоя анкета**\n\n"
            f"Имя: **{name}**, {age} лет\n"
            f"Пол: **{gender_str}**\n"
            f"Город и район: **{city} · {dist_name}**\n"
            f"Занятость: **{occ_str}**\n"
            f"Заселение: **{move_date}**\n\n"
            f"{housing_block}\n"
            f"📝 **О себе:**\n«{about_self}»\n\n"
            f"🎯 **Идеальный сосед:**\n«{ideal_roommate}»\n\n"
            f"🔔 Уведомления: **{notif_str}**"
        )
        if not profile.is_active:
            text = "⏸ **Анкета скрыта — тебя никто не видит.**\n\n" + text
        btn_pause = "▶️ Снова искать" if not profile.is_active else "⏸ Нашёл соседа — скрыть анкету"
        btn_edit = "✏️ Изменить анкету"
        btn_notif = "🔕 Выключить уведомления" if notif_enabled else "🔔 Включить уведомления"
        btn_lang = "🌐 Сменить язык / Тілді ауыстыру"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn_edit, callback_data="profile_edit")],
            [InlineKeyboardButton(text=btn_notif, callback_data="profile_toggle_notif")],
            [InlineKeyboardButton(text=btn_pause, callback_data="profile_toggle_active")],
            [InlineKeyboardButton(text=btn_lang, callback_data="profile_change_lang")],
        ]
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb, parse_mode="Markdown")
    else:
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await event.message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.message(
    StateFilter("*"),
    F.text.in_([
        MENU_PROFILE_RU,
        MENU_PROFILE_KZ,
        "👤 Профиль ✨",
        "👤 Профиль",
        "/profile",
    ]),
)
async def menu_profile_click(message: Message, state: FSMContext):
    """View user profile."""
    await state.clear()
    await render_profile_view(message, message.from_user.id)


@router.callback_query(F.data == "profile_toggle_notif")
async def cb_profile_toggle_notif(callback: CallbackQuery):
    """Toggle notification status on/off."""
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user and user.language else "ru"
        profile = await UserService.get_or_create_seeker_profile(session, user.id)
        profile.notifications_enabled = not getattr(profile, "notifications_enabled", True)
        new_status = profile.notifications_enabled
        await session.commit()

    if lang == "kz":
        alert = "Хабарламалар қосылды 🔔" if new_status else "Хабарламалар өшірілді 🔕"
    else:
        alert = "Уведомления включены 🔔" if new_status else "Уведомления выключены 🔕"

    await callback.answer(alert)
    await render_profile_view(callback, callback.from_user.id)


async def set_profile_active(session, user_id: int, active: bool) -> None:
    """Hide or show the user's profile together with their listings."""
    profile = await UserService.get_or_create_seeker_profile(session, user_id)
    if profile.is_active and not active:
        telegram_id = (await session.execute(select(User.telegram_id).where(User.id == user_id))).scalar_one_or_none()
        await track(session, telegram_id, EVENT_PROFILE_HIDDEN)
    profile.is_active = active
    profile.last_freshness_ping_at = None
    from_status, to_status = (
        (LISTING_STATUS_PAUSED, LISTING_STATUS_ACTIVE) if active else (LISTING_STATUS_ACTIVE, LISTING_STATUS_PAUSED)
    )
    if active and not profile.has_apartment:
        return
    await session.execute(
        update(Listing)
        .where(Listing.owner_id == user_id, Listing.status == from_status)
        .values(status=to_status)
    )


@router.callback_query(F.data == "profile_toggle_active")
async def cb_profile_toggle_active(callback: CallbackQuery):
    """Hide the profile after finding a roommate, or start searching again."""
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user and user.language else "ru"
        profile = await UserService.get_or_create_seeker_profile(session, user.id)
        new_active = not profile.is_active
        await set_profile_active(session, user.id, new_active)
        await session.commit()

    if lang == "kz":
        alert = "Сауалнама қайта көрінеді ▶️" if new_active else "Сауалнама жасырылды. Құттықтаймын! 🎉"
    else:
        alert = "Анкета снова видна ▶️" if new_active else "Анкета скрыта. Поздравляю! 🎉"
    await callback.answer(alert)
    await render_profile_view(callback, callback.from_user.id)


@router.callback_query(F.data == "profile_change_lang")
async def cb_profile_change_lang(callback: CallbackQuery):
    """Toggle language between kz and ru."""
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        current_lang = user.language or "ru"
        new_lang = "kz" if current_lang == "ru" else "ru"
        await UserService.set_user_language(session, callback.from_user.id, new_lang)
        await session.commit()

    alert_text = "Тіл қазақшаға ауыстырылды 🇰🇿" if new_lang == "kz" else "Язык переключен на русский 🇷🇺"
    await callback.answer(alert_text)

    # Refresh bottom menu
    await callback.message.answer(
        "👇 Мәзір жаңартылды:" if new_lang == "kz" else "👇 Меню обновлено:",
        reply_markup=get_main_menu_keyboard(new_lang),
    )
    await render_profile_view(callback, callback.from_user.id)


@router.callback_query(F.data == "profile_edit")
async def cb_profile_edit(callback: CallbackQuery, state: FSMContext):
    """Ask which part of the questionnaire to change."""
    await callback.answer()
    await state.clear()
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, callback.from_user.id)

    if lang == "kz":
        text = "✏️ **Не өзгерткің келеді?**"
        items = [
            ("📍 Аудан", "districts"),
            ("👥 Қандай көрші", "preferred_gender"),
            ("💰 Бюджет / баға", "budget"),
            ("📅 Көшу мерзімі", "move_in_date"),
            ("🎯 Идеал көрші", "ideal_neighbor"),
            ("📝 Өзің туралы", "about_self"),
        ]
        full, back = "🔄 Барлығын қайта толтыру", "⬅️ Артқа"
    else:
        text = "✏️ **Что хочешь изменить?**"
        items = [
            ("📍 Район", "districts"),
            ("👥 Какого соседа", "preferred_gender"),
            ("💰 Бюджет / цена", "budget"),
            ("📅 Дата заезда", "move_in_date"),
            ("🎯 Идеальный сосед", "ideal_neighbor"),
            ("📝 О себе", "about_self"),
        ]
        full, back = "🔄 Заполнить всё заново", "⬅️ Назад"
    rows = [
        [InlineKeyboardButton(text=items[i][0], callback_data=f"pedit:{items[i][1]}"),
         InlineKeyboardButton(text=items[i + 1][0], callback_data=f"pedit:{items[i + 1][1]}")]
        for i in range(0, len(items), 2)
    ]
    rows.append([InlineKeyboardButton(text=full, callback_data="profile_edit_full")])
    rows.append([InlineKeyboardButton(text=back, callback_data="profile_back")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")


@router.callback_query(F.data == "profile_back")
async def cb_profile_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await render_profile_view(callback, callback.from_user.id)


@router.callback_query(F.data.startswith("pedit:"))
async def cb_profile_edit_field(callback: CallbackQuery, state: FSMContext):
    """Re-ask one questionnaire question; start.finish_single_edit saves the answer."""
    from app.bot.handlers import start

    field = callback.data.split(":")[1]
    if field not in start.EDITABLE_FIELDS:
        await callback.answer()
        return
    await callback.answer()

    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, callback.from_user.id)
        profile = await UserService.get_or_create_seeker_profile(session, user.id)
        lang = user.language or "ru"
        await state.clear()
        await state.update_data(
            lang=lang,
            edit_field=field,
            has_apartment=bool(profile.has_apartment),
            city=profile.city or DEFAULT_CITY,
            districts=list(profile.districts or []),
            ideal_neighbor_desc=profile.ideal_neighbor_desc,
            about_self_desc=profile.about_self_desc,
        )
        has_apt = bool(profile.has_apartment)

    msg = callback.message
    if field == "districts":
        await start.ask_district(msg, state, lang)
    elif field == "preferred_gender":
        await start.ask_neighbor_gender(msg, state, lang)
    elif field == "budget":
        await start.ask_budget(msg, state, lang, has_apt=has_apt)
    elif field == "move_in_date":
        await start.ask_move_in_date(msg, state, lang, has_apt=has_apt)
    elif field == "ideal_neighbor":
        await start.ask_ideal_neighbor(msg, state, lang)
    elif field == "about_self":
        await start.ask_about_self(msg, state, lang)


@router.callback_query(F.data == "profile_edit_full")
async def cb_profile_edit_full(callback: CallbackQuery, state: FSMContext):
    """Restart questionnaire flow cleanly."""
    await callback.answer()
    await state.clear()

    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language or "ru"

    await state.update_data(lang=lang)
    await state.set_state(QuestionnaireState.waiting_city)

    text = "Қай қалада іздейсің? 📍" if lang == "kz" else "В каком городе ищешь? 📍"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Алматы", callback_data="onb_city:Алматы")],
            [InlineKeyboardButton(text="Астана", callback_data="onb_city:Астана")],
            [InlineKeyboardButton(text="Шымкент", callback_data="onb_city:Шымкент")],
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
