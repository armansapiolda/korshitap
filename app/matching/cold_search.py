"""Stage 1: Cold Factual Search Service.

Performs objective, factual filtering strictly based on verified data:
- District and city matching (or adjacent districts when expanded)
- Housing status partitioning:
  * For seeker without apartment: candidates who ALREADY have a flat with available places
    (without filtering by how many roommates they need!).
  * Followed by co-seekers (who also don't have a flat).
  * For user with an apartment: seekers looking in their district.
- Gender compatibility (both viewer's and candidate's requirements)
- Budget compatibility (price per person vs. seeker budget)
- Move-in date compatibility (windows must overlap within tolerance)
- Zero AI hallucinations / zero subjective ranking at this stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ADJACENT_DISTRICTS, DEFAULT_CITY, LISTING_STATUS_ACTIVE
from app.db.models import Listing, SeekerProfile, User
from app.matching.dates import parse_move_in_window, windows_compatible

# A seeker still sees a flat that costs up to 15% above their budget.
BUDGET_OVER_TOLERANCE = 1.15
# Co-seekers are paired when the larger budget is at most 1.5x the smaller one.
COSEEKER_BUDGET_RATIO = 1.5

PRIMARY = "primary"
SECONDARY = "secondary"


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
            "lifestyle_criteria": self.profile.neighbor_criteria or {},
        }


def _city_of(profile: Optional[SeekerProfile], user: User) -> str:
    return (profile.city if profile and profile.city else getattr(user, "city", None)) or DEFAULT_CITY


def _has_apartment(profile: Optional[SeekerProfile], listing: Optional[Listing]) -> bool:
    return bool(profile and profile.has_apartment) or listing is not None


def _price_or_budget(profile: Optional[SeekerProfile], listing: Optional[Listing]) -> Optional[int]:
    """Monthly amount per person: listing price for owners, budget for seekers."""
    if listing is not None and listing.price_per_person:
        return listing.price_per_person
    return profile.budget_max if profile and profile.budget_max else None


def _preferred_gender(profile: Optional[SeekerProfile], user: User, listing: Optional[Listing]) -> str:
    if listing is not None and listing.preferred_gender in ("male", "female"):
        return listing.preferred_gender
    return (
        getattr(user, "preferred_gender", None)
        or (profile.preferred_gender if profile else None)
        or "any"
    )


def budgets_compatible(
    viewer_amount: Optional[int],
    viewer_has_apt: bool,
    cand_amount: Optional[int],
    cand_has_apt: bool,
) -> bool:
    """Compare price per person against a seeker's budget."""
    if not viewer_amount or not cand_amount:
        return True
    if cand_has_apt and not viewer_has_apt:
        return cand_amount <= viewer_amount * BUDGET_OVER_TOLERANCE
    if viewer_has_apt and not cand_has_apt:
        return viewer_amount <= cand_amount * BUDGET_OVER_TOLERANCE
    low, high = sorted((viewer_amount, cand_amount))
    return high <= low * COSEEKER_BUDGET_RATIO


def allowed_districts_for(district: str, allow_adjacent: bool) -> Set[str]:
    if allow_adjacent:
        return set(ADJACENT_DISTRICTS.get(district, []))
    return {district}


def evaluate_candidate(
    viewer_user: User,
    viewer_profile: Optional[SeekerProfile],
    viewer_listing: Optional[Listing],
    cand_user: User,
    cand_profile: SeekerProfile,
    cand_listing: Optional[Listing],
    allowed_districts: Iterable[str],
) -> Optional[Tuple[str, ColdCandidate]]:
    """Check one candidate against the viewer's hard criteria.

    Returns (PRIMARY | SECONDARY, ColdCandidate), or None when filtered out.
    """
    if cand_user.id == viewer_user.id:
        return None
    if _city_of(cand_profile, cand_user) != _city_of(viewer_profile, viewer_user):
        return None

    # Gender compatibility (two-way check)
    viewer_pref_gender = _preferred_gender(viewer_profile, viewer_user, viewer_listing)
    cand_gender = cand_profile.gender or cand_user.gender or "other"
    if viewer_pref_gender in ("male", "female") and cand_gender != viewer_pref_gender:
        return None
    cand_pref_gender = _preferred_gender(cand_profile, cand_user, cand_listing)
    viewer_gender = (viewer_profile.gender if viewer_profile else None) or viewer_user.gender
    if cand_pref_gender in ("male", "female") and viewer_gender and viewer_gender != cand_pref_gender:
        return None

    # District check
    allowed = set(allowed_districts)
    matching_districts = [d for d in (cand_profile.districts or []) if d in allowed]
    if not matching_districts:
        return None
    matched_district = matching_districts[0]

    viewer_has_apt = _has_apartment(viewer_profile, viewer_listing)
    cand_has_apt = _has_apartment(cand_profile, cand_listing)

    # Housing status: an apartment owner only looks for people without one
    if viewer_has_apt and cand_has_apt:
        return None

    # Budget check
    if not budgets_compatible(
        _price_or_budget(viewer_profile, viewer_listing),
        viewer_has_apt,
        _price_or_budget(cand_profile, cand_listing),
        cand_has_apt,
    ):
        return None

    # Move-in date check
    viewer_date = (viewer_profile.move_in_date if viewer_profile else None) or (
        viewer_listing.move_in_date if viewer_listing else None
    )
    cand_date = cand_profile.move_in_date or (cand_listing.move_in_date if cand_listing else None)
    viewer_window = parse_move_in_window(viewer_date, viewer_profile.updated_at if viewer_profile else None)
    cand_window = parse_move_in_window(cand_date, cand_profile.updated_at)
    if not windows_compatible(viewer_window, cand_window):
        return None

    sp, u, listing = cand_profile, cand_user, cand_listing
    budget_val = sp.budget_max or (listing.price_per_person if listing else 100000)
    cold_cand = ColdCandidate(
        profile=sp,
        user=u,
        listing=listing,
        is_ready_apartment=cand_has_apt,
        district=matched_district,
        budget=budget_val,
        budget_range=sp.budget_range or f"{budget_val:,} ₸",
        move_in_date=cand_date or "Жақын арада",
        rooms_count=sp.rooms_count or (f"{listing.total_rooms}-бөлмелі" if listing and listing.total_rooms else "2-бөлмелі"),
        room_type=sp.room_type or ("separate" if listing and listing.housing_type == "room" else "shared"),
        neighbors_needed=sp.neighbors_needed or (listing.available_places if listing else 1),
        preferred_room_type=sp.preferred_room_type,
        address=sp.apartment_address or (listing.address_landmark if listing else None),
        occupation=sp.occupation or getattr(u, "occupation", "working") or "working",
        about_self=sp.about_self_desc or sp.raw_bio or "Жақсы және таза көрші іздеймін",
        ideal_neighbor=sp.ideal_neighbor_desc or sp.neighbor_preferences or "Тазалықты сақтайтын, тыныш адам",
    )

    if viewer_has_apt:
        return PRIMARY, cold_cand
    # Viewer has no apartment: ready flats first (DO NOT filter by neighbors_needed!),
    # then co-seekers looking in the same district.
    return (PRIMARY if cand_has_apt else SECONDARY), cold_cand


async def load_active_listings(session: AsyncSession) -> dict:
    """Map owner user_id -> active listing with free places."""
    listings_stmt = (
        select(Listing)
        .where(Listing.status == LISTING_STATUS_ACTIVE, Listing.available_places > 0)
        .order_by(Listing.id)
    )
    all_listings = (await session.execute(listings_stmt)).scalars().all()
    return {l.owner_id: l for l in all_listings}


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
    my_districts = viewer_profile.districts if viewer_profile and viewer_profile.districts else []
    my_district = district_filter or (my_districts[0] if my_districts else "Бостандыкский")
    allowed_districts = allowed_districts_for(my_district, allow_adjacent)

    # Fetch all active profiles excluding self and blocked users
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
    user_to_listing = await load_active_listings(session)
    viewer_listing = user_to_listing.get(viewer_user.id)

    primary: List[ColdCandidate] = []
    secondary: List[ColdCandidate] = []
    for sp, u in raw_results:
        result = evaluate_candidate(
            viewer_user,
            viewer_profile,
            viewer_listing,
            u,
            sp,
            user_to_listing.get(u.id),
            allowed_districts,
        )
        if result is None:
            continue
        bucket, cand = result
        (primary if bucket == PRIMARY else secondary).append(cand)

    return primary, secondary
