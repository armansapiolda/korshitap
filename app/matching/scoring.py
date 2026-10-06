"""Deterministic scoring algorithm for candidate listings."""

from typing import Any, Dict
from app.constants import ADJACENT_DISTRICTS
from app.matching.weights import MatchingWeights


def calculate_deterministic_score(
    seeker: Dict[str, Any],
    listing: Dict[str, Any],
    weights: MatchingWeights,
) -> float:
    """
    Calculate deterministic matching score (0.0 to 100.0) based on weights.
    """
    w = weights.normalized_dict()

    # 1. District Score (Weight: 35%)
    # Highest priority in Korshi Tap
    seeker_districts = seeker.get("districts") or []
    listing_district = listing.get("district")
    if listing_district in seeker_districts:
        district_subscore = 100.0
    else:
        # Check if it is an adjacent district
        is_adjacent = False
        for s_dist in seeker_districts:
            if listing_district in ADJACENT_DISTRICTS.get(s_dist, []):
                is_adjacent = True
                break
        district_subscore = 60.0 if is_adjacent else 20.0

    # 2. Budget Score (Weight: 20%)
    budget_max = seeker.get("budget_max") or 120000
    price = listing.get("price_per_person") or 100000
    if price <= budget_max:
        budget_subscore = 100.0
    elif price <= budget_max * 1.15:
        # Grace margin penalty
        over_pct = (price - budget_max) / (budget_max * 0.15)
        budget_subscore = max(40.0, 100.0 - (over_pct * 60.0))
    else:
        budget_subscore = 0.0

    # 3. Move-in Date Score (Weight: 15%)
    seeker_date = str(seeker.get("move_in_date") or "").lower()
    listing_date = str(listing.get("move_in_date") or "").lower()
    if not seeker_date or not listing_date or "любое" in seeker_date or "ближайшее" in seeker_date:
        date_subscore = 90.0
    elif seeker_date in listing_date or listing_date in seeker_date:
        date_subscore = 100.0
    else:
        date_subscore = 75.0

    # 4. Housing Type Score (Weight: 10%)
    seeker_types = seeker.get("housing_types") or []
    listing_type = listing.get("housing_type")
    if not seeker_types or listing_type in seeker_types:
        housing_subscore = 100.0
    else:
        housing_subscore = 50.0

    # 5. Gender Compatibility (Weight: 5%)
    seeker_gender = seeker.get("gender")
    listing_pref_gender = listing.get("preferred_gender", "any")
    if listing_pref_gender in ("any", None) or listing_pref_gender == seeker_gender:
        gender_subscore = 100.0
    else:
        gender_subscore = 0.0

    # 6. Lifestyle (Smoking & Pets) (Weight: 10%)
    lifestyle_points = 100.0
    seeker_smokes = seeker.get("smoking") == "yes"
    listing_smoking = listing.get("smoking_allowed", False)
    if seeker_smokes and not listing_smoking:
        lifestyle_points -= 50.0

    seeker_pets = seeker.get("pets") == "yes"
    listing_pets = listing.get("pets_allowed", False)
    if seeker_pets and not listing_pets:
        lifestyle_points -= 50.0
    lifestyle_subscore = max(0.0, lifestyle_points)

    # 7. Extra Preferences (Weight: 5%)
    extra_subscore = 80.0
    if listing.get("utilities_included"):
        extra_subscore += 20.0
    if listing.get("is_verified"):
        extra_subscore += 10.0
    extra_subscore = min(100.0, extra_subscore)

    # Total weighted sum
    total = (
        district_subscore * w["district"]
        + budget_subscore * w["budget"]
        + date_subscore * w["move_in_date"]
        + housing_subscore * w["housing_type"]
        + gender_subscore * w["gender"]
        + lifestyle_subscore * w["lifestyle"]
        + extra_subscore * w["extra"]
    )
    return round(total, 1)
