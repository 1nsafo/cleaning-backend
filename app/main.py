from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.admin import setup_admin
from app.config import Settings, get_settings
from app.notifications import NotificationDispatcher, NotificationSender
from app.notifications.telegram import TelegramNotificationSender
from app.routers.cleaning_requests import router as cleaning_requests_router
from app.routers.reviews import router as reviews_router
from app.services.reviews import ReviewRateLimiter

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    # Движок создаётся сразу, а не в lifespan: админке session_factory нужна при сборке приложения.
    # Подключение к БД при этом не открывается до первого запроса.
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.session_factory = session_factory
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="Cleaning API", lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    senders: list[NotificationSender] = []
    if settings.telegram_bot_token and settings.telegram_channel_id:
        senders.append(TelegramNotificationSender(settings.telegram_bot_token, settings.telegram_channel_id))
    app.state.notification_dispatcher = NotificationDispatcher(senders)
    app.state.reviews_admin_token = settings.reviews_admin_token
    app.state.review_rate_limiter = ReviewRateLimiter()

    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-Admin-Token"],
    )
    app.include_router(cleaning_requests_router)
    app.include_router(reviews_router)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.admin_enabled:
        setup_admin(app, session_factory, settings)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("Database operation failed: %s", type(exc).__name__)
        if "reviews" in getattr(request.scope.get("route"), "tags", ()):
            return JSONResponse(status_code=503, content={"detail": "Отзывы временно недоступны. Попробуйте позже."})
        return JSONResponse(status_code=503, content={"detail": "Не удалось сохранить заявку. Попробуйте позже."})

    return app
