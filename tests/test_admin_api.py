"""Test FastAPI Admin web application endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from app.admin.app import app


@pytest.mark.asyncio
async def test_admin_dashboard_response():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin")
        assert response.status_code == 200
        assert "KORSHI TAP" in response.text
        assert "Всего пользователей" in response.text


@pytest.mark.asyncio
async def test_admin_users_and_listings_pages():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_users = await client.get("/admin/users")
        assert res_users.status_code == 200
        assert "Управление пользователями" in res_users.text

        res_listings = await client.get("/admin/listings")
        assert res_listings.status_code == 200
        assert "Управление объявлениями" in res_listings.text

        res_weights = await client.get("/admin/weights")
        assert res_weights.status_code == 200
        assert "Настройка формулы AI-матчинга" in res_weights.text
