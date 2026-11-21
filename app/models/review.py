from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    rating: Mapped[int]
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
