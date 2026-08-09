from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.utils.time import utcnow


class ContentRecommendation(db.Model):
    __tablename__ = "content_recommendations"

    uuid: Mapped[str] = mapped_column(
        db.String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_uuid: Mapped[str] = mapped_column(
        db.String(36),
        db.ForeignKey("business_profiles.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_uuid: Mapped[str] = mapped_column(
        db.String(36),
        db.ForeignKey("discovered_queries.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_type: Mapped[str] = mapped_column(db.String(32), nullable=False)
    title: Mapped[str] = mapped_column(db.String(300), nullable=False)
    rationale: Mapped[str] = mapped_column(db.Text, nullable=False)
    target_keywords: Mapped[list[str]] = mapped_column(db.JSON, nullable=False)
    priority: Mapped[str] = mapped_column(db.String(16), nullable=False)
    created_at: Mapped[object] = mapped_column(
        db.DateTime(timezone=True), default=utcnow, nullable=False
    )

    profile = relationship("BusinessProfile", back_populates="recommendations")
    query = relationship("DiscoveredQuery", back_populates="recommendations")
