"""Handler for 'Кто ищет' section where owners browse seekers."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from sqlalchemy import select

from app.bot.bot_instance import get_bot
from app.bot.keyboards.reply import MENU_WHO_KZ, MENU_WHO_RU
from app.bot.keyboards.swipe import get_owner_swipe_keyboard
from app.bot.notifications import notify_seeker_about_owner_interest, send_mutual_match_celebration
from app.bot.states import OwnerBrowseState
from app.db.base import async_session_factory
from app.db.models import User
from app.matching.engine import matching_engine
from app.services.listing_service import ListingService
from app.services.match_service import MatchService
from app.services.user_service import UserService

router = Router(name="who_is_looking_router")


@router.message(F.text.in_([MENU_WHO_RU, MENU_WHO_KZ]))
async def menu_who_is_looking_click(message: Message, state: FSMContext):
    """Triggered from bottom reply keyboard: '👥 Кто ищет'."""
    await state.clear()

    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, message.from_user.id)
        owner_listings = await ListingService.get_owner_listings(session, user.id)

        if not owner_listings:
            await message.answer(
                "ℹ️ **У вас пока нет опубликованных объявлений.**\n\n"
                "Чтобы просматривать подходящих соискателей жилья в вашем районе, "
                "сначала добавьте объявление в разделе **➕ Создать**.",
                parse_mode="Markdown",
            )
            return

        active_listing = owner_listings[0]
        candidates = await matching_engine.get_seekers_for_owner_listing(
            session=session,
            listing_id=active_listing.id,
        )

    if not candidates:
        await message.answer(
            "⏳ **Сейчас нет новых соискателей в вашем районе.**\n"
            "Как только появятся новые анкеты, мы уведомим вас!",
            parse_mode="Markdown",
        )
        return

    # Store candidates queue in state
    cands_data = [
        {
            "user_id": c["user"].id,
            "name": c["profile"].name or c["user"].first_name or "Соискатель",
            "age": c["profile"].age or c["user"].age or 21,
            "districts": ", ".join(c["profile"].districts or ["Алматы"]),
            "budget_max": c["profile"].budget_max or 100000,
            "move_in_date": c["profile"].move_in_date or "В ближайшее время",
            "occupation": "Студент" if c["profile"].occupation == "student" else "Работает",
            "smoking": "Курит" if c["profile"].smoking == "yes" else "Не курит",
            "score": c["score"],
            "bio": c["profile"].raw_bio or "",
        }
        for c in candidates
    ]
    await state.set_state(OwnerBrowseState.browsing_seekers)
    await state.update_data(candidates_queue=cands_data, current_index=0)

    await send_next_seeker_card(message, state)


async def send_next_seeker_card(target: Message, state: FSMContext):
    data = await state.get_data()
    queue = data.get("candidates_queue", [])
    idx = data.get("current_index", 0)

    if idx >= len(queue):
        text = "✨ **Вы просмотрели всех актуальных соискателей в этом районе!**"
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, parse_mode="Markdown")
        else:
            await target.answer(text, parse_mode="Markdown")
        return

    cand = queue[idx]
    card_text = (
        f"👤 **{cand['name']}, {cand['age']}**\n"
        f"📍 Ищет район: **{cand['districts']}**\n"
        f"💰 Бюджет: **до {cand['budget_max']:,} ₸**\n"
        f"📅 Заселение: **{cand['move_in_date']}**\n"
        f"🎓 {cand['occupation']}\n"
        f"🚭 {cand['smoking']}\n"
    )
    if cand["bio"]:
        card_text += f"💬 _{cand['bio']}_\n"
    card_text += f"\n✨ **Совместимость с вашим жильём: {cand['score']}%**"

    kb = get_owner_swipe_keyboard(cand["user_id"])

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(card_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.answer(card_text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("owner_like:"))
async def cb_owner_like(callback: CallbackQuery, state: FSMContext):
    seeker_user_id = int(callback.data.split(":")[1])
    bot = get_bot()

    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, callback.from_user.id)
        lang = user.language or "ru"
        _, match = await MatchService.record_swipe(
            session=session,
            from_user_id=user.id,
            target_type="seeker",
            target_id=seeker_user_id,
            is_like=True,
        )
        if match:
            await session.commit()
            await send_mutual_match_celebration(bot, session, match.id)
        else:
            owner_listings = await ListingService.get_owner_listings(session, user.id)
            if owner_listings:
                s_stmt = select(User).where(User.id == seeker_user_id)
                s_res = await session.execute(s_stmt)
                seeker_user = s_res.scalar_one_or_none()
                if seeker_user:
                    await notify_seeker_about_owner_interest(bot, session, user, owner_listings[0], seeker_user)
            await session.commit()

    await callback.answer("❤️ Ұнады!" if lang == "kz" else "❤️ Подходит!")

    data = await state.get_data()
    idx = data.get("current_index", 0) + 1
    await state.update_data(current_index=idx)
    await send_next_seeker_card(callback, state)


@router.callback_query(F.data.startswith("owner_pass:"))
async def cb_owner_pass(callback: CallbackQuery, state: FSMContext):
    seeker_user_id = int(callback.data.split(":")[1])
    await callback.answer("❌ Пропущено")

    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, callback.from_user.id)
        await MatchService.record_swipe(
            session=session,
            from_user_id=user.id,
            target_type="seeker",
            target_id=seeker_user_id,
            is_like=False,
        )
        await session.commit()

    data = await state.get_data()
    idx = data.get("current_index", 0) + 1
    await state.update_data(current_index=idx)
    await send_next_seeker_card(callback, state)
