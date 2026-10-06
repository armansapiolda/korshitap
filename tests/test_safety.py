"""Seeds never touch real users; cards survive broken Markdown; funnel counts."""

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage
from sqlalchemy import func, select

from app.bot.cards import md_safe, send_card
from app.bot.notifications import chat_button, get_chat_url
from app.db.models import Listing, SeekerProfile, User
from app.seeds.test_data import seed_database, wipe_database
from app.services.funnel_service import funnel_report, track


@pytest.mark.asyncio
async def test_seeds_are_flagged_and_wipe_keeps_real_users(test_session):
    # conftest already seeded; add a real user with a profile and a listing
    real = User(telegram_id=5550000111, username="real_one", first_name="Real")
    test_session.add(real)
    await test_session.flush()
    test_session.add(SeekerProfile(user_id=real.id, districts=["Бостандыкский"], has_apartment=True))
    test_session.add(Listing(owner_id=real.id, district="Бостандыкский", price_per_person=90000))
    await test_session.commit()

    seeds = (await test_session.execute(select(User).where(User.is_seed == True))).scalars().all()
    assert seeds
    assert all(u.telegram_id < 0 and u.username is None for u in seeds)

    # Seeding twice does not reuse ids
    await seed_database(test_session, count=30)
    ids = (await test_session.execute(select(User.telegram_id))).scalars().all()
    assert len(ids) == len(set(ids))

    deleted = await wipe_database(test_session)
    assert deleted >= len(seeds)
    users = (await test_session.execute(select(User))).scalars().all()
    assert [u.telegram_id for u in users] == [5550000111]
    assert (await test_session.execute(select(func.count(Listing.id)))).scalar_one() == 1
    assert (await test_session.execute(select(func.count(SeekerProfile.id)))).scalar_one() == 1


def test_seed_chat_button_never_links_to_a_real_account():
    seed = User(id=1, telegram_id=-200001, username="aruzhan_4821", is_seed=True)
    real = User(id=2, telegram_id=5550000111, username="real_one", is_seed=False)
    assert chat_button(seed, "ru").url is None
    assert chat_button(seed, "ru").callback_data == "seed_chat"
    assert get_chat_url(seed) == "https://t.me"
    assert chat_button(real, "ru").url == "https://t.me/real_one"


def test_md_safe_strips_markdown_specials():
    assert md_safe("Ару_жан *best* [x]`") == "Аружан best x"
    assert md_safe(None) is None


@pytest.mark.asyncio
async def test_send_card_falls_back_to_plain_text():
    sent = []

    async def send(text, reply_markup=None, parse_mode=None):
        if parse_mode == "Markdown":
            raise TelegramBadRequest(method=SendMessage(chat_id=1, text=text), message="can't parse entities")
        sent.append(text)

    assert await send_card(send, "**Имя**, 22 жаста") is True
    assert sent == ["Имя, 22 жаста"]

    async def always_fails(text, reply_markup=None, parse_mode=None):
        raise RuntimeError("network")

    assert await send_card(always_fails, "x") is False  # never raises


@pytest.mark.asyncio
async def test_funnel_counts_each_user_once_and_ignores_seeds(test_session):
    for _ in range(3):
        await track(test_session, 5550000222, "start")
    await track(test_session, 5550000333, "start")
    await track(test_session, 5550000333, "q:waiting_city")
    await track(test_session, -200001, "start")  # seed
    await test_session.commit()

    report = await funnel_report(test_session)
    steps = {s["label"]: s for s in report["steps"]}
    assert steps["Нажали /start"]["count"] == 2
    assert steps["Начали анкету"]["count"] == 1
    assert steps["Выбрали язык"]["drop_from_prev"] == 2
