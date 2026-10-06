"""Tests for 12-step Scenario #1 neighbor description criteria parsing and storage."""

import pytest
from app.ai.factory import get_ai_provider
from app.db.base import async_session_factory
from app.matching.reason_generator import generate_human_match_reason
from app.services.listing_service import ListingService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_parse_neighbor_description_criteria():
    """Verify that natural language description is converted to structured compatibility criteria."""
    ai = get_ai_provider()
    user_text = (
        "Ищу спокойного человека, который не устраивает тусовки. "
        "Сам работаю с 9 до 18. Желательно чтобы не курил и был аккуратным. "
        "К животным отношусь нормально."
    )

    criteria = await ai.parse_neighbor_description(user_text)

    assert criteria.lifestyle == "quiet"
    assert criteria.parties == "undesirable"
    assert criteria.smoking == "non_smoker_preferred"
    assert criteria.cleanliness == "important"
    assert criteria.pets == "acceptable"
    assert criteria.schedule == "works_daytime"


@pytest.mark.asyncio
async def test_owner_listing_creation_with_all_12_step_fields():
    """Verify that ListingService saves all 12-step scenario fields including neighbor_criteria."""
    async with async_session_factory() as session:
        user = await UserService.get_or_create_user(
            session=session,
            telegram_id=987654321,
            first_name="Ерлан",
        )

        criteria_dict = {
            "lifestyle": "quiet",
            "parties": "undesirable",
            "smoking": "non_smoker_preferred",
            "cleanliness": "important",
            "pets": "acceptable",
            "schedule": "works_daytime",
        }

        listing = await ListingService.create_listing(
            session=session,
            owner_id=user.id,
            data={
                "city": "Алматы",
                "district": "Бостандыкский",
                "housing_type": "flat",
                "total_rooms": 2,
                "price_per_person": 95000,
                "utilities_status": "separate",
                "utilities_amount": 10000,
                "utilities_included": False,
                "occupied_places": 1,
                "available_places": 1,
                "move_in_date": "В ближайшее время",
                "lease_term": "6–12 месяцев",
                "preferred_gender": "male",
                "preferred_age_range": "20–30 лет",
                "smoking_allowed": False,
                "pets_allowed": True,
                "conditions_description": "Ищу спокойного соседа без вредных привычек",
                "neighbor_criteria": criteria_dict,
            },
        )
        await session.commit()

        # Retrieve and check
        loaded = await ListingService.get_listing_by_id(session, listing.id)
        assert loaded is not None
        assert loaded.city == "Алматы"
        assert loaded.housing_type == "flat"
        assert loaded.total_rooms == 2
        assert loaded.price_per_person == 95000
        assert loaded.utilities_status == "separate"
        assert loaded.utilities_amount == 10000
        assert loaded.lease_term == "6–12 месяцев"
        assert loaded.preferred_gender == "male"
        assert loaded.preferred_age_range == "20–30 лет"
        assert loaded.neighbor_criteria == criteria_dict


def test_reason_generator_with_neighbor_criteria():
    """Verify that match reason reflects AI extracted criteria for quiet/party preferences."""
    criteria = {
        "lifestyle": "quiet",
        "parties": "undesirable",
        "pets": "acceptable",
    }

    reason_ru = generate_human_match_reason(
        user_occ="working",
        cand_occ="working",
        lang="ru",
        criteria=criteria,
    )
    assert "тишину" in reason_ru or "порядок" in reason_ru

    reason_kz = generate_human_match_reason(
        user_occ="working",
        cand_occ="working",
        lang="kz",
        criteria=criteria,
    )
    assert "тыныштық" in reason_kz or "тәртіп" in reason_kz
