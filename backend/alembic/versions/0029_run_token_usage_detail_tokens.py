"""add detail token fields to run token usage steps

Revision ID: 0029_run_usage_detail_toks
Revises: 0028_model_pricing_display_name
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0029_run_usage_detail_toks"
down_revision = "0028_model_pricing_display_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("run_token_usage_steps", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("reasoning_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("audio_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("input_audio_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("output_audio_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("cache_audio_read_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("accepted_prediction_tokens", sa.Integer(), nullable=True))
    op.add_column("run_token_usage_steps", sa.Column("rejected_prediction_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("run_token_usage_steps", "rejected_prediction_tokens")
    op.drop_column("run_token_usage_steps", "accepted_prediction_tokens")
    op.drop_column("run_token_usage_steps", "cache_audio_read_tokens")
    op.drop_column("run_token_usage_steps", "output_audio_tokens")
    op.drop_column("run_token_usage_steps", "input_audio_tokens")
    op.drop_column("run_token_usage_steps", "audio_tokens")
    op.drop_column("run_token_usage_steps", "reasoning_tokens")
    op.drop_column("run_token_usage_steps", "cache_write_tokens")
    op.drop_column("run_token_usage_steps", "cache_read_tokens")
