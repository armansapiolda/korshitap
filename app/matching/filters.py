"""Filtering queries and conditions for matching candidates."""

from typing import List, Optional
from sqlalchemy import not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ADJACENT_DISTRICTS,
    DEFAULT_CITY,
    LISTING_STATUS_ACTIVE,
)
from app.db.models import Like, Listing, SeekerProfile, User


async def get_swiped_listing_ids(session: AsyncSession, user_id: int) -> List[int]:
    """Get list of listing IDs already swiped (liked or passed) by user."""
    stmt = select(Like.target_id).where(
        Like.from_user_id == user_id,
        Like.target_type == "listing",
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def query_candidate_listings(
    session: AsyncSession,
    seeker_user: User,
    profile: SeekerProfile,
    strict_district: bool = True,
    include_adjacent: bool = False,
    custom_districts: Optional[List[str]] = None,
) -> List[Listing]:
    """
    Query eligible listings matching seeker criteria.
    Respects strict district priority first.
    """
    swiped_ids = await get_swiped_listing_ids(session, seeker_user.id)

    stmt = select(Listing).where(
        Listing.city == DEFAULT_CITY,
        Listing.status == LISTING_STATUS_ACTIVE,
        Listing.available_places > 0,
        Listing.owner_id != seeker_user.id,
    )

    # Exclude already swiped listings
    if swiped_ids:
        stmt = stmt.where(not_(Listing.id.in_(swiped_ids)))

    # Budget filter with 15% grace threshold
    if profile.budget_max:
        stmt = stmt.where(Listing.price_per_person <= int(profile.budget_max * 1.15))

    # Gender filter (if listing specifies preferred gender and seeker has a known gender)
    if profile.gender and profile.gender != "any":
        stmt = stmt.where(
            Listing.preferred_gender.in_([profile.gender, "any", None])
        )

    # District filtering logic
    target_districts = custom_districts or profile.districts or []
    if target_districts:
        if strict_district:
            stmt = stmt.where(Listing.district.in_(target_districts))
        elif include_adjacent:
            expanded = set(target_districts)
            for d in target_districts:
                for adj in ADJACENT_DISTRICTS.get(d, []):
                    expanded.add(adj)
            stmt = stmt.where(Listing.district.in_(list(expanded)))
        # else: if neither strict nor adjacent, all Almaty districts are queried

    result = await session.execute(stmt)
    return list(result.scalars().all())
