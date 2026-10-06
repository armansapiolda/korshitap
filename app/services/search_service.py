"""Saved search service for notification subscriptions."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Listing, SavedSearch, User


class SearchService:

    @staticmethod
    async def save_search_preference(
        session: AsyncSession,
        user_id: int,
        districts: List[str],
        budget_max: Optional[int] = None,
        move_in_date: Optional[str] = None,
    ) -> SavedSearch:
        stmt = select(SavedSearch).where(SavedSearch.user_id == user_id)
        res = await session.execute(stmt)
        search = res.scalar_one_or_none()

        if not search:
            search = SavedSearch(
                user_id=user_id,
                districts=districts,
                budget_max=budget_max,
                move_in_date=move_in_date,
                notify_active=True,
            )
            session.add(search)
        else:
            search.districts = districts
            search.budget_max = budget_max
            search.move_in_date = move_in_date
            search.notify_active = True

        await session.flush()
        return search

    @staticmethod
    async def find_subscribers_for_listing(
        session: AsyncSession,
        listing: Listing,
    ) -> List[User]:
        """Find users who saved a search matching this new listing."""
        stmt = (
            select(SavedSearch)
            .options(selectinload(SavedSearch.user))
            .where(
                SavedSearch.notify_active == True,
                SavedSearch.user_id != listing.owner_id,
            )
        )
        res = await session.execute(stmt)
        searches = res.scalars().all()

        matching_users = []
        for s in searches:
            if not s.user or s.user.is_blocked:
                continue
            # District match
            if s.districts and listing.district not in s.districts:
                continue
            # Budget match
            if s.budget_max and listing.price_per_person > int(s.budget_max * 1.15):
                continue
            matching_users.append(s.user)

        return matching_users
