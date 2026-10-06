"""Main reply menu keyboards with Kazakh & Russian support - 3 clean aesthetic buttons."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

MENU_SEARCH_RU = "🏠 Поиск"
MENU_SEARCH_KZ = "🏠 Іздеу"

MENU_DISTRICTS_RU = "📍 Районы"
MENU_DISTRICTS_KZ = "📍 Райондар"

MENU_PROFILE_RU = "👤 Профиль"
MENU_PROFILE_KZ = "👤 Профиль"

# Legacy aliases for backward compatibility
MENU_LEGACY_SEARCH_RU = "🔍 Найти соседа 👥"
MENU_LEGACY_SEARCH_KZ = "🔍 Көрші табу 👥"
MENU_LEGACY_DIST_RU = "📍 По районам 📍"
MENU_LEGACY_DIST_KZ = "📍 Район бойынша 📍"
MENU_LEGACY_PROFILE_RU = "👤 Профиль ✨"
MENU_LEGACY_PROFILE_KZ = "👤 Профиль ✨"
MENU_CREATE_RU = "➕ Сдать жилье 🛏"
MENU_CREATE_KZ = "➕ Менде үй бар 🛏"
MENU_MATCHES_RU = "💌 Мэтчи"
MENU_MATCHES_KZ = "💌 Мэтчтер"
MENU_WHO_RU = "👥 Кто ищет"
MENU_WHO_KZ = "👥 Кім іздеп жүр"


def get_main_menu_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Returns minimalist 3-button navigation menu."""
    if lang == "kz":
        btn_search = MENU_SEARCH_KZ
        btn_districts = MENU_DISTRICTS_KZ
        btn_profile = MENU_PROFILE_KZ
    else:
        btn_search = MENU_SEARCH_RU
        btn_districts = MENU_DISTRICTS_RU
        btn_profile = MENU_PROFILE_RU

    keyboard = [
        [KeyboardButton(text=btn_search)],
        [
            KeyboardButton(text=btn_districts),
            KeyboardButton(text=btn_profile),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
