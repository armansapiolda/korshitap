"""Shared helpers for sending person cards safely."""

from __future__ import annotations

import logging
import re
from typing import Awaitable, Callable, Optional

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.notifications import chat_button
from app.db.models import User

logger = logging.getLogger(__name__)

_MD_SPECIAL = re.compile(r"[*_`\[\]]")

SAFETY_TIP_RU = "⚠️ Не переводи деньги и предоплату, пока сам не увидел квартиру и хозяина."
SAFETY_TIP_KZ = "⚠️ Пәтер мен иесін өз көзіңмен көрмейінше, ақша немесе алдын ала төлем аударма."


def md_safe(text: Optional[str]) -> Optional[str]:
    """Strip characters that break Telegram Markdown from user-provided text."""
    if text is None:
        return None
    return _MD_SPECIAL.sub("", str(text))


def safety_tip(lang: str) -> str:
    return SAFETY_TIP_KZ if lang == "kz" else SAFETY_TIP_RU


def person_keyboard(user: User, lang: str = "kz") -> InlineKeyboardMarkup:
    """«Написать» + «Пожаловаться» under a person card."""
    report = InlineKeyboardButton(
        text="🚩 Шағым" if lang == "kz" else "🚩 Жалоба",
        callback_data=f"report_user:{user.id}",
    )
    return InlineKeyboardMarkup(inline_keyboard=[[chat_button(user, lang), report]])


async def send_card(send: Callable[..., Awaitable], text: str, reply_markup=None) -> bool:
    """Send with Markdown; if Telegram rejects the formatting, resend as plain text.

    Never raises, so one broken card does not stop the rest of the feed.
    """
    try:
        await send(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    except TelegramBadRequest as e:
        logger.warning("Markdown card rejected (%s), sending as plain text", e)
        try:
            await send(text.replace("**", "").replace("*", ""), reply_markup=reply_markup)
            return True
        except Exception:
            logger.exception("Could not send card")
    except Exception:
        logger.exception("Could not send card")
    return False
