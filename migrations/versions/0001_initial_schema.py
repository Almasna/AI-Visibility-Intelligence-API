"""Initial AI visibility schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_profiles",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("industry", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("competitors", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("uuid", name="pk_business_profiles"),
        sa.UniqueConstraint("domain", name="uq_business_profiles_domain"),
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("profile_uuid", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queries_discovered", sa.Integer(), nullable=False),
        sa.Column("queries_scored", sa.Integer(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_uuid"], ["business_profiles.uuid"],
            name="fk_pipeline_runs_profile_uuid_business_profiles", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_pipeline_runs"),
    )
    op.create_index("ix_pipeline_runs_profile_uuid", "pipeline_runs", ["profile_uuid"])
    op.create_table(
        "discovered_queries",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("profile_uuid", sa.String(length=36), nullable=False),
        sa.Column("run_uuid", sa.String(length=36), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("search_intent", sa.String(length=32), nullable=False),
        sa.Column("estimated_search_volume", sa.Integer(), nullable=True),
        sa.Column("competitive_difficulty", sa.Float(), nullable=True),
        sa.Column("opportunity_score", sa.Float(), nullable=True),
        sa.Column("domain_visible", sa.Boolean(), nullable=True),
        sa.Column("visibility_position", sa.Integer(), nullable=True),
        sa.Column("visibility_source", sa.String(length=100), nullable=True),
        sa.Column("scoring_error", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_uuid"], ["business_profiles.uuid"],
            name="fk_discovered_queries_profile_uuid_business_profiles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_uuid"], ["pipeline_runs.uuid"],
            name="fk_discovered_queries_run_uuid_pipeline_runs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_discovered_queries"),
        sa.UniqueConstraint("run_uuid", "query_text", name="uq_discovered_queries_run_query"),
    )
    op.create_index("ix_discovered_queries_profile_uuid", "discovered_queries", ["profile_uuid"])
    op.create_index("ix_discovered_queries_run_uuid", "discovered_queries", ["run_uuid"])
    op.create_index("ix_discovered_queries_opportunity_score", "discovered_queries", ["opportunity_score"])
    op.create_index("ix_discovered_queries_domain_visible", "discovered_queries", ["domain_visible"])
    op.create_table(
        "content_recommendations",
        sa.Column("uuid", sa.String(length=36), nullable=False),
        sa.Column("profile_uuid", sa.String(length=36), nullable=False),
        sa.Column("query_uuid", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("target_keywords", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_uuid"], ["business_profiles.uuid"],
            name="fk_content_recommendations_profile_uuid_business_profiles", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["query_uuid"], ["discovered_queries.uuid"],
            name="fk_content_recommendations_query_uuid_discovered_queries", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("uuid", name="pk_content_recommendations"),
    )
    op.create_index("ix_content_recommendations_profile_uuid", "content_recommendations", ["profile_uuid"])
    op.create_index("ix_content_recommendations_query_uuid", "content_recommendations", ["query_uuid"])


def downgrade() -> None:
    op.drop_index("ix_content_recommendations_query_uuid", table_name="content_recommendations")
    op.drop_index("ix_content_recommendations_profile_uuid", table_name="content_recommendations")
    op.drop_table("content_recommendations")
    op.drop_index("ix_discovered_queries_domain_visible", table_name="discovered_queries")
    op.drop_index("ix_discovered_queries_opportunity_score", table_name="discovered_queries")
    op.drop_index("ix_discovered_queries_run_uuid", table_name="discovered_queries")
    op.drop_index("ix_discovered_queries_profile_uuid", table_name="discovered_queries")
    op.drop_table("discovered_queries")
    op.drop_index("ix_pipeline_runs_profile_uuid", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
    op.drop_table("business_profiles")
