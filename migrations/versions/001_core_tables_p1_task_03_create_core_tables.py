"""P1-TASK-03: Create core tables

Creates core database schema for AutoBiz Phase 1:
- tenants: Tenant registry
- state_versions: Versioned state store (INV-06)
- receipts: Side effect receipts with dual idempotency (INV-05)
- traces: Per-run transcripts (INV-04)
- event_store: Inbound event ledger
- reconciliation_jobs: Drift detection jobs
- hitl_requests: HITL approval queue (INV-07)

All tables are RLS-ready with tenant_id NOT NULL and audit columns.

Revision ID: 001_core_tables
Revises:
Create Date: 2026-01-30

Requirements: INV-06, P1-R07, P1-R08, P1-R26, P1-R27, P1-R28, P1-R29, P1-R30
Test Coverage: P1-T13, P1-T14, P1-T31, P1-T36
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_core_tables"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create all core tables."""

    # 1. Tenants table
    op.execute(
        """
        CREATE TABLE tenants (
            tenant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'::jsonb
        );

        CREATE INDEX idx_tenants_status ON tenants(status);
        """
    )

    # 2. State versions table (INV-06)
    op.execute(
        """
        CREATE TABLE state_versions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            version INT NOT NULL,
            state_patch JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            correlation_id TEXT,

            CONSTRAINT state_versions_tenant_fk FOREIGN KEY (tenant_id)
                REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            CONSTRAINT state_versions_version_check CHECK (version > 0),
            UNIQUE (tenant_id, entity_type, entity_id, version)
        );

        CREATE INDEX idx_state_versions_entity
            ON state_versions(tenant_id, entity_type, entity_id, version DESC);
        CREATE INDEX idx_state_versions_correlation
            ON state_versions(correlation_id) WHERE correlation_id IS NOT NULL;
        """
    )

    # 3. Receipts table (INV-05 - dual idempotency)
    op.execute(
        """
        CREATE TABLE receipts (
            receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            tool_version TEXT NOT NULL,

            -- Internal idempotency
            internal_idempotency_key TEXT NOT NULL,
            execution_id UUID NOT NULL,

            -- External idempotency (for FINANCIAL tools)
            external_idempotency_key TEXT,
            external_provider TEXT,
            external_transaction_id TEXT,

            -- Result
            status TEXT NOT NULL,
            result_json JSONB,

            -- Timestamps
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ttl_expires_at TIMESTAMPTZ NOT NULL,

            CONSTRAINT receipts_tenant_fk FOREIGN KEY (tenant_id)
                REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            UNIQUE (tenant_id, internal_idempotency_key)
        );

        CREATE INDEX idx_receipts_internal_key
            ON receipts(tenant_id, internal_idempotency_key);
        CREATE INDEX idx_receipts_external_key
            ON receipts(external_provider, external_idempotency_key)
            WHERE external_idempotency_key IS NOT NULL;
        CREATE INDEX idx_receipts_ttl
            ON receipts(ttl_expires_at) WHERE ttl_expires_at < NOW();
        """
    )

    # 4. Traces table (INV-04)
    op.execute(
        """
        CREATE TABLE traces (
            trace_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            execution_id UUID NOT NULL,

            -- Trace content
            steps JSONB NOT NULL DEFAULT '[]'::jsonb,
            tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb,
            state_diffs JSONB NOT NULL DEFAULT '[]'::jsonb,
            cost_cents INT NOT NULL DEFAULT 0,

            -- Metadata
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ,
            status TEXT NOT NULL DEFAULT 'RUNNING',

            CONSTRAINT traces_tenant_fk FOREIGN KEY (tenant_id)
                REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            UNIQUE (tenant_id, correlation_id)
        );

        CREATE INDEX idx_traces_correlation ON traces(correlation_id);
        CREATE INDEX idx_traces_execution ON traces(execution_id);
        CREATE INDEX idx_traces_tenant_time
            ON traces(tenant_id, started_at DESC);
        """
    )

    # 5. Event store table (§11.2a)
    op.execute(
        """
        CREATE TABLE event_store (
            event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,

            -- Source
            source TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            event_type TEXT NOT NULL,

            -- Timing & ordering
            received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            seq TEXT,
            predecessor_source_event_id TEXT,

            -- Security & validation
            signature_valid BOOLEAN NOT NULL DEFAULT FALSE,
            payload_json JSONB NOT NULL,
            payload_sha256 TEXT NOT NULL,

            -- Processing
            processing_status TEXT NOT NULL DEFAULT 'RECEIVED',
            run_id UUID,
            correlation_id TEXT,
            applied_at TIMESTAMPTZ,

            CONSTRAINT event_store_tenant_fk FOREIGN KEY (tenant_id)
                REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            UNIQUE (tenant_id, source, source_event_id)
        );

        CREATE INDEX idx_events_tenant_source
            ON event_store(tenant_id, source, source_event_id);
        CREATE INDEX idx_events_tenant_status
            ON event_store(tenant_id, processing_status, received_at);
        CREATE INDEX idx_events_dedup
            ON event_store(tenant_id, payload_sha256);
        """
    )

    # 6. Reconciliation jobs table
    op.execute(
        """
        CREATE TABLE reconciliation_jobs (
            job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,

            -- Job config
            job_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,

            -- Detection
            detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            drift_description TEXT,
            local_state JSONB,
            remote_state JSONB,

            -- Resolution
            status TEXT NOT NULL DEFAULT 'PENDING',
            resolved_at TIMESTAMPTZ,
            resolution_action TEXT,
            resolution_result JSONB,

            CONSTRAINT reconciliation_jobs_tenant_fk FOREIGN KEY (tenant_id)
                REFERENCES tenants(tenant_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_reconciliation_status
            ON reconciliation_jobs(tenant_id, status, detected_at);
        CREATE INDEX idx_reconciliation_entity
            ON reconciliation_jobs(tenant_id, entity_type, entity_id);
        """
    )

    # 7. HITL requests table (INV-07)
    op.execute(
        """
        CREATE TABLE hitl_requests (
            request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id TEXT NOT NULL,

            -- Request context
            tool_name TEXT NOT NULL,
            tool_input JSONB NOT NULL,
            execution_id UUID NOT NULL,
            correlation_id TEXT NOT NULL,

            -- HITL rule
            rule_id TEXT NOT NULL,
            rule_reason TEXT,

            -- Status
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            timeout_at TIMESTAMPTZ,

            -- Decision
            decision TEXT,
            decided_by TEXT,
            decided_at TIMESTAMPTZ,
            decision_reason TEXT,

            CONSTRAINT hitl_requests_tenant_fk FOREIGN KEY (tenant_id)
                REFERENCES tenants(tenant_id) ON DELETE CASCADE
        );

        CREATE INDEX idx_hitl_status
            ON hitl_requests(tenant_id, status, created_at);
        CREATE INDEX idx_hitl_timeout
            ON hitl_requests(timeout_at) WHERE status = 'PENDING';
        CREATE INDEX idx_hitl_correlation
            ON hitl_requests(correlation_id);
        """
    )

    # 8. RLS helper functions
    op.execute(
        """
        -- Set tenant context (transaction-scoped)
        CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id text)
        RETURNS void AS $$
        BEGIN
            -- true = LOCAL means transaction-scoped
            PERFORM set_config('app.current_tenant_id', p_tenant_id, true);
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;

        -- Require tenant context is set
        CREATE OR REPLACE FUNCTION require_tenant_context()
        RETURNS text AS $$
        DECLARE
            tid text;
        BEGIN
            tid := current_setting('app.current_tenant_id', true);
            IF tid IS NULL OR tid = '' THEN
                RAISE EXCEPTION 'Tenant context not set';
            END IF;
            RETURN tid;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Downgrade schema - drop all tables."""
    op.execute("DROP TABLE IF EXISTS hitl_requests CASCADE;")
    op.execute("DROP TABLE IF EXISTS reconciliation_jobs CASCADE;")
    op.execute("DROP TABLE IF EXISTS event_store CASCADE;")
    op.execute("DROP TABLE IF EXISTS traces CASCADE;")
    op.execute("DROP TABLE IF EXISTS receipts CASCADE;")
    op.execute("DROP TABLE IF EXISTS state_versions CASCADE;")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS set_tenant_context(text);")
    op.execute("DROP FUNCTION IF EXISTS require_tenant_context();")
