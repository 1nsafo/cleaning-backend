import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.admin import setup_admin
from app.config import Settings
from app.database import Base
from app.main import create_app
from app.models.cleaning_request import CleaningRequest

SETTINGS = Settings(
    _env_file=None,
    database_url='postgresql+asyncpg://test:test@localhost/test',
    admin_username='boss', admin_password='s3cret-pass', admin_secret_key='x' * 32,
)

@pytest_asyncio.fixture
async def admin():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as session:
        session.add(CleaningRequest(phone='+79001234567', cleaning_type='general', contact_method='call',
                                    name='Евгений', privacy_consent=True))
    app = FastAPI()
    setup_admin(app, factory, SETTINGS)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='https://test') as client:
        yield client, factory
    await engine.dispose()

async def login(client, password='s3cret-pass'):
    return await client.post('/admin/login', data={'username': 'boss', 'password': password})

async def test_requires_login(admin):
    client, _ = admin
    response = await client.get('/admin/cleaning-request/list')
    assert response.status_code == 302
    assert '/admin/login' in response.headers['location']

async def test_rejects_wrong_password(admin):
    client, _ = admin
    await login(client, password='wrong')
    assert (await client.get('/admin/cleaning-request/list')).status_code == 302

async def test_lists_requests_after_login(admin):
    client, _ = admin
    await login(client)
    response = await client.get('/admin/cleaning-request/list')
    assert response.status_code == 200
    assert '+79001234567' in response.text
    assert 'Генеральная' in response.text

async def test_updates_status(admin):
    client, factory = admin
    await login(client)
    async with factory() as session:
        row = await session.scalar(CleaningRequest.__table__.select())
    response = await client.post(f'/admin/cleaning-request/edit/{row}', data={'status': 'done'})
    assert response.status_code == 302
    async with factory() as session:
        updated = await session.get(CleaningRequest, row)
        assert updated.status == 'done'
        assert updated.phone == '+79001234567'

def test_admin_disabled_without_credentials():
    app = create_app(Settings(_env_file=None, database_url='postgresql+asyncpg://test:test@localhost/test'))
    assert not any(getattr(r, 'path', '') == '/admin' for r in app.routes)
