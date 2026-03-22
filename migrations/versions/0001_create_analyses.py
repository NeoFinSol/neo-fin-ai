"""Create analyses table

Revision ID: 0001_create_analyses
Revises: None
Create Date: 2026-03-22 10:56:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_create_analyses"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_analyses_id", "analyses", ["id"], unique=False)
    op.create_index("ix_analyses_task_id", "analyses", ["task_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_analyses_task_id", table_name="analyses")
    op.drop_index("ix_analyses_id", table_name="analyses")
    op.drop_table("analyses")
