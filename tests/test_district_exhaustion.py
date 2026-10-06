"""Test automated critical scenario:
User chooses Bostandyk -> browses listings -> listings exhaust -> system signals district_exhausted
-> user expands search -> receives adjacent district listings.
"""

import pytest
from sqlalchemy import select
from app.db.models import User
from app.matching.engine import MatchingEngine
from app.services.match_service import MatchService


@pytest.mark.asyncio
async def test_district_exhaustion_and_expansion_scenario(test_session):
    # 1. Fetch Seeker looking in Bostandyk
    stmt = select(User).where(User.telegram_id == 100001)
    res = await test_session.execute(stmt)
    user = res.scalar_one()

    engine = MatchingEngine()

    # 2. Swipe through all Bostandyk listings
    swiped_count = 0
    while True:
        result = await engine.get_next_listing_for_seeker(
            session=test_session,
            user_id=user.id,
            strict_district=True,
        )
        if result["status"] == "district_exhausted":
            break

        assert result["status"] == "ok"
        candidate = result["candidate"]
        assert candidate.listing.district == "Бостандыкский"

        # Record swipe (simulate user clicking [❌ Пропустить] or [❤️ Подходит])
        await MatchService.record_swipe(
            session=test_session,
            from_user_id=user.id,
            target_type="listing",
            target_id=candidate.listing.id,
            is_like=True,
        )
        await test_session.commit()
        swiped_count += 1

    assert swiped_count >= 3, f"Expected at least 3 Bostandyk listings to be browsed, got {swiped_count}"
    assert result["status"] == "district_exhausted"
    assert "Бостандыкский" in result["current_district"]

    # 3. User agrees to expand to adjacent districts
    expanded_result = await engine.get_next_listing_for_seeker(
        session=test_session,
        user_id=user.id,
        strict_district=False,
        include_adjacent=True,
    )

    assert expanded_result["status"] == "ok"
    assert expanded_result["candidate"] is not None
    # Adjacent to Bostandyk are Almaly, Medeu, or Auezov
    assert expanded_result["candidate"].listing.district in ["Алмалинский", "Медеуский", "Ауэзовский"]
