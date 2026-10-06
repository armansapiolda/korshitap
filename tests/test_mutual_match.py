"""Tests for Tinder-like mutual likes and Match creation."""

import pytest
from sqlalchemy import select
from app.db.models import Listing, User
from app.services.match_service import MatchService


@pytest.mark.asyncio
async def test_mutual_like_creates_match(test_session):
    # 1. Seeker Arman
    seeker = (await test_session.execute(select(User).where(User.telegram_id == -100001))).scalar_one()

    # 2. Owner Alibek
    owner = (await test_session.execute(select(User).where(User.telegram_id == -100009))).scalar_one()

    # 3. Listing of Alibek in Bostandyk
    listing = (await test_session.execute(
        select(Listing).where(Listing.owner_id == owner.id)
    )).scalars().first()
    assert listing is not None

    # Step 1: Seeker likes listing
    like1, match1 = await MatchService.record_swipe(
        session=test_session,
        from_user_id=seeker.id,
        target_type="listing",
        target_id=listing.id,
        is_like=True,
    )
    await test_session.commit()
    assert like1 is not None
    assert match1 is None  # Not a match yet, owner hasn't liked back

    # Step 2: Owner sees Seeker in "Кто ищет" and likes him
    like2, match2 = await MatchService.record_swipe(
        session=test_session,
        from_user_id=owner.id,
        target_type="seeker",
        target_id=seeker.id,
        is_like=True,
    )
    await test_session.commit()

    # Now it MUST be a mutual match!
    assert match2 is not None
    assert match2.seeker_user_id == seeker.id
    assert match2.owner_user_id == owner.id
    assert match2.listing_id == listing.id
    assert match2.status == "matched"

    # Step 3: Verify get_user_matches for both users
    seeker_matches = await MatchService.get_user_matches(test_session, seeker.id)
    assert len(seeker_matches) >= 1

    owner_matches = await MatchService.get_user_matches(test_session, owner.id)
    assert len(owner_matches) >= 1
