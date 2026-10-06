"""Matching Engine combining strict filtering, deterministic scoring, and AI re-ranking."""

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.db.models import Listing, SeekerProfile, Setting, User
from app.matching.filters import get_swiped_listing_ids, query_candidate_listings
from app.matching.scoring import calculate_deterministic_score
from app.matching.weights import DEFAULT_WEIGHTS, MatchingWeights


async def get_current_weights(session: AsyncSession) -> MatchingWeights:
    """Retrieve weights from database settings or return default."""
    stmt = select(Setting).where(Setting.key == "matching_weights")
    result = await session.execute(stmt)
    setting = result.scalar_one_or_none()
    if setting and isinstance(setting.value, dict):
        try:
            return MatchingWeights(**setting.value)
        except Exception:
            pass
    return DEFAULT_WEIGHTS


class MatchCandidate:
    def __init__(
        self,
        listing: Listing,
        score: int,
        reasoning: str,
        pros: List[str],
        cons: List[str],
    ):
        self.listing = listing
        self.score = score
        self.reasoning = reasoning
        self.pros = pros
        self.cons = cons


class MatchingEngine:
    """Core matching engine for Korshi Tap."""

    def __init__(self):
        self.ai = get_ai_provider()

    async def get_next_listing_for_seeker(
        self,
        session: AsyncSession,
        user_id: int,
        strict_district: bool = True,
        include_adjacent: bool = False,
        custom_districts: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Finds the single best candidate card for a seeker to swipe.
        Returns:
            {
                "status": "ok" | "district_exhausted" | "all_exhausted",
                "candidate": MatchCandidate or None,
                "current_district": str,
            }
        """
        # 1. Fetch user and profile
        user_stmt = select(User).where(User.id == user_id)
        res = await session.execute(user_stmt)
        user = res.scalar_one_or_none()
        if not user:
            return {"status": "all_exhausted", "candidate": None}

        prof_stmt = select(SeekerProfile).where(SeekerProfile.user_id == user_id)
        res = await session.execute(prof_stmt)
        profile = res.scalar_one_or_none()
        if not profile:
            return {"status": "all_exhausted", "candidate": None}

        target_districts = custom_districts or profile.districts or ["Бостандыкский"]
        current_district_name = ", ".join(target_districts)

        # 2. Query candidates under current district mode
        candidates = await query_candidate_listings(
            session=session,
            seeker_user=user,
            profile=profile,
            strict_district=strict_district,
            include_adjacent=include_adjacent,
            custom_districts=target_districts,
        )

        # 3. Check for district exhaustion
        if not candidates:
            if strict_district:
                # Check if other listings exist outside this district
                broader_candidates = await query_candidate_listings(
                    session=session,
                    seeker_user=user,
                    profile=profile,
                    strict_district=False,
                    include_adjacent=False,
                )
                if broader_candidates:
                    return {
                        "status": "district_exhausted",
                        "candidate": None,
                        "current_district": current_district_name,
                    }
            return {
                "status": "all_exhausted",
                "candidate": None,
                "current_district": current_district_name,
            }

        # 4. Score all candidate listings
        weights = await get_current_weights(session)
        seeker_dict = {
            "districts": target_districts,
            "budget_max": profile.budget_max,
            "move_in_date": profile.move_in_date,
            "housing_types": profile.housing_types,
            "gender": profile.gender,
            "smoking": profile.smoking,
            "pets": profile.pets,
            "occupation": profile.occupation,
        }

        scored = []
        for lst in candidates:
            listing_dict = {
                "district": lst.district,
                "price_per_person": lst.price_per_person,
                "move_in_date": lst.move_in_date,
                "housing_type": lst.housing_type,
                "preferred_gender": lst.preferred_gender,
                "smoking_allowed": lst.smoking_allowed,
                "pets_allowed": lst.pets_allowed,
                "utilities_included": lst.utilities_included,
                "is_verified": lst.is_verified,
            }
            score = calculate_deterministic_score(seeker_dict, listing_dict, weights)
            scored.append((score, lst, listing_dict))

        # Sort descending by deterministic score
        scored.sort(key=lambda x: x[0], reverse=True)
        top_score, best_listing, best_dict = scored[0]

        # 5. Enrich with AI compatibility reasoning
        ai_result = await self.ai.calculate_compatibility(seeker_dict, best_dict)
        # Blend deterministic score (70%) with AI semantic score (30%)
        final_score = int(round(top_score * 0.7 + ai_result.score * 0.3))
        final_score = max(35, min(99, final_score))

        candidate = MatchCandidate(
            listing=best_listing,
            score=final_score,
            reasoning=ai_result.reasoning,
            pros=ai_result.pros,
            cons=ai_result.cons,
        )

        return {
            "status": "ok",
            "candidate": candidate,
            "current_district": current_district_name,
        }

    async def get_seekers_for_owner_listing(
        self,
        session: AsyncSession,
        listing_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find seekers suitable for a specific owner listing."""
        stmt = select(Listing).where(Listing.id == listing_id)
        res = await session.execute(stmt)
        listing = res.scalar_one_or_none()
        if not listing:
            return []

        # Find active seeker profiles
        seeker_stmt = select(SeekerProfile, User).join(User, SeekerProfile.user_id == User.id).where(
            SeekerProfile.is_active == True,
            User.id != listing.owner_id,
        )
        res = await session.execute(seeker_stmt)
        rows = res.all()

        weights = await get_current_weights(session)
        listing_dict = {
            "district": listing.district,
            "price_per_person": listing.price_per_person,
            "move_in_date": listing.move_in_date,
            "housing_type": listing.housing_type,
            "preferred_gender": listing.preferred_gender,
            "smoking_allowed": listing.smoking_allowed,
            "pets_allowed": listing.pets_allowed,
            "utilities_included": listing.utilities_included,
            "is_verified": listing.is_verified,
        }

        results = []
        for profile, user in rows:
            seeker_dict = {
                "districts": profile.districts or [],
                "budget_max": profile.budget_max,
                "move_in_date": profile.move_in_date,
                "housing_types": profile.housing_types,
                "gender": profile.gender,
                "smoking": profile.smoking,
                "pets": profile.pets,
                "occupation": profile.occupation,
            }
            score = calculate_deterministic_score(seeker_dict, listing_dict, weights)
            results.append({
                "user": user,
                "profile": profile,
                "score": int(round(score)),
            })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]


matching_engine = MatchingEngine()
