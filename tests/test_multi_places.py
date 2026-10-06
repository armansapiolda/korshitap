"""Tests for single listing with multiple available spots."""

import pytest
from sqlalchemy import select
from app.db.models import Listing
from app.services.listing_service import ListingService


@pytest.mark.asyncio
async def test_single_listing_multiple_places(test_session):
    """
    Requirement 8:
    3-комнатная квартира
    Уже живёт: 1 человек
    Свободно: 2 места
    Цена: 90 000 ₸ с человека
    Система должна понимать: Это одно объявление с двумя свободными местами,
    а не 2 независимые квартиры.
    """
    # Create listing with 2 spots
    listing = await ListingService.create_listing(
        session=test_session,
        owner_id=1,
        data={
            "district": "Бостандыкский",
            "address_landmark": "Орбита-2",
            "housing_type": "sharing",
            "total_rooms": 3,
            "price_per_person": 90000,
            "available_places": 2,
            "occupied_places": 1,
            "move_in_date": "с 15 сентября",
        },
    )
    await test_session.commit()

    # Query back
    stmt = select(Listing).where(Listing.id == listing.id)
    res = await test_session.execute(stmt)
    retrieved = res.scalar_one()

    assert retrieved.available_places == 2
    assert retrieved.occupied_places == 1
    assert retrieved.price_per_person == 90000
    assert retrieved.district == "Бостандыкский"
