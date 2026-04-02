"""Harden status constraints and session lifecycle indexes.

Revision ID: 0004_status_constraints
Revises: 0003_multi_analysis_sessions
Create Date: 2026-03-28 18:30:00
"""
from __future__ import annotations

from alembic import op

revision = "0004_status_constraints"
down_revision = "0003_multi_analysis_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_analyses_status_valid",
        "analyses",
        "status IN ('uploading', 'processing', 'completed', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_multi_sessions_status_valid",
        "multi_analysis_sessions",
        "status IN ('processing', 'completed', 'failed')",
    )
    op.create_index(
        "ix_multi_sessions_status_updated_at",
        "multi_analysis_sessions",
        ["status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_multi_sessions_status_updated_at", table_name="multi_analysis_sessions")
    op.drop_constraint("ck_multi_sessions_status_valid", "multi_analysis_sessions", type_="check")
    op.drop_constraint("ck_analyses_status_valid", "analyses", type_="check")
