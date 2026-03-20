"""direct questions runtime support

Revision ID: 0046
Revises: 0045
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE direct_question_embedding_status AS ENUM (
                'ready', 'pending', 'failed'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "direct_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("search_title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("interrupt_dialog", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notify_telegram", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("followup", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "embedding_status",
            postgresql.ENUM("ready", "pending", "failed", name="direct_question_embedding_status", create_type=False),
            nullable=False,
            server_default=sa.text("'ready'"),
        ),
        sa.Column("embedding_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("ALTER TABLE direct_questions ADD COLUMN embedding vector(1536);")

    op.create_table(
        "direct_question_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "direct_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("direct_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_direct_questions_tenant_id", "direct_questions", ["tenant_id"], unique=False)
    op.create_index("idx_dq_agent", "direct_questions", ["agent_id"], unique=False)
    op.create_index("idx_dq_enabled", "direct_questions", ["agent_id", "is_enabled"], unique=False)
    op.create_index("ix_direct_question_files_tenant_id", "direct_question_files", ["tenant_id"], unique=False)
    op.create_index("idx_dq_files_question", "direct_question_files", ["direct_question_id"], unique=False)

    op.execute(
        """
        CREATE INDEX idx_dq_embedding
        ON direct_questions
        USING hnsw (embedding vector_cosine_ops);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_dq_tags_gin
        ON direct_questions
        USING gin (tags);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_dq_tags_gin;")
    op.execute("DROP INDEX IF EXISTS idx_dq_embedding;")
    op.drop_index("idx_dq_files_question", table_name="direct_question_files")
    op.drop_index("ix_direct_question_files_tenant_id", table_name="direct_question_files")
    op.drop_index("idx_dq_enabled", table_name="direct_questions")
    op.drop_index("idx_dq_agent", table_name="direct_questions")
    op.drop_index("ix_direct_questions_tenant_id", table_name="direct_questions")
    op.drop_table("direct_question_files")
    op.drop_table("direct_questions")
    op.execute("DROP TYPE IF EXISTS direct_question_embedding_status;")
