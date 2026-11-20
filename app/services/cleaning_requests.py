from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.cleaning_requests import CleaningRequestRepository
from app.schemas.cleaning_request import (
    CLEANING_TYPE_LABELS,
    CONTACT_METHOD_LABELS,
    CleaningRequestCreate,
    CleaningRequestResponse,
)


class CleaningRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = CleaningRequestRepository(session)

    async def create(self, data: CleaningRequestCreate) -> CleaningRequestResponse:
        # Выход из begin фиксирует транзакцию; исключение вызывает rollback.
        async with self.session.begin():
            record = await self.repository.add(data)
            result = CleaningRequestResponse.model_validate(record)
        return result


def format_new_request_notification(request_id: UUID, data: CleaningRequestCreate) -> str:
    lines = [
        "Новая заявка на уборку",
        f"ID: {request_id}",
        f"Телефон: {data.phone}",
        f"Тип уборки: {CLEANING_TYPE_LABELS[data.cleaning_type]}",
        f"Способ связи: {CONTACT_METHOD_LABELS[data.contact_method]}",
    ]
    if data.name:
        lines.append(f"Имя: {data.name}")
    if data.comment:
        lines.append(f"Комментарий: {data.comment}")
    return "\n".join(lines)
