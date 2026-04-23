"""Расширение session_script_contexts под motive-aware runtime.

Добавляет поля для трекинга диагностики клиента (мотивы, возражения,
эмоциональное состояние, стадия воронки) и истории взаимодействия (какие
follow-up вопросы уже задавались, какие proof показывались, какие тактики
не сработали) — чтобы LLM видела что уже было и вела беседу осознанно.

Revision ID: 0077
Revises: 0076
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0077"
down_revision: Union[str, None] = "0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "detected_motive_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "raised_objection_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "closed_objection_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "asked_followup_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "shown_proof_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "blocked_tactic_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column("emotional_state", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column("funnel_stage", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "emotional_pause_used",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "session_script_contexts",
        sa.Column(
            "last_diagnosis",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("session_script_contexts", "last_diagnosis")
    op.drop_column("session_script_contexts", "emotional_pause_used")
    op.drop_column("session_script_contexts", "funnel_stage")
    op.drop_column("session_script_contexts", "emotional_state")
    op.drop_column("session_script_contexts", "blocked_tactic_ids")
    op.drop_column("session_script_contexts", "shown_proof_ids")
    op.drop_column("session_script_contexts", "asked_followup_questions")
    op.drop_column("session_script_contexts", "closed_objection_ids")
    op.drop_column("session_script_contexts", "raised_objection_ids")
    op.drop_column("session_script_contexts", "detected_motive_ids")
