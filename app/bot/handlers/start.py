"""Conversational onboarding and questionnaire handler based on the new living specification.
Tone: strictly on 'ты', friendly, aesthetic, conversational, zero bureaucracy.
Strict language separation: pure Kazakh and pure Russian.
"""

from __future__ import annotations

import asyncio
import re
from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.ai.factory import get_ai_provider
from app.bot.keyboards.reply import get_main_menu_keyboard
from app.bot.states import QuestionnaireState
from app.constants import CITIES, CITY_DISTRICTS, DEFAULT_CITY
from app.db.base import async_session_factory
from app.i18n import get_district_name
from app.services.listing_service import ListingService
from app.services.user_service import UserService

router = Router(name="start_router")

# Keep references to fire-and-forget tasks so they are not garbage collected.
_background_tasks: set = set()


async def check_free_text(message: Message, lang: str) -> str | None:
    """Return cleaned free text, or None (after asking to rewrite) if it is empty or flagged."""
    text = (message.text or "").strip()
    if not text:
        await message.answer(
            "Мәтінмен жазып жіберші 🙏" if lang == "kz" else "Напиши, пожалуйста, текстом 🙏"
        )
        return None
    moderation = await get_ai_provider().moderate_content(text)
    if not moderation.is_safe:
        await message.answer(
            "Бұл мәтін тексеруден өтпеді 🙅 Басқаша жазып көрші."
            if lang == "kz"
            else
            "Этот текст не прошёл проверку 🙅 Попробуй написать по-другому."
        )
        return None
    return text


# ==============================================================================
# STEP 1: START & LANGUAGE CHOICE
# ==============================================================================

@router.message(CommandStart(), StateFilter("*"))
@router.message(Command("restart", "start"), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    """Entry point: friendly language picker."""
    await state.clear()
    async with async_session_factory() as session:
        await UserService.get_or_create_user(
            session=session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

    text = "Қай тілде сөйлесеміз? / На каком языке будем общаться?"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="onb_lang:kz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="onb_lang:ru"),
            ]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# STEP 2: WELCOME SCREEN
# ==============================================================================

@router.callback_query(F.data.startswith("onb_lang:"))
async def cb_select_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":")[1]
    await callback.answer()

    async with async_session_factory() as session:
        await UserService.set_user_language(session, callback.from_user.id, lang)
        await session.commit()

    await state.clear()
    await state.update_data(lang=lang)
    await state.set_state(QuestionnaireState.waiting_welcome)

    if lang == "kz":
        text = (
            "Сәлем! 👋\n"
            "Мен саған бірге тұратын жақсы көрші табуға көмектесемін.\n\n"
            "AI сенің қалауыңды, ауданыңды, бюджетің мен болашақ көршіңнің "
            "мінезін ескеріп, саған сәйкес келетін адамдарды таңдайды."
        )
        btn_text = "Бастайық 🚀"
    else:
        text = (
            "Привет! 👋\n"
            "Я помогу тебе найти соседа для совместной жизни.\n\n"
            "ИИ посмотрит на твои предпочтения, район, бюджет и характер "
            "будущего соседа и подберёт подходящие варианты."
        )
        btn_text = "Давай начнём 🚀"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=btn_text, callback_data="onb_start_survey")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# STEP 3: CITY CHOICE
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_welcome, F.data == "onb_start_survey")
async def cb_start_survey(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("lang", "ru")

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


# ==============================================================================
# STEP 4: NAME
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_city, F.data.startswith("onb_city:"))
async def cb_pick_city(callback: CallbackQuery, state: FSMContext):
    city = callback.data.split(":")[1]
    await state.update_data(city=city)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(QuestionnaireState.waiting_name)
    text = (
        "Есімің кім? 😊\n\n*(Есіміңді жаз 👇)*"
        if lang == "kz"
        else
        "Как тебя зовут? 😊\n\n*(Напиши имя 👇)*"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")


@router.message(QuestionnaireState.waiting_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(QuestionnaireState.waiting_gender)
    text = "Жігітсің бе әлде қызсың ба?" if lang == "kz" else "Ты парень или девушка?"

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👨 Жігіт", callback_data="onb_gender:male"),
                    InlineKeyboardButton(text="👩 Қыз", callback_data="onb_gender:female"),
                ]
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="👨 Парень", callback_data="onb_gender:male"),
                    InlineKeyboardButton(text="👩 Девушка", callback_data="onb_gender:female"),
                ]
            ]
        )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# STEP 5: GENDER
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_gender, F.data.startswith("onb_gender:"))
async def cb_pick_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(QuestionnaireState.waiting_age)
    text = (
        "Жасың нешеде? 🎂\n\n*(Жасыңды санмен жаз 👇)*"
        if lang == "kz"
        else
        "Сколько тебе лет? 🎂\n\n*(Напиши возраст числом 👇)*"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")


# ==============================================================================
# STEP 6: AGE
# ==============================================================================

@router.message(QuestionnaireState.waiting_age)
async def process_age(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")

    digits = re.sub(r"\D", "", message.text)
    if not digits or int(digits) < 14 or int(digits) > 100:
        err = "Жасыңды дұрыс санмен жаз (мысалы, 22):" if lang == "kz" else "Напиши корректный возраст числом (например, 22):"
        await message.answer(err)
        return

    age = int(digits)
    await state.update_data(age=age)

    await state.set_state(QuestionnaireState.waiting_occupation)
    text = "Қазір жұмыс істейсің бе әлде оқисың ба? 💼🎓" if lang == "kz" else "Сейчас работаешь или учишься? 💼🎓"

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💼 Жұмыс істеймін", callback_data="onb_occ:working")],
                [InlineKeyboardButton(text="🎓 Оқимын", callback_data="onb_occ:student")],
                [InlineKeyboardButton(text="✨ Жұмыс істеймін және оқимын", callback_data="onb_occ:both")],
                [InlineKeyboardButton(text="🛋 Әзірге жұмыс істемеймін және оқымаймын", callback_data="onb_occ:none")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💼 Работаю", callback_data="onb_occ:working")],
                [InlineKeyboardButton(text="🎓 Учусь", callback_data="onb_occ:student")],
                [InlineKeyboardButton(text="✨ Работаю и учусь", callback_data="onb_occ:both")],
                [InlineKeyboardButton(text="🛋 Пока не работаю и не учусь", callback_data="onb_occ:none")],
            ]
        )
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# STEP 7: OCCUPATION -> STEP 8: DISTRICT
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_occupation, F.data.startswith("onb_occ:"))
async def cb_pick_occupation(callback: CallbackQuery, state: FSMContext):
    occ = callback.data.split(":")[1]
    await state.update_data(occupation=occ)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")
    city = data.get("city", DEFAULT_CITY)

    await state.set_state(QuestionnaireState.waiting_district)
    text = "Қай ауданда баспана іздейсің? 📍" if lang == "kz" else "В каком районе ищешь жильё? 📍"

    districts = CITY_DISTRICTS.get(city, CITY_DISTRICTS["Алматы"])
    kb_rows = []
    current_pair = []
    for d in districts:
        label = get_district_name(d, lang)
        current_pair.append(InlineKeyboardButton(text=f"📍 {label}", callback_data=f"onb_dist:{d}"))
        if len(current_pair) == 2:
            kb_rows.append(current_pair)
            current_pair = []
    if current_pair:
        kb_rows.append(current_pair)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows), parse_mode="Markdown")


# ==============================================================================
# STEP 9: NEIGHBOR GENDER PREFERENCE
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_district, F.data.startswith("onb_dist:"))
async def cb_pick_district(callback: CallbackQuery, state: FSMContext):
    dist = callback.data.split(":")[1]
    await state.update_data(district=dist, districts=[dist])
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(QuestionnaireState.waiting_neighbor_gender)
    text = "Кімді көрші ретінде көргің келеді? 👥" if lang == "kz" else "Кого хочешь видеть своим соседом? 👥"

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👨 Жігітті", callback_data="onb_pgen:male")],
                [InlineKeyboardButton(text="👩 Қызды", callback_data="onb_pgen:female")],
                [InlineKeyboardButton(text="🤝 Бәрібір", callback_data="onb_pgen:any")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👨 Парня", callback_data="onb_pgen:male")],
                [InlineKeyboardButton(text="👩 Девушку", callback_data="onb_pgen:female")],
                [InlineKeyboardButton(text="🤝 Всё равно", callback_data="onb_pgen:any")],
            ]
        )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# STEP 10: HAS APARTMENT (KEY PARAMETER)
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_neighbor_gender, F.data.startswith("onb_pgen:"))
async def cb_pick_neighbor_gender(callback: CallbackQuery, state: FSMContext):
    pref_gender = callback.data.split(":")[1]
    await state.update_data(preferred_gender=pref_gender)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(QuestionnaireState.waiting_has_apartment)
    text = "Сенде пәтер бар ма? 🏠" if lang == "kz" else "У тебя уже есть квартира? 🏠"

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Иә, пәтер таптым — енді көрші керек",
                        callback_data="onb_apt:yes",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔍 Жоқ, әзірге таппадым",
                        callback_data="onb_apt:no",
                    )
                ],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🏠 Да, квартиру уже нашёл — теперь нужен сосед",
                        callback_data="onb_apt:yes",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔍 Нет, пока ещё не нашёл",
                        callback_data="onb_apt:no",
                    )
                ],
            ]
        )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ==============================================================================
# ==============================================================================
# STEP 10: HAS APARTMENT & BRANCHING
# ==============================================================================

@router.callback_query(QuestionnaireState.waiting_has_apartment, F.data.startswith("onb_apt:"))
async def cb_pick_has_apartment(callback: CallbackQuery, state: FSMContext):
    has_apt = (callback.data.split(":")[1] == "yes")
    await state.update_data(has_apartment=has_apt)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "kz")

    if has_apt:
        # User has apartment: ask rooms count
        await state.set_state(QuestionnaireState.waiting_rooms_count)
        text = "Пәтер неше бөлмелі? 🏠" if lang == "kz" else "Сколько комнат в квартире? 🏠"
        if lang == "kz":
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="1-бөлмелі", callback_data="onb_rooms:1-бөлмелі"),
                        InlineKeyboardButton(text="2-бөлмелі", callback_data="onb_rooms:2-бөлмелі"),
                    ],
                    [
                        InlineKeyboardButton(text="3-бөлмелі", callback_data="onb_rooms:3-бөлмелі"),
                        InlineKeyboardButton(text="4+ бөлмелі", callback_data="onb_rooms:4+ бөлмелі"),
                    ],
                ]
            )
        else:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="1-комнатная", callback_data="onb_rooms:1-комнатная"),
                        InlineKeyboardButton(text="2-комнатная", callback_data="onb_rooms:2-комнатная"),
                    ],
                    [
                        InlineKeyboardButton(text="3-комнатная", callback_data="onb_rooms:3-комнатная"),
                        InlineKeyboardButton(text="4+ комнатная", callback_data="onb_rooms:4+ комнатная"),
                    ],
                ]
            )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        # User does not have apartment: ask preferred room type (separate vs shared)
        await state.set_state(QuestionnaireState.waiting_preferred_room_type)
        text = (
            "Сен жеке бөлме қалайсың ба, әлде біреумен бір бөлмеде тұруға дайынсың ба? 🛏"
            if lang == "kz"
            else
            "Ты хочешь отдельную комнату или готов(а) жить с кем-то в одной комнате? 🛏"
        )
        if lang == "kz":
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🛏 Тек жеке бөлме", callback_data="onb_pref_rtype:separate")],
                    [InlineKeyboardButton(text="👥 Бір бөлмеде (подселение)", callback_data="onb_pref_rtype:shared")],
                    [InlineKeyboardButton(text="🤝 Бәрібір (кез келгені)", callback_data="onb_pref_rtype:any")],
                ]
            )
        else:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🛏 Только отдельная комната", callback_data="onb_pref_rtype:separate")],
                    [InlineKeyboardButton(text="👥 Могу в одной комнате (подселение)", callback_data="onb_pref_rtype:shared")],
                    [InlineKeyboardButton(text="🤝 Всё равно", callback_data="onb_pref_rtype:any")],
                ]
            )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


# ------------------------------------------------------------------------------
# BRANCH A (HAS APARTMENT): ROOMS COUNT -> ROOM TYPE -> NEIGHBORS NEEDED -> ADDRESS
# ------------------------------------------------------------------------------

@router.callback_query(QuestionnaireState.waiting_rooms_count, F.data.startswith("onb_rooms:"))
async def cb_pick_rooms_count(callback: CallbackQuery, state: FSMContext):
    rooms = callback.data.split(":")[1]
    await state.update_data(rooms_count=rooms)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "kz")

    await state.set_state(QuestionnaireState.waiting_room_type)
    text = (
        "Көршіге жеке бөлме бола ма, әлде бірге бір бөлмеде тұрасыздар ма? 🛏"
        if lang == "kz"
        else
        "У соседа будет отдельная комната или будете вместе в одной комнате? 🛏"
    )
    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛏 Жеке бөлме", callback_data="onb_rtype:separate")],
                [InlineKeyboardButton(text="👥 Бірге бір бөлмеде (ортақ бөлме)", callback_data="onb_rtype:shared")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛏 Отдельная комната", callback_data="onb_rtype:separate")],
                [InlineKeyboardButton(text="👥 Вместе в одной комнате (общая)", callback_data="onb_rtype:shared")],
            ]
        )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(QuestionnaireState.waiting_room_type, F.data.startswith("onb_rtype:"))
async def cb_pick_room_type(callback: CallbackQuery, state: FSMContext):
    rtype = callback.data.split(":")[1]
    await state.update_data(room_type=rtype)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "kz")

    await state.set_state(QuestionnaireState.waiting_neighbors_needed)
    text = "Қанша көрші іздейсің? 👥" if lang == "kz" else "Сколько соседей нужно? 👥"
    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="1 көрші", callback_data="onb_need:1"),
                    InlineKeyboardButton(text="2 көрші", callback_data="onb_need:2"),
                    InlineKeyboardButton(text="3+ көрші", callback_data="onb_need:3"),
                ]
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="1 сосед", callback_data="onb_need:1"),
                    InlineKeyboardButton(text="2 соседа", callback_data="onb_need:2"),
                    InlineKeyboardButton(text="3+ соседа", callback_data="onb_need:3"),
                ]
            ]
        )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(QuestionnaireState.waiting_neighbors_needed, F.data.startswith("onb_need:"))
async def cb_pick_neighbors_needed(callback: CallbackQuery, state: FSMContext):
    needed = int(callback.data.split(":")[1])
    await state.update_data(neighbors_needed=needed)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "kz")

    await state.set_state(QuestionnaireState.waiting_apartment_address)
    text = (
        "Пәтердің нақты мекенжайы немесе бағдары (ориентир) қандай? 📍\n\n*(Мысалы: Абай — Достық немесе ЖК Алма-Ата)*"
        if lang == "kz"
        else
        "Какой точный адрес или ориентир у квартиры? 📍\n\n*(Например: Абая — Достык или ЖК Алма-Ата)*"
    )
    skip_btn = "⏩ Кейінірек көрсету" if lang == "kz" else "⏩ Указать позже"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=skip_btn, callback_data="onb_skip_address")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.message(QuestionnaireState.waiting_apartment_address)
async def process_apartment_address(message: Message, state: FSMContext):
    addr = message.text.strip()
    await state.update_data(apartment_address=addr)

    data = await state.get_data()
    lang = data.get("lang", "kz")
    await ask_budget(message, state, lang, has_apt=True)


@router.callback_query(QuestionnaireState.waiting_apartment_address, F.data == "onb_skip_address")
async def cb_skip_address(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(apartment_address=None)

    data = await state.get_data()
    lang = data.get("lang", "kz")
    await ask_budget(callback.message, state, lang, has_apt=True)


# ------------------------------------------------------------------------------
# BRANCH B (NO APARTMENT): PREFERRED ROOM TYPE -> BUDGET
# ------------------------------------------------------------------------------

@router.callback_query(QuestionnaireState.waiting_preferred_room_type, F.data.startswith("onb_pref_rtype:"))
async def cb_pick_preferred_room_type(callback: CallbackQuery, state: FSMContext):
    pref_rtype = callback.data.split(":")[1]
    await state.update_data(preferred_room_type=pref_rtype)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "kz")
    await ask_budget(callback.message, state, lang, has_apt=False)


# ==============================================================================
# STEP 11: BUDGET
# ==============================================================================

async def ask_budget(target_msg: Message, state: FSMContext, lang: str, has_apt: bool):
    await state.set_state(QuestionnaireState.waiting_budget)
    if has_apt:
        text = (
            "Бір көршіден ай сайынғы төлем қанша? 💰"
            if lang == "kz"
            else
            "Какая стоимость с одного соседа в месяц? 💰"
        )
    else:
        text = (
            "Айына қандай бюджетке есептейсің? 💰"
            if lang == "kz"
            else
            "На какой бюджет рассчитываешь в месяц? 💰"
        )

    ranges = [
        ("До 70 000 ₸", "70 000 ₸ дейін", 70000),
        ("70 000–100 000 ₸", "70 000–100 000 ₸", 100000),
        ("100 000–150 000 ₸", "100 000–150 000 ₸", 150000),
        ("150 000–200 000 ₸", "150 000–200 000 ₸", 200000),
        ("Более 200 000 ₸", "200 000 ₸-дан жоғары", 250000),
    ]

    kb_buttons = []
    for ru_label, kz_label, val in ranges:
        btn_text = kz_label if lang == "kz" else ru_label
        kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"onb_bgt:{val}:{btn_text}")])

    custom_text = "✍️ Өз нұсқам" if lang == "kz" else "✍️ Свой вариант"
    kb_buttons.append([InlineKeyboardButton(text=custom_text, callback_data="onb_bgt:custom:custom")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    if isinstance(target_msg, Message) and target_msg.from_user.is_bot:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(QuestionnaireState.waiting_budget, F.data.startswith("onb_bgt:"))
async def cb_pick_budget(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    val_str = parts[1]
    label = parts[2] if len(parts) > 2 else ""

    data = await state.get_data()
    lang = data.get("lang", "kz")
    await callback.answer()

    if val_str == "custom":
        await state.set_state(QuestionnaireState.waiting_custom_budget)
        prompt = (
            "Бюджетіңді жаз (₸ түрінде, мысалы, 120000):"
            if lang == "kz"
            else
            "Напиши свой бюджет (в тенге, например, 120000):"
        )
        await callback.message.edit_text(prompt, parse_mode="Markdown")
        return

    val = int(val_str)
    await state.update_data(budget_max=val, budget_range=label)
    has_apt = data.get("has_apartment", False)
    await ask_move_in_date(callback.message, state, lang, has_apt=has_apt)


@router.message(QuestionnaireState.waiting_custom_budget)
async def process_custom_budget(message: Message, state: FSMContext):
    digits = re.sub(r"\D", "", message.text)
    val = int(digits) if digits else 120000
    label = f"{val:,} ₸"
    await state.update_data(budget_max=val, budget_range=label)

    data = await state.get_data()
    lang = data.get("lang", "kz")
    has_apt = data.get("has_apartment", False)
    await ask_move_in_date(message, state, lang, has_apt=has_apt)


# ==============================================================================
# STEP 12: MOVE-IN DATE
# ==============================================================================

async def ask_move_in_date(target_msg: Message, state: FSMContext, lang: str, has_apt: bool):
    await state.set_state(QuestionnaireState.waiting_move_in_date)
    if has_apt:
        text = "Көрші қашан көшіп келе алады? 📅" if lang == "kz" else "Когда можно заехать? 📅"
    else:
        text = "Қашан көшкің келеді? 📅" if lang == "kz" else "Когда хочешь заехать? 📅"

    if lang == "kz":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Мүмкіндігінше тезірек", callback_data="onb_date:soon:Мүмкіндігінше тезірек")],
                [InlineKeyboardButton(text="📅 Бір апта ішінде", callback_data="onb_date:week:Бір апта ішінде")],
                [InlineKeyboardButton(text="🗓 Бір ай ішінде", callback_data="onb_date:month:Бір ай ішінде")],
                [InlineKeyboardButton(text="⏳ 1–2 айдан кейін", callback_data="onb_date:1-2m:1–2 айдан кейін")],
                [InlineKeyboardButton(text="🔍 Әзірге жай іздеп жүрмін", callback_data="onb_date:looking:Әзірге жай іздеп жүрмін")],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚡ Как можно скорее", callback_data="onb_date:soon:Как можно скорее")],
                [InlineKeyboardButton(text="📅 В течение недели", callback_data="onb_date:week:В течение недели")],
                [InlineKeyboardButton(text="🗓 В течение месяца", callback_data="onb_date:month:В течение месяца")],
                [InlineKeyboardButton(text="⏳ Через 1–2 месяца", callback_data="onb_date:1-2m:Через 1–2 месяца")],
                [InlineKeyboardButton(text="🔍 Пока просто ищу", callback_data="onb_date:looking:Пока просто ищу")],
            ]
        )

    if isinstance(target_msg, Message) and target_msg.from_user.is_bot:
        await target_msg.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target_msg.answer(text, reply_markup=kb, parse_mode="Markdown")


async def ask_ideal_neighbor(target_msg: Message, state: FSMContext, lang: str):
    await state.set_state(QuestionnaireState.waiting_ideal_neighbor)
    if lang == "kz":
        text = (
            "🎯 **Қандай көрші іздейсің?**\n\n"
            "Өз сөзіңмен жазып өт, қандай адаммен бірге тұрғың келеді?\n\n"
            "*Мысалы:*\n"
            "«тазалықты жақсы көретін, жұмыс істейтін немесе оқитын, зиянды әдеттері жоқ»\n\n"
            "Өз сөзіңмен жаз 👇"
        )
    else:
        text = (
            "🎯 **Какого соседа ты ищешь?**\n\n"
            "Опиши своими словами, какого соседа ты ищешь?\n\n"
            "*Например:*\n"
            "«чистоплотный, работающий или студент, без вредных привычек»\n\n"
            "Напиши своими словами 👇"
        )

    try:
        await target_msg.edit_text(text, parse_mode="Markdown")
    except Exception:
        await target_msg.answer(text, parse_mode="Markdown")


@router.callback_query(QuestionnaireState.waiting_move_in_date, F.data.startswith("onb_date:"))
async def cb_pick_move_in_date(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    date_label = parts[2] if len(parts) > 2 else "В течение недели"
    await state.update_data(move_in_date=date_label)
    await callback.answer()

    data = await state.get_data()
    lang = data.get("lang", "kz")

    # Proceed directly to ideal neighbor
    await ask_ideal_neighbor(callback.message, state, lang)


@router.message(QuestionnaireState.waiting_ideal_neighbor)
async def process_ideal_neighbor(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "kz")
    desc = await check_free_text(message, lang)
    if desc is None:
        return
    await state.update_data(ideal_neighbor_desc=desc, neighbor_preferences=desc)

    await state.set_state(QuestionnaireState.waiting_about_self)
    if lang == "kz":
        text = (
            "✨ **Ал енді өзің туралы қысқаша айтып өт**\n\n"
            "Бұл ИИ-ге сені жақсырақ түсінуге және бірге тұруға барынша жайлы адамдарды табуға көмектеседі.\n\n"
            "*Мысалы:*\n"
            "«жұмыс істеймін, көбіне жұмыста боламын, тәртіп пен тыныштықты ұнатамын»\n\n"
            "Өз сөзіңмен жаз 👇"
        )
    else:
        text = (
            "✨ **А теперь пару слов о себе**\n\n"
            "Это поможет ИИ лучше понять тебя и подобрать людей, с которыми тебе будет комфортно жить.\n\n"
            "*Например:*\n"
            "«работаю, часто бываю на работе, люблю порядок и спокойную атмосферу»\n\n"
            "Напиши своими словами 👇"
        )

    await message.answer(text, parse_mode="Markdown")


# ==============================================================================
# STEP 15: ABOUT SELF & AI SEARCH TRANSITION
# ==============================================================================

@router.message(QuestionnaireState.waiting_about_self)
async def process_about_self(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "kz")
    about_text = await check_free_text(message, lang)
    if about_text is None:
        return
    await state.update_data(about_self_desc=about_text, raw_bio=about_text)
    data = await state.get_data()

    # Save to Database
    ai = get_ai_provider()
    criteria = await ai.parse_neighbor_description(data.get("ideal_neighbor_desc", "") + " " + about_text)
    criteria_dict = criteria.model_dump()

    user_id = message.from_user.id
    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(
            session=session,
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=data.get("name", message.from_user.first_name),
        )
        user.age = data.get("age", 22)
        user.gender = data.get("gender")
        user.occupation = data.get("occupation", "working")
        user.preferred_gender = data.get("preferred_gender", "any")

        profile = await UserService.get_or_create_seeker_profile(session, user.id)
        profile.name = data.get("name")
        profile.age = data.get("age")
        profile.gender = data.get("gender")
        profile.city = data.get("city", DEFAULT_CITY)
        profile.districts = data.get("districts", [data.get("district", "Бостандыкский")])
        profile.occupation = data.get("occupation")
        profile.preferred_gender = data.get("preferred_gender")
        profile.has_apartment = data.get("has_apartment", False)
        profile.apartment_address = data.get("apartment_address")
        profile.rooms_count = data.get("rooms_count")
        profile.room_type = data.get("room_type")
        profile.neighbors_needed = data.get("neighbors_needed", 1)
        profile.preferred_room_type = data.get("preferred_room_type", "any")
        profile.budget_max = data.get("budget_max", 150000)
        profile.budget_range = data.get("budget_range", "100 000–150 000 ₸")
        profile.move_in_date = data.get("move_in_date", "В течение недели")
        profile.ideal_neighbor_desc = data.get("ideal_neighbor_desc")
        profile.about_self_desc = about_text
        profile.neighbor_preferences = data.get("ideal_neighbor_desc")
        profile.raw_bio = about_text
        profile.neighbor_criteria = criteria_dict
        profile.notifications_enabled = True
        profile.is_active = True

        # Keep exactly one active listing for apartment owners, none for seekers
        await ListingService.sync_profile_listing(session, user.id, profile, criteria_dict)

        await session.commit()
        saved_user_id = user.id

    await state.clear()

    # Tell people who are already searching that a matching person appeared
    from app.bot.notifications import alert_users_about_new_profile
    task = asyncio.create_task(alert_users_about_new_profile(message.bot, saved_user_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    # Step 18: Loading Screen & Animation
    search_screen = (
        "Всё, анкета готова. ✅\n\n"
        "Сейчас ИИ ищет тебе подходящих людей... 🤖✨"
        if lang == "ru"
        else
        "Барлығы дайын. ✅\n\n"
        "Қазір ИИ саған сәйкес келетін адамдарды іздеп жатыр... 🤖✨"
    )
    loading_msg = await message.answer(search_screen, parse_mode="Markdown")

    # Provide persistent 3-button bottom menu
    await message.answer(
        "👇 Мәзір:" if lang == "kz" else "👇 Главное меню:",
        reply_markup=get_main_menu_keyboard(lang),
    )

    # Launch multi-tiered recommendations feed!
    from app.bot.handlers.recommendations import show_instant_recommendations
    try:
        await show_instant_recommendations(message, user_id=user_id)
    finally:
        try:
            await loading_msg.delete()
        except Exception:
            pass
