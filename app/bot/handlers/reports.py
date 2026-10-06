"""Complaint and moderation reports handler."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.constants import REPORT_REASON_LABELS, REPORT_REASON_LABELS_KZ
from app.db.base import async_session_factory
from app.db.models import Report
from app.services.funnel_service import EVENT_REPORT_SENT, track
from app.services.report_service import ReportService
from app.services.user_service import UserService

router = Router(name="reports_router")


def get_report_reasons_keyboard(target_type: str, target_id: int, lang: str) -> InlineKeyboardMarkup:
    labels = REPORT_REASON_LABELS_KZ if lang == "kz" else REPORT_REASON_LABELS
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"rep_reason:{target_type}:{target_id}:{key}")]
        for key, label in labels.items()
    ]
    buttons.append([
        InlineKeyboardButton(text="Болдырмау" if lang == "kz" else "Отмена", callback_data="rep_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _ask_reason(callback: CallbackQuery, target_type: str):
    target_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        lang = await UserService.get_user_language(session, callback.from_user.id)
    await callback.answer()
    if target_type == "listing":
        text = "🚩 **Хабарландыруға шағым**\nСебебін таңда:" if lang == "kz" else "🚩 **Жалоба на объявление**\nВыбери причину:"
    else:
        text = "🚩 **Адамға шағым**\nСебебін таңда:" if lang == "kz" else "🚩 **Жалоба на человека**\nВыбери причину:"
    await callback.message.reply(
        text,
        reply_markup=get_report_reasons_keyboard(target_type, target_id, lang),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("report_listing:"))
async def cb_report_listing(callback: CallbackQuery):
    await _ask_reason(callback, "listing")


@router.callback_query(F.data.startswith("report_user:"))
async def cb_report_user(callback: CallbackQuery):
    await _ask_reason(callback, "user")


@router.callback_query(F.data.startswith("rep_reason:"))
async def cb_rep_reason_chosen(callback: CallbackQuery):
    parts = callback.data.split(":")
    target_type = parts[1]
    target_id = int(parts[2])
    reason_code = parts[3]

    async with async_session_factory() as session:
        reporter = await UserService.get_or_create_user(session, callback.from_user.id)
        lang = reporter.language or "ru"
        already = (
            await session.execute(
                select(Report.id).where(
                    Report.reporter_id == reporter.id,
                    Report.target_type == target_type,
                    Report.target_id == target_id,
                    Report.status == "pending",
                )
            )
        ).first()
        if not already:
            await ReportService.create_report(
                session=session,
                reporter_id=reporter.id,
                target_type=target_type,
                target_id=target_id,
                reason=reason_code,
            )
            await track(session, callback.from_user.id, EVENT_REPORT_SENT)
            await session.commit()

    await callback.answer("Шағым қабылданды!" if lang == "kz" else "Жалоба принята!", show_alert=True)
    await callback.message.edit_text(
        "✅ **Рақмет! Шағымың модераторларға тексеруге жіберілді.**"
        if lang == "kz"
        else
        "✅ **Спасибо! Жалоба отправлена модераторам на проверку.**",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "rep_cancel")
async def cb_rep_cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
