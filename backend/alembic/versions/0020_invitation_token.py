"""Add token field to invitations for invite_link retrieval

Revision ID: 0020_invitation_token
Revises: 0019_role_system_invitations
Create Date: 2026-02-05

"""

from alembic import op
import sqlalchemy as sa

revision = "0020_invitation_token"
down_revision = "0019_role_system_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add token column to invitations (nullable for existing rows)
    op.add_column(
        "invitations",
        sa.Column("token", sa.String(64), nullable=True),
    )
    # Note: existing invitations will have token=NULL
    # They will still work via token_hash, but won't show invite_link in list


def downgrade() -> None:
    op.drop_column("invitations", "token")
