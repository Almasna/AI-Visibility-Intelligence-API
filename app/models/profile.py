from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.base import TimestampMixin


class BusinessProfile(TimestampMixin, db.Model):
    __tablename__ = "business_profiles"

    uuid: Mapped[str] = mapped_column(
        db.String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(db.String(200), nullable=False)
    domain: Mapped[str] = mapped_column(db.String(253), nullable=False, unique=True)
    industry: Mapped[str] = mapped_column(db.String(200), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    competitors: Mapped[list[str]] = mapped_column(db.JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        db.String(32), nullable=False, default="created"
    )

    pipeline_runs = relationship(
        "PipelineRun",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    queries = relationship(
        "DiscoveredQuery",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recommendations = relationship(
        "ContentRecommendation",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
