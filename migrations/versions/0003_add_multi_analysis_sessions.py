"""Add multi_analysis_sessions table

Revision ID: 0003_add_multi_analysis_sessions
Revises: 0002_add_status_created_at_indexes
Create Date: 2026-03-24 12:00:00

Supports multi-period financial analysis sessions (neofin-competition-release).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_add_multi_analysis_sessions"
down_revision = "0002_add_status_created_at_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "multi_analysis_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'processing'"),
        ),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Unique index on session_id — sole uniqueness constraint for this column
    op.create_index(
        "ix_multi_sessions_session_id",
        "multi_analysis_sessions",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        "ix_multi_sessions_created_at",
        "multi_analysis_sessions",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_multi_sessions_created_at", table_name="multi_analysis_sessions")
    op.drop_index("ix_multi_sessions_session_id", table_name="multi_analysis_sessions")
    op.drop_table("multi_analysis_sessions")
