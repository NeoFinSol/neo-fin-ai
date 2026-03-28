"""Add runtime cancellation and heartbeat fields.

Revision ID: 0006_add_runtime_cancellation_fields
Revises: 0005_add_analysis_summary_columns
Create Date: 2026-03-29 12:40:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0006_add_runtime_cancellation_fields"
down_revision = "0005_add_analysis_summary_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in ("analyses", "multi_analysis_sessions"):
        op.add_column(table_name, sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table_name, sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table_name, sa.Column("runtime_heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE analyses
        SET
            cancel_requested_at = COALESCE(cancel_requested_at, created_at),
            cancelled_at = COALESCE(cancelled_at, created_at)
        WHERE status = 'cancelled'
        """
    )

    op.drop_constraint("ck_multi_sessions_status_valid", "multi_analysis_sessions", type_="check")
    op.create_check_constraint(
        "ck_multi_sessions_status_valid",
        "multi_analysis_sessions",
        "status IN ('processing', 'completed', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_multi_sessions_status_valid", "multi_analysis_sessions", type_="check")
    op.create_check_constraint(
        "ck_multi_sessions_status_valid",
        "multi_analysis_sessions",
        "status IN ('processing', 'completed', 'failed')",
    )

    for table_name in ("multi_analysis_sessions", "analyses"):
        op.drop_column(table_name, "runtime_heartbeat_at")
        op.drop_column(table_name, "cancelled_at")
        op.drop_column(table_name, "cancel_requested_at")
