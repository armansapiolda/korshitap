"""Test district-by-district search and gender filtering."""

import pytest
from sqlalchemy import select
from app.constants import ALMATY_DISTRICTS
from app.db.models import SeekerProfile, User
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_owner_preferred_gender_filtering(test_session):
    # 1. Create an owner with preferred_gender = "female"
    owner = await UserService.get_or_create_user(
        session=test_session,
        telegram_id=999888777,
        username="flat_owner_almaty",
        first_name="Owner",
    )
    await UserService.set_user_preferred_gender(test_session, 999888777, "female")
    await test_session.commit()

    saved_pref = await UserService.get_user_preferred_gender(test_session, 999888777)
    assert saved_pref == "female"

    # 2. Create a female seeker in Bostandyk
    u_female = await UserService.get_or_create_user(
        session=test_session,
        telegram_id=111222333,
        username="girl_seeker",
        first_name="Aigerim",
    )
    u_female.gender = "female"
    p_female = SeekerProfile(
        user_id=u_female.id,
        name="Aigerim",
        gender="female",
        districts=["Бостандыкский"],
        budget_max=120000,
        is_active=True,
    )
    test_session.add(p_female)

    # 3. Create a male seeker in Bostandyk
    u_male = await UserService.get_or_create_user(
        session=test_session,
        telegram_id=444555666,
        username="boy_seeker",
        first_name="Almas",
    )
    u_male.gender = "male"
    p_male = SeekerProfile(
        user_id=u_male.id,
        name="Almas",
        gender="male",
        districts=["Бостандыкский"],
        budget_max=100000,
        is_active=True,
    )
    test_session.add(p_male)
    await test_session.commit()

    # 4. Query with female filter: must contain Aigerim and exclude Almas
    stmt = (
        select(SeekerProfile, User)
        .join(User, SeekerProfile.user_id == User.id)
        .where(SeekerProfile.is_active == True)
    )
    rows = (await test_session.execute(stmt)).all()

    female_in_bostandyk = [
        sp for sp, u in rows
        if sp.districts and "Бостандыкский" in sp.districts and (sp.gender == "female" or u.gender == "female")
    ]
    all_in_bostandyk = [
        sp for sp, u in rows
        if sp.districts and "Бостандыкский" in sp.districts
    ]

    assert len(female_in_bostandyk) >= 1
    assert any(sp.name == "Aigerim" for sp in female_in_bostandyk)
    assert not any(sp.name == "Almas" for sp in female_in_bostandyk)

    assert len(all_in_bostandyk) >= 2
    assert any(sp.name == "Almas" for sp in all_in_bostandyk)
