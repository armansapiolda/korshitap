"""Configurable matching weights for KORSHI TAP."""

from typing import Dict
from pydantic import BaseModel, Field


class MatchingWeights(BaseModel):
    district: float = Field(0.35, ge=0.0, le=1.0)
    budget: float = Field(0.20, ge=0.0, le=1.0)
    move_in_date: float = Field(0.15, ge=0.0, le=1.0)
    housing_type: float = Field(0.10, ge=0.0, le=1.0)
    gender: float = Field(0.05, ge=0.0, le=1.0)
    lifestyle: float = Field(0.10, ge=0.0, le=1.0)
    extra: float = Field(0.05, ge=0.0, le=1.0)

    def normalized_dict(self) -> Dict[str, float]:
        raw = {
            "district": self.district,
            "budget": self.budget,
            "move_in_date": self.move_in_date,
            "housing_type": self.housing_type,
            "gender": self.gender,
            "lifestyle": self.lifestyle,
            "extra": self.extra,
        }
        total = sum(raw.values())
        if total <= 0:
            return raw
        return {k: v / total for k, v in raw.items()}


DEFAULT_WEIGHTS = MatchingWeights()
