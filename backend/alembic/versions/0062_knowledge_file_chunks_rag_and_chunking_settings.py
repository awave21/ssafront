"""knowledge file chunk-level rag + chunking settings

Revision ID: 0062
Revises: 0061
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # Chunking settings are stored on knowledge tree nodes (folders).
    op.add_column("knowledge_files", sa.Column("chunk_size_chars", sa.Integer(), nullable=True))
    op.add_column("knowledge_files", sa.Column("chunk_overlap_chars", sa.Integer(), nullable=True))

    op.create_table(
        "knowledge_file_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("file_id", "chunk_index", name="uq_kfc_file_chunk_index"),
    )

    op.execute("ALTER TABLE knowledge_file_chunks ADD COLUMN embedding vector(1536);")

    op.create_index("ix_kfc_tenant_id", "knowledge_file_chunks", ["tenant_id"], unique=False)
    op.create_index("ix_kfc_agent_id", "knowledge_file_chunks", ["agent_id"], unique=False)
    op.create_index("ix_kfc_file_id", "knowledge_file_chunks", ["file_id"], unique=False)
    op.create_index("ix_kfc_chunk_index", "knowledge_file_chunks", ["file_id", "chunk_index"], unique=False)

    op.execute(
        """
        CREATE INDEX idx_kfc_embedding
        ON knowledge_file_chunks
        USING hnsw (embedding vector_cosine_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_kfc_embedding;")
    op.drop_index("ix_kfc_chunk_index", table_name="knowledge_file_chunks")
    op.drop_index("ix_kfc_file_id", table_name="knowledge_file_chunks")
    op.drop_index("ix_kfc_agent_id", table_name="knowledge_file_chunks")
    op.drop_index("ix_kfc_tenant_id", table_name="knowledge_file_chunks")
    op.drop_table("knowledge_file_chunks")

    op.drop_column("knowledge_files", "chunk_overlap_chars")
    op.drop_column("knowledge_files", "chunk_size_chars")

