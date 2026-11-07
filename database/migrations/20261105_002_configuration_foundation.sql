-- APPLIED 05-Nov-2026 after explicit user approval and verified database backup.
-- Configuration foundation: versioned, company-scoped, auditable rule payloads.
-- Existing master.* tables remain the authoritative source for brands, shades,
-- units, items, variants, ownership types and process stages.
-- This migration deliberately creates no seed policy for the unresolved Nalki PARTY rule.

BEGIN;

CREATE SCHEMA IF NOT EXISTS configuration;

CREATE TABLE configuration.config_versions (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES core.company(id),
    config_type VARCHAR(60) NOT NULL,
    config_key VARCHAR(120) NOT NULL,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    display_name VARCHAR(160) NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT','PENDING','APPROVED','REJECTED','RETIRED')),
    effective_from DATE NOT NULL,
    effective_to DATE,
    supersedes_version_id BIGINT REFERENCES configuration.config_versions(id),
    change_reason TEXT NOT NULL,
    created_by BIGINT NOT NULL REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_by BIGINT REFERENCES core.users(id),
    approved_at TIMESTAMPTZ,
    CONSTRAINT ck_config_effective_period
        CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT ck_config_approval_pair
        CHECK ((approved_by IS NULL) = (approved_at IS NULL)),
    CONSTRAINT uq_config_version
        UNIQUE (company_id, config_type, config_key, version_no)
);

CREATE INDEX ix_config_versions_current
    ON configuration.config_versions
       (company_id, config_type, config_key, status, effective_from DESC);

CREATE TABLE configuration.config_approval_events (
    id BIGSERIAL PRIMARY KEY,
    config_version_id BIGINT NOT NULL
        REFERENCES configuration.config_versions(id),
    decision VARCHAR(20) NOT NULL
        CHECK (decision IN ('SUBMITTED','APPROVED','REJECTED','WITHDRAWN')),
    decided_by BIGINT NOT NULL REFERENCES core.users(id),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comments TEXT,
    request_id UUID
);

CREATE INDEX ix_config_approval_events_version
    ON configuration.config_approval_events(config_version_id, decided_at);

CREATE TABLE configuration.config_audit_events (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES core.company(id),
    config_version_id BIGINT
        REFERENCES configuration.config_versions(id),
    config_type VARCHAR(60) NOT NULL,
    config_key VARCHAR(120) NOT NULL,
    event_type VARCHAR(30) NOT NULL
        CHECK (event_type IN
          ('CREATED','SUBMITTED','APPROVED','REJECTED','RETIRED','SUPERSEDED')),
    old_payload JSONB,
    new_payload JSONB,
    changed_by BIGINT NOT NULL REFERENCES core.users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL,
    correlation_id UUID
);

CREATE INDEX ix_config_audit_lookup
    ON configuration.config_audit_events
       (company_id, config_type, config_key, changed_at DESC);

COMMIT;

-- IMPLEMENTATION GATES BEFORE THIS PROPOSAL MAY BE APPLIED:
-- 1. Confirm the application DB role has only required schema/table privileges.
-- 2. Add server-side permissions for create, submit, approve, retire and view.
-- 3. Add service-level state transitions and reject edits to approved versions.
-- 4. Add concurrency protection and an immutable audit-write path.
-- 5. Validate payloads per config_type using app/configuration_rules.py.
-- 6. Add tests for tenant isolation, approval separation, effective-date overlap,
--    duplicate versions, rollback, concurrent submissions and historical snapshots.
-- 7. Confirm unresolved Nalki PARTY-stock policy before creating any such policy row.