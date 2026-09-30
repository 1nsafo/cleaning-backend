from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CleaningRequest(Base):
    __tablename__ = "cleaning_requests"
    __table_args__ = (
        CheckConstraint("privacy_consent = true", name="ck_requests_consent"),
        CheckConstraint("cleaning_type IN ('maintenance', 'general', 'after_renovation')", name="ck_requests_cleaning_type"),
        CheckConstraint("contact_method IN ('call', 'message')", name="ck_requests_contact_method"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    phone: Mapped[str] = mapped_column(String(12))
    cleaning_type: Mapped[str] = mapped_column(String(32))
    contact_method: Mapped[str] = mapped_column(String(16))
    name: Mapped[str | None] = mapped_column(String(100))
    comment: Mapped[str | None] = mapped_column(String(2000))
    privacy_consent: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(16), server_default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
