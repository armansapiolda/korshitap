"""District selection keyboards with bilingual support."""

from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.constants import ALMATY_DISTRICTS
from app.i18n import DISTRICTS_RU_TO_KZ


def get_multi_district_keyboard(selected: List[str], lang: str = "ru") -> InlineKeyboardMarkup:
    """Multi-select inline keyboard for Almaty districts with checkboxes."""
    buttons = []
    done_label = "✅ Дайын" if lang == "kz" else "✅ Готово"

    for i in range(0, len(ALMATY_DISTRICTS), 2):
        row = []
        d1 = ALMATY_DISTRICTS[i]
        d1_label = DISTRICTS_RU_TO_KZ.get(d1, d1) if lang == "kz" else d1
        icon1 = "✅ " if d1 in selected else "⬜️ "
        row.append(InlineKeyboardButton(text=f"{icon1}{d1_label}", callback_data=f"dist_toggle:{d1}"))

        if i + 1 < len(ALMATY_DISTRICTS):
            d2 = ALMATY_DISTRICTS[i + 1]
            d2_label = DISTRICTS_RU_TO_KZ.get(d2, d2) if lang == "kz" else d2
            icon2 = "✅ " if d2 in selected else "⬜️ "
            row.append(InlineKeyboardButton(text=f"{icon2}{d2_label}", callback_data=f"dist_toggle:{d2}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text=done_label, callback_data="dist_done")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_single_district_keyboard(prefix: str = "dist_select", lang: str = "ru") -> InlineKeyboardMarkup:
    """Single-select inline keyboard for Almaty districts."""
    buttons = []
    for i in range(0, len(ALMATY_DISTRICTS), 2):
        row = []
        d1 = ALMATY_DISTRICTS[i]
        d1_label = DISTRICTS_RU_TO_KZ.get(d1, d1) if lang == "kz" else d1
        row.append(InlineKeyboardButton(text=f"📍 {d1_label}", callback_data=f"{prefix}:{d1}"))

        if i + 1 < len(ALMATY_DISTRICTS):
            d2 = ALMATY_DISTRICTS[i + 1]
            d2_label = DISTRICTS_RU_TO_KZ.get(d2, d2) if lang == "kz" else d2
            row.append(InlineKeyboardButton(text=f"📍 {d2_label}", callback_data=f"{prefix}:{d2}"))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)
