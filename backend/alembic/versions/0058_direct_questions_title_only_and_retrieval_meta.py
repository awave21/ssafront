"""direct questions title-only and retrieval meta

Revision ID: 0058
Revises: 0057
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE direct_questions
        SET title = search_title
        WHERE (title IS NULL OR btrim(title) = '')
          AND search_title IS NOT NULL
          AND btrim(search_title) <> ''
        """
    )
    op.alter_column(
        "direct_questions",
        "title",
        existing_type=sa.String(length=200),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.drop_column("direct_questions", "search_title")
    op.add_column(
        "runs",
        sa.Column("knowledge_retrieval_decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.add_column("direct_questions", sa.Column("search_title", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE direct_questions
        SET search_title = title
        WHERE search_title IS NULL OR btrim(search_title) = ''
        """
    )
    op.alter_column(
        "direct_questions",
        "search_title",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "direct_questions",
        "title",
        existing_type=sa.String(length=255),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.drop_column("runs", "knowledge_retrieval_decisions")
