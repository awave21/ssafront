"""Add function rules, post actions, dialog tags, rule logs and tool parameters.

Revision ID: 0037
Revises: 0036
Create Date: 2026-03-03
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS function_rules_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS function_rules_allow_semantic BOOLEAN NOT NULL DEFAULT TRUE;
        """
    )
    op.execute(
        """
        ALTER TABLE tenants
        ADD COLUMN IF NOT EXISTS function_rules_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS function_rules_allow_semantic BOOLEAN NOT NULL DEFAULT TRUE;
        """
    )

    op.create_table(
        "function_rules",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stop_on_match", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_semantic", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "trigger_mode",
            sa.Enum("pre_run", "post_tool", "post_run", name="function_rule_trigger_mode"),
            nullable=False,
            server_default="pre_run",
        ),
        sa.Column(
            "condition_type",
            sa.Enum("keyword", "regex", "semantic", "json_context", "always", name="function_rule_condition_type"),
            nullable=False,
            server_default="keyword",
        ),
        sa.Column("condition_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "reaction_to_execution",
            sa.Enum(
                "send_message",
                "ai_instruction",
                "ai_self_reply",
                "silent",
                name="function_rule_reaction_to_execution",
            ),
            nullable=False,
            server_default="ai_self_reply",
        ),
        sa.Column(
            "behavior_after_execution",
            sa.Enum("continue", "pause", "augment_prompt", name="function_rule_behavior_after_execution"),
            nullable=False,
            server_default="continue",
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "name", name="uq_function_rule_agent_name"),
    )
    op.create_index(op.f("ix_function_rules_agent_id"), "function_rules", ["agent_id"], unique=False)
    op.create_index(op.f("ix_function_rules_tenant_id"), "function_rules", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_function_rules_tool_id"), "function_rules", ["tool_id"], unique=False)

    op.create_table(
        "function_post_actions",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum(
                "set_tag",
                "send_message",
                "webhook",
                "pause_dialog",
                "augment_prompt",
                "set_result",
                "noop",
                name="function_post_action_type",
            ),
            nullable=False,
        ),
        sa.Column("action_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "on_status",
            sa.Enum("success", "error", "always", name="function_post_action_on_status"),
            nullable=False,
            server_default="always",
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["function_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_function_post_actions_rule_id"), "function_post_actions", ["rule_id"], unique=False)
    op.create_index(op.f("ix_function_post_actions_tenant_id"), "function_post_actions", ["tenant_id"], unique=False)

    op.create_table(
        "dialog_tags",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="rule"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dialog_tags_agent_id"), "dialog_tags", ["agent_id"], unique=False)
    op.create_index(op.f("ix_dialog_tags_session_id"), "dialog_tags", ["session_id"], unique=False)
    op.create_index(op.f("ix_dialog_tags_tag"), "dialog_tags", ["tag"], unique=False)
    op.create_index(op.f("ix_dialog_tags_tenant_id"), "dialog_tags", ["tenant_id"], unique=False)
    op.create_index("ix_dialog_tag_agent_session", "dialog_tags", ["agent_id", "session_id"], unique=False)

    op.create_table(
        "rule_execution_logs",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", sa.String(length=200), nullable=False),
        sa.Column("trace_id", sa.String(length=200), nullable=False),
        sa.Column("trigger_phase", sa.String(length=30), nullable=False, server_default="pre_run"),
        sa.Column("matched", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "result_status",
            sa.Enum("success", "error", "dry_run", "skipped", name="rule_execution_status"),
            nullable=False,
            server_default="success",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "approval_status",
            sa.Enum("pending_approval", "approved", "denied", "expired", name="rule_approval_status"),
            nullable=True,
        ),
        sa.Column("approval_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["function_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rule_execution_logs_agent_id"), "rule_execution_logs", ["agent_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_logs_rule_id"), "rule_execution_logs", ["rule_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_logs_run_id"), "rule_execution_logs", ["run_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_logs_session_id"), "rule_execution_logs", ["session_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_logs_tenant_id"), "rule_execution_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_rule_execution_logs_trace_id"), "rule_execution_logs", ["trace_id"], unique=False)

    op.create_table(
        "tool_parameters",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.Enum("text", "number", "boolean", name="tool_parameter_type"), nullable=False),
        sa.Column("instruction", sa.String(length=500), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enum_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("x_from_ai", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_id", "name", name="uq_tool_parameter_tool_name"),
    )
    op.create_index(op.f("ix_tool_parameters_tenant_id"), "tool_parameters", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tool_parameters_tool_id"), "tool_parameters", ["tool_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_parameters_tool_id"), table_name="tool_parameters")
    op.drop_index(op.f("ix_tool_parameters_tenant_id"), table_name="tool_parameters")
    op.drop_table("tool_parameters")
    sa.Enum(name="tool_parameter_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_rule_execution_logs_trace_id"), table_name="rule_execution_logs")
    op.drop_index(op.f("ix_rule_execution_logs_tenant_id"), table_name="rule_execution_logs")
    op.drop_index(op.f("ix_rule_execution_logs_session_id"), table_name="rule_execution_logs")
    op.drop_index(op.f("ix_rule_execution_logs_run_id"), table_name="rule_execution_logs")
    op.drop_index(op.f("ix_rule_execution_logs_rule_id"), table_name="rule_execution_logs")
    op.drop_index(op.f("ix_rule_execution_logs_agent_id"), table_name="rule_execution_logs")
    op.drop_table("rule_execution_logs")
    sa.Enum(name="rule_approval_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="rule_execution_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_dialog_tag_agent_session", table_name="dialog_tags")
    op.drop_index(op.f("ix_dialog_tags_tenant_id"), table_name="dialog_tags")
    op.drop_index(op.f("ix_dialog_tags_tag"), table_name="dialog_tags")
    op.drop_index(op.f("ix_dialog_tags_session_id"), table_name="dialog_tags")
    op.drop_index(op.f("ix_dialog_tags_agent_id"), table_name="dialog_tags")
    op.drop_table("dialog_tags")

    op.drop_index(op.f("ix_function_post_actions_tenant_id"), table_name="function_post_actions")
    op.drop_index(op.f("ix_function_post_actions_rule_id"), table_name="function_post_actions")
    op.drop_table("function_post_actions")
    sa.Enum(name="function_post_action_on_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="function_post_action_type").drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_function_rules_tool_id"), table_name="function_rules")
    op.drop_index(op.f("ix_function_rules_tenant_id"), table_name="function_rules")
    op.drop_index(op.f("ix_function_rules_agent_id"), table_name="function_rules")
    op.drop_table("function_rules")
    sa.Enum(name="function_rule_behavior_after_execution").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="function_rule_reaction_to_execution").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="function_rule_condition_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="function_rule_trigger_mode").drop(op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS function_rules_allow_semantic;")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS function_rules_enabled;")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS function_rules_allow_semantic;")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS function_rules_enabled;")
