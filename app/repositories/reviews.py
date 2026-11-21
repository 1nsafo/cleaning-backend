from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewSort, ReviewStats

SORT_ORDERS = {
    "newest": Review.created_at.desc(),
    "oldest": Review.created_at.asc(),
    "highest": Review.rating.desc(),
    "lowest": Review.rating.asc(),
}


class ReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, limit: int, offset: int, sort: ReviewSort) -> Sequence[Review]:
        statement = select(Review).order_by(SORT_ORDERS[sort], Review.id.desc()).limit(limit).offset(offset)
        return (await self.session.scalars(statement)).all()

    async def add(self, data: ReviewCreate) -> Review:
        review = Review(name=data.name, rating=data.rating, comment=data.comment)
        self.session.add(review)
        await self.session.flush()
        return review

    async def delete(self, review_id: int) -> bool:
        statement = delete(Review).where(Review.id == review_id).returning(Review.id)
        return await self.session.scalar(statement) is not None

    async def stats(self) -> ReviewStats:
        statement = select(Review.rating, func.count(Review.id)).group_by(Review.rating)
        distribution = dict.fromkeys(range(1, 6), 0)
        for rating, count in await self.session.execute(statement):
            distribution[rating] = count
        count = sum(distribution.values())
        average = round(sum(rating * total for rating, total in distribution.items()) / count, 2) if count else 0.0
        return ReviewStats(count=count, average=average, distribution=distribution)
