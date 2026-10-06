"""Match and swipe service managing likes, mutual matches, and notifications."""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import MATCH_STATUS_MATCHED
from app.db.models import Like, Listing, Match, User


class MatchService:

    @staticmethod
    async def record_swipe(
        session: AsyncSession,
        from_user_id: int,
        target_type: str,  # 'listing' or 'seeker'
        target_id: int,    # listing_id or seeker_user_id
        is_like: bool,
    ) -> Tuple[Like, Optional[Match]]:
        """
        Record a swipe (Like or Pass).
        If both parties like each other, creates and returns a Match.
        """
        # Save like/pass
        like = Like(
            from_user_id=from_user_id,
            target_type=target_type,
            target_id=target_id,
            is_like=is_like,
        )
        session.add(like)
        await session.flush()

        if not is_like:
            return like, None

        match_created = None

        if target_type == "listing":
            # Seeker liked an owner's listing
            listing_stmt = select(Listing).where(Listing.id == target_id)
            res = await session.execute(listing_stmt)
            listing = res.scalar_one_or_none()

            if listing:
                owner_id = listing.owner_id
                # Check if owner previously liked this seeker
                owner_like_stmt = select(Like).where(
                    Like.from_user_id == owner_id,
                    Like.target_type == "seeker",
                    Like.target_id == from_user_id,
                    Like.is_like == True,
                )
                res_owner_like = await session.execute(owner_like_stmt)
                if res_owner_like.scalar_one_or_none():
                    # Mutual match!
                    match_created = Match(
                        seeker_user_id=from_user_id,
                        listing_id=listing.id,
                        owner_user_id=owner_id,
                        status=MATCH_STATUS_MATCHED,
                        matched_at=datetime.utcnow(),
                    )
                    session.add(match_created)
                    await session.flush()

        elif target_type == "seeker":
            # Owner liked a seeker in "Кто ищет"
            seeker_user_id = target_id
            owner_id = from_user_id

            # Find owner's active listings
            listings_stmt = select(Listing).where(
                Listing.owner_id == owner_id,
                Listing.status == "active",
            )
            res = await session.execute(listings_stmt)
            owner_listings = list(res.scalars().all())

            for lst in owner_listings:
                # Check if seeker previously liked this listing
                seeker_like_stmt = select(Like).where(
                    Like.from_user_id == seeker_user_id,
                    Like.target_type == "listing",
                    Like.target_id == lst.id,
                    Like.is_like == True,
                )
                res_seeker_like = await session.execute(seeker_like_stmt)
                if res_seeker_like.scalar_one_or_none():
                    # Mutual match!
                    match_created = Match(
                        seeker_user_id=seeker_user_id,
                        listing_id=lst.id,
                        owner_user_id=owner_id,
                        status=MATCH_STATUS_MATCHED,
                        matched_at=datetime.utcnow(),
                    )
                    session.add(match_created)
                    await session.flush()
                    break

        return like, match_created

    @staticmethod
    async def create_direct_match(
        session: AsyncSession,
        seeker_user_id: int,
        listing_id: int,
        owner_user_id: int,
    ) -> Match:
        """Create a direct match when owner accepts a seeker's application."""
        # Ensure not already matched
        stmt = select(Match).where(
            Match.seeker_user_id == seeker_user_id,
            Match.listing_id == listing_id,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        new_match = Match(
            seeker_user_id=seeker_user_id,
            listing_id=listing_id,
            owner_user_id=owner_user_id,
            status=MATCH_STATUS_MATCHED,
            matched_at=datetime.utcnow(),
        )
        session.add(new_match)
        await session.flush()
        return new_match

    @staticmethod
    async def get_user_matches(session: AsyncSession, user_id: int) -> List[Match]:
        """Fetch all matches involving this user."""
        stmt = (
            select(Match)
            .options(
                selectinload(Match.seeker_user),
                selectinload(Match.owner_user),
                selectinload(Match.listing),
            )
            .where(
                or_(
                    Match.seeker_user_id == user_id,
                    Match.owner_user_id == user_id,
                )
            )
            .order_by(Match.matched_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
