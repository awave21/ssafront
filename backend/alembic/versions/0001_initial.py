"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-01-20
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing tables and types if any to start clean
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS runs CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_tool_bindings CASCADE")
    op.execute("DROP TABLE IF EXISTS tools CASCADE")
    op.execute("DROP TABLE IF EXISTS agents CASCADE")

    op.execute("DROP TYPE IF EXISTS run_status CASCADE")
    op.execute("DROP TYPE IF EXISTS binding_permission_scope CASCADE")
    op.execute("DROP TYPE IF EXISTS tool_status CASCADE")
    op.execute("DROP TYPE IF EXISTS tool_auth_type CASCADE")
    op.execute("DROP TYPE IF EXISTS tool_execution_type CASCADE")
    op.execute("DROP TYPE IF EXISTS agent_status CASCADE")

    # Create types manually (idempotent)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'agent_status') THEN
            CREATE TYPE agent_status AS ENUM ('draft', 'published');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tool_execution_type') THEN
            CREATE TYPE tool_execution_type AS ENUM ('http_webhook', 'internal');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tool_auth_type') THEN
            CREATE TYPE tool_auth_type AS ENUM ('none', 'api_key', 'oauth2', 'service');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tool_status') THEN
            CREATE TYPE tool_status AS ENUM ('active', 'deprecated');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'binding_permission_scope') THEN
            CREATE TYPE binding_permission_scope AS ENUM ('read', 'write');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'run_status') THEN
            CREATE TYPE run_status AS ENUM ('queued', 'running', 'succeeded', 'failed');
        END IF;
    END
    $$;
    """)

    # Raw SQL for table creation to bypass SQLAlchemy Enum issues
    op.execute("""
        CREATE TABLE agents (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            owner_user_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            system_prompt TEXT NOT NULL DEFAULT '',
            model VARCHAR(200) NOT NULL,
            llm_params JSONB,
            status agent_status NOT NULL DEFAULT 'draft',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            deleted_at TIMESTAMPTZ
        )
    """)
    op.create_index("ix_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("ix_agents_owner_user_id", "agents", ["owner_user_id"])

    op.execute("""
        CREATE TABLE tools (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            input_schema JSONB NOT NULL,
            execution_type tool_execution_type NOT NULL DEFAULT 'http_webhook',
            endpoint VARCHAR(500),
            auth_type tool_auth_type NOT NULL DEFAULT 'none',
            status tool_status NOT NULL DEFAULT 'active',
            version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            deleted_at TIMESTAMPTZ,
            CONSTRAINT uq_tool_tenant_name UNIQUE (tenant_id, name)
        )
    """)
    op.create_index("ix_tools_tenant_id", "tools", ["tenant_id"])

    op.execute("""
        CREATE TABLE agent_tool_bindings (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
            permission_scope binding_permission_scope NOT NULL DEFAULT 'read',
            timeout_ms INTEGER,
            rate_limit JSONB,
            allowed_domains JSONB,
            secrets_ref VARCHAR,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_agent_tool UNIQUE (agent_id, tool_id)
        )
    """)
    op.create_index("ix_agent_tool_bindings_tenant_id", "agent_tool_bindings", ["tenant_id"])

    op.execute("""
        CREATE TABLE runs (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            session_id VARCHAR(200) NOT NULL,
            status run_status NOT NULL DEFAULT 'queued',
            input_message TEXT NOT NULL,
            output_message TEXT,
            trace_id VARCHAR(200) NOT NULL,
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        )
    """)
    op.create_index("ix_runs_tenant_id", "runs", ["tenant_id"])
    op.create_index("ix_runs_agent_id", "runs", ["agent_id"])

    op.execute("""
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            action VARCHAR(200) NOT NULL,
            entity_type VARCHAR(200) NOT NULL,
            entity_id VARCHAR(200) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        )
    """)
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])

    # audit_logs table already created via raw SQL above


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("runs")
    op.drop_table("agent_tool_bindings")
    op.drop_table("tools")
    op.drop_table("agents")

    op.execute("DROP TYPE IF EXISTS run_status")
    op.execute("DROP TYPE IF EXISTS binding_permission_scope")
    op.execute("DROP TYPE IF EXISTS tool_status")
    op.execute("DROP TYPE IF EXISTS tool_auth_type")
    op.execute("DROP TYPE IF EXISTS tool_execution_type")
    op.execute("DROP TYPE IF EXISTS agent_status")
