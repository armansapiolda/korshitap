"""Tinder-style card swiping with Kazakh & Russian support and minimalist aesthetic."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.bot_instance import get_bot
from app.bot.keyboards.districts import get_single_district_keyboard
from app.bot.keyboards.swipe import get_district_exhausted_keyboard, get_swipe_keyboard
from app.bot.notifications import notify_owner_about_applicant, send_mutual_match_celebration
from app.bot.states import SwipeState
from app.constants import HOUSING_TYPE_LABELS
from app.db.base import async_session_factory
from app.i18n import get_district_name, t
from app.matching.engine import matching_engine
from app.services.listing_service import ListingService
from app.services.match_service import MatchService
from app.services.search_service import SearchService
from app.services.user_service import UserService

router = Router(name="swipe_router")


async def send_next_card(
    target: Message,
    telegram_id: int,
    state: FSMContext,
    strict_district: bool = True,
    include_adjacent: bool = False,
    custom_districts: list = None,
):
    """Fetches and sends the next matching listing card in user's language."""
    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, telegram_id)
        lang = user.language or "ru"
        result = await matching_engine.get_next_listing_for_seeker(
            session=session,
            user_id=user.id,
            strict_district=strict_district,
            include_adjacent=include_adjacent,
            custom_districts=custom_districts,
        )

    status = result["status"]
    district_name = result["current_district"]
    localized_dist = get_district_name(district_name, lang)

    if status == "district_exhausted":
        await state.set_state(SwipeState.district_exhausted)
        await state.update_data(last_exhausted_district=district_name, lang=lang)

        if lang == "kz":
            text = (
                f"📍 **{localized_dist} бойынша қазірше нұсқалар аяқталды.**\n\n"
                "Көршілес аудандардан қараймыз ба?"
            )
        else:
            text = (
                f"📍 **В районе {localized_dist} пока закончились варианты.**\n\n"
                "Поискать в соседних районах Алматы?"
            )

        kb = get_district_exhausted_keyboard(district_name, lang)
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await target.answer(text, reply_markup=kb, parse_mode="Markdown")
        return

    if status == "all_exhausted":
        text = (
            "✨ **Барлық нұсқаларды қарап шықтың!**\n\n"
            "Жаңа хабарландыру шыққанда міндетті түрде хабарлаймын."
            if lang == "kz"
            else "✨ **Ты просмотрел все доступные варианты!**\n\n"
            "Как только появятся новые квартиры или соседи — я сразу напишу."
        )
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, parse_mode="Markdown")
        else:
            await target.answer(text, parse_mode="Markdown")
        return

    # Normal candidate card
    candidate = result["candidate"]
    lst = candidate.listing
    urgent_badge = "🔥 **ЖЕДЕЛ** " if (lst.is_urgent and lang == "kz") else ("🔥 **СРОЧНО** " if lst.is_urgent else "")

    if lang == "kz":
        housing_label = f"{lst.total_rooms} бөлмелі пәтер"
        card_text = (
            f"🏠 **{housing_label}**\n"
            f"📍 **{get_district_name(lst.district, lang)}** ({lst.address_landmark or 'Алматы'})\n"
            f"💰 **{lst.price_per_person:,} ₸/ай** (бір адамға)\n"
            f"🛏 Бос орын: **{lst.available_places}**\n"
            f"📅 Көшу: **{lst.move_in_date}** {urgent_badge}\n"
            f"👥 Тұрып жатыр: {lst.occupied_places} адам\n\n"
            f"✨ **Сәйкестік: {candidate.score}%**\n"
            f"💡 _{candidate.reasoning}_\n"
        )
    else:
        housing_label = HOUSING_TYPE_LABELS.get(lst.housing_type, f"{lst.total_rooms}-комнатная квартира")
        card_text = (
            f"🏠 **{housing_label}**\n"
            f"📍 **{lst.district} район** ({lst.address_landmark or 'Алматы'})\n"
            f"💰 **{lst.price_per_person:,} ₸/мес** с человека\n"
            f"🛏 Свободно: **{lst.available_places} мест(а)**\n"
            f"📅 Заселение: **{lst.move_in_date}** {urgent_badge}\n"
            f"👥 Уже живут: {lst.occupied_places} чел.\n\n"
            f"✨ **Совместимость: {candidate.score}%**\n"
            f"💡 _{candidate.reasoning}_\n"
        )

    kb = get_swipe_keyboard(lst.id, lang)

    if lst.photos and len(lst.photos) > 0:
        photo_id = lst.photos[0]
        try:
            if isinstance(target, CallbackQuery):
                await target.message.delete()
                await target.message.answer_photo(photo=photo_id, caption=card_text, reply_markup=kb, parse_mode="Markdown")
            else:
                await target.answer_photo(photo=photo_id, caption=card_text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            pass

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(card_text, reply_markup=kb, parse_mode="Markdown")
    else:
        await target.answer(card_text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("swipe_like:"))
async def cb_swipe_like(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split(":")[1])
    bot = get_bot()
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, callback.from_user.id)
        user = await UserService.get_or_create_user(session, callback.from_user.id)
        _, match = await MatchService.record_swipe(
            session=session,
            from_user_id=user.id,
            target_type="listing",
            target_id=listing_id,
            is_like=True,
        )
        if match:
            await session.commit()
            await send_mutual_match_celebration(bot, session, match.id)
        else:
            listing = await ListingService.get_listing_by_id(session, listing_id)
            if listing:
                await notify_owner_about_applicant(bot, session, user, listing)
            await session.commit()

    await callback.answer("❤️ Ұнады!" if lang == "kz" else "❤️ Подходит!")

    data = await state.get_data()
    strict = data.get("strict_district", True)
    adj = data.get("include_adjacent", False)
    custom = data.get("custom_districts", None)
    await send_next_card(callback, callback.from_user.id, state, strict_district=strict, include_adjacent=adj, custom_districts=custom)


@router.callback_query(F.data.startswith("swipe_pass:"))
async def cb_swipe_pass(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, callback.from_user.id)
        user = await UserService.get_or_create_user(session, callback.from_user.id)
        await MatchService.record_swipe(
            session=session,
            from_user_id=user.id,
            target_type="listing",
            target_id=listing_id,
            is_like=False,
        )
        await session.commit()

    await callback.answer("❌ Өткізілді" if lang == "kz" else "❌ Пропущено")

    data = await state.get_data()
    strict = data.get("strict_district", True)
    adj = data.get("include_adjacent", False)
    custom = data.get("custom_districts", None)
    await send_next_card(callback, callback.from_user.id, state, strict_district=strict, include_adjacent=adj, custom_districts=custom)


@router.callback_query(F.data.startswith("swipe_details:"))
async def cb_swipe_details(callback: CallbackQuery, state: FSMContext):
    listing_id = int(callback.data.split(":")[1])
    await callback.answer()

    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, callback.from_user.id)
        listing = await ListingService.get_listing_by_id(session, listing_id)

    if not listing:
        return

    if lang == "kz":
        details = (
            f"📋 **Пәтер туралы толығырақ:**\n\n"
            f"📍 Мекенжай: {listing.address_landmark or 'Алматы'}\n"
            f"💰 Депозит: {listing.deposit_amount:,} ₸\n"
            f"💡 Коммуналдық: {'Ішінде' if listing.utilities_included else 'Бөлек'}\n"
            f"🚭 Темекі: {'Рұқсат' if listing.smoking_allowed else 'Болмайды'}\n\n"
            f"📝 **Сипаттамасы:**\n_{listing.conditions_description or 'Жазылмаған'}_\n"
        )
    else:
        details = (
            f"📋 **Подробности о жилье:**\n\n"
            f"📍 Адрес: {listing.address_landmark or 'Алматы'}\n"
            f"💰 Депозит: {listing.deposit_amount:,} ₸\n"
            f"💡 Коммунальные: {'Включены' if listing.utilities_included else 'Отдельно'}\n"
            f"🚭 Курение: {'Разрешено' if listing.smoking_allowed else 'Запрещено'}\n\n"
            f"📝 **Условия:**\n_{listing.conditions_description or 'Не указаны'}_\n"
        )
    await callback.message.answer(details, parse_mode="Markdown")


# --- Exhaustion handlers ---

@router.callback_query(F.data == "exhaust_adjacent")
async def cb_exhaust_adjacent(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(strict_district=False, include_adjacent=True)
    msg = "🔎 Көршілес аудандардан іздеудемін..." if lang == "kz" else "🔎 Расширяю поиск на соседние районы..."
    await callback.message.edit_text(msg, parse_mode="Markdown")
    await send_next_card(callback, callback.from_user.id, state, strict_district=False, include_adjacent=True)


@router.callback_query(F.data == "exhaust_choose_other")
async def cb_exhaust_choose_other(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.set_state(SwipeState.choosing_new_district)
    title = "📍 Басқа аудан таңдаңыз:" if lang == "kz" else "📍 Выбери другой район:"
    await callback.message.edit_text(title, reply_markup=get_single_district_keyboard("exhaust_pick", lang))


@router.callback_query(SwipeState.choosing_new_district, F.data.startswith("exhaust_pick:"))
async def cb_exhaust_picked(callback: CallbackQuery, state: FSMContext):
    new_district = callback.data.split(":")[1]
    await callback.answer()
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(custom_districts=[new_district], strict_district=True, include_adjacent=False)
    msg = f"📍 {get_district_name(new_district, lang)} ауыстырылды..." if lang == "kz" else f"📍 Переключаю на {new_district} район..."
    await callback.message.edit_text(msg, parse_mode="Markdown")
    await send_next_card(callback, callback.from_user.id, state, strict_district=True, include_adjacent=False, custom_districts=[new_district])


@router.callback_query(F.data == "exhaust_subscribe")
async def cb_exhaust_subscribe(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    lang = data.get("lang", "ru")
    dist_name = data.get("last_exhausted_district", "Бостандыкский")

    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(session, callback.from_user.id)
        await SearchService.save_search_preference(
            session=session,
            user_id=user.id,
            districts=[dist_name],
        )
        await session.commit()

    text = (
        f"🔔 **Хабарламалар қосылды!**\n\n{get_district_name(dist_name, lang)} жаңа пәтер пайда болғанда хабарлаймын."
        if lang == "kz"
        else f"🔔 **Уведомления включены!**\n\nКак только в районе {dist_name} появится новый вариант — я сразу напишу."
    )
    await callback.message.edit_text(text, parse_mode="Markdown")
