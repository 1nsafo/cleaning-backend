import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.reviews import ReviewRepository
from app.schemas.review import ReviewCreate, ReviewOut, ReviewSort, ReviewStats
from app.services.reviews import ReviewService

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("", response_model=list[ReviewOut])
async def list_reviews(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
    sort: ReviewSort = "newest",
):
    return await ReviewRepository(session).list(limit, offset, sort)


@router.get("/stats", response_model=ReviewStats)
async def stats(session: Annotated[AsyncSession, Depends(get_session)]) -> ReviewStats:
    return await ReviewRepository(session).stats()


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReviewOut:
    client_ip = request.client.host if request.client else "unknown"
    return await ReviewService(session).create(data, client_ip, request.app.state.review_rate_limiter)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: Annotated[int, Path(ge=-(2**31), le=2**31 - 1)],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    configured_token = request.app.state.reviews_admin_token
    secret = configured_token.get_secret_value() if configured_token else ""
    if not secret or not x_admin_token or not secrets.compare_digest(x_admin_token.encode(), secret.encode()):
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    await ReviewService(session).delete(review_id)
