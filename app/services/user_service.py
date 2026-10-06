"""User and SeekerProfile service."""

from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import DEFAULT_CITY, ROLE_SEEKER
from app.db.models import SeekerProfile, User


class UserService:

    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role=ROLE_SEEKER,
            )
            session.add(user)
            await session.flush()
        else:
            # Update meta if changed
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            if last_name and user.last_name != last_name:
                user.last_name = last_name

        return user

    @staticmethod
    async def set_user_language(session: AsyncSession, telegram_id: int, lang: str) -> User:
        user = await UserService.get_or_create_user(session, telegram_id)
        user.language = lang
        await session.flush()
        return user

    @staticmethod
    async def get_user_language(session: AsyncSession, telegram_id: int) -> str:
        user = await UserService.get_or_create_user(session, telegram_id)
        return user.language or "ru"

    @staticmethod
    async def get_user_by_telegram_id(
        session: AsyncSession,
        telegram_id: int,
    ) -> Optional[User]:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def set_user_preferred_gender(session: AsyncSession, telegram_id: int, gender: str) -> User:
        user = await UserService.get_or_create_user(session, telegram_id)
        user.preferred_gender = gender
        await session.flush()
        return user

    @staticmethod
    async def get_user_preferred_gender(session: AsyncSession, telegram_id: int) -> str:
        user = await UserService.get_or_create_user(session, telegram_id)
        return getattr(user, "preferred_gender", None) or "any"

    @staticmethod
    async def update_user_onboarding(
        session: AsyncSession,
        telegram_id: int,
        name: str,
        age: int,
        occupation: str,
    ) -> User:
        user = await UserService.get_or_create_user(session, telegram_id)
        user.first_name = name
        user.age = age
        user.occupation = occupation
        await session.flush()

        profile = await UserService.get_or_create_seeker_profile(session, user.id)
        profile.name = name
        profile.age = age
        profile.occupation = occupation
        await session.flush()
        return user

    @staticmethod
    async def get_or_create_seeker_profile(
        session: AsyncSession,
        user_id: int,
    ) -> SeekerProfile:
        stmt = select(SeekerProfile).where(SeekerProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        if not profile:
            profile = SeekerProfile(
                user_id=user_id,
                city=DEFAULT_CITY,
                districts=["Бостандыкский"],
                budget_max=120000,
            )
            session.add(profile)
            await session.flush()

        return profile

    @staticmethod
    async def update_seeker_profile(
        session: AsyncSession,
        user_id: int,
        data: Dict[str, Any],
    ) -> SeekerProfile:
        profile = await UserService.get_or_create_seeker_profile(session, user_id)
        for key, val in data.items():
            if hasattr(profile, key) and val is not None:
                setattr(profile, key, val)
        await session.flush()
        return profile
