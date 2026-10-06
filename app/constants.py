"""Constants for KORSHI TAP."""

# Supported cities
DEFAULT_CITY = "Алматы"
CITIES = ["Алматы", "Астана", "Шымкент"]

# Official 8 districts of Almaty
ALMATY_DISTRICTS = [
    "Алмалинский",
    "Алатауский",
    "Ауэзовский",
    "Бостандыкский",
    "Жетысуский",
    "Медеуский",
    "Наурызбайский",
    "Турксибский",
]

# Official 5 districts of Astana
ASTANA_DISTRICTS = [
    "Есильский",
    "Алматинский",
    "Байконурский",
    "Сарыаркинский",
    "Нуринский",
]

# Official 5 districts of Shymkent
SHYMKENT_DISTRICTS = [
    "Абайский",
    "Аль-Фарабийский",
    "Енбекшинский",
    "Каратауский",
    "Туранский",
]

CITY_DISTRICTS = {
    "Алматы": ALMATY_DISTRICTS,
    "Астана": ASTANA_DISTRICTS,
    "Шымкент": SHYMKENT_DISTRICTS,
}

# Adjacent districts mapping for intelligent search expansion
ADJACENT_DISTRICTS = {
    # Almaty
    "Бостандыкский": ["Алмалинский", "Медеуский", "Ауэзовский"],
    "Медеуский": ["Бостандыкский", "Алмалинский", "Жетысуский", "Турксибский"],
    "Алмалинский": ["Бостандыкский", "Ауэзовский", "Жетысуский", "Медеуский"],
    "Ауэзовский": ["Бостандыкский", "Алмалинский", "Наурызбайский", "Алатауский"],
    "Наурызбайский": ["Ауэзовский", "Алатауский", "Бостандыкский"],
    "Алатауский": ["Ауэзовский", "Наурызбайский", "Жетысуский", "Турксибский"],
    "Жетысуский": ["Алмалинский", "Медеуский", "Турксибский", "Алатауский"],
    "Турксибский": ["Жетысуский", "Медеуский", "Алатауский"],
    # Astana
    "Есильский": ["Нуринский", "Алматинский", "Сарыаркинский"],
    "Нуринский": ["Есильский", "Сарыаркинский"],
    "Алматинский": ["Есильский", "Байконурский", "Сарыаркинский"],
    "Байконурский": ["Алматинский", "Сарыаркинский"],
    "Сарыаркинский": ["Байконурский", "Есильский", "Нуринский", "Алматинский"],
    # Shymkent
    "Абайский": ["Аль-Фарабийский", "Туранский"],
    "Аль-Фарабийский": ["Абайский", "Енбекшинский", "Каратауский"],
    "Енбекшинский": ["Аль-Фарабийский", "Каратауский"],
    "Каратауский": ["Енбекшинский", "Аль-Фарабийский", "Туранский"],
    "Туранский": ["Абайский", "Каратауский"],
}

# Housing types
HOUSING_TYPE_FLAT = "flat"            # Квартира целиком
HOUSING_TYPE_ROOM = "room"            # Отдельная комната
HOUSING_TYPE_SPOT = "spot"            # Койко-место в комнате
HOUSING_TYPE_SHARING = "sharing"      # Подселение в квартиру

HOUSING_TYPE_LABELS = {
    HOUSING_TYPE_FLAT: "Квартира целиком",
    HOUSING_TYPE_ROOM: "Отдельная комната",
    HOUSING_TYPE_SPOT: "Место в комнате",
    HOUSING_TYPE_SHARING: "Подселение в квартиру",
}

# User roles
ROLE_SEEKER = "seeker"    # Ищу место
ROLE_OWNER = "owner"      # У меня есть место
ROLE_BOTH = "both"

# Genders
GENDER_MALE = "male"
GENDER_FEMALE = "female"
GENDER_ANY = "any"

GENDER_LABELS = {
    GENDER_MALE: "Парень",
    GENDER_FEMALE: "Девушка",
    GENDER_ANY: "Не имеет значения",
}

# Habit choices
HABIT_NO = "no"
HABIT_YES = "yes"
HABIT_NEUTRAL = "neutral"

# Listing statuses
LISTING_STATUS_ACTIVE = "active"
LISTING_STATUS_PAUSED = "paused"
LISTING_STATUS_FILLED = "filled"
LISTING_STATUS_ARCHIVED = "archived"

# Report reasons
REPORT_REASON_FRAUD = "fraud"
REPORT_REASON_OUTDATED = "outdated"
REPORT_REASON_WRONG_INFO = "wrong_info"
REPORT_REASON_BROKER = "broker"
REPORT_REASON_SUSPICIOUS = "suspicious"
REPORT_REASON_OTHER = "other"

REPORT_REASON_LABELS = {
    REPORT_REASON_FRAUD: "Мошенничество",
    REPORT_REASON_OUTDATED: "Уже неактуально",
    REPORT_REASON_WRONG_INFO: "Неправильная информация",
    REPORT_REASON_BROKER: "Посредник / Риелтор",
    REPORT_REASON_SUSPICIOUS: "Подозрительный пользователь",
    REPORT_REASON_OTHER: "Другое",
}

# Match statuses
MATCH_STATUS_MATCHED = "matched"
MATCH_STATUS_CONTACTED = "contacted"
MATCH_STATUS_ARCHIVED = "archived"
