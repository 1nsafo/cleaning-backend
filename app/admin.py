import secrets
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqladmin.filters import StaticValuesFilter
from sqladmin.i18n import I18nConfig
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request
from wtforms import SelectField
from app.config import Settings
from app.models.cleaning_request import CleaningRequest

STATUSES = {"new": "Новая", "in_progress": "В работе", "done": "Выполнена", "cancelled": "Отменена"}
CLEANING_TYPES = {"maintenance": "Поддерживающая", "general": "Генеральная", "after_renovation": "После ремонта"}
CONTACT_METHODS = {"call": "Звонок", "message": "Сообщение"}


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
        CleaningRequest.cleaning_type: lambda m, a: CLEANING_TYPES.get(m.cleaning_type, m.cleaning_type),
        CleaningRequest.contact_method: lambda m, a: CONTACT_METHODS.get(m.contact_method, m.contact_method),
        CleaningRequest.created_at: lambda m, a: m.created_at.strftime("%d.%m.%Y %H:%M"),
    }
    column_formatters_detail = column_formatters
    column_default_sort = (CleaningRequest.created_at, True)
    column_searchable_list = [CleaningRequest.phone, CleaningRequest.name]
    column_filters = [
        StaticValuesFilter(CleaningRequest.status, list(STATUSES.items()), title="Статус"),
        StaticValuesFilter(CleaningRequest.cleaning_type, list(CLEANING_TYPES.items()), title="Тип уборки"),
    ]

    # Менять можно только статус; данные клиента остаются как пришли с сайта.
    form_columns = [CleaningRequest.status]
    form_overrides = {"status": SelectField}
    form_args = {"status": {"label": "Статус", "choices": list(STATUSES.items())}}


def setup_admin(app: FastAPI, session_factory: async_sessionmaker, settings: Settings) -> None:
    admin = Admin(
        app, session_maker=session_factory, title="Заявки на уборку",
        authentication_backend=AdminAuth(settings),
        i18n_config=I18nConfig(default_locale="ru", language_cookie_name=None, language_header_name=None),
    )
    admin.add_view(CleaningRequestAdmin)
