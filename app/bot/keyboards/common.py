"""Common minimalist inline keyboards with bilingual support."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.constants import GENDER_FEMALE, GENDER_MALE
from app.i18n import t


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Language picker at startup or profile."""
    buttons = [
        [
            InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_start_role_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Start role picker in user's language."""
    buttons = [
        [InlineKeyboardButton(text=t("role_seeker", lang), callback_data="role_seeker")],
        [InlineKeyboardButton(text=t("role_owner", lang), callback_data="role_owner")],
        [InlineKeyboardButton(text="🌐 Тілді ауыстыру / Сменить язык", callback_data="change_lang")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_registration_method_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Choice between AI free-text and 3-click express."""
    buttons = [
        [InlineKeyboardButton(text=t("btn_ai_text", lang), callback_data="reg_ai_text")],
        [InlineKeyboardButton(text=t("btn_express", lang), callback_data="reg_express")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_express_budget_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Quick 1-tap budget choices."""
    other_label = "✍️ Басқа сома" if lang == "kz" else "✍️ Другая сумма"
    buttons = [
        [
            InlineKeyboardButton(text="80 000 ₸", callback_data="budget:80000"),
            InlineKeyboardButton(text="100 000 ₸", callback_data="budget:100000"),
        ],
        [
            InlineKeyboardButton(text="120 000 ₸", callback_data="budget:120000"),
            InlineKeyboardButton(text="150 000 ₸", callback_data="budget:150000"),
        ],
        [
            InlineKeyboardButton(text=other_label, callback_data="budget:custom"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_gender_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Minimal gender selector."""
    male_label = t("gender_male", lang)
    female_label = t("gender_female", lang)
    buttons = [
        [
            InlineKeyboardButton(text=male_label, callback_data=f"gender:{GENDER_MALE}"),
            InlineKeyboardButton(text=female_label, callback_data=f"gender:{GENDER_FEMALE}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_ready_to_search_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """1-tap button to launch search."""
    btn_text = "🚀 Кеттік! Варианттарды көру" if lang == "kz" else "🚀 Поехали! Смотреть варианты"
    buttons = [
        [InlineKeyboardButton(text=btn_text, callback_data="launch_search")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirmation_keyboard(prefix: str = "confirm", lang: str = "ru") -> InlineKeyboardMarkup:
    """Quick confirmation."""
    ok_text = "✅ Дұрыс, сақтау" if lang == "kz" else "✅ Всё верно, сохранить"
    redo_text = "✏️ Қайта жазу" if lang == "kz" else "✏️ Переписать"
    buttons = [
        [
            InlineKeyboardButton(text=ok_text, callback_data=f"{prefix}:ok"),
            InlineKeyboardButton(text=redo_text, callback_data=f"{prefix}:redo"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_available_places_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Minimal free spots picker for owners."""
    label = "адам" if lang == "kz" else "чел."
    buttons = [
        [
            InlineKeyboardButton(text=f"1 {label}", callback_data="places:1"),
            InlineKeyboardButton(text=f"2 {label}", callback_data="places:2"),
        ],
        [
            InlineKeyboardButton(text=f"3 {label}", callback_data="places:3"),
            InlineKeyboardButton(text=f"4+ {label}", callback_data="places:4"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_report_reasons_keyboard(target_type: str, target_id: int) -> InlineKeyboardMarkup:
    """Complaint reasons keyboard."""
    from app.constants import REPORT_REASON_LABELS
    buttons = []
    for reason_key, label in REPORT_REASON_LABELS.items():
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"rep_reason:{target_type}:{target_id}:{reason_key}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="rep_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
