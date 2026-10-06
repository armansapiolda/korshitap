"""Instant recommendations feed with 4-tier match hierarchy:
- Tier 1: Same district + target housing status (has apartment vs seeking)
- Tier 2: Same district + co-seekers who can team up
- Tier 3: Adjacent districts expansion
- Tier 4: Zero match fallback with instant notification subscription
"""

from __future__ import annotations

import random
from typing import Optional, Union
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.ai.factory import get_ai_provider
from app.bot.keyboards.reply import MENU_SEARCH_KZ, MENU_SEARCH_RU
from app.bot.notifications import get_chat_url
from app.constants import ADJACENT_DISTRICTS, DEFAULT_CITY, LISTING_STATUS_ACTIVE
from app.db.base import async_session_factory
from app.db.models import Listing, SeekerProfile, User
from app.i18n import get_district_name
from app.matching.cold_search import ColdCandidate, perform_cold_search
from app.matching.reason_generator import generate_human_match_reason
from app.services.candidate_event_service import KIND_SHOWN, CandidateEventService
from app.services.user_service import UserService

router = Router(name="recommendations_router")


def format_card_for_apartment_owner(
    sp: SeekerProfile,
    u: User,
    lang: str = "kz",
    custom_reason: Optional[str] = None,
    show_reason: bool = True,
) -> str:
    """Format card when viewer already HAS an apartment.
    Shows a person seeking an apartment in viewer's district.
    """
    c_gender = sp.gender or u.gender or "male"
    emoji = "👩" if c_gender == "female" else "👨"
    name = sp.name or u.first_name or ("Көрші" if lang == "kz" else "Сосед")
    age = sp.age or u.age or 22
    district = sp.districts[0] if sp.districts else "Бостандыкский"
    dist_name = get_district_name(district, lang)
    budget = sp.budget_range or (f"{sp.budget_max:,} ₸" if sp.budget_max else ("Келісімді" if lang == "kz" else "По договорённости"))
    move_date = sp.move_in_date or ("Жақын арада" if lang == "kz" else "В ближайшее время")

    occ = sp.occupation or getattr(u, "occupation", "working") or "working"
    if lang == "kz":
        occ_label = "Студент 🎓" if occ in ("student", "учусь") else ("Жұмыс істейді 💼" if occ in ("working", "работает") else "Жұмыс істейді және оқиды 💼🎓")
        reason_block = ""
        if show_reason:
            reason_text = custom_reason or "Сенің ауданыңнан іздеп жүр, бюджеті келеді және шамамен осы уақытта көше алады."
            reason_block = f"\n\n💡 **Неге сәйкес келеді:**\n{reason_text}"
        return (
            f"{emoji} **{name}**, {age} жаста\n"
            f"📍 Іздейтін жері: **{dist_name}**\n"
            f"🔎 **Әзірге пәтер таппаған**\n\n"
            f"💰 Бюджеті: **{budget}**\n"
            f"📅 Көшу мерзімі: **{move_date}**\n"
            f"💼 Қызметі: **{occ_label}**"
            f"{reason_block}"
        )
    else:
        occ_label = "Студент 🎓" if occ in ("student", "учусь") else ("Работает 💼" if occ in ("working", "работает") else "Работает и учится 💼🎓")
        reason_block = ""
        if show_reason:
            reason_text = custom_reason or "Ищет твой район, подходит по бюджету и может заехать примерно в это время."
            reason_block = f"\n\n💡 **Почему подходит тебе:**\n{reason_text}"
        return (
            f"{emoji} **{name}**, {age} лет\n"
            f"📍 Ищет в: **{dist_name} районе**\n"
            f"🔎 **Квартиру пока не нашёл**\n\n"
            f"💰 Бюджет: **{budget}**\n"
            f"📅 Когда хочет заехать: **{move_date}**\n"
            f"💼 Занятость: **{occ_label}**"
            f"{reason_block}"
        )


def format_card_for_ready_apartment(
    sp: SeekerProfile,
    u: User,
    lang: str = "kz",
    custom_reason: Optional[str] = None,
    show_reason: bool = True,
) -> str:
    """Format card when candidate ALREADY HAS an apartment.
    Shows ready apartment details for a seeker.
    """
    c_gender = sp.gender or u.gender or "male"
    emoji = "👩" if c_gender == "female" else "👨"
    name = sp.name or u.first_name or ("Көрші" if lang == "kz" else "Сосед")
    age = sp.age or u.age or 22
    district = sp.districts[0] if sp.districts else "Бостандыкский"
    dist_name = get_district_name(district, lang)
    rooms = sp.rooms_count or ("2-бөлмелі" if lang == "kz" else "2-комнатная")

    if lang == "kz":
        rtype_label = "Жеке бөлме 🛏" if sp.room_type == "separate" else "Ортақ бөлме (бір бөлмеде) 👥"
        address_str = sp.apartment_address or dist_name
        budget = sp.budget_range or (f"{sp.budget_max:,} ₸" if sp.budget_max else "Келісімді")
        move_date = sp.move_in_date or "Жақын арада"
        need_cnt = sp.neighbors_needed or 1
        reason_block = ""
        if show_reason:
            reason_text = custom_reason or "Сол аудан, сәйкес бюджет және саған арналған жайлы бөлме."
            reason_block = f"\n\n💡 **Неге сәйкес келеді:**\n{reason_text}"

        return (
            f"{emoji} **{name}**, {age} жаста\n"
            f"📍 Ауданы: **{dist_name}**\n"
            f"🏠 **Пәтер дайын**\n"
            f"🏠 Бөлме саны: **{rooms}**\n"
            f"🛏 **{rtype_label}**\n"
            f"📍 Мекенжайы: **{address_str}**\n"
            f"💰 Құны: **{budget}**\n"
            f"📅 Қашан көшуге болады: **{move_date}**\n"
            f"👥 Қанша көрші қажет: **{need_cnt} адам**"
            f"{reason_block}"
        )
    else:
        rtype_label = "Отдельная комната 🛏" if sp.room_type == "separate" else "Общая комната (вместе) 👥"
        address_str = sp.apartment_address or dist_name
        budget = sp.budget_range or (f"{sp.budget_max:,} ₸" if sp.budget_max else "По договорённости")
        move_date = sp.move_in_date or "В ближайшее время"
        need_cnt = sp.neighbors_needed or 1
        reason_block = ""
        if show_reason:
            reason_text = custom_reason or "Тот же район, подходящий бюджет и отдельная комната для тебя."
            reason_block = f"\n\n💡 **Почему подходит тебе:**\n{reason_text}"

        return (
            f"{emoji} **{name}**, {age} лет\n"
            f"📍 Район: **{dist_name}**\n"
            f"🏠 **Квартира уже есть**\n"
            f"🏠 Количество комнат: **{rooms}**\n"
            f"🛏 **{rtype_label}**\n"
            f"📍 Адрес: **{address_str}**\n"
            f"💰 Стоимость: **{budget}**\n"
            f"📅 Когда можно заехать: **{move_date}**\n"
            f"👥 Сколько соседей нужно: **{need_cnt}**"
            f"{reason_block}"
        )


def format_card_for_coseeker(
    sp: SeekerProfile,
    u: User,
    lang: str = "kz",
    custom_reason: Optional[str] = None,
    show_reason: bool = True,
) -> str:
    """Format card for co-seeker (looking together).
    NEVER show neighbors needed!
    """
    c_gender = sp.gender or u.gender or "male"
    emoji = "👩" if c_gender == "female" else "👨"
    name = sp.name or u.first_name or ("Көрші" if lang == "kz" else "Сосед")
    age = sp.age or u.age or 22
    district = sp.districts[0] if sp.districts else "Бостандыкский"
    dist_name = get_district_name(district, lang)
    budget = sp.budget_range or (f"{sp.budget_max:,} ₸" if sp.budget_max else ("Келісімді" if lang == "kz" else "По договорённости"))
    move_date = sp.move_in_date or ("Жақын арада" if lang == "kz" else "В ближайшее время")

    occ = sp.occupation or getattr(u, "occupation", "working") or "working"
    if lang == "kz":
        occ_label = "Студент 🎓" if occ in ("student", "учусь") else ("Жұмыс істейді 💼" if occ in ("working", "работает") else "Жұмыс істейді және оқиды 💼🎓")
        reason_block = ""
        if show_reason:
            reason_text = custom_reason or "Бір аудан және ұқсас бюджет — бірге пәтер іздесеңдер болады."
            reason_block = f"\n\n💡 **Неге сәйкес келеді:**\n{reason_text}"
        return (
            f"{emoji} **{name}**, {age} жаста\n"
            f"📍 Осы ауданнан іздейді: **{dist_name}**\n"
            f"🔎 **Әзірге пәтер таппаған**\n\n"
            f"💰 Бюджеті: **{budget}**\n"
            f"📅 Көшу мерзімі: **{move_date}**\n"
            f"💼 Қызметі: **{occ_label}**"
            f"{reason_block}"
        )
    else:
        occ_label = "Студент 🎓" if occ in ("student", "учусь") else ("Работает 💼" if occ in ("working", "работает") else "Работает и учится 💼🎓")
        reason_block = ""
        if show_reason:
            reason_text = custom_reason or "Одинаковый район и похожий бюджет — можете вместе поискать квартиру."
            reason_block = f"\n\n💡 **Почему подходит тебе:**\n{reason_text}"
        return (
            f"{emoji} **{name}**, {age} лет\n"
            f"📍 Ищет в этом районе: **{dist_name}**\n"
            f"🔎 **Квартиру пока не нашёл**\n\n"
            f"💰 Бюджет: **{budget}**\n"
            f"📅 Когда хочет заехать: **{move_date}**\n"
            f"💼 Занятость: **{occ_label}**"
            f"{reason_block}"
        )


def format_candidate_card(
    sp: SeekerProfile,
    u: User,
    viewer_user: User,
    viewer_profile: Optional[SeekerProfile],
    lang: str = "kz",
    criteria: Optional[dict] = None,
    custom_reason: Optional[str] = None,
    show_reason: bool = True,
) -> str:
    """Unified dispatcher for candidate card formatting."""
    viewer_has_apt = bool(viewer_profile and viewer_profile.has_apartment)
    cand_has_apt = bool(sp.has_apartment)

    if viewer_has_apt:
        return format_card_for_apartment_owner(sp, u, lang=lang, custom_reason=custom_reason, show_reason=show_reason)
    else:
        if cand_has_apt:
            return format_card_for_ready_apartment(sp, u, lang=lang, custom_reason=custom_reason, show_reason=show_reason)
        else:
            return format_card_for_coseeker(sp, u, lang=lang, custom_reason=custom_reason, show_reason=show_reason)


async def show_instant_recommendations(
    event: Union[Message, CallbackQuery],
    user_id: int,
    district_filter: Optional[str] = None,
    show_adjacent: bool = False,
):
    """Present matching candidates with 2-stage architecture:
    Stage 1: Cold factual search (strict verified data matching).
    Stage 2: AI comparative ranking & individualized human explanations via Gemini Vertex AI.
    """
    send_msg = event.answer if isinstance(event, Message) else event.message.answer

    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, user_id)
        if not user:
            user = await UserService.get_or_create_user(session, user_id)

        lang = user.language or "kz"
        my_prof = (
            await session.execute(
                select(SeekerProfile).where(SeekerProfile.user_id == user.id)
            )
        ).scalar_one_or_none()

        my_city = (my_prof.city if my_prof and my_prof.city else getattr(user, "city", None)) or DEFAULT_CITY
        my_districts = (my_prof.districts if my_prof and my_prof.districts else [])
        my_district = district_filter or (my_districts[0] if my_districts else "Бостандыкский")
        dist_name = get_district_name(my_district, lang)
        user_pref_gender = getattr(user, "preferred_gender", None) or (my_prof.preferred_gender if my_prof else None) or "any"

        # Owner's criteria if any
        my_listing = (
            await session.execute(
                select(Listing).where(Listing.owner_id == user.id).order_by(Listing.id.desc())
            )
        ).scalars().first()
        my_criteria = my_listing.neighbor_criteria if my_listing and my_listing.neighbor_criteria else {}
        has_apt = bool(my_prof and my_prof.has_apartment) or bool(
            my_listing and my_listing.status == LISTING_STATUS_ACTIVE and (my_listing.available_places or 0) > 0
        )
        if my_listing and my_listing.preferred_gender and my_listing.preferred_gender != "any":
            user_pref_gender = my_listing.preferred_gender

        # 1. STAGE 1: COLD FACTUAL SEARCH
        primary_cands, secondary_cands = await perform_cold_search(
            session=session,
            viewer_user=user,
            viewer_profile=my_prof,
            district_filter=my_district,
            allow_adjacent=show_adjacent,
        )

        # Skip people this user has already seen in earlier recommendations
        shown_ids = await CandidateEventService.get_candidate_ids(session, user.id, KIND_SHOWN)

    found_total = len(primary_cands) + len(secondary_cands)
    primary_cands = [c for c in primary_cands if c.user.id not in shown_ids]
    secondary_cands = [c for c in secondary_cands if c.user.id not in shown_ids]

    # Candidate selection logic based on housing status:
    # If viewer has apartment: primary_cands are seekers without apartments.
    # If viewer does not have apartment:
    #   primary_cands = ready apartment candidates
    #   secondary_cands = co-seekers looking in the same district
    # If ready apartments are fewer than 4, supplement with co-seekers to give good options.
    if has_apt:
        pool = primary_cands[:8]
    else:
        if len(primary_cands) >= 4:
            pool = primary_cands[:6]
        else:
            needed = 6 - len(primary_cands)
            pool = primary_cands + secondary_cands[:needed]

    btn_chat_label = "💬 Сөйлесу" if lang == "kz" else "💬 Написать"

    # Everyone matching was already shown earlier
    if not pool and found_total > 0:
        seen_text = (
            "👀 **Саған сәйкес келетін адамдардың барлығын көрдің.**\n\n"
            "Жаңа адам тіркелгенде хабарлаймын. Тізімді басынан қайта көрсетейін бе?"
            if lang == "kz"
            else
            "👀 **Ты уже посмотрел всех подходящих людей.**\n\n"
            "Когда появится кто-то новый, я сообщу. Показать список заново?"
        )
        reset_cb = f"rec_reset:{my_district}:{1 if show_adjacent else 0}"
        btns = [
            [InlineKeyboardButton(text="🔁 Қайта көрсету" if lang == "kz" else "🔁 Показать заново", callback_data=reset_cb)],
            [
                InlineKeyboardButton(
                    text="🔔 Хабарламаларды қосу" if lang == "kz" else "🔔 Включить уведомления",
                    callback_data="toggle_notif:enable",
                )
            ],
        ]
        if ADJACENT_DISTRICTS.get(my_district) and not show_adjacent:
            btns.append([
                InlineKeyboardButton(
                    text="🏘 Көршілес аудандарды көрсету" if lang == "kz" else "🏘 Показать соседние районы",
                    callback_data=f"rec_adjacent:{my_district}",
                )
            ])
        btns.append([
            InlineKeyboardButton(
                text="📍 Басқа аудандарды қарау" if lang == "kz" else "📍 Смотреть другие районы",
                callback_data="dist_filter:all",
            )
        ])
        await send_msg(seen_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="Markdown")
        return

    # Zero candidates fallback
    if not pool:
        if show_adjacent:
            no_text = (
                "🔍 **Көршілес аудандарда да әзірге кандидаттар жоқ.**\n\n"
                "Бірақ сәйкес келетін адам тіркелген бойда мен саған хабарлаймын."
                if lang == "kz"
                else
                "🔍 **В соседних районах тоже пока нет кандидатов.**\n\n"
                "Но как только появится человек, который тебе подходит, я сообщу."
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔔 Хабарламаларды қосу" if lang == "kz" else "🔔 Включить уведомления",
                            callback_data="toggle_notif:enable",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📍 Райондар бойынша" if lang == "kz" else "📍 Посмотреть по районам",
                            callback_data="dist_filter:all",
                        )
                    ],
                ]
            )
        else:
            no_text = (
                f"🔍 **{dist_name} ауданында әзірге саған сәйкес келетін адамдар табылмады.**\n\n"
                "Бірақ жаңа адам тіркелгенде мен саған бірден хабарлаймын! Көршілес аудандарды немесе басқа аудандарды қарап көре аласың 👇"
                if lang == "kz"
                else
                f"🔍 **В {dist_name} районе пока не нашлось подходящих людей.**\n\n"
                "Но как только появится подходящий человек, я сразу сообщу! Можешь посмотреть соседние районы или выбрать другой 👇"
            )
            adj_districts = ADJACENT_DISTRICTS.get(my_district, [])
            btns = [
                [
                    InlineKeyboardButton(
                        text="🔔 Хабарламаларды қосу" if lang == "kz" else "🔔 Включить уведомления",
                        callback_data="toggle_notif:enable",
                    )
                ]
            ]
            if adj_districts:
                btns.append([
                    InlineKeyboardButton(
                        text="🏘 Көршілес аудандарды көрсету" if lang == "kz" else "🏘 Показать соседние районы",
                        callback_data=f"rec_adjacent:{my_district}",
                    )
                ])
            btns.append([
                InlineKeyboardButton(
                    text="📍 Басқа аудандарды қарау" if lang == "kz" else "📍 Смотреть другие районы",
                    callback_data="dist_filter:all",
                )
            ])
            kb = InlineKeyboardMarkup(inline_keyboard=btns)

        await send_msg(no_text, reply_markup=kb, parse_mode="Markdown")
        return

    # 2. STAGE 2: AI RANKING (Gemini 2.5 Flash on Vertex AI)
    viewer_dict = {
        "user_id": user.id,
        "name": user.first_name or ("Көрші" if lang == "kz" else "Сосед"),
        "age": user.age or (my_prof.age if my_prof else 22),
        "gender": (my_prof.gender if my_prof else None) or user.gender or "not_specified",
        "preferred_gender": user_pref_gender,
        "city": my_city,
        "target_district": my_district,
        "has_apartment": has_apt,
        "budget": (my_prof.budget_max if my_prof and my_prof.budget_max else 120000),
        "budget_range": (my_prof.budget_range if my_prof else None),
        "move_in_date": (my_prof.move_in_date if my_prof and my_prof.move_in_date else "Жақын арада"),
        "occupation": (getattr(my_prof, "occupation", None) if my_prof else None) or getattr(user, "occupation", "working"),
        "about_self": (my_prof.about_self_desc if my_prof else "") or (my_prof.raw_bio if my_prof else ""),
        "ideal_neighbor": (my_prof.ideal_neighbor_desc if my_prof else "") or (my_prof.neighbor_preferences if my_prof else ""),
        "preferred_room_type": my_prof.preferred_room_type if my_prof else None,
        "lifestyle_criteria": (my_prof.neighbor_criteria if my_prof and my_prof.neighbor_criteria else my_criteria) or {},
    }

    candidates_dict = [c.to_ai_dict() for c in pool]
    ai = get_ai_provider()
    ranking_res = await ai.rank_candidates(viewer_dict, candidates_dict, lang=lang)

    # Reorder candidates according to AI ranking & attach individualized explanations
    cand_by_id = {c.user.id: c for c in pool}
    ranked_cards_data: list[tuple[ColdCandidate, Optional[str]]] = []
    seen_ids = set()

    if ranking_res and ranking_res.candidates:
        sorted_items = sorted(ranking_res.candidates, key=lambda x: x.rank_order)
        for item in sorted_items:
            cand = cand_by_id.get(item.candidate_user_id)
            if cand and cand.user.id not in seen_ids:
                seen_ids.add(cand.user.id)
                ranked_cards_data.append((cand, item.human_reason))

    # Append any candidates not explicitly in ranking result (e.g. if partial)
    for cand in pool:
        if cand.user.id not in seen_ids:
            seen_ids.add(cand.user.id)
            ranked_cards_data.append((cand, None))

    # Telegram Header
    if show_adjacent:
        header_text = (
            "✨ **Көршілес аудандардан саған сәйкес келетін адамдарды тауып, ең қолайлысынан бастап реттеп шықтық 👇**"
            if lang == "kz"
            else
            "✨ **Мы нашли подходящих людей в соседних районах и расположили их от наиболее подходящего к менее подходящему 👇**"
        )
    else:
        header_text = (
            "✨ **Міне, саған сәйкес келетін адамдарды тауып, ең қолайлысынан бастап реттеп шықтық 👇**"
            if lang == "kz"
            else
            "✨ **Мы нашли подходящих людей и расположили их от наиболее подходящего к менее подходящему 👇**"
        )
    await send_msg(header_text, parse_mode="Markdown")

    # Send candidate cards with individualized reasons
    shown_cards = ranked_cards_data[:5]
    async with async_session_factory() as session:
        await CandidateEventService.record(session, user.id, [c.user.id for c, _ in shown_cards], KIND_SHOWN)
        await session.commit()

    for cand, reason in shown_cards:
        card_text = format_candidate_card(
            cand.profile,
            cand.user,
            user,
            my_prof,
            lang=lang,
            criteria=my_criteria,
            custom_reason=reason,
        )
        chat_url = get_chat_url(cand.user)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=btn_chat_label, url=chat_url)]]
        )
        await send_msg(card_text, reply_markup=kb, parse_mode="Markdown")

    # Footer navigation
    adj_districts = ADJACENT_DISTRICTS.get(my_district, [])
    footer_buttons = [
        [
            InlineKeyboardButton(
                text="🔄 Тағы көрсету" if lang == "kz" else "🔄 Показать ещё",
                callback_data="rec_refresh",
            )
        ],
    ]
    if adj_districts and not show_adjacent:
        footer_buttons.append([
            InlineKeyboardButton(
                text="🏘 Көршілес аудандарды көрсету" if lang == "kz" else "🏘 Показать соседние районы",
                callback_data=f"rec_adjacent:{my_district}",
            )
        ])
    footer_buttons.append([
        InlineKeyboardButton(
            text="📍 Басқа аудандарды қарау" if lang == "kz" else "📍 Смотреть другие районы",
            callback_data="dist_filter:all",
        )
    ])
    footer_text = (
        "✨ Ұнаған адамға **«Сөйлесу»** батырмасын басып, бірден Telegram-да жаза аласың! 💬"
        if lang == "kz"
        else
        "✨ Нажимай **«Написать»** у понравившегося соседа и сразу пиши ему в Telegram! 💬"
    )
    await send_msg(
        footer_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=footer_buttons),
        parse_mode="Markdown",
    )


@router.message(
    StateFilter("*"),
    F.text.in_([
        MENU_SEARCH_RU,
        MENU_SEARCH_KZ,
        "🔍 Найти соседа 👥",
        "🔍 Көрші табу 👥",
        "🔍 Поиск",
        "🔍 Іздеу",
        "/search",
        "/find",
    ]),
)
async def cmd_recommendations(message: Message, state: FSMContext):
    """Main trigger for roommate recommendations."""
    await state.clear()
    await show_instant_recommendations(message, message.from_user.id)


@router.callback_query(F.data == "rec_refresh")
async def cb_rec_refresh(callback: CallbackQuery):
    """Refresh recommendations."""
    await callback.answer()
    await show_instant_recommendations(callback, callback.from_user.id)


@router.callback_query(F.data.startswith("rec_adjacent:"))
async def cb_rec_adjacent(callback: CallbackQuery):
    """Show adjacent districts recommendations."""
    await callback.answer()
    district = callback.data.split(":")[1]
    await show_instant_recommendations(callback, callback.from_user.id, district_filter=district, show_adjacent=True)


@router.callback_query(F.data.startswith("rec_reset:"))
async def cb_rec_reset(callback: CallbackQuery):
    """Forget already shown candidates and show the list from the start."""
    await callback.answer()
    _, district, adjacent = callback.data.split(":")
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        if user:
            await CandidateEventService.reset(session, user.id, KIND_SHOWN)
            await session.commit()
    await show_instant_recommendations(
        callback,
        callback.from_user.id,
        district_filter=district,
        show_adjacent=adjacent == "1",
    )


@router.callback_query(F.data.startswith("toggle_notif:"))
async def cb_toggle_notif(callback: CallbackQuery):
    """Enable notifications for new matching roommates."""
    async with async_session_factory() as session:
        user = await UserService.get_user_by_telegram_id(session, callback.from_user.id)
        lang = user.language if user and user.language else "ru"
        profile = await UserService.get_or_create_seeker_profile(session, user.id)
        profile.notifications_enabled = True
        await session.commit()

    alert_text = (
        "Хабарламалар қосылды! Жаңа көрші шыққанда хабарлаймын 🔔✨"
        if lang == "kz"
        else
        "Уведомления включены! Я напишу, как только появится подходящий сосед 🔔✨"
    )
    await callback.answer(alert_text, show_alert=True)
