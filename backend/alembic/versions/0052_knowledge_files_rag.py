"""knowledge files storage and rag indexing

Revision ID: 0052
Revises: 0051
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE knowledge_file_type AS ENUM ('folder', 'file');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE knowledge_vector_status AS ENUM ('not_indexed', 'indexing', 'indexed', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "knowledge_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_files.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "type",
            postgresql.ENUM("folder", "file", name="knowledge_file_type", create_type=False),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("meta_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "vector_status",
            postgresql.ENUM(
                "not_indexed",
                "indexing",
                "indexed",
                "failed",
                name="knowledge_vector_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'not_indexed'"),
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("ALTER TABLE knowledge_files ADD COLUMN embedding vector(1536);")

    op.create_index("ix_knowledge_files_tenant_id", "knowledge_files", ["tenant_id"], unique=False)
    op.create_index("ix_knowledge_files_agent_id", "knowledge_files", ["agent_id"], unique=False)
    op.create_index("ix_knowledge_files_parent_id", "knowledge_files", ["parent_id"], unique=False)
    op.create_index("ix_knowledge_files_type", "knowledge_files", ["type"], unique=False)
    op.create_index("ix_knowledge_files_vector_status", "knowledge_files", ["vector_status"], unique=False)
    op.execute(
        """
        CREATE INDEX idx_knowledge_files_embedding
        ON knowledge_files
        USING hnsw (embedding vector_cosine_ops);
        """
    )
    op.execute(
        """
        CREATE INDEX idx_knowledge_files_meta_tags_gin
        ON knowledge_files
        USING gin (meta_tags);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_files_meta_tags_gin;")
    op.execute("DROP INDEX IF EXISTS idx_knowledge_files_embedding;")
    op.drop_index("ix_knowledge_files_vector_status", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_type", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_parent_id", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_agent_id", table_name="knowledge_files")
    op.drop_index("ix_knowledge_files_tenant_id", table_name="knowledge_files")
    op.drop_table("knowledge_files")
    op.execute("DROP TYPE IF EXISTS knowledge_vector_status;")
    op.execute("DROP TYPE IF EXISTS knowledge_file_type;")
