"""Ultra-streamlined, minimal seeker flow without redundant text typing."""

import re
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.common import (
    get_express_budget_keyboard,
    get_gender_keyboard,
)
from app.bot.keyboards.districts import get_multi_district_keyboard
from app.bot.states import SeekerRegistration
from app.constants import DEFAULT_CITY
from app.db.base import async_session_factory
from app.i18n import t
from app.services.user_service import UserService

router = Router(name="seeker_flow_router")


async def start_seeker_flow(message: Message, state: FSMContext, user_id: int):
    """Directly start 3-tap district selection."""
    await state.clear()
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, user_id)

    await state.set_state(SeekerRegistration.waiting_district)
    await state.update_data(lang=lang, selected_districts=["Бостандыкский"])

    text = t("choose_district", lang)
    kb = get_multi_district_keyboard(["Бостандыкский"], lang)

    if isinstance(message, Message):
        try:
            await message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(SeekerRegistration.waiting_district, F.data.startswith("dist_toggle:"))
async def process_district_toggle(callback: CallbackQuery, state: FSMContext):
    district = callback.data.split(":")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")
    selected = list(data.get("selected_districts", []))

    if district in selected:
        selected.remove(district)
    else:
        selected.append(district)

    if not selected:
        selected = [district]

    await state.update_data(selected_districts=selected)
    await callback.message.edit_reply_markup(
        reply_markup=get_multi_district_keyboard(selected, lang)
    )
    await callback.answer()


@router.callback_query(SeekerRegistration.waiting_district, F.data == "dist_done")
async def process_district_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    selected = data.get("selected_districts", ["Бостандыкский"])
    await state.update_data(districts=selected)
    await callback.answer()

    # Step 2: Budget
    await state.set_state(SeekerRegistration.waiting_budget)
    text = t("choose_budget", lang)
    await callback.message.edit_text(
        text,
        reply_markup=get_express_budget_keyboard(lang),
        parse_mode="Markdown",
    )


@router.callback_query(SeekerRegistration.waiting_budget, F.data.startswith("budget:"))
async def process_express_budget(callback: CallbackQuery, state: FSMContext):
    val_str = callback.data.split(":")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")

    if val_str == "custom":
        await callback.answer()
        prompt = "Соманы санмен жаз (мысалы 110000):" if lang == "kz" else "Напиши сумму числом (например 110000):"
        await callback.message.edit_text(prompt)
        return

    budget = int(val_str)
    await state.update_data(budget_max=budget)
    await callback.answer()

    # Step 3: Gender
    await state.set_state(SeekerRegistration.waiting_gender)
    text = t("choose_gender", lang)
    await callback.message.edit_text(
        text,
        reply_markup=get_gender_keyboard(lang),
        parse_mode="Markdown",
    )


@router.message(SeekerRegistration.waiting_budget)
async def process_custom_budget(message: Message, state: FSMContext):
    val = re.sub(r"\D", "", message.text)
    budget = int(val) if val else 120000
    await state.update_data(budget_max=budget)

    data = await state.get_data()
    lang = data.get("lang", "ru")

    await state.set_state(SeekerRegistration.waiting_gender)
    text = t("choose_gender", lang)
    await message.answer(
        text,
        reply_markup=get_gender_keyboard(lang),
        parse_mode="Markdown",
    )


@router.callback_query(SeekerRegistration.waiting_gender, F.data.startswith("gender:"))
async def process_express_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await callback.answer()

    data = await state.get_data()

    # Instant Save & Launch!
    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(
            session=session,
            telegram_id=callback.from_user.id,
            first_name=callback.from_user.first_name,
        )
        user.gender = gender

        await UserService.update_seeker_profile(
            session=session,
            user_id=user.id,
            data={
                "name": callback.from_user.first_name,
                "gender": gender,
                "city": DEFAULT_CITY,
                "districts": data.get("districts", ["Бостандыкский"]),
                "budget_max": data.get("budget_max", 120000),
                "move_in_date": "В ближайшее время",
                "housing_types": ["room", "spot", "sharing"],
                "smoking": "no",
                "pets": "no",
                "occupation": "student",
                "is_active": True,
            },
        )
        await session.commit()

    from app.bot.handlers.swipe import send_next_card
    await send_next_card(callback.message, callback.from_user.id, state)
