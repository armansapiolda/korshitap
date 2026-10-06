"""Abstract AI provider interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParsedSeekerProfile(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None  # male, female, any
    city: str = "Алматы"
    districts: List[str] = Field(default_factory=list)
    budget_max: Optional[int] = None
    move_in_date: Optional[str] = None
    spots_needed: int = 1
    housing_types: List[str] = Field(default_factory=list)  # room, spot, sharing, flat
    smoking: Optional[str] = "no"  # no, yes, neutral
    pets: Optional[str] = "no"
    occupation: Optional[str] = "student"  # student, working, other
    preferred_gender: Optional[str] = "any"
    neighbor_preferences: Optional[str] = None
    raw_summary: Optional[str] = None


class CompatibilityScore(BaseModel):
    score: int = Field(..., ge=0, le=100)
    reasoning: str
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)


class ModerationResult(BaseModel):
    is_safe: bool = True
    flag_reason: Optional[str] = None


class NeighborCompatibilityCriteria(BaseModel):
    lifestyle: Optional[str] = None      # quiet, active, neutral
    parties: Optional[str] = None        # undesirable, rare, acceptable
    smoking: Optional[str] = None        # strictly_no, non_smoker_preferred, acceptable
    cleanliness: Optional[str] = None    # important, moderate, relaxed
    pets: Optional[str] = None           # acceptable, no_pets, loves_pets
    schedule: Optional[str] = None       # works_daytime, student_routine, flexible, night_shift
    guest_policy: Optional[str] = None   # rare_guests, open, by_agreement
    raw_summary: Optional[str] = None


class RankedCandidateItem(BaseModel):
    candidate_user_id: int
    rank_order: int
    human_reason: str = Field(description="Natural, personalized, 1-2 sentence human explanation of why this candidate fits, noting advantages or slight differences without technical jargon or percentages.")
    match_quality: str = Field(default="good", description="excellent, good, or moderate")


class AIRankingResult(BaseModel):
    candidates: List[RankedCandidateItem] = Field(default_factory=list)


class AIProvider(ABC):
    """Abstract interface for AI capabilities in KORSHI TAP."""

    @abstractmethod
    async def parse_seeker_text(self, text: str) -> ParsedSeekerProfile:
        """Parse natural language questionnaire into structured seeker profile."""
        pass

    @abstractmethod
    async def parse_neighbor_description(self, text: str) -> NeighborCompatibilityCriteria:
        """Parse natural language neighbor description into structured compatibility criteria."""
        pass

    @abstractmethod
    async def calculate_compatibility(
        self,
        seeker_info: Dict[str, Any],
        listing_info: Dict[str, Any],
    ) -> CompatibilityScore:
        """Calculate semantic compatibility between seeker and listing."""
        pass

    @abstractmethod
    async def rank_candidates(
        self,
        viewer_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        lang: str = "kz",
    ) -> AIRankingResult:
        """Rank candidates comparatively from best to worst and generate unique human explanations."""
        pass

    @abstractmethod
    async def moderate_content(self, text: str) -> ModerationResult:
        """Check user inputs and listings for fraud, spam, or illicit content."""
        pass
