"""singleton template unique per agent + clipboard_import enum

Revision ID: 0060
Revises: 0059
Create Date: 2026-03-25
"""

from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD VALUE must commit before the new enum literal can appear in a later
    # statement in the same migration (PostgreSQL / asyncpg UnsafeNewEnumValueUsageError).
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE directory_template ADD VALUE IF NOT EXISTS 'clipboard_import'"
        )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_directories_agent_singleton_template
        ON directories (agent_id, template)
        WHERE is_deleted = false
          AND template IN (
            'qa',
            'service_catalog',
            'product_catalog',
            'company_info',
            'theme_catalog',
            'medical_course_catalog',
            'clipboard_import'
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_directories_agent_singleton_template")
    # PostgreSQL enum values are not safely removable in-place.
