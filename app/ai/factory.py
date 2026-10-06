"""AI Provider factory."""

from app.ai.base import AIProvider
from app.ai.gemini_provider import GeminiAIProvider
from app.ai.mock_provider import MockAIProvider
from app.config import settings

_provider_instance = None


def get_ai_provider() -> AIProvider:
    """Return configured AIProvider instance."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    if settings.AI_PROVIDER in ("gemini", "vertex"):
        _provider_instance = GeminiAIProvider()
    else:
        _provider_instance = MockAIProvider()

    return _provider_instance
