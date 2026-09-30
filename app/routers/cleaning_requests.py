from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.schemas.cleaning_request import CleaningRequestCreate, CleaningRequestResponse
from app.services.cleaning_requests import CleaningRequestService

router = APIRouter(prefix="/api/v1/requests", tags=["Заявки"])


@router.post("", response_model=CleaningRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    data: CleaningRequestCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CleaningRequestResponse:
    return await CleaningRequestService(session).create(data)
