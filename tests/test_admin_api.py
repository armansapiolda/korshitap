"""Test FastAPI Admin web application endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.admin.app import app

# Matches ADMIN_USERNAME / ADMIN_PASSWORD set in conftest.py
ADMIN_AUTH = ("test-admin", "test-password")


@pytest.mark.asyncio
async def test_admin_dashboard_response():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=ADMIN_AUTH) as client:
        response = await client.get("/admin")
        assert response.status_code == 200
        assert "KORSHI TAP" in response.text
        assert "Всего пользователей" in response.text


@pytest.mark.asyncio
async def test_admin_users_and_listings_pages():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=ADMIN_AUTH) as client:
        res_users = await client.get("/admin/users")
        assert res_users.status_code == 200
        assert "Управление пользователями" in res_users.text

        res_listings = await client.get("/admin/listings")
        assert res_listings.status_code == 200
        assert "Управление объявлениями" in res_listings.text

        res_weights = await client.get("/admin/weights")
        assert res_weights.status_code == 200
        assert "Настройка формулы AI-матчинга" in res_weights.text


@pytest.mark.asyncio
async def test_admin_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/admin")).status_code == 401
        assert (await client.post("/admin/seed/wipe")).status_code == 401

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", auth=("test-admin", "wrong")
    ) as client:
        assert (await client.get("/admin/users")).status_code == 401


@pytest.mark.asyncio
async def test_map_requires_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/map")).status_code == 401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=ADMIN_AUTH) as client:
        assert (await client.get("/map")).status_code == 200
