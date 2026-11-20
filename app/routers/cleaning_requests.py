from typing import Annotated
from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.notifications import NotificationDispatcher
from app.schemas.cleaning_request import CleaningRequestCreate, CleaningRequestResponse
from app.services.cleaning_requests import CleaningRequestService, format_new_request_notification

router = APIRouter(prefix="/api/v1/requests", tags=["Заявки"])


def get_notification_dispatcher(request: Request) -> NotificationDispatcher:
    return request.app.state.notification_dispatcher


@router.post("", response_model=CleaningRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    data: CleaningRequestCreate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],
    notifications: Annotated[NotificationDispatcher, Depends(get_notification_dispatcher)],
) -> CleaningRequestResponse:
    result = await CleaningRequestService(session).create(data)
    background_tasks.add_task(notifications.send, format_new_request_notification(result.id, data))
    return result
