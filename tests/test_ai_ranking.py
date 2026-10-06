"""Tests for Stage 1 (Cold Factual Search) & Stage 2 (AI Ranking & Explanations)."""

import pytest
from app.ai.base import AIRankingResult
from app.ai.mock_provider import MockAIProvider
from app.bot.handlers.recommendations import (
    format_card_for_apartment_owner,
    format_card_for_coseeker,
    format_card_for_ready_apartment,
)
from app.db.models import SeekerProfile, User
from app.matching.cold_search import perform_cold_search


@pytest.mark.asyncio
async def test_cold_search_seeker_without_apartment(test_session):
    """Test that a seeker without an apartment gets ready apartment candidates first, then co-seekers."""
    # Create test seeker looking in Bostandykskiy
    viewer = User(
        id=999901,
        telegram_id=999901,
        first_name="Ернар",
        gender="male",
        preferred_gender="male",
    )
    test_session.add(viewer)
    await test_session.flush()

    profile = SeekerProfile(
        user_id=viewer.id,
        name="Ернар",
        gender="male",
        preferred_gender="male",
        city="Алматы",
        districts=["Бостандыкский"],
        has_apartment=False,
        budget_max=120000,
        move_in_date="15 қыркүйек",
        is_active=True,
    )
    test_session.add(profile)
    await test_session.flush()

    # Create test candidates: one with ready apartment, one coseeker
    cand_owner_user = User(
        id=999910,
        telegram_id=999910,
        first_name="Асет",
        gender="male",
        preferred_gender="male",
    )
    test_session.add(cand_owner_user)
    await test_session.flush()

    cand_owner_profile = SeekerProfile(
        user_id=cand_owner_user.id,
        name="Асет",
        gender="male",
        preferred_gender="male",
        city="Алматы",
        districts=["Бостандыкский"],
        has_apartment=True,
        budget_max=100000,
        is_active=True,
    )
    test_session.add(cand_owner_profile)

    cand_seeker_user = User(
        id=999911,
        telegram_id=999911,
        first_name="Данияр",
        gender="male",
        preferred_gender="male",
    )
    test_session.add(cand_seeker_user)
    await test_session.flush()

    cand_seeker_profile = SeekerProfile(
        user_id=cand_seeker_user.id,
        name="Данияр",
        gender="male",
        preferred_gender="male",
        city="Алматы",
        districts=["Бостандыкский"],
        has_apartment=False,
        budget_max=110000,
        is_active=True,
    )
    test_session.add(cand_seeker_profile)
    await test_session.commit()

    primary, secondary = await perform_cold_search(
        session=test_session,
        viewer_user=viewer,
        viewer_profile=profile,
        district_filter="Бостандыкский",
        allow_adjacent=False,
    )

    # Primary candidates must have ready apartments
    assert len(primary) > 0
    for cand in primary:
        assert cand.is_ready_apartment is True
        assert cand.district == "Бостандыкский"
        assert cand.user.id != viewer.id

    # Secondary candidates must be co-seekers without apartment
    assert len(secondary) > 0
    for cand in secondary:
        assert cand.is_ready_apartment is False
        assert cand.district == "Бостандыкский"
        assert cand.user.id != viewer.id


@pytest.mark.asyncio
async def test_cold_search_apartment_owner(test_session):
    """Test that an owner with an apartment gets seekers without apartments."""
    viewer = User(
        id=999902,
        telegram_id=999902,
        first_name="Айжан",
        gender="female",
        preferred_gender="female",
    )
    test_session.add(viewer)
    await test_session.flush()

    profile = SeekerProfile(
        user_id=viewer.id,
        name="Айжан",
        gender="female",
        preferred_gender="female",
        city="Алматы",
        districts=["Алмалинский"],
        has_apartment=True,
        budget_max=150000,
        is_active=True,
    )
    test_session.add(profile)

    # A seeker who certainly fits (seed data is random and may not contain one)
    cand_user = User(id=999920, telegram_id=999920, first_name="Аружан", gender="female", preferred_gender="female")
    test_session.add(cand_user)
    await test_session.flush()
    test_session.add(SeekerProfile(
        user_id=cand_user.id,
        name="Аружан",
        gender="female",
        preferred_gender="female",
        city="Алматы",
        districts=["Алмалинский"],
        has_apartment=False,
        budget_max=150000,
        is_active=True,
    ))
    await test_session.commit()

    primary, secondary = await perform_cold_search(
        session=test_session,
        viewer_user=viewer,
        viewer_profile=profile,
        district_filter="Алмалинский",
        allow_adjacent=False,
    )

    # All primary candidates must be seekers without an apartment
    assert len(primary) > 0
    for cand in primary:
        assert cand.is_ready_apartment is False
        assert cand.district == "Алмалинский"
        assert cand.user.id != viewer.id

    # Secondary must be empty for apartment owners
    assert secondary == []


@pytest.mark.asyncio
async def test_mock_ai_ranking_generates_natural_reasons():
    """Test AI ranking fallback produces structured output and human explanations without jargon."""
    ai = MockAIProvider()

    viewer = {
        "user_id": 100,
        "name": "Азамат",
        "age": 23,
        "gender": "male",
        "city": "Алматы",
        "target_district": "Бостандыкский",
        "has_apartment": False,
        "budget": 100000,
        "move_in_date": "10 қыркүйек",
    }

    candidates = [
        {
            "candidate_user_id": 101,
            "name": "Данияр",
            "age": 24,
            "district": "Бостандыкский",
            "has_apartment": True,
            "budget": 95000,
            "move_in_date": "10 қыркүйек",
        },
        {
            "candidate_user_id": 102,
            "name": "Нұрлан",
            "age": 22,
            "district": "Бостандыкский",
            "has_apartment": False,
            "budget": 100000,
            "move_in_date": "20 қыркүйек",
        },
    ]

    result_kz: AIRankingResult = await ai.rank_candidates(viewer, candidates, lang="kz")
    assert len(result_kz.candidates) == 2
    assert result_kz.candidates[0].rank_order == 1
    assert result_kz.candidates[1].rank_order == 2
    # Ensure no technical formulas/percentages in human reason
    for item in result_kz.candidates:
        assert "%" not in item.human_reason
        assert "скоринг" not in item.human_reason.lower()
        assert len(item.human_reason) > 10

    result_ru: AIRankingResult = await ai.rank_candidates(viewer, candidates, lang="ru")
    assert len(result_ru.candidates) == 2
    for item in result_ru.candidates:
        assert "%" not in item.human_reason
        assert "вес" not in item.human_reason.lower()


def test_card_formatters_with_custom_reason():
    """Verify formatters display custom AI human reasons properly."""
    u = User(id=1, first_name="Арман", gender="male")
    sp = SeekerProfile(
        user_id=1,
        name="Арман",
        age=24,
        districts=["Бостандыкский"],
        has_apartment=True,
        budget_range="100,000 ₸",
        move_in_date="10 қазан",
        rooms_count="2-бөлмелі",
        room_type="separate",
    )

    custom_ai_reason_kz = "Арман — өте жақсы нұсқа. Пәтері сен іздеген ауданда, ал бюджетің толық сәйкес келеді."
    card_kz = format_card_for_ready_apartment(sp, u, lang="kz", custom_reason=custom_ai_reason_kz)
    assert "💡 **Неге сәйкес келеді:**" in card_kz
    assert custom_ai_reason_kz in card_kz

    custom_ai_reason_ru = "Арман — отличный вариант. Квартира в твоём районе, и бюджет полностью совпадает."
    card_ru = format_card_for_ready_apartment(sp, u, lang="ru", custom_reason=custom_ai_reason_ru)
    assert "💡 **Почему подходит тебе:**" in card_ru
    assert custom_ai_reason_ru in card_ru
