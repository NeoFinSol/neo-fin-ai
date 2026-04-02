"""Add typed analysis summary columns and backfill from JSONB.

Revision ID: 0005_analysis_summary_cols
Revises: 0004_status_constraints
Create Date: 2026-03-28 23:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_analysis_summary_cols"
down_revision = "0004_status_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("filename", sa.String(length=255), nullable=True))
    op.add_column("analyses", sa.Column("score", sa.Float(), nullable=True))
    op.add_column("analyses", sa.Column("risk_level", sa.String(length=16), nullable=True))
    op.add_column("analyses", sa.Column("scanned", sa.Boolean(), nullable=True))
    op.add_column("analyses", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("analyses", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analyses", sa.Column("error_message", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE analyses
        SET
            filename = CASE
                WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result->'filename') = 'string'
                    THEN result->>'filename'
                ELSE NULL
            END,
            score = CASE
                WHEN NULLIF(result #>> '{data,score,score}', '') IS NOT NULL
                     AND (result #>> '{data,score,score}') ~ '^-?\\d+(\\.\\d+)?$'
                     AND ((result #>> '{data,score,score}')::double precision BETWEEN 0 AND 100)
                    THEN (result #>> '{data,score,score}')::double precision
                ELSE NULL
            END,
            risk_level = CASE
                WHEN result #>> '{data,score,risk_level}' IN ('low', 'medium', 'high', 'critical')
                    THEN result #>> '{data,score,risk_level}'
                ELSE NULL
            END,
            scanned = CASE
                WHEN result #>> '{data,scanned}' IN ('true', 'false')
                    THEN (result #>> '{data,scanned}')::boolean
                ELSE NULL
            END,
            confidence_score = CASE
                WHEN NULLIF(result #>> '{data,score,confidence_score}', '') IS NOT NULL
                     AND (result #>> '{data,score,confidence_score}') ~ '^-?\\d+(\\.\\d+)?$'
                     AND ((result #>> '{data,score,confidence_score}')::double precision BETWEEN 0 AND 1)
                    THEN (result #>> '{data,score,confidence_score}')::double precision
                ELSE NULL
            END,
            completed_at = CASE
                WHEN status = 'completed' THEN created_at
                ELSE NULL
            END,
            error_message = CASE
                WHEN jsonb_typeof(result) = 'object' AND jsonb_typeof(result->'error') = 'string'
                    THEN result->>'error'
                ELSE NULL
            END
        WHERE result IS NOT NULL
        """
    )

    op.create_check_constraint(
        "ck_analyses_risk_level_valid",
        "analyses",
        "risk_level IS NULL OR risk_level IN ('low', 'medium', 'high', 'critical')",
    )
    op.create_check_constraint(
        "ck_analyses_score_range",
        "analyses",
        "score IS NULL OR (score >= 0 AND score <= 100)",
    )
    op.create_check_constraint(
        "ck_analyses_confidence_score_range",
        "analyses",
        "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_analyses_confidence_score_range", "analyses", type_="check")
    op.drop_constraint("ck_analyses_score_range", "analyses", type_="check")
    op.drop_constraint("ck_analyses_risk_level_valid", "analyses", type_="check")
    op.drop_column("analyses", "error_message")
    op.drop_column("analyses", "completed_at")
    op.drop_column("analyses", "confidence_score")
    op.drop_column("analyses", "scanned")
    op.drop_column("analyses", "risk_level")
    op.drop_column("analyses", "score")
    op.drop_column("analyses", "filename")
