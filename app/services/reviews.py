from collections import Counter, deque
from time import monotonic

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.reviews import ReviewRepository
from app.schemas.review import ReviewCreate, ReviewOut


class ReviewRateLimiter:
    """Per-process limit. Called synchronously from the async review service."""

    def __init__(self):
        self.attempts: deque[tuple[float, str]] = deque()
        self.counts: Counter[str] = Counter()

    def check(self, client_ip: str) -> None:
        now = monotonic()
        while self.attempts and self.attempts[0][0] <= now - 3600:
            _, expired_ip = self.attempts.popleft()
            self.counts[expired_ip] -= 1
            if self.counts[expired_ip] == 0:
                del self.counts[expired_ip]
        if self.counts[client_ip] >= 3:
            raise HTTPException(status_code=429, detail="Не более 3 отзывов в час")
        self.attempts.append((now, client_ip))
        self.counts[client_ip] += 1


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ReviewRepository(session)

    async def create(self, data: ReviewCreate, client_ip: str, limiter: ReviewRateLimiter) -> ReviewOut:
        if data.website:
            raise HTTPException(status_code=400, detail="Некорректная отправка")
        limiter.check(client_ip)
        async with self.session.begin():
            review = await self.repository.add(data)
            result = ReviewOut.model_validate(review)
        return result

    async def delete(self, review_id: int) -> None:
        async with self.session.begin():
            if not await self.repository.delete(review_id):
                raise HTTPException(status_code=404, detail="Отзыв не найден")
