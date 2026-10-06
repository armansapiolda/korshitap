"""Profile and settings management handler with bilingual support and survey edit."""

from typing import Union
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.bot.keyboards.reply import (
    MENU_PROFILE_KZ,
    MENU_PROFILE_RU,
    get_main_menu_keyboard,
)
from app.bot.states import QuestionnaireState
from app.constants import DEFAULT_CITY
from app.db.base import async_session_factory
from app.db.models import SeekerProfile, User
from app.i18n import get_district_name
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
    district = profile.districts[0] if profile.districts else "Бостандыкский"
    dist_name = get_district_name(district, lang)

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
        btn_edit = "✏️ Изменить анкету"
        btn_notif = "🔕 Выключить уведомления" if notif_enabled else "🔔 Включить уведомления"
        btn_lang = "🌐 Сменить язык / Тілді ауыстыру"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=btn_edit, callback_data="profile_edit")],
            [InlineKeyboardButton(text=btn_notif, callback_data="profile_toggle_notif")],
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
