from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.utils.time import utcnow


class DiscoveredQuery(db.Model):
    __tablename__ = "discovered_queries"

    uuid: Mapped[str] = mapped_column(
        db.String(36), primary_key=True, default=lambda: str(uuid4())
    )
    profile_uuid: Mapped[str] = mapped_column(
        db.String(36),
        db.ForeignKey("business_profiles.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_uuid: Mapped[str] = mapped_column(
        db.String(36),
        db.ForeignKey("pipeline_runs.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text: Mapped[str] = mapped_column(db.Text, nullable=False)
    search_intent: Mapped[str] = mapped_column(db.String(32), nullable=False)
    estimated_search_volume: Mapped[int | None] = mapped_column(
        db.Integer, nullable=True
    )
    competitive_difficulty: Mapped[float | None] = mapped_column(
        db.Float, nullable=True
    )
    opportunity_score: Mapped[float | None] = mapped_column(
        db.Float, nullable=True, index=True
    )
    domain_visible: Mapped[bool | None] = mapped_column(
        db.Boolean, nullable=True, index=True
    )
    visibility_position: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    visibility_source: Mapped[str | None] = mapped_column(
        db.String(100), nullable=True
    )
    scoring_error: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    discovered_at: Mapped[object] = mapped_column(
        db.DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[object] = mapped_column(
        db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    profile = relationship("BusinessProfile", back_populates="queries")
    pipeline_run = relationship("PipelineRun", back_populates="queries")
    recommendations = relationship(
        "ContentRecommendation",
        back_populates="query",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "run_uuid", "query_text", name="uq_discovered_queries_run_query"
        ),
    )
