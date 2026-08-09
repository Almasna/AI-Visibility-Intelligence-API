from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.utils.time import utcnow


class TimestampMixin:
    created_at: Mapped[object] = mapped_column(
        db.DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
