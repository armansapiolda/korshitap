"""Tracking of already shown / already notified candidates."""

from typing import Iterable, Set
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateEvent

KIND_SHOWN = "shown"
KIND_NOTIFIED = "notified"


class CandidateEventService:

    @staticmethod
    async def get_candidate_ids(session: AsyncSession, viewer_user_id: int, kind: str) -> Set[int]:
        stmt = select(CandidateEvent.candidate_user_id).where(
            CandidateEvent.viewer_user_id == viewer_user_id,
            CandidateEvent.kind == kind,
        )
        return set((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def record(
        session: AsyncSession,
        viewer_user_id: int,
        candidate_user_ids: Iterable[int],
        kind: str,
    ) -> None:
        existing = await CandidateEventService.get_candidate_ids(session, viewer_user_id, kind)
        for cand_id in set(candidate_user_ids) - existing:
            session.add(CandidateEvent(viewer_user_id=viewer_user_id, candidate_user_id=cand_id, kind=kind))
        await session.flush()

    @staticmethod
    async def reset(session: AsyncSession, viewer_user_id: int, kind: str) -> None:
        await session.execute(
            delete(CandidateEvent).where(
                CandidateEvent.viewer_user_id == viewer_user_id,
                CandidateEvent.kind == kind,
            )
        )
