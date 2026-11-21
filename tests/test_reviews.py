import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import Base, get_session
from app.main import create_app

PAYLOAD = {"name": " Анна ", "rating": 5, "comment": " Отличная уборка! "}
ORIGIN = "https://landing.example"


@pytest_asyncio.fixture
async def client():
    app = create_app(
        Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            cors_origins=[ORIGIN],
            reviews_admin_token="test-review-token",
        )
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reviews_lifecycle(client):
    first = await client.post("/api/reviews", json=PAYLOAD)
    second = await client.post("/api/reviews", json={**PAYLOAD, "rating": 2})
    assert first.status_code == second.status_code == 201
    first_review = first.json()
    assert first_review["name"] == "Анна"
    assert first_review["comment"] == "Отличная уборка!"
    assert first_review["created_at"]

    page = await client.get("/api/reviews", params={"sort": "lowest", "limit": 1, "offset": 1})
    assert page.json() == [first_review]
    response = await client.get("/api/reviews/stats")
    assert response.json() == {
        "count": 2,
        "average": 3.5,
        "distribution": {"1": 0, "2": 1, "3": 0, "4": 0, "5": 1},
    }

    url = f"/api/reviews/{first_review['id']}"
    assert (await client.delete(url)).status_code == 403
    assert (await client.delete(url, headers={"X-Admin-Token": "wrong"})).status_code == 403
    headers = {"X-Admin-Token": "test-review-token"}
    deleted = await client.delete(url, headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert (await client.delete(url, headers=headers)).status_code == 404
    assert (await client.get("/api/reviews")).json() == [second.json()]


@pytest.mark.asyncio
async def test_reviews_validate_and_limit_submissions(client):
    assert (await client.get("/api/reviews", params={"sort": "unknown"})).status_code == 422
    assert (await client.post("/api/reviews", json={**PAYLOAD, "rating": 6})).status_code == 422
    assert (await client.post("/api/reviews", json={**PAYLOAD, "website": "spam"})).status_code == 400
    for _ in range(3):
        assert (await client.post("/api/reviews", json=PAYLOAD)).status_code == 201
    assert (await client.post("/api/reviews", json=PAYLOAD)).status_code == 429
    assert (await client.get("/api/reviews/stats")).json()["count"] == 3


@pytest.mark.asyncio
async def test_reviews_allow_admin_cors_preflight(client):
    response = await client.options(
        "/api/reviews/1",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-Admin-Token",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
