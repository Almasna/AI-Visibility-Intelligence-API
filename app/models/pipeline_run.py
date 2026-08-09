from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.utils.time import utcnow


class PipelineRun(db.Model):
    __tablename__ = "pipeline_runs"

    uuid: Mapped[str] = mapped_column(
        db.String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_uuid: Mapped[str] = mapped_column(
        db.String(36),
        db.ForeignKey("business_profiles.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        db.String(32), nullable=False, default="running"
    )
    queries_discovered: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=0
    )
    queries_scored: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    tokens_used: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    started_at: Mapped[object] = mapped_column(
        db.DateTime(timezone=True), default=utcnow, nullable=False
    )
    completed_at: Mapped[object | None] = mapped_column(
        db.DateTime(timezone=True), nullable=True
    )

    profile = relationship("BusinessProfile", back_populates="pipeline_runs")
    queries = relationship(
        "DiscoveredQuery", back_populates="pipeline_run", passive_deletes=True
    )
