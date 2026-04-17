"""Scenarios phase 1: extend function rule enums, dialog_states.last_user_message_at, scenario_delayed_messages.

Revision ID: 0069
Revises: 0068
Create Date: 2026-04-07
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_enum_value_safe(sql_enum_type: str, value: str) -> None:
    """Append enum value; IF NOT EXISTS requires PostgreSQL 15+."""
    op.execute(f"ALTER TYPE {sql_enum_type} ADD VALUE IF NOT EXISTS '{value}'")


def upgrade() -> None:
    for value in (
        "dialog_start",
        "client_message",
        "agent_message",
        "manager_message",
        "client_return",
        "spend_limit",
        "send_error",
    ):
        _add_enum_value_safe("function_rule_trigger_mode", value)

    for value in (
        "schedule_time",
        "schedule_weekday",
        "dialog_source",
        "start_param",
        "after_scenario",
        "client_return_gap",
    ):
        _add_enum_value_safe("function_rule_condition_type", value)

    for value in (
        "block_user",
        "unblock_user",
        "resume_dialog",
        "send_delayed",
    ):
        _add_enum_value_safe("function_post_action_type", value)

    op.add_column(
        "dialog_states",
        sa.Column("last_user_message_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "scenario_delayed_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column(
            "channel_type",
            sa.Enum("telegram", "telegram_phone", "whatsapp", "max", name="scenario_delayed_channel_type"),
            nullable=False,
        ),
        sa.Column("channel_target", sa.String(length=200), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "failed", "cancelled", name="scenario_delayed_message_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["function_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scenario_delayed_messages_tenant_id"),
        "scenario_delayed_messages",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scenario_delayed_messages_agent_id"),
        "scenario_delayed_messages",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scenario_delayed_messages_session_id"),
        "scenario_delayed_messages",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "idx_scenario_delayed_pending_schedule",
        "scenario_delayed_messages",
        ["status", "scheduled_at"],
        unique=False,
    )
    op.create_index(
        "ix_rule_execution_logs_session_rule",
        "rule_execution_logs",
        ["session_id", "rule_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rule_execution_logs_session_rule", table_name="rule_execution_logs")
    op.drop_index("idx_scenario_delayed_pending_schedule", table_name="scenario_delayed_messages")
    op.drop_index(op.f("ix_scenario_delayed_messages_session_id"), table_name="scenario_delayed_messages")
    op.drop_index(op.f("ix_scenario_delayed_messages_agent_id"), table_name="scenario_delayed_messages")
    op.drop_index(op.f("ix_scenario_delayed_messages_tenant_id"), table_name="scenario_delayed_messages")
    op.drop_table("scenario_delayed_messages")
    op.execute("DROP TYPE IF EXISTS scenario_delayed_message_status")
    op.execute("DROP TYPE IF EXISTS scenario_delayed_channel_type")

    op.drop_column("dialog_states", "last_user_message_at")
