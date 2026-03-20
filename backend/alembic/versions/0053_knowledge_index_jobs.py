"""knowledge index jobs for live status

Revision ID: 0053
Revises: 0052
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE knowledge_index_job_status AS ENUM ('queued', 'indexing', 'indexed', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "knowledge_index_jobs",
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
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "indexing",
                "indexed",
                "failed",
                name="knowledge_index_job_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("stage", sa.String(length=50), nullable=True),
        sa.Column("chunks_total", sa.Integer(), nullable=True),
        sa.Column("chunks_done", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_knowledge_index_jobs_tenant_id", "knowledge_index_jobs", ["tenant_id"], unique=False)
    op.create_index("ix_knowledge_index_jobs_agent_id", "knowledge_index_jobs", ["agent_id"], unique=False)
    op.create_index("ix_knowledge_index_jobs_file_id", "knowledge_index_jobs", ["file_id"], unique=False)
    op.create_index("ix_knowledge_index_jobs_status", "knowledge_index_jobs", ["status"], unique=False)
    op.create_index(
        "idx_knowledge_index_jobs_file_created",
        "knowledge_index_jobs",
        ["file_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_index_jobs_file_created", table_name="knowledge_index_jobs")
    op.drop_index("ix_knowledge_index_jobs_status", table_name="knowledge_index_jobs")
    op.drop_index("ix_knowledge_index_jobs_file_id", table_name="knowledge_index_jobs")
    op.drop_index("ix_knowledge_index_jobs_agent_id", table_name="knowledge_index_jobs")
    op.drop_index("ix_knowledge_index_jobs_tenant_id", table_name="knowledge_index_jobs")
    op.drop_table("knowledge_index_jobs")
    op.execute("DROP TYPE IF EXISTS knowledge_index_job_status;")
