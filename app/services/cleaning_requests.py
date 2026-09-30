from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.cleaning_requests import CleaningRequestRepository
from app.schemas.cleaning_request import CleaningRequestCreate, CleaningRequestResponse


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
