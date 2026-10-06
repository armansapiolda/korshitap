"""Report service for handling user complaints and fraud flags."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Report, User


class ReportService:

    @staticmethod
    async def create_report(
        session: AsyncSession,
        reporter_id: int,
        target_type: str,
        target_id: int,
        reason: str,
        details: Optional[str] = None,
    ) -> Report:
        report = Report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            details=details,
            status="pending",
        )
        session.add(report)
        await session.flush()
        return report

    @staticmethod
    async def get_all_reports(session: AsyncSession) -> List[Report]:
        stmt = select(Report).options(selectinload(Report.reporter)).order_by(Report.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def update_report_status(session: AsyncSession, report_id: int, new_status: str) -> Optional[Report]:
        stmt = select(Report).where(Report.id == report_id)
        res = await session.execute(stmt)
        report = res.scalar_one_or_none()
        if report:
            report.status = new_status
            await session.flush()
        return report
