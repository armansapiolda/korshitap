"""Minimalist bilingual localization (Kazakh & Russian) - clean, concise, no extra words."""

from typing import Dict

DISTRICTS_RU_TO_KZ = {
    # Almaty
    "Бостандыкский": "Бостандық",
    "Алмалинский": "Алмалы",
    "Медеуский": "Медеу",
    "Ауэзовский": "Әуезов",
    "Жетысуский": "Жетісу",
    "Наурызбайский": "Наурызбай",
    "Турксибский": "Түрксіб",
    "Алатауский": "Алатау",
    # Astana
    "Есильский": "Есіл",
    "Байконурский": "Байқоңыр",
    "Сарыаркинский": "Сарыарқа",
    "Нуринский": "Нұра",
    # Shymkent
    "Абайский": "Абай",
    "Аль-Фарабийский": "Әл-Фараби",
    "Енбекшинский": "Еңбекші",
    "Каратауский": "Қаратау",
    "Туранский": "Тұран",
}

DISTRICTS_KZ_TO_RU = {v: k for k, v in DISTRICTS_RU_TO_KZ.items()}

TEXTS: Dict[str, Dict[str, str]] = {
    # Main Navigation Menu
    "menu_search": {
        "ru": "🔍 Поиск",
        "kz": "🔍 Іздеу",
    },
    "menu_matches": {
        "ru": "❤️ Мэтчи",
        "kz": "❤️ Сәйкестіктер",
    },
    "menu_create": {
        "ru": "➕ Добавить",
        "kz": "➕ Қосу",
    },
    "menu_districts": {
        "ru": "📍 Поиск по районам",
        "kz": "📍 Район бойынша іздеу",
    },
    "menu_who_is_looking": {
        "ru": "👥 Кто ищет",
        "kz": "👥 Кім іздеп жүр?",
    },
    "menu_profile": {
        "ru": "👤 Профиль",
        "kz": "👤 Профиль",
    },

    # Welcome
    "welcome": {
        "ru": "Привет! 👋 Что ищешь?",
        "kz": "Сәлем! 👋 Не істейміз?",
    },

    # Roles
    "role_seeker": {
        "ru": "🏠 Ищу жильё / подселение",
        "kz": "🏠 Пәтер / подселение іздеймін",
    },
    "role_owner": {
        "ru": "🛏 Сдаю свободное место",
        "kz": "🛏 Бос орын беремін",
    },

    # Seeker steps - Super simple, no examples
    "choose_district": {
        "ru": "📍 Какой район?",
        "kz": "📍 Қай аудан?",
    },
    "choose_budget": {
        "ru": "💰 Твой бюджет:",
        "kz": "💰 Бюджетің қанша:",
    },
    "choose_gender": {
        "ru": "🙋‍♂️ Пол:",
        "kz": "🙋‍♂️ Жынысың:",
    },
    "gender_male": {
        "ru": "Парень",
        "kz": "Жігіт",
    },
    "gender_female": {
        "ru": "Девушка",
        "kz": "Қыз",
    },

    # Card Swipe Buttons
    "btn_like": {
        "ru": "❤️ Подходит",
        "kz": "❤️ Ұнайды",
    },
    "btn_pass": {
        "ru": "❌ Пропустить",
        "kz": "❌ Өткізу",
    },
    "btn_details": {
        "ru": "👀 Подробнее",
        "kz": "👀 Толығырақ",
    },
    "btn_report": {
        "ru": "🚩 Жалоба",
        "kz": "🚩 Шағым",
    },

    # District Exhaustion
    "district_exhausted": {
        "ru": "📍 В этом районе варианты закончились. Поискать в соседних?",
        "kz": "📍 Бұл ауданда нұсқалар бітті. Көрші аудандардан қараймыз ба?",
    },
    "btn_adjacent": {
        "ru": "🔎 В соседних районах",
        "kz": "🔎 Көршілес аудандардан",
    },
    "btn_choose_other": {
        "ru": "📍 Другой район",
        "kz": "📍 Басқа аудан",
    },
    "btn_subscribe": {
        "ru": "⏳ Уведомить о новых (🔔)",
        "kz": "⏳ Жаңадан шықса хабарлау (🔔)",
    },

    # Match announcement
    "match_alert": {
        "ru": "🎉 **У вас MATCH!**\nВы понравились друг другу! Напишите прямо сейчас:",
        "kz": "🎉 **Сіздерде MATCH!**\nБір-біріңізге сәйкес келдіңіздер! Қазір жазыңыз:",
    },
}


def t(key: str, lang: str = "ru") -> str:
    """Get localized text."""
    entry = TEXTS.get(key, {})
    return entry.get(lang) or entry.get("ru", key)


def get_district_name(district_ru: str, lang: str = "ru") -> str:
    """Get localized district name."""
    if lang == "kz":
        base = DISTRICTS_RU_TO_KZ.get(district_ru, district_ru)
        return f"{base} ауданы"
    return f"{district_ru} район"
