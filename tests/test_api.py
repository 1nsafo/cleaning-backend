from unittest.mock import AsyncMock
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import Settings
from app.database import Base, get_session
from app.main import create_app
from app.models.cleaning_request import CleaningRequest

PAYLOAD = dict(phone='8 (900) 123-45-67', cleaning_type='maintenance', contact_method='call', privacy_consent=True)

@pytest_asyncio.fixture
async def setup():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(Settings(database_url='postgresql+asyncpg://test:test@localhost/test'))
    async def session_override():
        async with factory() as session:
            yield session
    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        yield client, factory, app
    await engine.dispose()

async def test_persists(setup):
    client, factory, _ = setup
    response = await client.post('/api/v1/requests', json={**PAYLOAD, 'name': '  Евгений  ', 'comment': '  '})
    assert response.status_code == 201
    assert response.json()['status'] == 'new'
    async with factory() as session:
        row = (await session.scalars(select(CleaningRequest))).one()
        assert str(row.id) == response.json()['id']
        assert row.phone == '+79001234567'
        assert row.name == 'Евгений'
        assert row.comment is None
        assert row.created_at is not None

@pytest.mark.parametrize('patch', [
    {'phone': 'abc'}, {'phone': '+1 555 123 4567'},
    {'privacy_consent': False}, {'privacy_consent': 'true'},
    {'cleaning_type': 'unknown'}, {'cleaning_type': 'Windows'}, {'contact_method': 'unknown'},
    {'comment': 'x' * 2001}, {'name': 'x' * 101}, {'status': 'done'},
])
async def test_rejects_invalid_without_insert(setup, patch):
    client, factory, _ = setup
    response = await client.post('/api/v1/requests', json={**PAYLOAD, **patch})
    assert response.status_code == 422
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(CleaningRequest)) == 0

async def test_database_failure_rolls_back(setup):
    client, factory, app = setup
    async def broken_session():
        async with factory() as session:
            # Ошибка flush после добавления объекта: сервис должен откатить транзакцию.
            session.flush = AsyncMock(side_effect=OperationalError('secret SQL', {}, Exception('secret')))
            yield session
            assert not session.in_transaction()
    app.dependency_overrides[get_session] = broken_session
    response = await client.post('/api/v1/requests', json=PAYLOAD)
    assert response.status_code == 503
    assert 'secret' not in response.text
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(CleaningRequest)) == 0

@pytest.mark.parametrize('cleaning_type', ['windows', 'not_sure'])
async def test_accepts_new_cleaning_types(setup, cleaning_type):
    client, factory, _ = setup
    response = await client.post('/api/v1/requests', json={**PAYLOAD, 'cleaning_type': cleaning_type})
    assert response.status_code == 201
    async with factory() as session:
        assert (await session.scalars(select(CleaningRequest))).one().cleaning_type == cleaning_type
