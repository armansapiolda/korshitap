"""Streamlined 12-step owner listing creation flow (Scenario #1: 'Я уже нашёл жильё').
Extracts natural language criteria via Gemini AI and launches smart recommendations.
Strict language separation: pure Kazakh and pure Russian.
"""

from __future__ import annotations

import re
from typing import Union
from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.ai.factory import get_ai_provider
from app.bot.keyboards.districts import get_single_district_keyboard
from app.bot.states import OwnerListingCreation
from app.constants import DEFAULT_CITY, ROLE_BOTH, ROLE_OWNER
from app.db.base import async_session_factory
from app.i18n import get_district_name
from app.services.listing_service import ListingService
from app.services.user_service import UserService

router = Router(name="owner_flow_router")


# ==============================================================================
# MENU SHORTCUT & COMMANDS
# ==============================================================================

@router.message(
    StateFilter("*"),
    F.text.in_([
        "➕ Сдать жилье 🛏",
        "➕ Менде үй бар 🛏",
        "➕ Сдать жилье",
        "➕ Менде үй бар",
        "Сдать жилье",
        "Сдать жильё",
        "Менде үй бар",
        "/create",
        "/owner",
        "/add",
    ]),
)
@router.message(Command("create", "owner", "add"), StateFilter("*"))
async def trigger_owner_flow_menu(message: Message, state: FSMContext):
    """Trigger Scenario 1 from reply menu or command at any time."""
    await start_owner_flow(message, state, message.from_user.id)


# ==============================================================================
# ENTRY POINT: STEP 1 - CITY
# ==============================================================================

async def start_owner_flow(event: Union[Message, CallbackQuery], state: FSMContext, user_id: int):
    """Start Scenario #1: 'Я уже нашёл жильё' (12 steps)."""
    await state.clear()
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, user_id)

    await state.set_state(OwnerListingCreation.waiting_city)
    await state.update_data(lang=lang)

    text = (
        "🏠 **«Менде баспана бар» бөлімі**\n\n"
        "1 / 12-қадам 📍\n"
        "**Тұрғын үй қай қалада орналасқан?**\n\n"
        "Әзірге келесі қалалар қолжетімді:"
        if lang == "kz"
        else
        "🏠 **Сценарий — «Я уже нашёл жильё»**\n\n"
        "Шаг 1 из 12 📍\n"
        "**В каком городе находится жильё?**\n\n"
        "Пока доступны только эти три города:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇰🇿 Астана", callback_data="owner_city:Астана")],
            [InlineKeyboardButton(text="🇰🇿 Алматы", callback_data="owner_city:Алматы")],
            [InlineKeyboardButton(text="🇰🇿 Шымкент", callback_data="owner_city:Шымкент")],
        ]
    )

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await event.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    elif isinstance(event, Message):
        if event.from_user and event.from_user.is_bot:
            try:
                await event.edit_text(text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await event.answer(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await event.answer(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# STEP 1 CALLBACK: PROCESS CITY & OPTIONAL DISTRICT (FOR ALMATY)
# ==============================================================================

@router.callback_query(OwnerListingCreation.waiting_city, F.data.startswith("owner_city:"))
async def process_owner_city(callback: CallbackQuery, state: FSMContext):
    city = callback.data.split(":")[1]
    await state.update_data(city=city)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    if city == "Алматы":
        await state.set_state(OwnerListingCreation.waiting_district)
        text = (
            "📍 **Алматының қай ауданында орналасқан?**"
            if lang == "kz"
            else
            "📍 **В каком районе Алматы находится жильё?**"
        )
        kb = get_single_district_keyboard("owner_dist", lang)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        # For Astana or Shymkent, set district to city name and proceed to step 2
        await state.update_data(district=city)
        await ask_housing_type(callback.message, state, lang)


@router.callback_query(OwnerListingCreation.waiting_district, F.data.startswith("owner_dist:"))
async def process_owner_district(callback: CallbackQuery, state: FSMContext):
    district = callback.data.split(":")[1]
    await state.update_data(district=district)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_housing_type(callback.message, state, lang)


# ==============================================================================
# STEP 2: HOUSING TYPE
# ==============================================================================

async def ask_housing_type(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_housing_type)
    text = (
        "2 / 12-қадам 🏢\n**Тұрғын үй түрі қандай?**"
        if lang == "kz"
        else
        "Шаг 2 из 12 🏢\n**Какой тип жилья?**"
    )

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏢 Пәтер", callback_data="owner_type:flat")],
                [InlineKeyboardButton(text="🛏 Бөлме", callback_data="owner_type:room")],
                [InlineKeyboardButton(text="🏠 Жер үй", callback_data="owner_type:house")],
                [InlineKeyboardButton(text="✨ Басқа", callback_data="owner_type:other")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏢 Квартира", callback_data="owner_type:flat")],
                [InlineKeyboardButton(text="🛏 Комната", callback_data="owner_type:room")],
                [InlineKeyboardButton(text="🏠 Дом", callback_data="owner_type:house")],
                [InlineKeyboardButton(text="✨ Другое", callback_data="owner_type:other")],
            ]
        )

    await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_housing_type, F.data.startswith("owner_type:"))
async def process_housing_type(callback: CallbackQuery, state: FSMContext):
    htype = callback.data.split(":")[1]
    await state.update_data(housing_type=htype)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_rooms_count(callback.message, state, lang)


# ==============================================================================
# STEP 3: ROOMS COUNT
# ==============================================================================

async def ask_rooms_count(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_rooms_count)
    text = (
        "3 / 12-қадам 🚪\n**Тұрғын үйде неше бөлме бар?**"
        if lang == "kz"
        else
        "Шаг 3 из 12 🚪\n**Сколько комнат в жилье?**"
    )

    suffix = "бөлме" if lang == "kz" else "комн."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"1 {suffix}", callback_data="owner_rooms:1"),
                InlineKeyboardButton(text=f"2 {suffix}", callback_data="owner_rooms:2"),
            ],
            [
                InlineKeyboardButton(text=f"3 {suffix}", callback_data="owner_rooms:3"),
                InlineKeyboardButton(text=f"4+ {suffix}", callback_data="owner_rooms:4"),
            ],
        ]
    )
    await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_rooms_count, F.data.startswith("owner_rooms:"))
async def process_rooms_count(callback: CallbackQuery, state: FSMContext):
    rooms = int(callback.data.split(":")[1])
    await state.update_data(total_rooms=rooms)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(OwnerListingCreation.waiting_price)
    text = (
        "4 / 12-қадам 💰\n"
        "**Бір көрші үшін айлық тұру құны қанша?**\n\n"
        "Соманы ₸ түрінде жазыңыз (мысалы: 100000):"
        if lang == "kz"
        else
        "Шаг 4 из 12 💰\n"
        "**Сколько будет стоить проживание для одного соседа?**\n\n"
        "Укажите сумму в ₸ (например: 100000):"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")


# ==============================================================================
# STEP 4: COST / PRICE PER PERSON
# ==============================================================================

@router.message(OwnerListingCreation.waiting_price)
async def process_price(message: Message, state: FSMContext):
    val = re.sub(r"\D", "", message.text)
    price = int(val) if val else 100000
    await state.update_data(price_per_person=price)

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_utilities(message, state, lang)


# ==============================================================================
# STEP 5: UTILITIES
# ==============================================================================

async def ask_utilities(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_utilities)
    text = (
        "5 / 12-қадам 💡\n**Коммуналдық қызметтер бағаға кіре ме?**"
        if lang == "kz"
        else
        "Шаг 5 из 12 💡\n**Коммунальные услуги входят в стоимость?**"
    )

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Иә, кіреді", callback_data="owner_util:included")],
                [InlineKeyboardButton(text="❌ Жоқ, бөлек төленеді", callback_data="owner_util:separate")],
                [InlineKeyboardButton(text="🤷 Білмеймін / шығынға байланысты", callback_data="owner_util:unknown")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, входят", callback_data="owner_util:included")],
                [InlineKeyboardButton(text="❌ Нет, оплачиваются отдельно", callback_data="owner_util:separate")],
                [InlineKeyboardButton(text="🤷 Не знаю / зависит от расхода", callback_data="owner_util:unknown")],
            ]
        )

    await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_utilities, F.data.startswith("owner_util:"))
async def process_utilities(callback: CallbackQuery, state: FSMContext):
    util_choice = callback.data.split(":")[1]
    await state.update_data(
        utilities_status=util_choice,
        utilities_included=(util_choice == "included"),
    )
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    if util_choice == "separate":
        await state.set_state(OwnerListingCreation.waiting_utilities_amount)
        text = (
            "💡 **Коммуналдық қызметтердің шамамен сомасы қанша?**\n"
            "₸ түрінде жазыңыз немесе «Өткізу» батырмасын басыңыз:"
            if lang == "kz"
            else
            "💡 **Примерная сумма комуслуг с человека (в тенге):**\n"
            "Напишите число или нажмите «Пропустить»:"
        )
        skip_btn = "⏩ Өткізу" if lang == "kz" else "⏩ Пропустить"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=skip_btn, callback_data="skip_util_amount")]]
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await ask_occupied_count(callback.message, state, lang)


@router.message(OwnerListingCreation.waiting_utilities_amount)
async def process_utilities_amount(message: Message, state: FSMContext):
    val = re.sub(r"\D", "", message.text)
    amount = int(val) if val else None
    await state.update_data(utilities_amount=amount)

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_occupied_count(message, state, lang)


@router.callback_query(OwnerListingCreation.waiting_utilities_amount, F.data == "skip_util_amount")
async def process_skip_utilities_amount(callback: CallbackQuery, state: FSMContext):
    await state.update_data(utilities_amount=None)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_occupied_count(callback.message, state, lang)


# ==============================================================================
# STEP 6: ALREADY LIVING (OCCUPIED COUNT)
# ==============================================================================

async def ask_occupied_count(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_occupied_count)
    text = (
        "6 / 12-қадам 👥\n**Үйде қазір қанша адам тұрып жатыр?**"
        if lang == "kz"
        else
        "Шаг 6 из 12 👥\n**Сколько человек уже проживает в жилье?**"
    )

    suffix = "адам" if lang == "kz" else "чел."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"1 {suffix}", callback_data="owner_occupied:1"),
                InlineKeyboardButton(text=f"2 {suffix}", callback_data="owner_occupied:2"),
            ],
            [
                InlineKeyboardButton(text=f"3 {suffix}", callback_data="owner_occupied:3"),
                InlineKeyboardButton(text=f"4+ {suffix}", callback_data="owner_occupied:4"),
            ],
        ]
    )
    if isinstance(target_msg, Message) and target_msg.from_user.is_bot:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_occupied_count, F.data.startswith("owner_occupied:"))
async def process_occupied_count(callback: CallbackQuery, state: FSMContext):
    occupied = int(callback.data.split(":")[1])
    await state.update_data(occupied_places=occupied)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_roommates_needed(callback.message, state, lang)


# ==============================================================================
# STEP 7: HOW MANY ROOMMATES NEEDED
# ==============================================================================

async def ask_roommates_needed(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_roommates_needed)
    text = (
        "7 / 12-қадам 🛏\n**Қанша көрші іздеп жүрсіз?**"
        if lang == "kz"
        else
        "Шаг 7 из 12 🛏\n**Сколько соседей вы ищете?**"
    )

    suffix = "көрші" if lang == "kz" else "соседа"
    other_label = "✨ Басқа сан" if lang == "kz" else "✨ Другое количество"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"1 {suffix}", callback_data="owner_needed:1"),
                InlineKeyboardButton(text=f"2 {suffix}", callback_data="owner_needed:2"),
                InlineKeyboardButton(text=f"3 {suffix}", callback_data="owner_needed:3"),
            ],
            [
                InlineKeyboardButton(text=other_label, callback_data="owner_needed:more"),
            ],
        ]
    )
    await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_roommates_needed, F.data.startswith("owner_needed:"))
async def process_roommates_needed(callback: CallbackQuery, state: FSMContext):
    needed_val = callback.data.split(":")[1]
    places = 4 if needed_val == "more" else int(needed_val)
    await state.update_data(available_places=places)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_move_in_date(callback.message, state, lang)


# ==============================================================================
# STEP 8: MOVE-IN DATE
# ==============================================================================

async def ask_move_in_date(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_move_in_date)
    text = (
        "8 / 12-қадам 📅\n**Қашан көшіп келуге болады?**"
        if lang == "kz"
        else
        "Шаг 8 из 12 📅\n**Когда можно заселиться?**"
    )

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Жақын арада", callback_data="owner_date:soon")],
                [InlineKeyboardButton(text="📅 Осы айда", callback_data="owner_date:this_month")],
                [InlineKeyboardButton(text="🗓 Келесі айдан бастап", callback_data="owner_date:next_month")],
                [InlineKeyboardButton(text="✍️ Күнді жазу", callback_data="owner_date:custom")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚡ В ближайшее время", callback_data="owner_date:soon")],
                [InlineKeyboardButton(text="📅 В этом месяце", callback_data="owner_date:this_month")],
                [InlineKeyboardButton(text="🗓 Со следующего месяца", callback_data="owner_date:next_month")],
                [InlineKeyboardButton(text="✍️ Указать дату", callback_data="owner_date:custom")],
            ]
        )
    await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_move_in_date, F.data.startswith("owner_date:"))
async def process_move_in_date(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    if choice == "custom":
        await state.set_state(OwnerListingCreation.waiting_custom_date)
        prompt = (
            "✍️ Көшу күнін жазыңыз (мысалы: «15 қыркүйектен бастап»):"
            if lang == "kz"
            else
            "✍️ Напишите дату заселения (например: «с 15 сентября»):"
        )
        await callback.message.edit_text(prompt, parse_mode="Markdown")
    else:
        date_map_kz = {
            "soon": "Жақын арада",
            "this_month": "Осы айда",
            "next_month": "Келесі айдан бастап",
        }
        date_map_ru = {
            "soon": "В ближайшее время",
            "this_month": "В этом месяце",
            "next_month": "Со следующего месяца",
        }
        date_str = date_map_kz.get(choice, "Жақын арада") if lang == "kz" else date_map_ru.get(choice, "В ближайшее время")
        await state.update_data(move_in_date=date_str)
        await ask_lease_duration(callback.message, state, lang)


@router.message(OwnerListingCreation.waiting_custom_date)
async def process_custom_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    await state.update_data(move_in_date=date_str)

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_lease_duration(message, state, lang)


# ==============================================================================
# STEP 9: LEASE DURATION
# ==============================================================================

async def ask_lease_duration(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_lease_duration)
    text = (
        "9 / 12-қадам ⏳\n**Қандай мерзімге көрші іздейсіз?**"
        if lang == "kz"
        else
        "Шаг 9 из 12 ⏳\n**На какой срок вы ищете соседа?**"
    )

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1–3 ай", callback_data="owner_term:1-3m")],
                [InlineKeyboardButton(text="3–6 ай", callback_data="owner_term:3-6m")],
                [InlineKeyboardButton(text="6–12 ай", callback_data="owner_term:6-12m")],
                [InlineKeyboardButton(text="1 жыл және одан көп", callback_data="owner_term:1y+")],
                [InlineKeyboardButton(text="🤝 Кез келген мерзім", callback_data="owner_term:any")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="1–3 месяца", callback_data="owner_term:1-3m")],
                [InlineKeyboardButton(text="3–6 месяцев", callback_data="owner_term:3-6m")],
                [InlineKeyboardButton(text="6–12 месяцев", callback_data="owner_term:6-12m")],
                [InlineKeyboardButton(text="1 год и более", callback_data="owner_term:1y+")],
                [InlineKeyboardButton(text="🤝 Любой срок", callback_data="owner_term:any")],
            ]
        )

    if isinstance(target_msg, Message) and target_msg.from_user.is_bot:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_lease_duration, F.data.startswith("owner_term:"))
async def process_lease_duration(callback: CallbackQuery, state: FSMContext):
    term_choice = callback.data.split(":")[1]
    term_labels = {
        "1-3m": "1–3 месяца",
        "3-6m": "3–6 месяцев",
        "6-12m": "6–12 месяцев",
        "1y+": "1 год и более",
        "any": "Любой срок",
    }
    await state.update_data(lease_term=term_labels.get(term_choice, "Любой срок"))
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_gender_preference(callback.message, state, lang)


# ==============================================================================
# STEP 10: GENDER PREFERENCE (Strict KZ/RU, no brackets)
# ==============================================================================

async def ask_gender_preference(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_gender_pref)
    text = (
        "10 / 12-қадам 🙋‍♂️\n**Кімді іздейсіз?**"
        if lang == "kz"
        else
        "Шаг 10 из 12 🙋‍♂️\n**Кого вы ищете?**"
    )

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👨 Ер бала", callback_data="owner_gender:male")],
                [InlineKeyboardButton(text="👩 Қыз бала", callback_data="owner_gender:female")],
                [InlineKeyboardButton(text="🤝 Маңызды емес", callback_data="owner_gender:any")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👨 Мужчину", callback_data="owner_gender:male")],
                [InlineKeyboardButton(text="👩 Женщину", callback_data="owner_gender:female")],
                [InlineKeyboardButton(text="🤝 Не имеет значения", callback_data="owner_gender:any")],
            ]
        )
    await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_gender_pref, F.data.startswith("owner_gender:"))
async def process_gender_pref(callback: CallbackQuery, state: FSMContext):
    gender_pref = callback.data.split(":")[1]
    await state.update_data(preferred_gender=gender_pref)
    await callback.answer()

    # Save to user in database
    async with async_session_factory() as session:
        await UserService.set_user_preferred_gender(session, callback.from_user.id, gender_pref)
        await session.commit()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_age_preference(callback.message, state, lang)


# ==============================================================================
# STEP 11: AGE PREFERENCE
# ==============================================================================

async def ask_age_preference(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_age_pref)
    text = (
        "11 / 12-қадам 🎂\n"
        "**Көршінің жасы қандай болғаны қолайлы?**\n\n"
        "Нұсқаны таңдаңыз немесе өз жауабыңызды жазыңыз (мысалы: 18-30):"
        if lang == "kz"
        else
        "Шаг 11 из 12 🎂\n"
        "**Какой возраст соседа вам подходит?**\n\n"
        "Выберите вариант или напишите свой (например: 18-30):"
    )

    suffix = "жас" if lang == "kz" else "лет"
    any_label = "🤝 Кез келген жас" if lang == "kz" else "🤝 Любой возраст"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"18–25 {suffix}", callback_data="owner_age:18-25"),
                InlineKeyboardButton(text=f"20–30 {suffix}", callback_data="owner_age:20-30"),
            ],
            [
                InlineKeyboardButton(text=f"25–35 {suffix}", callback_data="owner_age:25-35"),
                InlineKeyboardButton(text=any_label, callback_data="owner_age:any"),
            ],
        ]
    )
    await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(OwnerListingCreation.waiting_age_pref, F.data.startswith("owner_age:"))
async def process_age_pref_callback(callback: CallbackQuery, state: FSMContext):
    age_choice = callback.data.split(":")[1]
    age_label = "Любой" if age_choice == "any" else f"{age_choice} лет"
    await state.update_data(preferred_age_range=age_label)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_neighbor_description(callback.message, state, lang)


@router.message(OwnerListingCreation.waiting_age_pref)
async def process_age_pref_message(message: Message, state: FSMContext):
    age_str = message.text.strip()
    await state.update_data(preferred_age_range=age_str)

    data = await state.get_data()
    lang = data.get("lang", "ru")
    await ask_neighbor_description(message, state, lang)


# ==============================================================================
# STEP 12: THE CORE STEP - NATURAL LANGUAGE NEIGHBOR DESCRIPTION (GEMINI AI)
# ==============================================================================

async def ask_neighbor_description(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(OwnerListingCreation.waiting_neighbor_description)

    if lang == "kz":
        text = (
            "12 / 12-қадам 👤\n\n"
            "👤 **Қандай көрші іздейсіз?**\n\n"
            "Бірге тұруға дайын адамыңыз қандай болуы керек екенін өз сөзіңізбен айтып беріңіз.\n\n"
            "Бұл сипаттама ақылды іздеу және ұсыныстар үшін қажет — AI мәтінді талдап, "
            "талаптарыңызға барынша сәйкес келетін адамдарды табады.\n\n"
            "*Мысалы:*\n"
            "«Сабырлы және тазалықты жақсы көретін адам іздеймін. Жаман әдеттері жоқ, тыныш болғаны дұрыс. "
            "Мен 9-дан 18-ге дейін жұмыс істеймін, үйде көбіне кешке боламын. Үй жануарларына қарсы емеспін.»\n\n"
            "Өз сөзіңізбен жазыңыз 👇"
        )
    else:
        text = (
            "Шаг 12 из 12 👤\n\n"
            "👤 **Какого соседа вы ищете?**\n\n"
            "Расскажите своими словами, каким должен быть человек, с которым вы готовы жить.\n\n"
            "Это описание нужно для умного поиска и рекомендаций — ИИ проанализирует ваш текст "
            "и найдёт людей, которые лучше всего соответствуют вашим требованиям.\n\n"
            "*Например:*\n"
            "«Ищу спокойного и аккуратного человека. Желательно без вредных привычек, не шумного. "
            "Я работаю с 9 до 18, поэтому дома обычно бываю вечером. Не против домашних животных.»\n\n"
            "Напишите своими словами 👇"
        )

    if isinstance(target_msg, Message) and target_msg.from_user.is_bot:
        await target_msg.edit_text(text, parse_mode="Markdown")
    else:
        await target_msg.answer(text, parse_mode="Markdown")


@router.message(OwnerListingCreation.waiting_neighbor_description)
async def process_neighbor_description(message: Message, state: FSMContext):
    desc_text = message.text.strip()
    data = await state.get_data()
    lang = data.get("lang", "ru")

    wait_notice = (
        "🤖 *AI сипаттамаңызды талдауда...*"
        if lang == "kz"
        else
        "🤖 *ИИ анализирует ваше описание...*"
    )
    status_msg = await message.answer(wait_notice, parse_mode="Markdown")

    # Call Gemini AI to parse semantic criteria
    ai = get_ai_provider()
    criteria = await ai.parse_neighbor_description(desc_text)
    criteria_dict = criteria.model_dump()

    # Determine derived lifestyle flags from Gemini
    smoking_allowed = True if criteria.smoking in ("acceptable", "yes") else False
    pets_allowed = True if criteria.pets in ("acceptable", "loves_pets", "yes") else False

    # Save to database
    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, message.from_user.id)
        user.role = ROLE_BOTH if user.role == "seeker" else ROLE_OWNER

        listing = await ListingService.create_listing(
            session=session,
            owner_id=user.id,
            data={
                "city": data.get("city", DEFAULT_CITY),
                "district": data.get("district", "Бостандыкский"),
                "housing_type": data.get("housing_type", "room"),
                "total_rooms": data.get("total_rooms", 2),
                "price_per_person": data.get("price_per_person", 100000),
                "utilities_status": data.get("utilities_status", "included"),
                "utilities_amount": data.get("utilities_amount"),
                "utilities_included": data.get("utilities_included", True),
                "occupied_places": data.get("occupied_places", 1),
                "available_places": data.get("available_places", 1),
                "move_in_date": data.get("move_in_date", "В ближайшее время"),
                "lease_term": data.get("lease_term", "Любой срок"),
                "preferred_gender": data.get("preferred_gender", "any"),
                "preferred_age_range": data.get("preferred_age_range", "Любой"),
                "smoking_allowed": smoking_allowed,
                "pets_allowed": pets_allowed,
                "conditions_description": desc_text,
                "neighbor_criteria": criteria_dict,
                "photos": [],
            },
        )
        await session.commit()

    await state.clear()

    # Remove the temporary wait notice
    try:
        await status_msg.delete()
    except Exception:
        pass

    # Required completion message
    if lang == "kz":
        completion_text = (
            "🎉 **Дайын! Хабарландыру құрылды.**\n\n"
            "Енді мен сізге және тұрғын үйіңізге сәйкес келетін адамдарды іздеймін.\n\n"
            "🤖 Мен тек баға мен ауданды ғана емес, бірге тұрудың қаншалықты жайлы болатынын да ескеремін."
        )
    else:
        completion_text = (
            "🎉 **Готово! Объявление создано.**\n\n"
            "Теперь я буду искать людей, которые подходят вам и вашему жилью.\n\n"
            "🤖 Я буду учитывать не только цену и район, но и то, насколько вам будет комфортно жить вместе."
        )

    await message.answer(completion_text, parse_mode="Markdown")

    # Launch smart recommendations feed right away!
    from app.bot.handlers.recommendations import show_instant_recommendations
    district_filter = data.get("district") if data.get("city") == "Алматы" else None
    await show_instant_recommendations(message, user_id=message.from_user.id, district_filter=district_filter)
