"""Funnel analytics: which steps real users reach and where they drop off."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FunnelEvent

logger = logging.getLogger(__name__)

EVENT_START = "start"
EVENT_PROFILE_COMPLETED = "profile_completed"
EVENT_SEARCH_SHOWN = "search_shown"
EVENT_SEARCH_EMPTY = "search_empty"
EVENT_REPORT_SENT = "report_sent"
EVENT_PROFILE_HIDDEN = "profile_hidden"

# Ordered funnel shown on the admin dashboard: (event name, label)
FUNNEL_STEPS: List[Tuple[str, str]] = [
    (EVENT_START, "Нажали /start"),
    ("q:waiting_welcome", "Выбрали язык"),
    ("q:waiting_city", "Начали анкету"),
    ("q:waiting_name", "Выбрали город"),
    ("q:waiting_gender", "Написали имя"),
    ("q:waiting_age", "Указали пол"),
    ("q:waiting_occupation", "Указали возраст"),
    ("q:waiting_has_apartment", "Указали занятость"),
    ("q:waiting_district", "Ответили про квартиру"),
    ("q:waiting_neighbor_gender", "Выбрали район"),
    ("q:waiting_budget", "Ответили про жильё"),
    ("q:waiting_move_in_date", "Указали бюджет"),
    ("q:waiting_ideal_neighbor", "Указали дату заезда"),
    ("q:waiting_about_self", "Описали идеального соседа"),
    (EVENT_PROFILE_COMPLETED, "Анкета заполнена"),
    (EVENT_SEARCH_SHOWN, "Увидели кандидатов"),
]

EXTRA_EVENTS: List[Tuple[str, str]] = [
    (EVENT_SEARCH_EMPTY, "Получили пустую выдачу"),
    (EVENT_REPORT_SENT, "Отправили жалобу"),
    (EVENT_PROFILE_HIDDEN, "Скрыли анкету (нашли соседа)"),
]


async def track(session: AsyncSession, telegram_id: int, name: str) -> None:
    """Record that a user reached a step (only the first time). Seeds are never tracked."""
    if telegram_id is None or telegram_id <= 0:
        return
    exists = (
        await session.execute(
            select(FunnelEvent.id).where(FunnelEvent.telegram_id == telegram_id, FunnelEvent.name == name)
        )
    ).first()
    if exists:
        return
    try:
        async with session.begin_nested():
            session.add(FunnelEvent(telegram_id=telegram_id, name=name))
    except IntegrityError:
        pass  # recorded concurrently


async def track_now(telegram_id: int, name: str) -> None:
    """Fire-and-forget style helper that opens its own session and never raises."""
    from app.db.base import async_session_factory

    try:
        async with async_session_factory() as session:
            await track(session, telegram_id, name)
            await session.commit()
    except Exception:
        logger.exception("Funnel tracking failed")


async def funnel_counts(session: AsyncSession) -> Dict[str, int]:
    rows = (
        await session.execute(select(FunnelEvent.name, func.count(FunnelEvent.id)).group_by(FunnelEvent.name))
    ).all()
    return {name: count for name, count in rows}


async def funnel_report(session: AsyncSession) -> dict:
    counts = await funnel_counts(session)
    top = counts.get(EVENT_START, 0) or max(counts.values(), default=0)
    steps = []
    prev = None
    for name, label in FUNNEL_STEPS:
        value = counts.get(name, 0)
        steps.append({
            "label": label,
            "count": value,
            "pct_of_start": round(value * 100 / top) if top else 0,
            "drop_from_prev": (prev - value) if prev is not None else 0,
        })
        prev = value
    extras = [{"label": label, "count": counts.get(name, 0)} for name, label in EXTRA_EVENTS]
    return {"steps": steps, "extras": extras}
