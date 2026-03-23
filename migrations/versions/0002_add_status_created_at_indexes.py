"""Add indexes on status and created_at

Revision ID: 0002_add_status_created_at_indexes
Revises: 0001_create_analyses
Create Date: 2026-03-23 12:00:00

Add indexes on frequently queried fields for better performance.
"""
from __future__ import annotations

from alembic import op

revision = "0002_add_status_created_at_indexes"
down_revision = "0001_create_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes on status and created_at columns."""
    # Index on status for filtering by status (e.g., "processing", "completed")
    op.create_index("ix_analyses_status", "analyses", ["status"], unique=False)
    
    # Index on created_at for sorting and time-based queries
    op.create_index("ix_analyses_created_at", "analyses", ["created_at"], unique=False)
    
    # Composite index for common query pattern: filter by status + sort by created_at
    op.create_index(
        "ix_analyses_status_created_at",
        "analyses",
        ["status", "created_at"],
        unique=False
    )


def downgrade() -> None:
    """Remove indexes on status and created_at columns."""
    op.drop_index("ix_analyses_status_created_at", table_name="analyses")
    op.drop_index("ix_analyses_created_at", table_name="analyses")
    op.drop_index("ix_analyses_status", table_name="analyses")
