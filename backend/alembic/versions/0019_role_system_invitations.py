"""Add role system and invitations

Revision ID: 0019_role_system_invitations
Revises: 0018_pgvector_embedding
Create Date: 2026-02-05

"""

from alembic import op
import sqlalchemy as sa

revision = "0019_role_system_invitations"
down_revision = "0018_pgvector_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add owner_user_id to tenants (nullable initially for data migration)
    op.add_column(
        "tenants",
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tenants_owner_user_id",
        "tenants",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # Create invitations table
    op.execute("""
        CREATE TABLE invitations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(320) NOT NULL,
            role VARCHAR(50) NOT NULL,
            token_hash VARCHAR(255) NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            invited_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
    """)
    op.create_index("ix_invitations_tenant_id", "invitations", ["tenant_id"])
    op.create_index("ix_invitations_email", "invitations", ["email"])
    op.create_index("ix_invitations_expires_at", "invitations", ["expires_at"])
    # Unique: one pending invite per (tenant_id, email)
    op.create_unique_constraint(
        "uq_invitations_tenant_email",
        "invitations",
        ["tenant_id", "email"],
    )

    # Data migration: set owner_user_id = first user with role=owner, else first user
    op.execute("""
        UPDATE tenants t
        SET owner_user_id = COALESCE(
            (SELECT u.id FROM users u
             WHERE u.tenant_id = t.id AND u.role = 'owner'
             ORDER BY u.created_at ASC LIMIT 1),
            (SELECT u.id FROM users u
             WHERE u.tenant_id = t.id
             ORDER BY u.created_at ASC LIMIT 1)
        );
    """)

    # Update member -> manager for backward compatibility
    op.execute("""
        UPDATE users SET role = 'manager' WHERE role = 'member';
    """)


def downgrade() -> None:
    op.drop_constraint("fk_tenants_owner_user_id", "tenants", type_="foreignkey")
    op.drop_column("tenants", "owner_user_id")

    op.drop_table("invitations")