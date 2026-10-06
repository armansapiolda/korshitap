"""FastAPI Admin Web Application for KORSHI TAP."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from fastapi import Depends, FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import ALMATY_DISTRICTS, LISTING_STATUS_ACTIVE
from app.db.base import get_db, init_db
from app.db.models import Listing, Match, Report, Setting, User
from app.matching.weights import DEFAULT_WEIGHTS, MatchingWeights
from app.seeds.test_data import seed_database, wipe_database

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="KORSHI TAP Admin Panel", lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
DISTRICT_COORDS = {
    "Бостандыкский": {"lat": 43.2185, "lng": 76.9275},
    "Алмалинский": {"lat": 43.2530, "lng": 76.9290},
    "Медеуский": {"lat": 43.2350, "lng": 76.9600},
    "Ауэзовский": {"lat": 43.2280, "lng": 76.8550},
    "Жетысуский": {"lat": 43.2950, "lng": 76.9380},
    "Наурызбайский": {"lat": 43.2050, "lng": 76.8150},
    "Турксибский": {"lat": 43.3400, "lng": 76.9550},
    "Алатауский": {"lat": 43.2850, "lng": 76.8250},
}


@app.get("/map", response_class=HTMLResponse)
async def map_view(request: Request, db: AsyncSession = Depends(get_db)):
    import json
    from app.db.models import SeekerProfile, User

    # Fetch seekers with user relations
    seekers_stmt = (
        select(SeekerProfile, User)
        .join(User, SeekerProfile.user_id == User.id)
        .where(SeekerProfile.is_active == True)
    )
    seekers_rows = (await db.execute(seekers_stmt)).all()

    # Fetch active listings with owner relations
    listings_stmt = (
        select(Listing, User)
        .join(User, Listing.owner_id == User.id)
        .where(Listing.status == LISTING_STATUS_ACTIVE)
    )
    listings_rows = (await db.execute(listings_stmt)).all()

    total_seekers_count = len(seekers_rows)
    total_places_count = sum(l.available_places for l, _ in listings_rows)

    districts_info = []
    for d in ALMATY_DISTRICTS:
        coords = DISTRICT_COORDS.get(d, {"lat": 43.2389, "lng": 76.8897})

        # Match seekers for this district
        matching_seekers = []
        for sp, u in seekers_rows:
            if sp.districts and d in sp.districts:
                contact_url = f"https://t.me/{u.username}" if u.username else f"tg://user?id={u.telegram_id}"
                matching_seekers.append({
                    "name": sp.name or u.first_name or "Соискатель",
                    "age": sp.age or u.age or 21,
                    "gender": sp.gender or "other",
                    "budget": sp.budget_max or 120000,
                    "date": sp.move_in_date or "Жақын арада",
                    "bio": sp.raw_bio or "Жақсы және таза көрші іздеймін",
                    "smoking": sp.smoking or "no",
                    "pets": sp.pets or "no",
                    "occupation": sp.occupation or "student",
                    "contact_url": contact_url,
                })

        # Match listings for this district
        matching_listings = []
        for l, u in listings_rows:
            if l.district == d:
                contact_url = f"https://t.me/{u.username}" if u.username else f"tg://user?id={u.telegram_id}"
                matching_listings.append({
                    "id": l.id,
                    "housing_type": l.housing_type,
                    "price": l.price_per_person,
                    "places": l.available_places,
                    "landmark": l.address_landmark or f"{d} ауданы",
                    "urgent": l.is_urgent,
                    "move_in_date": l.move_in_date or "Қазір бос",
                    "description": l.conditions_description or "Барлық жағдайы жасалған пәтер",
                    "contact_url": contact_url,
                })

        districts_info.append({
            "name": d,
            "lat": coords["lat"],
            "lng": coords["lng"],
            "seekers_count": len(matching_seekers),
            "listings_count": sum(item["places"] for item in matching_listings),
            "total_listings": len(matching_listings),
            "seekers": matching_seekers,
            "listings": matching_listings,
        })

    return templates.TemplateResponse(
        request=request,
        name="map.html",
        context={
            "districts_json": json.dumps(districts_info, ensure_ascii=False),
            "total_seekers": total_seekers_count,
            "total_places": total_places_count,
        },
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    users_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_listings = (await db.execute(select(func.count(Listing.id)).where(Listing.status == LISTING_STATUS_ACTIVE))).scalar_one()
    matches_count = (await db.execute(select(func.count(Match.id)))).scalar_one()
    pending_reports = (await db.execute(select(func.count(Report.id)).where(Report.status == "pending"))).scalar_one()

    # Sum of available places
    avail_sum = (await db.execute(select(func.sum(Listing.available_places)).where(Listing.status == LISTING_STATUS_ACTIVE))).scalar_one() or 0

    # Listings per district
    districts_count = {}
    for d in ALMATY_DISTRICTS:
        cnt = (await db.execute(select(func.count(Listing.id)).where(Listing.district == d, Listing.status == LISTING_STATUS_ACTIVE))).scalar_one()
        districts_count[d] = cnt

    stats = {
        "users_count": users_count,
        "active_listings": active_listings,
        "available_places": avail_sum,
        "matches_count": matches_count,
        "pending_reports": pending_reports,
        "districts_count": districts_count,
    }

    return templates.TemplateResponse(request=request, name="dashboard.html", context={"stats": stats})


@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request, db: AsyncSession = Depends(get_db)):
    users = (await db.execute(select(User).order_by(User.id.desc()))).scalars().all()
    return templates.TemplateResponse(request=request, name="users.html", context={"users": users})


@app.post("/admin/users/{user_id}/toggle-verify")
async def toggle_user_verify(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user:
        user.is_verified = not user.is_verified
        await db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/users/{user_id}/toggle-block")
async def toggle_user_block(user_id: int, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user:
        user.is_blocked = not user.is_blocked
        await db.commit()
    return RedirectResponse(url="/admin/users", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/listings", response_class=HTMLResponse)
async def admin_listings(request: Request, db: AsyncSession = Depends(get_db)):
    listings = (await db.execute(select(Listing).order_by(Listing.id.desc()))).scalars().all()
    return templates.TemplateResponse(request=request, name="listings.html", context={"listings": listings})


@app.post("/admin/listings/{listing_id}/toggle-status")
async def toggle_listing_status(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = (await db.execute(select(Listing).where(Listing.id == listing_id))).scalar_one_or_none()
    if listing:
        listing.status = "paused" if listing.status == "active" else "active"
        await db.commit()
    return RedirectResponse(url="/admin/listings", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/listings/{listing_id}/confirm-freshness")
async def confirm_listing_freshness(listing_id: int, db: AsyncSession = Depends(get_db)):
    from datetime import datetime
    listing = (await db.execute(select(Listing).where(Listing.id == listing_id))).scalar_one_or_none()
    if listing:
        listing.last_confirmed_at = datetime.utcnow()
        listing.status = "active"
        await db.commit()
    return RedirectResponse(url="/admin/listings", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/matches", response_class=HTMLResponse)
async def admin_matches(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(Match).options(
        selectinload(Match.seeker_user),
        selectinload(Match.owner_user),
        selectinload(Match.listing),
    ).order_by(Match.matched_at.desc())
    matches = (await db.execute(stmt)).scalars().all()
    return templates.TemplateResponse(request=request, name="matches.html", context={"matches": matches})


@app.get("/admin/reports", response_class=HTMLResponse)
async def admin_reports(request: Request, db: AsyncSession = Depends(get_db)):
    stmt = select(Report).options(selectinload(Report.reporter)).order_by(Report.id.desc())
    reports = (await db.execute(stmt)).scalars().all()
    return templates.TemplateResponse(request=request, name="reports.html", context={"reports": reports})


@app.post("/admin/reports/{report_id}/resolve")
async def resolve_report(report_id: int, db: AsyncSession = Depends(get_db)):
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report:
        report.status = "resolved"
        await db.commit()
    return RedirectResponse(url="/admin/reports", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/reports/{report_id}/dismiss")
async def dismiss_report(report_id: int, db: AsyncSession = Depends(get_db)):
    report = (await db.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if report:
        report.status = "dismissed"
        await db.commit()
    return RedirectResponse(url="/admin/reports", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/weights", response_class=HTMLResponse)
async def admin_weights(request: Request, saved: bool = False, db: AsyncSession = Depends(get_db)):
    stmt = select(Setting).where(Setting.key == "matching_weights")
    setting = (await db.execute(stmt)).scalar_one_or_none()
    weights = MatchingWeights(**setting.value) if setting and isinstance(setting.value, dict) else DEFAULT_WEIGHTS
    return templates.TemplateResponse(request=request, name="weights.html", context={"weights": weights, "saved": saved})


@app.post("/admin/weights")
async def save_weights(
    request: Request,
    district: float = Form(...),
    budget: float = Form(...),
    move_in_date: float = Form(...),
    housing_type: float = Form(...),
    lifestyle: float = Form(...),
    gender: float = Form(...),
    extra: float = Form(0.05),
    db: AsyncSession = Depends(get_db),
):
    w = MatchingWeights(
        district=district,
        budget=budget,
        move_in_date=move_in_date,
        housing_type=housing_type,
        lifestyle=lifestyle,
        gender=gender,
        extra=extra,
    )
    stmt = select(Setting).where(Setting.key == "matching_weights")
    setting = (await db.execute(stmt)).scalar_one_or_none()
    if not setting:
        setting = Setting(key="matching_weights", value=w.model_dump())
        db.add(setting)
    else:
        setting.value = w.model_dump()
    await db.commit()
    return RedirectResponse(url="/admin/weights?saved=true", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/admin/seed", response_class=HTMLResponse)
async def admin_seed_view(request: Request, message: Optional[str] = None):
    return templates.TemplateResponse(request=request, name="seed.html", context={"message": message})


@app.post("/admin/seed/populate")
async def populate_seed_data(
    count: int = Form(500),
    city: str = Form("all"),
    db: AsyncSession = Depends(get_db),
):
    res = await seed_database(db, count=count, city=city)
    msg = f"Успешно сгенерировано {res['users_created']} анкет и {res['listings_created']} объявлений!"
    return RedirectResponse(url=f"/admin/seed?message={msg}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/admin/seed/wipe")
async def wipe_seed_data(db: AsyncSession = Depends(get_db)):
    await wipe_database(db)
    return RedirectResponse(url="/admin/seed?message=База данных очищена.", status_code=status.HTTP_303_SEE_OTHER)
