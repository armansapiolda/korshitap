"""Google Gemini AI Provider with Vertex AI & AI Studio support."""

import asyncio
import json
import logging
from typing import Any, Dict, List
from app.ai.base import (
    AIProvider,
    AIRankingResult,
    CompatibilityScore,
    ModerationResult,
    NeighborCompatibilityCriteria,
    ParsedSeekerProfile,
    RankedCandidateItem,
)
from app.ai.mock_provider import MockAIProvider
from app.config import settings
from app.constants import ALMATY_DISTRICTS

logger = logging.getLogger(__name__)


class GeminiAIProvider(AIProvider):
    """Integrates Gemini models via Google GenAI SDK (Vertex AI or AI Studio)."""

    def __init__(self):
        self.mock_fallback = MockAIProvider()
        self._client = None
        self._initialized = False

    def _get_client(self):
        if self._initialized:
            return self._client
        try:
            import os
            from google import genai

            if settings.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(settings.GOOGLE_APPLICATION_CREDENTIALS):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(settings.GOOGLE_APPLICATION_CREDENTIALS)

            if settings.USE_VERTEX_AI and settings.GOOGLE_CLOUD_PROJECT:
                self._client = genai.Client(
                    vertexai=True,
                    project=settings.GOOGLE_CLOUD_PROJECT,
                    location=settings.GOOGLE_CLOUD_LOCATION,
                )
                logger.info("Initialized Gemini via Google Cloud Vertex AI (project=%s)", settings.GOOGLE_CLOUD_PROJECT)
            elif settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "test_gemini_key_placeholder":
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Initialized Gemini via Google AI Studio API Key")
            else:
                self._client = None
                logger.warning("No Vertex AI or Gemini API key provided. Using fallback.")
        except Exception as e:
            logger.error("Failed to initialize Google GenAI client: %s", e)
            self._client = None

        self._initialized = True
        return self._client

    async def parse_seeker_text(self, text: str) -> ParsedSeekerProfile:
        client = self._get_client()
        if not client:
            return await self.mock_fallback.parse_seeker_text(text)

        districts_str = ", ".join(ALMATY_DISTRICTS)
        prompt = f"""
Ты AI-ассистент сервиса KORSHI TAP для поиска жилья и соседей в городе Алматы.
Проанализируй текст соискателя жилья и извлеки структурированные данные.
Официальные 8 районов Алматы: {districts_str}.

Текст пользователя:
\"\"\"{text}\"\"\"

Верни JSON со следующими полями:
- name: имя (если упомянуто, иначе null)
- age: возраст (число или null)
- gender: "male", "female" или null
- city: "Алматы"
- districts: массив строк из списка официальных районов Алматы, которые подходят пользователю
- budget_max: число, максимальный бюджет в тенге (например 100000)
- move_in_date: строка, дата заселения (например "с 15 сентября")
- spots_needed: число необходимых мест (по умолчанию 1)
- housing_types: массив из ["room", "spot", "sharing", "flat"]
- smoking: "no", "yes" или "neutral"
- pets: "no", "yes" или "neutral"
- occupation: "student", "working" или "other"
- preferred_gender: "male", "female" или "any"
- neighbor_preferences: строка с пожеланиями к соседям
- raw_summary: краткое резюме требований (1-2 предложения)
"""
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ParsedSeekerProfile,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.AI_MODEL,
                    contents=prompt,
                    config=config,
                ),
                timeout=7.0,
            )
            if response.text:
                data = json.loads(response.text)
                return ParsedSeekerProfile(**data)
        except Exception as e:
            logger.warning("Gemini parsing failed, falling back to mock: %s", e)

        return await self.mock_fallback.parse_seeker_text(text)

    async def parse_neighbor_description(self, text: str) -> NeighborCompatibilityCriteria:
        client = self._get_client()
        if not client:
            return await self.mock_fallback.parse_neighbor_description(text)

        prompt = f"""
Ты экспертный AI-психолог и аналитик совместимости сервиса KORSHI TAP.
Пользователь написал свободное описание идеального соседа или условий проживания (на русском или казахском языке).
Проанализируй глубокий смысл и психологический подтекст текста и извлеки ключевые критерии совместимости.

Текст пользователя:
\"\"\"{text}\"\"\"

Критерии для извлечения:
- lifestyle: стиль жизни ("quiet" если спокойный/тихий/без шума, "active" если активный, "neutral" если нейтральный)
- parties: отношение к тусовкам/вечеринкам ("undesirable" если против тусовок/вечеринок/шума, "rare", "acceptable")
- smoking: отношение к курению ("strictly_no" если строго против, "non_smoker_preferred" если желательно некурящий, "acceptable" если нормально)
- cleanliness: требование к чистоте ("important" если чистоплотный/аккуратный/порядок, "moderate", "relaxed")
- pets: отношение к животным ("acceptable" если нормально/не против, "no_pets" если без животных/аллергия, "loves_pets" если любит)
- schedule: рабочий график/ритм ("works_daytime" если работает с 9 до 18 / днём, "student_routine" если студент, "night_shift" если ночью, "flexible" если гибкий)
- guest_policy: гости ("rare_guests" если без ночёвок гостей, "open" если можно, "by_agreement" если по согласованию)
- raw_summary: 1 ёмкое предложение с ключевыми требованиями
"""
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=NeighborCompatibilityCriteria,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.AI_MODEL,
                    contents=prompt,
                    config=config,
                ),
                timeout=7.0,
            )
            if response.text:
                data = json.loads(response.text)
                return NeighborCompatibilityCriteria(**data)
        except Exception as e:
            logger.warning("Gemini neighbor description parsing failed, falling back to mock: %s", e)

        return await self.mock_fallback.parse_neighbor_description(text)

    async def calculate_compatibility(
        self,
        seeker_info: Dict[str, Any],
        listing_info: Dict[str, Any],
    ) -> CompatibilityScore:
        client = self._get_client()
        if not client:
            return await self.mock_fallback.calculate_compatibility(seeker_info, listing_info)

        prompt = f"""
Ты экспертный AI-ранжировщик сервиса KORSHI TAP в Алматы.
Оцени совместимость соискателя жилья и объявления.

Данные соискателя:
{json.dumps(seeker_info, ensure_ascii=False, default=str)}

Данные объявления:
{json.dumps(listing_info, ensure_ascii=False, default=str)}

Обрати особое внимание на:
1. Район Алматы (критический приоритет)
2. Бюджет (в тенге)
3. Дату заселения
4. Совместимость образов жизни (курение, животные, студенты/работающие)

Верни JSON со следующей структурой:
- score: число от 0 до 100 (процент совместимости)
- reasoning: краткое, ёмкое объяснение на русском языке (почему подходят или нет)
- pros: список строк с главными плюсами совпадения
- cons: список строк с возможными компромиссами/минусами
"""
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CompatibilityScore,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.AI_MODEL,
                    contents=prompt,
                    config=config,
                ),
                timeout=7.0,
            )
            if response.text:
                data = json.loads(response.text)
                return CompatibilityScore(**data)
        except Exception as e:
            logger.warning("Gemini compatibility scoring failed, using fallback: %s", e)

        return await self.mock_fallback.calculate_compatibility(seeker_info, listing_info)

    async def rank_candidates(
        self,
        viewer_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        lang: str = "kz",
    ) -> AIRankingResult:
        """Rank candidates comparatively from best to worst and generate unique human explanations using Gemini Vertex AI."""
        client = self._get_client()
        if not client or not candidates:
            return await self.mock_fallback.rank_candidates(viewer_profile, candidates, lang)

        lang_instruction = (
            "Жауапты таза қазақ тілінде жаз ('сен' деп сөйле, жылы әрі достық үнмен, ешқандай орысша сөздерсіз немесе жақшасыз)."
            if lang == "kz"
            else
            "Пиши на русском языке (обращайся строго на 'ты', дружелюбно, естественно и просто)."
        )

        prompt = f"""
Ты AI-эксперт сервиса KORSHI TAP по сравнительному ранжированию соседей.
Твоя задача — выполнить Второй этап поиска (AI Ranking) на основе объективных фактов.

{lang_instruction}

ДАННЫЕ ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ (для кого подбираем соседа):
{json.dumps(viewer_profile, ensure_ascii=False, indent=2)}

СПИСОК ОТОБРАННЫХ КАНДИДАТОВ (результат объективного холодного поиска):
{json.dumps(candidates, ensure_ascii=False, indent=2)}

СТРОГИЕ ИНСТРУКЦИИ ДЛЯ AI-РАНЖИРОВАНИЯ:
1. Сравни всех переданных кандидатов МЕЖДУ СОБОЙ относительно текущего пользователя.
2. Расположи их в строгом порядке: от наиболее подходящего к менее подходящему (rank_order: 1 для лучшего, 2 для следующего и т.д.). Включи ВСЕХ переданных кандидатов.
3. Оценивай реальные факторы: район, бюджет, сроки заселения, статус жилья (есть ли квартира, отдельная/общая комната), стиль жизни (студент/работа, чистота, тишина).

СТРОГИЕ ТРЕБОВАНИЯ К ОБЪЯСНЕНИЮ (human_reason):
- Текст должен быть МАКСИМАЛЬНО ПРИЗЕМЛЁННЫМ, СВЕРХКОРОТКИМ И СТРОГО ПО ФАКТУ (1 короткое предложение, максимум 15-18 слов).
- НИКАКОЙ ВОДЫ И РЕКЛАМНЫХ ШТАМПОВ: категорически запрещены слова вроде «отличный вариант», «прекрасный выбор», «хороший кандидат», «подходит чуть меньше».
- Пиши только конкретные жизненные факты: район, совпадение бюджета, дата заезда, реальный нюанс (если есть) или стиль жизни.
- Примеры стиля на русском:
  * «Твой район, бюджет совпадает и готов заехать в те же сроки.»
  * «Квартира уже готова, цена комфортная, но заселяется на неделю позже.»
  * «Ищет в твоём районе, тоже студент, тихий режим и схожий бюджет.»
  * «Район и бюджет сходятся, но комната общая, а не отдельная.»
- Примеры стиля на казахском:
  * «Ауданың бір, бюджетіңе сай келеді және көшу мерзімі тура.»
  * «Дайын пәтері бар, бағасы қолайлы, бірақ бір аптаға кешірек көшеді.»
  * «Сенің ауданыңнан іздеп жүр, студент, тыныштық пен тәртіпті ұнатады.»
  * «Бағасы мен ауданы сәйкес, бірақ бөлме жеке емес, ортақ.»
- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать проценты, формулы, веса алгоритма или выдуманные факты.

Верни строго JSON со схемой AIRankingResult.
"""
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AIRankingResult,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.AI_MODEL,
                    contents=prompt,
                    config=config,
                ),
                timeout=7.0,
            )
            if response.text:
                data = json.loads(response.text)
                res = AIRankingResult(**data)
                if res.candidates:
                    return res
        except Exception as e:
            logger.warning("Gemini AI ranking failed, falling back to heuristic: %s", e)

        return await self.mock_fallback.rank_candidates(viewer_profile, candidates, lang)

    async def moderate_content(self, text: str) -> ModerationResult:
        client = self._get_client()
        if not client:
            return await self.mock_fallback.moderate_content(text)

        prompt = f"""
Проверь текст объявления или сообщения на мошенничество, спам, запрещённые темы (наркотики, интим-услуги, скам).
Текст: \"\"\"{text}\"\"\"

Верни JSON:
- is_safe: boolean (true если безопасно)
- flag_reason: строка с причиной подозрения или null
"""
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ModerationResult,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.AI_MODEL,
                    contents=prompt,
                    config=config,
                ),
                timeout=7.0,
            )
            if response.text:
                data = json.loads(response.text)
                return ModerationResult(**data)
        except Exception as e:
            logger.warning("Gemini moderation check failed, using fallback: %s", e)

        return await self.mock_fallback.moderate_content(text)
