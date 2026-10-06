"""End-to-end bot flows through the real dispatcher with a fake Telegram API.

Covers: full questionnaire with several districts, single-field edit, menu buttons
during the questionnaire, blocked users, seed profiles and the funnel.
"""

from __future__ import annotations

import asyncio
import itertools
from datetime import datetime
from typing import Any, List

import pytest
import pytest_asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy import delete, select, update

from app.bot.bot import setup_routers
from app.db.base import async_session_factory
from app.db.models import FunnelEvent, Listing, SeekerProfile, User
from app.seeds.test_data import seed_database, wipe_database

BOT_USER = TgUser(id=42, is_bot=True, first_name="KorshiTap")


class FakeSession(BaseSession):
    """Records every Bot API call and returns a plausible result."""

    def __init__(self):
        super().__init__()
        self.calls: List[TelegramMethod] = []
        self._ids = itertools.count(1000)

    async def make_request(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(
                message_id=next(self._ids),
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                from_user=BOT_USER,
                text=method.text,
            )
        return True

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:
        pass

    def texts(self) -> List[str]:
        return [getattr(c, "text", None) or "" for c in self.calls]

    def alerts(self) -> List[str]:
        return [getattr(c, "text", None) or "" for c in self.calls if type(c).__name__ == "AnswerCallbackQuery"]


_dispatcher: Dispatcher | None = None


def get_dispatcher() -> Dispatcher:
    # Routers are module-level and can be attached to one dispatcher only
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher(storage=MemoryStorage())
        setup_routers(_dispatcher)
    return _dispatcher


class Client:
    """A fake Telegram user talking to the bot."""

    _update_ids = itertools.count(1)

    def __init__(self, bot: Bot, tg_id: int):
        self.bot = bot
        self.user = TgUser(id=tg_id, is_bot=False, first_name="Тест", language_code="ru")
        self.chat = Chat(id=tg_id, type="private")
        self.dp = get_dispatcher()

    async def send(self, text: str) -> None:
        msg = Message(message_id=next(self._update_ids), date=datetime.now(), chat=self.chat, from_user=self.user, text=text)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), message=msg))

    async def press(self, data: str) -> None:
        bot_msg = Message(message_id=next(self._update_ids), date=datetime.now(), chat=self.chat, from_user=BOT_USER, text="…")
        cb = CallbackQuery(id=str(next(self._update_ids)), from_user=self.user, chat_instance="ci", data=data, message=bot_msg)
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), callback_query=cb))


@pytest_asyncio.fixture
async def bot_env():
    session = FakeSession()
    bot = Bot(token="42:TEST", session=session)
    async with async_session_factory() as db:
        await seed_database(db, count=150, city="Алматы")
    yield bot, session
    test_ids = (7000001, 7000002, 7000003, 7000004)
    async with async_session_factory() as db:
        # Mark the test users as seeds so wipe_database removes them with everything attached
        await db.execute(update(User).where(User.telegram_id.in_(test_ids)).values(is_seed=True))
        await db.execute(delete(FunnelEvent).where(FunnelEvent.telegram_id.in_(test_ids)))
        await db.commit()
        await wipe_database(db)


async def get_profile(tg_id: int):
    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.telegram_id == tg_id))).scalar_one()
        profile = (await db.execute(select(SeekerProfile).where(SeekerProfile.user_id == user.id))).scalar_one_or_none()
        return user, profile


async def fill_questionnaire(c: Client):
    await c.send("/start")
    await c.press("onb_lang:ru")
    await c.press("onb_start_survey")
    await c.press("onb_city:Алматы")
    await c.send("Арман")
    await c.press("onb_gender:male")
    await c.send("23")
    await c.press("onb_occ:working")
    await c.press("onb_apt:no")
    await c.press("onb_dtog:Бостандыкский")
    await c.press("onb_dtog:Алмалинский")
    await c.press("onb_ddone")
    await c.press("onb_pgen:any")
    await c.press("onb_pref_rtype:separate")
    await c.press("onb_bgt:150000:100 000–150 000 ₸")
    await c.press("onb_date:soon:Как можно скорее")
    await c.send("спокойный, не курит")
    await c.send("работаю, люблю порядок")


@pytest.mark.asyncio
async def test_full_questionnaire_with_two_districts(bot_env):
    bot, session = bot_env
    c = Client(bot, 7000001)
    await fill_questionnaire(c)
    await asyncio.sleep(0.2)  # let background alerts finish

    user, profile = await get_profile(7000001)
    assert profile is not None
    assert profile.districts == ["Бостандыкский", "Алмалинский"]
    assert profile.budget_max == 150000
    assert profile.has_apartment is False
    assert user.is_seed is False

    texts = session.texts()
    assert any("Не переводи деньги" in t for t in texts), "safety tip must be shown under the feed"
    # The feed was shown with seed cards, and seed «Написать» buttons do not link anywhere
    sent_markups = [c.reply_markup for c in session.calls if isinstance(c, SendMessage) and c.reply_markup]
    buttons = [b for m in sent_markups for row in getattr(m, "inline_keyboard", []) for b in row]
    assert any(b.callback_data == "seed_chat" for b in buttons)
    assert any((b.callback_data or "").startswith("report_user:") for b in buttons)
    assert not any((b.url or "").startswith("https://t.me/") and b.url != "https://t.me" for b in buttons)

    async with async_session_factory() as db:
        events = set((await db.execute(select(FunnelEvent.name).where(FunnelEvent.telegram_id == 7000001))).scalars())
    assert {"start", "q:waiting_district", "q:waiting_about_self", "profile_completed", "search_shown"} <= events


@pytest.mark.asyncio
async def test_single_field_edit_and_menu_during_questionnaire(bot_env):
    bot, session = bot_env
    c = Client(bot, 7000002)
    await fill_questionnaire(c)

    # Edit only the budget
    await c.press("profile_edit")
    await c.press("pedit:budget")
    await c.press("onb_bgt:200000:150 000–200 000 ₸")
    _, profile = await get_profile(7000002)
    assert profile.budget_max == 200000
    assert profile.districts == ["Бостандыкский", "Алмалинский"]  # untouched

    # Edit districts: toggle one off
    await c.press("pedit:districts")
    await c.press("onb_dtog:Бостандыкский")
    await c.press("onb_ddone")
    _, profile = await get_profile(7000002)
    assert profile.districts == ["Алмалинский"]

    # A menu button pressed mid-questionnaire opens the menu, it is not saved as the name
    await c.press("profile_edit")
    await c.press("profile_edit_full")
    await c.press("onb_city:Алматы")
    await c.send("👤 Профиль")
    _, profile = await get_profile(7000002)
    assert profile.name == "Арман"
    assert any("Твоя анкета" in t for t in session.texts()[-3:])


@pytest.mark.asyncio
async def test_blocked_user_and_seed_chat(bot_env):
    bot, session = bot_env
    c = Client(bot, 7000003)
    await c.send("/start")

    await c.press("seed_chat")
    assert any("тест" in a.lower() for a in session.alerts())  # default language is kz

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.telegram_id == 7000003))).scalar_one()
        user.is_blocked = True
        await db.commit()

    before = len(session.calls)
    await c.send("🏠 Поиск")
    new_texts = session.texts()[before:]
    assert len(new_texts) == 1 and "заблокирован" in new_texts[0]


async def fill_owner_questionnaire(c: Client, budget: str = "100000"):
    await c.send("/start")
    await c.press("onb_lang:kz")
    await c.press("onb_start_survey")
    await c.press("onb_city:Алматы")
    await c.send("Айгерім")
    await c.press("onb_gender:female")
    await c.send("25")
    await c.press("onb_occ:working")
    await c.press("onb_apt:yes")
    await c.press("onb_dist:Медеуский")
    await c.press("onb_pgen:female")
    await c.press("onb_rooms:2-бөлмелі")
    await c.press("onb_rtype:separate")
    await c.press("onb_need:1")
    await c.press("onb_skip_address")
    await c.press(f"onb_bgt:{budget}:{budget} ₸")
    await c.press("onb_date:week:Бір апта ішінде")
    await c.send("таза, тыныш қыз")
    await c.send("жұмыс істеймін")


@pytest.mark.asyncio
async def test_owner_questionnaire_creates_one_listing(bot_env):
    bot, session = bot_env
    c = Client(bot, 7000004)
    await fill_owner_questionnaire(c, "100000")
    await fill_owner_questionnaire(c, "120000")  # re-filled: must not duplicate the listing

    user, profile = await get_profile(7000004)
    assert profile.has_apartment is True
    assert profile.districts == ["Медеуский"]
    async with async_session_factory() as db:
        listings = (await db.execute(select(Listing).where(Listing.owner_id == user.id))).scalars().all()
    assert len(listings) == 1
    assert listings[0].district == "Медеуский"
    assert listings[0].price_per_person == 120000
    assert listings[0].preferred_gender == "female"
