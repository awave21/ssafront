"""Per-dialog state for pausing/disabling agent in specific chats

Revision ID: 0021_dialog_states
Revises: 0020_invitation_token
Create Date: 2026-02-08

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = "0021_dialog_states"
down_revision = "0020_invitation_token"
branch_labels = None
depends_on = None

dialog_status_enum = ENUM("active", "paused", "disabled", name="dialog_status", create_type=False)


def upgrade() -> None:
    # Создаём enum-тип, если ещё не существует
    op.execute("DO $$ BEGIN CREATE TYPE dialog_status AS ENUM ('active', 'paused', 'disabled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    op.create_table(
        "dialog_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("session_id", sa.String(200), nullable=False, index=True),
        sa.Column(
            "status",
            dialog_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_id", "agent_id", name="uq_dialog_state_session_agent"),
    )


def downgrade() -> None:
    op.drop_table("dialog_states")
    op.execute("DROP TYPE IF EXISTS dialog_status")
