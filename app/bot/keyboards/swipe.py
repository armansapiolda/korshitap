"""Tinder-style card keyboards with bilingual support."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.i18n import t


def get_swipe_keyboard(listing_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Action buttons for listing swipe card."""
    buttons = [
        [
            InlineKeyboardButton(text=t("btn_like", lang), callback_data=f"swipe_like:{listing_id}"),
            InlineKeyboardButton(text=t("btn_pass", lang), callback_data=f"swipe_pass:{listing_id}"),
        ],
        [
            InlineKeyboardButton(text=t("btn_details", lang), callback_data=f"swipe_details:{listing_id}"),
            InlineKeyboardButton(text=t("btn_report", lang), callback_data=f"report_listing:{listing_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_district_exhausted_keyboard(district_name: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Prompt when listings in the chosen district run out."""
    buttons = [
        [
            InlineKeyboardButton(
                text=t("btn_adjacent", lang),
                callback_data="exhaust_adjacent",
            )
        ],
        [
            InlineKeyboardButton(
                text=t("btn_choose_other", lang),
                callback_data="exhaust_choose_other",
            )
        ],
        [
            InlineKeyboardButton(
                text=t("btn_subscribe", lang),
                callback_data="exhaust_subscribe",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_owner_swipe_keyboard(seeker_user_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Action buttons for owner viewing seeker candidates in 'Кто ищет'."""
    buttons = [
        [
            InlineKeyboardButton(text=t("btn_like", lang), callback_data=f"owner_like:{seeker_user_id}"),
            InlineKeyboardButton(text=t("btn_pass", lang), callback_data=f"owner_pass:{seeker_user_id}"),
        ],
        [
            InlineKeyboardButton(text=t("btn_report", lang), callback_data=f"report_user:{seeker_user_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
