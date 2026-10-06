"""Complaint and moderation reports handler."""

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.bot.keyboards.common import get_report_reasons_keyboard
from app.db.base import async_session_factory
from app.services.report_service import ReportService
from app.services.user_service import UserService

router = Router(name="reports_router")


@router.callback_query(F.data.startswith("report_listing:"))
async def cb_report_listing(callback: CallbackQuery):
    listing_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.reply(
        "🚩 **Пожаловаться на объявление**\nУкажите причину жалобы:",
        reply_markup=get_report_reasons_keyboard("listing", listing_id),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("report_user:"))
async def cb_report_user(callback: CallbackQuery):
    target_user_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.reply(
        "🚩 **Пожаловаться на пользователя**\nУкажите причину жалобы:",
        reply_markup=get_report_reasons_keyboard("user", target_user_id),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("rep_reason:"))
async def cb_rep_reason_chosen(callback: CallbackQuery):
    parts = callback.data.split(":")
    target_type = parts[1]
    target_id = int(parts[2])
    reason_code = parts[3]

    async with async_session_factory() as session:
        reporter = await UserService.get_or_create_user(session, callback.from_user.id)
        await ReportService.create_report(
            session=session,
            reporter_id=reporter.id,
            target_type=target_type,
            target_id=target_id,
            reason=reason_code,
        )
        await session.commit()

    await callback.answer("Жалоба принята!", show_alert=True)
    await callback.message.edit_text(
        "✅ **Спасибо! Ваша жалоба отправлена на проверку модераторам.**\n"
        "Мы следим за безопасностью и качеством объявлений в KORSHI TAP.",
        parse_mode="Markdown",
    )


@router.callback_query(F.data == "rep_cancel")
async def cb_rep_cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
