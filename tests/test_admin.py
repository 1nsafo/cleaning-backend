import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.admin import setup_admin
from app.config import Settings
from app.database import Base
from app.main import create_app
from app.models.cleaning_request import CleaningRequest
from app.models.review import Review

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
        session.add(Review(id=1, name='Анна', rating=5, comment='Отличная уборка!'))
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

async def test_reviews_require_login(admin):
    client, _ = admin
    assert (await client.get('/admin/review/list')).status_code == 302
    assert (await client.get('/admin/review/details/1')).status_code == 302
    assert (await client.post('/admin/review/create')).status_code == 302
    assert (await client.post('/admin/review/edit/1')).status_code == 302
    await login(client)

    response = await client.get('/admin/review/list')
    assert response.status_code == 200
    assert 'Отзывы' in response.text
    assert 'Анна' in response.text
    response = await client.get('/admin/review/details/1')
    assert response.status_code == 200
    assert 'Отличная уборка!' in response.text
    assert (await client.delete('/admin/review/delete', params={'pks': '1'})).status_code == 403


async def test_create_and_edit_review(admin):
    client, factory = admin
    await login(client)
    assert (await client.get('/admin/review/create')).status_code == 200
    created = await client.post('/admin/review/create', data={
        'name': '  Олег  ', 'rating': '4', 'comment': '  Спасибо за уборку!  ',
    })
    assert created.status_code == 302
    async with factory() as session:
        review = await session.scalar(select(Review).where(Review.name == 'Олег'))
        assert (review.rating, review.comment) == (4, 'Спасибо за уборку!')
        review_id, created_at = review.id, review.created_at
        assert created_at is not None

    edit_url = f'/admin/review/edit/{review_id}'
    assert (await client.get(edit_url)).status_code == 200
    edited = await client.post(edit_url, data={
        'name': 'Ольга', 'rating': '5', 'comment': 'Спасибо за отличную уборку!',
        'created_at': '2000-01-01T00:00:00',
    })
    assert edited.status_code == 302
    async with factory() as session:
        review = await session.get(Review, review_id)
        assert (review.name, review.rating, review.comment) == ('Ольга', 5, 'Спасибо за отличную уборку!')
        assert review.created_at == created_at


async def test_rejects_invalid_review_changes(admin):
    client, factory = admin
    await login(client)
    created = await client.post('/admin/review/create', data={'rating': '5'})
    assert created.status_code == 400
    edited = await client.post('/admin/review/edit/1', data={
        'name': '  ', 'rating': '6', 'comment': 'Коротко',
    })
    assert edited.status_code == 400
    assert 'Введите оценку от 1 до 5.' in edited.text
    async with factory() as session:
        review = (await session.scalars(select(Review))).one()
        assert (review.name, review.rating, review.comment) == ('Анна', 5, 'Отличная уборка!')


def test_admin_disabled_without_credentials():
    app = create_app(Settings(_env_file=None, database_url='postgresql+asyncpg://test:test@localhost/test'))
    assert not any(getattr(r, 'path', '') == '/admin' for r in app.routes)
