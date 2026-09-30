from sqlalchemy.ext.asyncio import AsyncSession
from app.models.cleaning_request import CleaningRequest
from app.schemas.cleaning_request import CleaningRequestCreate


class CleaningRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, data: CleaningRequestCreate) -> CleaningRequest:
        record = CleaningRequest(**data.model_dump(mode="json"))
        self.session.add(record)
        await self.session.flush()
        return record
