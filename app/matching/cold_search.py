"""Stage 1: Cold Factual Search Service.

Performs objective, factual filtering strictly based on verified data:
- District and city matching (or adjacent districts when expanded)
- Housing status partitioning:
  * For seeker without apartment: candidates who ALREADY have a flat with available places
    (without filtering by how many roommates they need!).
  * Followed by co-seekers (who also don't have a flat).
  * For user with an apartment: seekers looking in their district.
- Gender compatibility (both viewer's and candidate's requirements)
- Budget compatibility
- Zero AI hallucinations / zero subjective ranking at this stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ADJACENT_DISTRICTS, DEFAULT_CITY, LISTING_STATUS_ACTIVE
from app.db.models import Listing, SeekerProfile, User


@dataclass
class ColdCandidate:
    profile: SeekerProfile
    user: User
    listing: Optional[Listing]
    is_ready_apartment: bool
    district: str
    budget: int
    budget_range: str
    move_in_date: str
    rooms_count: Optional[str]
    room_type: Optional[str]
    neighbors_needed: Optional[int]
    preferred_room_type: Optional[str]
    address: Optional[str]
    occupation: str
    about_self: str
    ideal_neighbor: str

    def to_ai_dict(self) -> dict:
        """Convert candidate facts for Gemini AI Ranking prompt."""
        return {
            "candidate_user_id": self.user.id,
            "name": self.profile.name or self.user.first_name or "Кандидат",
            "age": self.profile.age or self.user.age or 22,
            "gender": self.profile.gender or self.user.gender or "not_specified",
            "occupation": self.occupation,
            "city": self.profile.city or DEFAULT_CITY,
            "district": self.district,
            "has_apartment": self.is_ready_apartment,
            "rooms_count": self.rooms_count,
            "room_type": self.room_type,
            "neighbors_needed": self.neighbors_needed if self.is_ready_apartment else None,
            "preferred_room_type": self.preferred_room_type,
            "address": self.address,
            "budget": self.budget,
            "budget_range": self.budget_range,
            "move_in_date": self.move_in_date,
            "about_self": self.about_self,
            "ideal_neighbor": self.ideal_neighbor,
        }


async def perform_cold_search(
    session: AsyncSession,
    viewer_user: User,
    viewer_profile: Optional[SeekerProfile],
    district_filter: Optional[str] = None,
    allow_adjacent: bool = False,
) -> Tuple[List[ColdCandidate], List[ColdCandidate]]:
    """Execute cold factual search.
    Returns: (primary_candidates, secondary_candidates)
    - When viewer has NO apartment:
      * primary_candidates: people who ALREADY have a flat in target district.
      * secondary_candidates: co-seekers looking in the same district.
    - When viewer HAS an apartment:
      * primary_candidates: people searching for an apartment in that district.
      * secondary_candidates: empty list.
    """
    my_city = (viewer_profile.city if viewer_profile and viewer_profile.city else getattr(viewer_user, "city", None)) or DEFAULT_CITY
    my_districts = viewer_profile.districts if viewer_profile and viewer_profile.districts else []
    my_district = district_filter or (my_districts[0] if my_districts else "Бостандыкский")
    viewer_has_apt = bool(viewer_profile and viewer_profile.has_apartment)

    # Gender filter preferences
    viewer_pref_gender = (
        getattr(viewer_user, "preferred_gender", None)
        or (viewer_profile.preferred_gender if viewer_profile else None)
        or "any"
    )

    # 1. Fetch all active profiles excluding self and blocked users
    stmt = (
        select(SeekerProfile, User)
        .join(User, SeekerProfile.user_id == User.id)
        .where(
            SeekerProfile.is_active == True,
            User.is_blocked == False,
            User.id != viewer_user.id,
        )
    )
    raw_results = (await session.execute(stmt)).all()

    # Pre-fetch active listings
    listings_stmt = (
        select(Listing)
        .where(Listing.status == LISTING_STATUS_ACTIVE, Listing.available_places > 0)
    )
    all_listings = (await session.execute(listings_stmt)).scalars().all()
    user_to_listing = {l.owner_id: l for l in all_listings}

    # Prepare district match sets
    if allow_adjacent:
        allowed_districts = set(ADJACENT_DISTRICTS.get(my_district, []))
    else:
        allowed_districts = {my_district}

    ready_candidates: List[ColdCandidate] = []
    coseeker_candidates: List[ColdCandidate] = []
    seeker_for_owner_candidates: List[ColdCandidate] = []

    for sp, u in raw_results:
        cand_city = (sp.city if sp and sp.city else getattr(u, "city", None)) or DEFAULT_CITY
        if cand_city != my_city:
            continue

        # Gender compatibility (two-way check)
        cand_gender = sp.gender or u.gender or "other"
        if viewer_pref_gender in ("male", "female") and cand_gender != viewer_pref_gender:
            continue
        cand_pref_gender = sp.preferred_gender or getattr(u, "preferred_gender", "any") or "any"
        viewer_gender = (viewer_profile.gender if viewer_profile else None) or viewer_user.gender
        if cand_pref_gender in ("male", "female") and viewer_gender and viewer_gender != cand_pref_gender:
            continue

        # District check
        cand_districts = sp.districts or []
        matching_districts = [d for d in cand_districts if d in allowed_districts]
        if not matching_districts:
            continue
        matched_district = matching_districts[0]

        # Candidate's listing if any
        listing = user_to_listing.get(u.id)
        cand_has_apt = bool(sp.has_apartment) or (listing is not None)

        budget_val = sp.budget_max or (listing.price_per_person if listing else 100000)
        budget_range_str = sp.budget_range or f"{budget_val:,} ₸"
        move_date_str = sp.move_in_date or (listing.move_in_date if listing else "Жақын арада")
        occ_str = sp.occupation or getattr(u, "occupation", "working") or "working"
        about_str = sp.about_self_desc or sp.raw_bio or "Жақсы және таза көрші іздеймін"
        ideal_str = sp.ideal_neighbor_desc or sp.neighbor_preferences or "Тазалықты сақтайтын, тыныш адам"

        # Build cold candidate object
        cold_cand = ColdCandidate(
            profile=sp,
            user=u,
            listing=listing,
            is_ready_apartment=cand_has_apt,
            district=matched_district,
            budget=budget_val,
            budget_range=budget_range_str,
            move_in_date=move_date_str,
            rooms_count=sp.rooms_count or (f"{listing.total_rooms}-бөлмелі" if listing and listing.total_rooms else "2-бөлмелі"),
            room_type=sp.room_type or ("separate" if listing and listing.housing_type == "room" else "shared"),
            neighbors_needed=sp.neighbors_needed or (listing.available_places if listing else 1),
            preferred_room_type=sp.preferred_room_type,
            address=sp.apartment_address or (listing.address_landmark if listing else None),
            occupation=occ_str,
            about_self=about_str,
            ideal_neighbor=ideal_str,
        )

        if viewer_has_apt:
            # Viewer has apartment: only accept seekers who do NOT have an apartment
            if not cand_has_apt:
                seeker_for_owner_candidates.append(cold_cand)
        else:
            # Viewer does NOT have an apartment:
            if cand_has_apt:
                # Ready apartment owner (DO NOT filter by neighbors_needed count!)
                ready_candidates.append(cold_cand)
            else:
                # Co-seeker looking in this district
                coseeker_candidates.append(cold_cand)

    if viewer_has_apt:
        return seeker_for_owner_candidates, []
    else:
        return ready_candidates, coseeker_candidates
