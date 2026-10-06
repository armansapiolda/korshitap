"""Deterministic Mock AI Provider for testing and offline local development."""

import re
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
from app.constants import ALMATY_DISTRICTS, DEFAULT_CITY


class MockAIProvider(AIProvider):
    """Rule-based mock AI provider simulating LLM extraction and scoring."""

    async def parse_neighbor_description(self, text: str) -> NeighborCompatibilityCriteria:
        text_lower = text.lower()
        criteria = NeighborCompatibilityCriteria()

        # Lifestyle
        if any(w in text_lower for w in ["спокойн", "тыныш", "тихий", "тишин", "не шум"]):
            criteria.lifestyle = "quiet"
        elif any(w in text_lower for w in ["активн", "белсенді"]):
            criteria.lifestyle = "active"
        else:
            criteria.lifestyle = "neutral"

        # Parties
        if any(w in text_lower for w in ["тусовк", "вечеринк", "party", "той"]):
            if any(neg in text_lower for neg in ["не ", "без", "қарсы", "болмай"]):
                criteria.parties = "undesirable"
            else:
                criteria.parties = "acceptable"
        elif "не шум" in text_lower or "тыныш" in text_lower:
            criteria.parties = "undesirable"

        # Smoking
        if any(w in text_lower for w in ["не кур", "без кур", "некурящ", "шылым шекпей", "темекісіз"]):
            criteria.smoking = "non_smoker_preferred"
        elif any(w in text_lower for w in ["курить", "кур", "темекі"]):
            criteria.smoking = "acceptable"

        # Cleanliness
        if any(w in text_lower for w in ["аккуратн", "чистот", "таза", "порядок", "жинақы"]):
            criteria.cleanliness = "important"
        else:
            criteria.cleanliness = "moderate"

        # Pets
        if any(w in text_lower for w in ["животн", "жануар", "кот", "кошк", "собак", "ит", "мысық"]):
            if any(ok in text_lower for ok in ["не против", "нормально", "қарсы емес", "жақсы"]):
                criteria.pets = "acceptable"
            elif any(no in text_lower for no in ["без", "болмай", "аллерги", "қарсы"]):
                criteria.pets = "no_pets"
            else:
                criteria.pets = "acceptable"

        # Schedule
        if any(w in text_lower for w in ["9 до 18", "9-18", "жұмыс", "работ", "офис"]):
            criteria.schedule = "works_daytime"
        elif any(w in text_lower for w in ["студент", "оқу", "универ"]):
            criteria.schedule = "student_routine"
        elif any(w in text_lower for w in ["ноч", "түн"]):
            criteria.schedule = "night_shift"
        else:
            criteria.schedule = "flexible"

        criteria.raw_summary = (
            f"Стиль: {criteria.lifestyle}, "
            f"Вечеринки: {criteria.parties or 'нейтрально'}, "
            f"Курение: {criteria.smoking or 'нейтрально'}, "
            f"Чистота: {criteria.cleanliness}, "
            f"Животные: {criteria.pets or 'нейтрально'}"
        )
        return criteria

    async def parse_seeker_text(self, text: str) -> ParsedSeekerProfile:
        text_lower = text.lower()
        profile = ParsedSeekerProfile(city=DEFAULT_CITY)

        # 1. Extract Districts
        found_districts = []
        for dist in ALMATY_DISTRICTS:
            # Match root e.g. "бостандык", "алмалин"
            root = dist[:6].lower()
            if root in text_lower:
                found_districts.append(dist)
        if not found_districts:
            found_districts = ["Бостандыкский"]  # default fallback
        profile.districts = found_districts

        # 2. Extract Budget (e.g., "до 100 000", "120000", "100к", "90 тыс")
        budget_match = re.search(r'(?:до\s*)?(\d{2,3})(?:\s*000|\s*тыс|\s*k|\s*к)', text_lower)
        if budget_match:
            val = int(budget_match.group(1))
            profile.budget_max = val * 1000
        else:
            num_match = re.search(r'(\d{5,6})', text_lower)
            if num_match:
                profile.budget_max = int(num_match.group(1))
            else:
                profile.budget_max = 120000

        # 3. Extract Smoking
        if "не кур" in text_lower or "без кур" in text_lower:
            profile.smoking = "no"
        elif "кур" in text_lower:
            profile.smoking = "yes"
        else:
            profile.smoking = "no"

        # 4. Extract Pets
        if "без животн" in text_lower or "нет животн" in text_lower or "аллерги" in text_lower:
            profile.pets = "no"
        elif "кот" in text_lower or "кошк" in text_lower or "собак" in text_lower or "животн" in text_lower:
            profile.pets = "yes"
        else:
            profile.pets = "no"

        # 5. Extract Occupation
        if "студент" in text_lower or "учусь" in text_lower or "универ" in text_lower:
            profile.occupation = "student"
        elif "работ" in text_lower:
            profile.occupation = "working"
        else:
            profile.occupation = "working"

        # 6. Extract Gender
        if "парень" in text_lower or "мужчин" in text_lower or "парня" in text_lower:
            profile.gender = "male"
        elif "девушк" in text_lower or "женщин" in text_lower:
            profile.gender = "female"

        # 7. Extract Move-in Date
        date_match = re.search(r'(?:с|заселен\w*\s*с)\s*(\d{1,2}\s*[а-яА-Я]+|\d{1,2}\.\d{2})', text_lower)
        if date_match:
            profile.move_in_date = f"с {date_match.group(1)}"
        else:
            profile.move_in_date = "В ближайшее время"

        # 8. Housing type
        if "комнат" in text_lower and "отдельн" in text_lower:
            profile.housing_types = ["room"]
        elif "подселен" in text_lower or "место" in text_lower:
            profile.housing_types = ["spot", "sharing"]
        else:
            profile.housing_types = ["room", "spot"]

        profile.raw_summary = (
            f"Район: {', '.join(profile.districts)}, "
            f"Бюджет: до {profile.budget_max:,} ₸, "
            f"Заселение: {profile.move_in_date}, "
            f"Курение: {profile.smoking}"
        )
        return profile

    async def calculate_compatibility(
        self,
        seeker_info: Dict[str, Any],
        listing_info: Dict[str, Any],
    ) -> CompatibilityScore:
        score = 80
        pros = []
        cons = []

        # District check
        s_districts = seeker_info.get("districts") or []
        l_district = listing_info.get("district")
        if l_district in s_districts:
            score += 10
            pros.append(f"Идеально совпадает район: {l_district}")
        else:
            score -= 15
            cons.append(f"Район {l_district} отличается от запрошенного")

        # Budget check
        s_budget = seeker_info.get("budget_max") or 120000
        l_price = listing_info.get("price_per_person") or 100000
        if l_price <= s_budget:
            score += 5
            pros.append(f"Цена {l_price:,} ₸ укладывается в бюджет")
        else:
            diff = l_price - s_budget
            score -= min(20, int(diff / 5000) * 5)
            cons.append(f"Цена выше бюджета на {diff:,} ₸")

        # Smoking check
        s_smoking = seeker_info.get("smoking") == "yes"
        l_smoking = listing_info.get("smoking_allowed", False)
        if s_smoking and not l_smoking:
            score -= 15
            cons.append("В квартире запрещено курить")
        elif not s_smoking and not l_smoking:
            pros.append("Общее правило: для некурящих")

        # Final bounds
        score = max(30, min(98, score))

        reasoning = f"Совпадение по району ({l_district}) и ключевым бытовым параметрам."
        if pros:
            reasoning += f" Плюсы: {'; '.join(pros)}."

        return CompatibilityScore(
            score=score,
            reasoning=reasoning,
            pros=pros,
            cons=cons,
        )

    async def rank_candidates(
        self,
        viewer_profile: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        lang: str = "kz",
    ) -> AIRankingResult:
        """Deterministic heuristic fallback ranking for candidates."""
        if not candidates:
            return AIRankingResult(candidates=[])

        v_dist = viewer_profile.get("district", "Бостандыкский")
        v_budget = viewer_profile.get("budget", 120000) or 120000
        v_occ = viewer_profile.get("occupation", "working")
        v_has_apt = bool(viewer_profile.get("has_apartment", False))

        scored = []
        for c in candidates:
            score = 50
            c_dist = c.get("district", "")
            c_budget = c.get("budget", 100000) or 100000
            c_occ = c.get("occupation", "")
            c_has_apt = bool(c.get("has_apartment", False))

            if c_dist == v_dist:
                score += 30
            if abs(c_budget - v_budget) <= 20000:
                score += 15
            if c_occ == v_occ:
                score += 10
            if not v_has_apt and c_has_apt:
                score += 15
            elif v_has_apt and not c_has_apt:
                score += 15

            scored.append((score, c))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        ranked_items = []
        for idx, (sc, c) in enumerate(scored):
            name = c.get("name", "Кандидат")
            c_id = c.get("candidate_user_id")
            c_has_apt = bool(c.get("has_apartment", False))
            rank = idx + 1

            if lang == "kz":
                if rank == 1:
                    quality = "excellent"
                    if c_has_apt:
                        reason = "Ауданың бір, бюджетіңе сай келеді және көшу мерзімі тура."
                    else:
                        reason = "Сенің ауданыңнан іздеп жүр, бюджетің мен көшу мерзімің сәйкес."
                elif rank == 2:
                    quality = "good"
                    if c_has_apt:
                        reason = "Дайын пәтері бар, бағасы қолайлы, бірақ бір аптаға кешірек көшеді."
                    else:
                        reason = "Ауданы мен бюджеті сай, бірге пәтер қарастыруға ыңғайлы."
                else:
                    quality = "moderate"
                    reason = "Аудан мен бюджет сәйкес, бірақ көшу мерзімі сәл өзгеше."
            else:
                if rank == 1:
                    quality = "excellent"
                    if c_has_apt:
                        reason = "Твой район, бюджет совпадает и готов заехать в те же сроки."
                    else:
                        reason = "Ищет в твоём районе, бюджет и сроки заселения сходятся."
                elif rank == 2:
                    quality = "good"
                    if c_has_apt:
                        reason = "Квартира уже готова, цена подходит, но заселяется на неделю позже."
                    else:
                        reason = "Район и бюджет сходятся, подходите для совместного поиска."
                else:
                    quality = "moderate"
                    reason = "Район и бюджет сходятся, но дата заселения слегка отличается."

            ranked_items.append(
                RankedCandidateItem(
                    candidate_user_id=c_id,
                    rank_order=rank,
                    human_reason=reason,
                    match_quality=quality,
                )
            )

        return AIRankingResult(candidates=ranked_items)

    async def moderate_content(self, text: str) -> ModerationResult:
        text_lower = text.lower()
        forbidden = ["наркот", "оружи", "интим", "казино", "ставки"]
        for word in forbidden:
            if word in text_lower:
                return ModerationResult(
                    is_safe=False,
                    flag_reason=f"Обнаружено запрещенное слово: {word}",
                )
        return ModerationResult(is_safe=True)
