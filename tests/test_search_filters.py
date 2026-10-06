"""Tests for budget/date filters, "already shown" tracking, new-profile alerts,
freshness reminders and questionnaire -> listing sync."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.bot.handlers.freshness import ACTION_HIDE, ACTION_PING, find_stale_profiles
from app.bot.handlers.profile import set_profile_active
from app.bot.notifications import find_users_to_alert_about
from app.constants import LISTING_STATUS_ACTIVE, LISTING_STATUS_ARCHIVED, LISTING_STATUS_PAUSED
from app.db.models import Listing, SeekerProfile, User
from app.matching.cold_search import budgets_compatible, perform_cold_search
from app.matching.dates import parse_move_in_window, windows_compatible
from app.services.candidate_event_service import KIND_SHOWN, CandidateEventService
from app.services.listing_service import ListingService

TODAY = date(2026, 10, 6)
# Turksib district of Almaty is not used by the seed generator's fixed users,
# but seeds may still put people there, so tests only assert on their own users.
DISTRICT = "Турксибский"


async def make_person(session, uid, *, has_apartment=False, budget=100000, move_in="Как можно скорее",
                      gender="male", preferred_gender="any", district=DISTRICT, notifications=True):
    user = User(id=uid, telegram_id=uid, first_name=f"U{uid}", gender=gender, preferred_gender=preferred_gender)
    session.add(user)
    await session.flush()
    profile = SeekerProfile(
        user_id=uid,
        name=f"U{uid}",
        gender=gender,
        preferred_gender=preferred_gender,
        city="Алматы",
        districts=[district],
        has_apartment=has_apartment,
        budget_max=budget,
        move_in_date=move_in,
        notifications_enabled=notifications,
        is_active=True,
    )
    session.add(profile)
    await session.flush()
    return user, profile


# ------------------------------------------------------------------ dates

def test_parse_specific_dates_ru_and_kz():
    assert parse_move_in_window("с 20 октября", today=TODAY) == (14, 28)
    assert parse_move_in_window("20 қазан", today=TODAY) == (14, 28)
    # A date that already passed means "available now"
    assert parse_move_in_window("с 10 сентября", today=TODAY) == (0, 14)
    # Far in the past -> next year
    start, _ = parse_move_in_window("с 1 марта", today=TODAY)
    assert start > 100


def test_parse_relative_labels():
    assert parse_move_in_window("В течение недели", today=TODAY) == (0, 7)
    assert parse_move_in_window("Бір ай ішінде", today=TODAY) == (0, 30)
    assert parse_move_in_window("Через 1–2 месяца", today=TODAY) == (30, 60)
    assert parse_move_in_window("1–2 айдан кейін", today=TODAY) == (30, 60)
    assert parse_move_in_window("⚡ Как можно скорее", today=TODAY) == (0, 7)
    assert parse_move_in_window("в ближайшие 3 дня", today=TODAY) == (0, 7)
    # Flexible / unknown
    assert parse_move_in_window("Пока просто ищу", today=TODAY) is None
    assert parse_move_in_window("Әзірге жай іздеп жүрмін", today=TODAY) is None
    assert parse_move_in_window(None) is None


def test_relative_label_counts_from_when_it_was_said():
    stated = datetime(2026, 9, 6)  # 30 days before TODAY
    assert parse_move_in_window("Через 1–2 месяца", stated_at=stated, today=TODAY) == (0, 30)


def test_window_compatibility():
    assert windows_compatible((0, 7), (0, 30))
    assert windows_compatible((0, 7), (14, 28))  # 7 day gap, within tolerance
    assert not windows_compatible((0, 7), (30, 60))
    assert windows_compatible(None, (30, 60))


# ------------------------------------------------------------------ budget

def test_budget_compatibility_rules():
    # Seeker vs flat: price may exceed budget by up to 15%
    assert budgets_compatible(100000, False, 110000, True)
    assert not budgets_compatible(100000, False, 130000, True)
    # Owner vs seeker: same rule from the other side
    assert budgets_compatible(110000, True, 100000, False)
    assert not budgets_compatible(150000, True, 100000, False)
    # Co-seekers: larger budget at most 1.5x the smaller one
    assert budgets_compatible(100000, False, 150000, False)
    assert not budgets_compatible(70000, False, 150000, False)
    # Missing data never filters anyone out
    assert budgets_compatible(None, False, 500000, True)


@pytest.mark.asyncio
async def test_cold_search_applies_budget_and_date(test_session):
    viewer, viewer_prof = await make_person(test_session, 990001, budget=100000, move_in="Как можно скорее")
    await make_person(test_session, 990002, has_apartment=True, budget=105000, move_in="Как можно скорее")
    await make_person(test_session, 990003, has_apartment=True, budget=200000, move_in="Как можно скорее")
    await make_person(test_session, 990004, has_apartment=True, budget=100000, move_in="Через 1–2 месяца")
    await make_person(test_session, 990005, budget=120000, move_in="Пока просто ищу")
    await make_person(test_session, 990006, budget=60000, move_in="Как можно скорее")
    await test_session.commit()

    primary, secondary = await perform_cold_search(test_session, viewer, viewer_prof, district_filter=DISTRICT)
    primary_ids = {c.user.id for c in primary}
    secondary_ids = {c.user.id for c in secondary}

    assert 990002 in primary_ids          # fits budget and date
    assert 990003 not in primary_ids      # too expensive
    assert 990004 not in primary_ids      # moves in too late
    assert 990005 in secondary_ids        # flexible date, close budget
    assert 990006 not in secondary_ids    # budget too far apart


# ------------------------------------------------------------------ already shown

@pytest.mark.asyncio
async def test_candidate_event_service_roundtrip(test_session):
    viewer, _ = await make_person(test_session, 990101)
    await make_person(test_session, 990102)
    await make_person(test_session, 990103)

    await CandidateEventService.record(test_session, viewer.id, [990102, 990103], KIND_SHOWN)
    await CandidateEventService.record(test_session, viewer.id, [990102], KIND_SHOWN)  # no duplicate error
    await test_session.commit()
    assert await CandidateEventService.get_candidate_ids(test_session, viewer.id, KIND_SHOWN) == {990102, 990103}

    await CandidateEventService.reset(test_session, viewer.id, KIND_SHOWN)
    await test_session.commit()
    assert await CandidateEventService.get_candidate_ids(test_session, viewer.id, KIND_SHOWN) == set()


# ------------------------------------------------------------------ new profile alerts

@pytest.mark.asyncio
async def test_new_profile_alert_recipients(test_session):
    owner, _ = await make_person(test_session, 990201, has_apartment=True, budget=100000)
    await make_person(test_session, 990202, has_apartment=True, budget=100000, notifications=False)
    await make_person(test_session, 990203, has_apartment=True, budget=300000)
    newcomer, _ = await make_person(test_session, 990204, budget=100000)
    await test_session.commit()

    recipients = await find_users_to_alert_about(test_session, newcomer.id, limit=100)
    ids = {viewer.id for viewer, _, _, _ in recipients}
    assert owner.id in ids
    assert 990202 not in ids  # notifications off
    assert 990203 not in ids  # price way above newcomer's budget

    # Already notified (or shown) people are not alerted twice
    await CandidateEventService.record(test_session, owner.id, [newcomer.id], KIND_SHOWN)
    await test_session.commit()
    recipients = await find_users_to_alert_about(test_session, newcomer.id, limit=100)
    assert owner.id not in {viewer.id for viewer, _, _, _ in recipients}


# ------------------------------------------------------------------ freshness

@pytest.mark.asyncio
async def test_freshness_ping_then_hide(test_session):
    now = datetime(2026, 10, 6, 12, 0)
    _, fresh = await make_person(test_session, 990301)
    _, old = await make_person(test_session, 990302)
    _, ignored = await make_person(test_session, 990303)
    await test_session.commit()

    fresh.updated_at = now - timedelta(days=1)
    old.updated_at = now - timedelta(days=10)
    ignored.updated_at = now - timedelta(days=20)
    ignored.last_freshness_ping_at = now - timedelta(days=8)
    await test_session.commit()

    actions = {p.user_id: action for action, _, p in await find_stale_profiles(test_session, now=now, days=7)}
    assert 990301 not in actions
    assert actions[990302] == ACTION_PING
    assert actions[990303] == ACTION_HIDE


# ------------------------------------------------------------------ questionnaire -> listing

@pytest.mark.asyncio
async def test_sync_profile_listing_has_no_duplicates(test_session):
    user, profile = await make_person(test_session, 990401, has_apartment=True, budget=90000)
    profile.rooms_count = "3-комнатная"

    first = await ListingService.sync_profile_listing(test_session, user.id, profile)
    profile.budget_max = 95000
    second = await ListingService.sync_profile_listing(test_session, user.id, profile)
    await test_session.commit()

    assert first.id == second.id
    active = (
        await test_session.execute(
            select(Listing).where(Listing.owner_id == user.id, Listing.status == LISTING_STATUS_ACTIVE)
        )
    ).scalars().all()
    assert len(active) == 1
    assert active[0].price_per_person == 95000
    assert active[0].total_rooms == 3

    # Pausing the profile pauses the listing; resuming brings it back
    await set_profile_active(test_session, user.id, False)
    await test_session.commit()
    await test_session.refresh(active[0])
    assert active[0].status == LISTING_STATUS_PAUSED
    await set_profile_active(test_session, user.id, True)
    await test_session.commit()
    await test_session.refresh(active[0])
    assert active[0].status == LISTING_STATUS_ACTIVE

    # Re-filled as "no apartment": listing is archived
    profile.has_apartment = False
    await ListingService.sync_profile_listing(test_session, user.id, profile)
    await test_session.commit()
    await test_session.refresh(active[0])
    assert active[0].status == LISTING_STATUS_ARCHIVED
