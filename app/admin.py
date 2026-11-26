import secrets
from datetime import timezone
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqladmin.filters import StaticValuesFilter
from sqladmin.i18n import I18nConfig
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request
from wtforms import SelectField
from wtforms.validators import Length, NumberRange, Optional
from app.config import Settings
from app.models.cleaning_request import CleaningRequest
from app.models.review import Review
from app.schemas.cleaning_request import CLEANING_TYPE_LABELS, CONTACT_METHOD_LABELS

STATUSES = {"new": "Новая", "in_progress": "В работе", "done": "Выполнена", "cancelled": "Отменена"}


class AdminAuth(AuthenticationBackend):
    def __init__(self, settings: Settings):
        super().__init__(
            secret_key=settings.admin_secret_key.get_secret_value(),
            https_only=settings.admin_secure_cookie, same_site="strict", max_age=8 * 60 * 60,
        )
        self.username = settings.admin_username
        self.password = settings.admin_password.get_secret_value()

    async def login(self, request: Request) -> bool:
        form = await request.form()
        # compare_digest: сравнение за постоянное время, без утечки по таймингу.
        valid = secrets.compare_digest(str(form.get("username", "")).encode(), self.username.encode())
        valid &= secrets.compare_digest(str(form.get("password", "")).encode(), self.password.encode())
        if valid:
            request.session.update({"user_id": self.username})
        return valid

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("user_id") == self.username


class CleaningRequestAdmin(ModelView, model=CleaningRequest):
    name = "Заявка"
    name_plural = "Заявки"
    icon = "fa-solid fa-broom"
    can_create = False
    can_export = False
    page_size = 50

    column_list = [
        CleaningRequest.created_at, CleaningRequest.status, CleaningRequest.name, CleaningRequest.phone,
        CleaningRequest.cleaning_type, CleaningRequest.contact_method,
    ]
    column_details_list = column_list + [CleaningRequest.comment, CleaningRequest.id]
    column_labels = {
        CleaningRequest.id: "ID", CleaningRequest.created_at: "Создана", CleaningRequest.status: "Статус",
        CleaningRequest.name: "Имя", CleaningRequest.phone: "Телефон", CleaningRequest.cleaning_type: "Тип уборки",
        CleaningRequest.contact_method: "Связаться", CleaningRequest.comment: "Комментарий",
    }
    column_formatters = {
        CleaningRequest.status: lambda m, a: STATUSES.get(m.status, m.status),
        CleaningRequest.cleaning_type: lambda m, a: CLEANING_TYPE_LABELS.get(m.cleaning_type, m.cleaning_type),
        CleaningRequest.contact_method: lambda m, a: CONTACT_METHOD_LABELS.get(m.contact_method, m.contact_method),
        CleaningRequest.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M"),
    }
    column_formatters_detail = column_formatters
    column_default_sort = (CleaningRequest.created_at, True)
    column_searchable_list = [CleaningRequest.phone, CleaningRequest.name]
    column_filters = [
        StaticValuesFilter(CleaningRequest.status, list(STATUSES.items()), title="Статус"),
        StaticValuesFilter(CleaningRequest.cleaning_type, list(CLEANING_TYPE_LABELS.items()), title="Тип уборки"),
    ]

    # Менять можно только статус; данные клиента остаются как пришли с сайта.
    form_columns = [CleaningRequest.status]
    form_overrides = {"status": SelectField}
    form_args = {"status": {"label": "Статус", "choices": list(STATUSES.items())}}


def strip_review_text(value: str | None) -> str:
    return (value or "").strip()


class ReviewAdmin(ModelView, model=Review):
    name = "Отзыв"
    name_plural = "Отзывы"
    icon = "fa-solid fa-star"
    can_create = True
    can_edit = True
    can_delete = False
    can_export = False
    can_view_details = True

    column_list = [Review.created_at, Review.name, Review.rating]
    column_details_list = column_list + [Review.comment, Review.id]
    column_labels = {
        Review.created_at: "Дата публикации (UTC)",
        Review.name: "Имя",
        Review.rating: "Оценка",
        Review.comment: "Комментарий",
        Review.id: "ID",
    }
    column_formatters = {Review.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M")}
    column_formatters_detail = column_formatters
    column_default_sort = [(Review.created_at, True), (Review.id, True)]
    form_columns = [Review.name, Review.rating, Review.comment, Review.created_at]
    form_create_rules = ["name", "rating", "comment"]
    form_args = {
        "name": {
            "filters": [strip_review_text],
            "validators": [Length(min=2, max=80, message="Введите имя длиной от 2 до 80 символов.")],
        },
        "rating": {
            "validators": [NumberRange(min=1, max=5, message="Введите оценку от 1 до 5.")],
        },
        "comment": {
            "filters": [strip_review_text],
            "validators": [Length(min=10, max=2000, message="Введите текст длиной от 10 до 2000 символов.")],
        },
        "created_at": {
            "format": ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"],
            "description": "Дата и время в UTC. Пустое поле сохраняет текущую дату публикации.",
            "validators": [Optional()],
        },
    }

    async def on_model_change(self, data: dict, model: Review, is_created: bool, request: Request) -> None:
        published_at = data.pop("created_at", None)
        if is_created or published_at is None:
            return

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        current = model.created_at
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        # The picker displays whole seconds. Preserve the stored precision on other edits.
        if published_at != current.replace(microsecond=0):
            data["created_at"] = published_at


def setup_admin(app: FastAPI, session_factory: async_sessionmaker, settings: Settings) -> None:
    admin = Admin(
        app, session_maker=session_factory, title="Заявки на уборку",
        authentication_backend=AdminAuth(settings),
        i18n_config=I18nConfig(default_locale="ru", language_cookie_name=None, language_header_name=None),
    )
    admin.add_view(CleaningRequestAdmin)
    admin.add_view(ReviewAdmin)
