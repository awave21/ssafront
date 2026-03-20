"""direct question followup jobs queue

Revision ID: 0050
Revises: 0049_sqns_clients_sync_storage
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0050"
down_revision = "0049_sqns_clients_sync_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE direct_question_followup_channel_type AS ENUM ('telegram');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE direct_question_followup_status AS ENUM ('pending', 'sent', 'failed', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "direct_question_followup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "direct_question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("direct_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column(
            "channel_type",
            postgresql.ENUM("telegram", name="direct_question_followup_channel_type", create_type=False),
            nullable=False,
        ),
        sa.Column("channel_target", sa.String(length=200), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "sent",
                "failed",
                "cancelled",
                name="direct_question_followup_status",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "run_id",
            "direct_question_id",
            "session_id",
            name="uq_dq_followup_job_run_question_session",
        ),
    )

    op.create_index("ix_direct_question_followup_jobs_tenant_id", "direct_question_followup_jobs", ["tenant_id"], unique=False)
    op.create_index("ix_direct_question_followup_jobs_agent_id", "direct_question_followup_jobs", ["agent_id"], unique=False)
    op.create_index(
        "ix_direct_question_followup_jobs_direct_question_id",
        "direct_question_followup_jobs",
        ["direct_question_id"],
        unique=False,
    )
    op.create_index("ix_direct_question_followup_jobs_run_id", "direct_question_followup_jobs", ["run_id"], unique=False)
    op.create_index("ix_direct_question_followup_jobs_session_id", "direct_question_followup_jobs", ["session_id"], unique=False)
    op.create_index("ix_direct_question_followup_jobs_channel_type", "direct_question_followup_jobs", ["channel_type"], unique=False)
    op.create_index("ix_direct_question_followup_jobs_status", "direct_question_followup_jobs", ["status"], unique=False)
    op.create_index(
        "ix_direct_question_followup_jobs_scheduled_at",
        "direct_question_followup_jobs",
        ["scheduled_at"],
        unique=False,
    )
    op.create_index(
        "idx_dq_followup_jobs_pending_schedule",
        "direct_question_followup_jobs",
        ["status", "scheduled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_dq_followup_jobs_pending_schedule", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_scheduled_at", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_status", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_channel_type", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_session_id", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_run_id", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_direct_question_id", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_agent_id", table_name="direct_question_followup_jobs")
    op.drop_index("ix_direct_question_followup_jobs_tenant_id", table_name="direct_question_followup_jobs")
    op.drop_table("direct_question_followup_jobs")
    op.execute("DROP TYPE IF EXISTS direct_question_followup_status;")
    op.execute("DROP TYPE IF EXISTS direct_question_followup_channel_type;")
