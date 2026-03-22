-- ═══════════════════════════════════════════════════════════
-- Migration 001: Evidence Module
-- Date: 2026-03-22
-- Description: Add evidence as domain entity with file/link
--              subtypes, M:N bindings, and requires_evidence flag
-- ═══════════════════════════════════════════════════════════

BEGIN;

-- ── 1. Alter requirement_items: add requires_evidence flag ──
ALTER TABLE requirement_items
    ADD COLUMN requires_evidence boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN requirement_items.requires_evidence IS
    'If true, completeness engine requires at least one evidence linked to approve';

-- ── 2. evidences: main entity ──
CREATE TABLE evidences (
    id                  bigserial PRIMARY KEY,
    organization_id     bigint NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    type                text NOT NULL CHECK (type IN ('file', 'link')),
    title               text NOT NULL,
    description         text,
    source_type         text NOT NULL CHECK (source_type IN ('manual', 'upload', 'integration')),
    created_by          bigint REFERENCES users(id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE evidences IS
    'Domain entity for supporting documents and links. Reusable across data_points and requirement_items.';

-- ── 3. evidence_files: file subtype (1:1 with evidences) ──
CREATE TABLE evidence_files (
    evidence_id         bigint PRIMARY KEY REFERENCES evidences(id) ON DELETE CASCADE,
    file_name           text NOT NULL,
    file_uri            text NOT NULL,
    mime_type           text,
    file_size           integer
);

COMMENT ON TABLE evidence_files IS
    'File metadata for evidences with type=file. S3/MinIO URI stored in file_uri.';

-- ── 4. evidence_links: link subtype (1:1 with evidences) ──
CREATE TABLE evidence_links (
    evidence_id         bigint PRIMARY KEY REFERENCES evidences(id) ON DELETE CASCADE,
    url                 text NOT NULL,
    label               text,
    access_note         text
);

COMMENT ON TABLE evidence_links IS
    'URL metadata for evidences with type=link. access_note for VPN/auth instructions.';

-- ── 5. data_point_evidences: M:N binding ──
CREATE TABLE data_point_evidences (
    id                  bigserial PRIMARY KEY,
    data_point_id       bigint NOT NULL REFERENCES data_points(id) ON DELETE CASCADE,
    evidence_id         bigint NOT NULL REFERENCES evidences(id) ON DELETE CASCADE,
    linked_by           bigint REFERENCES users(id) ON DELETE SET NULL,
    linked_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (data_point_id, evidence_id)
);

COMMENT ON TABLE data_point_evidences IS
    'M:N binding between data_points and evidences. One evidence can support multiple data_points.';

-- ── 6. requirement_item_evidences: M:N binding ──
CREATE TABLE requirement_item_evidences (
    id                  bigserial PRIMARY KEY,
    requirement_item_id bigint NOT NULL REFERENCES requirement_items(id) ON DELETE CASCADE,
    evidence_id         bigint NOT NULL REFERENCES evidences(id) ON DELETE CASCADE,
    linked_by           bigint REFERENCES users(id) ON DELETE SET NULL,
    linked_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (requirement_item_id, evidence_id)
);

COMMENT ON TABLE requirement_item_evidences IS
    'M:N binding between requirement_items and evidences. Evidence as proof of requirement compliance.';

-- ── 7. Indexes ──

-- evidences lookups
CREATE INDEX idx_evidences_organization
    ON evidences(organization_id);

CREATE INDEX idx_evidences_type
    ON evidences(type);

CREATE INDEX idx_evidences_created_by
    ON evidences(created_by);

-- data_point_evidences lookups
CREATE INDEX idx_data_point_evidences_data_point
    ON data_point_evidences(data_point_id);

CREATE INDEX idx_data_point_evidences_evidence
    ON data_point_evidences(evidence_id);

-- requirement_item_evidences lookups
CREATE INDEX idx_requirement_item_evidences_requirement_item
    ON requirement_item_evidences(requirement_item_id);

CREATE INDEX idx_requirement_item_evidences_evidence
    ON requirement_item_evidences(evidence_id);

COMMIT;
