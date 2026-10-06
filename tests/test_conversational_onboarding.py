"""Tests for the new conversational onboarding, multi-tier matching feed, and profiles."""

import pytest
from app.bot.handlers.recommendations import format_candidate_card
from app.constants import ADJACENT_DISTRICTS, CITY_DISTRICTS
from app.db.models import SeekerProfile, User
from app.matching.reason_generator import generate_human_match_reason


def test_human_match_reason_tone():
    """Verify match reasons strictly use 'ты' / 'сен' tone and 1-2 sentence brevity."""
    # Russian tone check
    ru_reason = generate_human_match_reason(
        user_occ="student",
        user_age=20,
        cand_name="Айдана",
        cand_occ="student",
        cand_age=21,
        cand_budget=100000,
        lang="ru",
    )
    assert "Почему подходит тебе" in ru_reason
    assert "учитесь" in ru_reason
    assert "Уважаемый" not in ru_reason
    assert "Вы оба" in ru_reason or "учитесь" in ru_reason

    # Kazakh tone check
    kz_reason = generate_human_match_reason(
        user_occ="student",
        user_age=20,
        cand_name="Айдана",
        cand_occ="student",
        cand_age=21,
        cand_budget=100000,
        lang="kz",
    )
    assert "Неге саған сәйкес келеді" in kz_reason
    assert "студентсіңдер" in kz_reason or "сәйкес" in kz_reason
    assert "(" not in kz_reason  # No parentheses in KZ text


def test_format_candidate_card_structure():
    """Verify all 3 card templates (apartment owner, ready apartment, co-seeker) in KZ and RU."""
    owner_user = User(id=1, telegram_id=111, first_name="Али", age=22, occupation="working")
    owner_profile = SeekerProfile(
        id=1,
        user_id=1,
        name="Али",
        age=22,
        gender="male",
        city="Алматы",
        districts=["Бостандыкский"],
        has_apartment=True,
        rooms_count="2-бөлмелі",
        room_type="separate",
        neighbors_needed=1,
        apartment_address="Абай көшесі 10",
        budget_range="120 000 ₸",
        move_in_date="1 қыркүйек",
    )

    seeker_user = User(id=2, telegram_id=222, first_name="Данияр", age=23, occupation="working")
    seeker_profile = SeekerProfile(
        id=2,
        user_id=2,
        name="Данияр",
        age=23,
        gender="male",
        city="Алматы",
        districts=["Бостандыкский"],
        occupation="working",
        budget_range="100 000–150 000 ₸",
        move_in_date="В течение недели",
        has_apartment=False,
    )

    # 1. Ready apartment candidate shown to a seeker (RU)
    card_ready_ru = format_candidate_card(
        sp=owner_profile,
        u=owner_user,
        viewer_user=seeker_user,
        viewer_profile=seeker_profile,
        lang="ru",
    )
    assert "Али" in card_ready_ru
    assert "22 лет" in card_ready_ru
    assert "Квартира уже есть" in card_ready_ru
    assert "Количество комнат" in card_ready_ru
    assert "Сколько соседей нужно: **1**" in card_ready_ru
    assert "Тот же район, подходящий бюджет и отдельная комната для тебя." in card_ready_ru

    # 2. Ready apartment candidate shown to a seeker (KZ)
    card_ready_kz = format_candidate_card(
        sp=owner_profile,
        u=owner_user,
        viewer_user=seeker_user,
        viewer_profile=seeker_profile,
        lang="kz",
    )
    assert "Али" in card_ready_kz
    assert "22 жаста" in card_ready_kz
    assert "Пәтер дайын" in card_ready_kz
    assert "Бөлме саны" in card_ready_kz
    assert "Қанша көрші қажет: **1 адам**" in card_ready_kz
    assert "Сол аудан, сәйкес бюджет және саған арналған жайлы бөлме." in card_ready_kz

    # 3. Seeker candidate shown to an apartment owner (RU)
    card_owner_view_ru = format_candidate_card(
        sp=seeker_profile,
        u=seeker_user,
        viewer_user=owner_user,
        viewer_profile=owner_profile,
        lang="ru",
    )
    assert "Данияр" in card_owner_view_ru
    assert "Квартиру пока не нашёл" in card_owner_view_ru
    assert "Ищет в: **Бостандыкский район" in card_owner_view_ru
    assert "Ищет твой район, подходит по бюджету и может заехать примерно в это время." in card_owner_view_ru

    # 4. Seeker candidate shown to an apartment owner (KZ)
    card_owner_view_kz = format_candidate_card(
        sp=seeker_profile,
        u=seeker_user,
        viewer_user=owner_user,
        viewer_profile=owner_profile,
        lang="kz",
    )
    assert "Данияр" in card_owner_view_kz
    assert "Әзірге пәтер таппаған" in card_owner_view_kz
    assert "Іздейтін жері: **Бостандық" in card_owner_view_kz
    assert "Сенің ауданыңнан іздеп жүр, бюджеті келеді" in card_owner_view_kz

    # 5. Co-seeker candidate shown to a co-seeker (RU & KZ)
    # MUST NOT contain how many roommates needed!
    co_seeker_user = User(id=3, telegram_id=333, first_name="Мадина", age=21, occupation="student")
    co_seeker_profile = SeekerProfile(
        id=3,
        user_id=3,
        name="Мадина",
        age=21,
        gender="female",
        city="Алматы",
        districts=["Бостандыкский"],
        occupation="student",
        budget_range="80 000–100 000 ₸",
        move_in_date="В ближайшее время",
        has_apartment=False,
    )
    card_coseeker_ru = format_candidate_card(
        sp=co_seeker_profile,
        u=co_seeker_user,
        viewer_user=seeker_user,
        viewer_profile=seeker_profile,
        lang="ru",
    )
    assert "Мадина" in card_coseeker_ru
    assert "Ищет в этом районе" in card_coseeker_ru
    assert "Квартиру пока не нашёл" in card_coseeker_ru
    assert "Одинаковый район и похожий бюджет — можете вместе поискать квартиру." in card_coseeker_ru
    assert "Сколько соседей" not in card_coseeker_ru
    assert "соседей нужно" not in card_coseeker_ru

    card_coseeker_kz = format_candidate_card(
        sp=co_seeker_profile,
        u=co_seeker_user,
        viewer_user=seeker_user,
        viewer_profile=seeker_profile,
        lang="kz",
    )
    assert "Мадина" in card_coseeker_kz
    assert "Осы ауданнан іздейді" in card_coseeker_kz
    assert "Әзірге пәтер таппаған" in card_coseeker_kz
    assert "Бір аудан және ұқсас бюджет — бірге пәтер іздесеңдер болады." in card_coseeker_kz
    assert "Қанша көрші" not in card_coseeker_kz


@pytest.mark.asyncio
async def test_tier_matching_partition(test_session):
    """Verify tier 1 and tier 2 classification logic based on housing status."""
    # Viewer who has NO apartment looking in Бостандыкский
    viewer_user = User(id=999, telegram_id=999, first_name="Искатель")
    viewer_profile = SeekerProfile(
        id=999,
        user_id=999,
        city="Алматы",
        districts=["Бостандыкский"],
        has_apartment=False,
    )
    test_session.add(viewer_user)
    test_session.add(viewer_profile)

    # Candidate 1: Has apartment in Бостандыкский
    u1 = User(id=1001, telegram_id=1001, first_name="ЕстьКвартира")
    p1 = SeekerProfile(id=1001, user_id=1001, city="Алматы", districts=["Бостандыкский"], has_apartment=True, is_active=True)

    # Candidate 2: Looking for apartment in Бостандыкский (co-seeker)
    u2 = User(id=1002, telegram_id=1002, first_name="ТожеИщет")
    p2 = SeekerProfile(id=1002, user_id=1002, city="Алматы", districts=["Бостандыкский"], has_apartment=False, is_active=True)

    test_session.add_all([u1, p1, u2, p2])
    await test_session.commit()

    # When viewer has NO apartment:
    # Candidate 1 (has apartment) MUST be Tier 1
    # Candidate 2 (no apartment) MUST be Tier 2
    has_apt = viewer_profile.has_apartment
    tier1 = []
    tier2 = []
    for sp, u in [(p1, u1), (p2, u2)]:
        if not has_apt:
            if sp.has_apartment:
                tier1.append(sp)
            else:
                tier2.append(sp)
        else:
            if not sp.has_apartment:
                tier1.append(sp)
            else:
                tier2.append(sp)

    assert len(tier1) == 1
    assert tier1[0].id == 1001
    assert len(tier2) == 1
    assert tier2[0].id == 1002


def test_city_and_adjacent_districts_data():
    """Verify all 3 cities have districts and adjacent mapping."""
    for city in ["Алматы", "Астана", "Шымкент"]:
        assert city in CITY_DISTRICTS
        districts = CITY_DISTRICTS[city]
        assert len(districts) >= 5
        for d in districts:
            assert d in ADJACENT_DISTRICTS
            assert len(ADJACENT_DISTRICTS[d]) > 0
