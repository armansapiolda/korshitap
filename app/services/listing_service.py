"""Listing service handling housing, multi-places, and freshness."""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import DEFAULT_CITY, LISTING_STATUS_ACTIVE, LISTING_STATUS_ARCHIVED, LISTING_STATUS_PAUSED
from app.db.models import Listing, SeekerProfile


class ListingService:

    @staticmethod
    async def create_listing(
        session: AsyncSession,
        owner_id: int,
        data: Dict[str, Any],
    ) -> Listing:
        """Create a listing supporting 1 or multiple available spots."""
        listing = Listing(
            owner_id=owner_id,
            city=data.get("city", DEFAULT_CITY),
            district=data.get("district", "Бостандыкский"),
            address_landmark=data.get("address_landmark"),
            housing_type=data.get("housing_type", "room"),
            total_rooms=data.get("total_rooms", 2),
            total_price=data.get("total_price"),
            price_per_person=data.get("price_per_person", 100000),
            utilities_included=data.get("utilities_included", False),
            deposit_amount=data.get("deposit_amount", 0),
            move_in_date=data.get("move_in_date", "В ближайшее время"),
            available_places=data.get("available_places", 1),
            occupied_places=data.get("occupied_places", 1),
            current_gender=data.get("current_gender", "mixed"),
            preferred_gender=data.get("preferred_gender", "any"),
            smoking_allowed=data.get("smoking_allowed", False),
            pets_allowed=data.get("pets_allowed", False),
            conditions_description=data.get("conditions_description"),
            lease_term=data.get("lease_term"),
            preferred_age_range=data.get("preferred_age_range"),
            utilities_status=data.get("utilities_status"),
            utilities_amount=data.get("utilities_amount"),
            neighbor_criteria=data.get("neighbor_criteria", {}),
            photos=data.get("photos", []),
            status=LISTING_STATUS_ACTIVE,
            is_urgent=data.get("is_urgent", False),
            last_confirmed_at=datetime.utcnow(),
        )
        session.add(listing)
        await session.flush()
        return listing

    @staticmethod
    async def sync_profile_listing(
        session: AsyncSession,
        owner_id: int,
        profile: SeekerProfile,
        criteria: Optional[Dict[str, Any]] = None,
    ) -> Optional[Listing]:
        """Mirror the questionnaire into the owner's listing.

        Has apartment -> update the latest listing (or create one), archive the rest.
        No apartment -> archive all listings, so the user is not treated as an owner.
        """
        existing = (
            await session.execute(
                select(Listing)
                .where(
                    Listing.owner_id == owner_id,
                    Listing.status.in_([LISTING_STATUS_ACTIVE, LISTING_STATUS_PAUSED]),
                )
                .order_by(Listing.id.desc())
            )
        ).scalars().all()

        listing: Optional[Listing] = None
        stale = list(existing)
        if profile.has_apartment:
            rooms_val = 2
            if profile.rooms_count:
                m = re.search(r"\d+", profile.rooms_count)
                if m:
                    rooms_val = int(m.group(0))
            data = {
                "city": profile.city,
                "district": profile.districts[0] if profile.districts else "Бостандыкский",
                "address_landmark": profile.apartment_address or profile.city,
                "housing_type": "flat",
                "total_rooms": rooms_val,
                "price_per_person": profile.budget_max,
                "utilities_status": "included",
                "utilities_included": True,
                "occupied_places": 1,
                "available_places": profile.neighbors_needed or 1,
                "move_in_date": profile.move_in_date,
                "preferred_gender": profile.preferred_gender,
                "conditions_description": profile.ideal_neighbor_desc,
                "neighbor_criteria": criteria or {},
            }
            if existing:
                listing = existing[0]
                stale = list(existing[1:])
                for key, value in data.items():
                    setattr(listing, key, value)
                listing.status = LISTING_STATUS_ACTIVE
                listing.last_confirmed_at = datetime.utcnow()
            else:
                listing = await ListingService.create_listing(session, owner_id, data)

        for old in stale:
            old.status = LISTING_STATUS_ARCHIVED
        await session.flush()
        return listing

    @staticmethod
    async def get_listing_by_id(session: AsyncSession, listing_id: int) -> Optional[Listing]:
        stmt = select(Listing).where(Listing.id == listing_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_owner_listings(session: AsyncSession, owner_id: int) -> List[Listing]:
        stmt = select(Listing).where(Listing.owner_id == owner_id).order_by(desc(Listing.created_at))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_status(session: AsyncSession, listing_id: int, status: str) -> Optional[Listing]:
        listing = await ListingService.get_listing_by_id(session, listing_id)
        if listing:
            listing.status = status
            await session.flush()
        return listing

    @staticmethod
    async def confirm_freshness(session: AsyncSession, listing_id: int) -> Optional[Listing]:
        listing = await ListingService.get_listing_by_id(session, listing_id)
        if listing:
            listing.last_confirmed_at = datetime.utcnow()
            listing.status = LISTING_STATUS_ACTIVE
            await session.flush()
        return listing

    @staticmethod
    async def get_stale_listings(session: AsyncSession, days_threshold: int = 7) -> List[Listing]:
        """Find active listings that haven't been confirmed in X days."""
        cutoff = datetime.utcnow() - timedelta(days=days_threshold)
        stmt = select(Listing).where(
            Listing.status == LISTING_STATUS_ACTIVE,
            Listing.last_confirmed_at < cutoff,
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
