"""Tests for matching engine scoring and strict district priority."""

import pytest
from app.matching.engine import MatchingEngine
from app.matching.scoring import calculate_deterministic_score
from app.matching.weights import DEFAULT_WEIGHTS


@pytest.mark.asyncio
async def test_district_priority_over_other_factors():
    """
    TЗ Requirement:
    User wants Bostandyk up to 120 000.
    Variant A: Bostandyk, 110 000
    Variant B: Almaly, 100 000
    Variant A MUST score higher because district is the #1 priority (35%).
    """
    seeker = {
        "districts": ["Бостандыкский"],
        "budget_max": 120000,
        "move_in_date": "с 10 сентября",
        "housing_types": ["room"],
        "gender": "male",
        "smoking": "no",
        "pets": "no",
    }

    variant_a = {
        "district": "Бостандыкский",
        "price_per_person": 110000,
        "move_in_date": "с 10 сентября",
        "housing_type": "room",
        "preferred_gender": "male",
        "smoking_allowed": False,
        "pets_allowed": False,
    }

    variant_b = {
        "district": "Алмалинский",  # Different district
        "price_per_person": 100000, # Cheaper price
        "move_in_date": "с 10 сентября",
        "housing_type": "room",
        "preferred_gender": "male",
        "smoking_allowed": False,
        "pets_allowed": False,
    }

    score_a = calculate_deterministic_score(seeker, variant_a, DEFAULT_WEIGHTS)
    score_b = calculate_deterministic_score(seeker, variant_b, DEFAULT_WEIGHTS)

    assert score_a > score_b, f"Expected variant A ({score_a}) to beat variant B ({score_b}) due to district weight"


@pytest.mark.asyncio
async def test_get_next_listing_returns_bostandyk_first(test_session):
    """
    Checks that seeker asking for Bostandyk gets Bostandyk listings first.
    """
    from sqlalchemy import select
    from app.db.models import SeekerProfile, User

    # Find test user Arman (looking in Bostandyk)
    stmt = select(User).where(User.telegram_id == -100001)
    res = await test_session.execute(stmt)
    user = res.scalar_one()

    engine = MatchingEngine()
    result = await engine.get_next_listing_for_seeker(
        session=test_session,
        user_id=user.id,
        strict_district=True,
    )

    assert result["status"] == "ok"
    assert result["candidate"] is not None
    assert result["candidate"].listing.district == "Бостандыкский"
    assert result["candidate"].score >= 70
