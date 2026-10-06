"""Test AI free-text extraction capabilities."""

import pytest
from app.ai.mock_provider import MockAIProvider


@pytest.mark.asyncio
async def test_ai_parsing_extracts_all_parameters():
    """
    Requirement 6:
    Input: «Ищу подселение в Бостандыкском районе, желательно рядом с Сайраном,
    бюджет до 100 тысяч, заселиться могу с 15 сентября, не курю».
    AI extracts:
    city = Алматы
    district = Бостандыкский
    budget_max = 100000
    move_in_date = 15 сентября
    smoking = no
    """
    ai = MockAIProvider()
    user_text = (
        "Ищу подселение в Бостандыкском районе, желательно рядом с Сайраном, "
        "бюджет до 100 тысяч, заселиться могу с 15 сентября, не курю."
    )

    parsed = await ai.parse_seeker_text(user_text)

    assert parsed.city == "Алматы"
    assert "Бостандыкский" in parsed.districts
    assert parsed.budget_max == 100000
    assert "15 сентября" in parsed.move_in_date
    assert parsed.smoking == "no"
