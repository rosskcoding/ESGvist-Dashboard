# ESGvist — Business Rules for Backend Implementation

**Версия:** 1.0
**Дата:** 2026-03-22

---

## Evidence Module

### Rule 1: Evidence type consistency

Enforce at **application/service layer** (not SQL):

```
IF evidences.type = 'file':
    → evidence_files row MUST exist
    → evidence_links row MUST NOT exist

IF evidences.type = 'link':
    → evidence_links row MUST exist
    → evidence_files row MUST NOT exist
```

**Implementation:** Service layer validates on create/update. If mismatch → `VALIDATION_ERROR` (400).

### Rule 2: Approve restriction (EVIDENCE_REQUIRED)

At `POST /review/data-points/{id}/approve`:

```
FOR EACH requirement_item linked to this data_point (via requirement_item_data_points):
    IF requirement_item.requires_evidence = true:
        evidence_count = COUNT(data_point_evidences WHERE data_point_id = dp.id)
                       + COUNT(requirement_item_evidences WHERE requirement_item_id = ri.id)
        IF evidence_count = 0:
            → REJECT transition
            → return EVIDENCE_REQUIRED (422)
            → message: "This data point requires supporting evidence before approval."
```

### Rule 3: Completeness Engine integration

When calculating `requirement_item_status`:

```
IF requirement_item.requires_evidence = true:
    IF no linked evidence (data_point_evidences + requirement_item_evidences):
        IF data_point exists and approved:
            → status = 'partial'
            → status_reason = "Missing required evidence"
        ELSE IF no data_point:
            → status = 'missing'
    ELSE:
        → proceed with normal completeness logic
```

### Rule 4: Delete / unlink restriction

```
ON DELETE /evidences/{id}:
    IF evidence is linked to any data_point with status = 'approved':
        → return EVIDENCE_IN_USE (409)
        → message: "Cannot delete evidence used in approved scope."

ON DELETE /data-points/{id}/evidences/{evidenceId}:
    IF data_point.status = 'approved':
        → return DATA_POINT_LOCKED (422)
        → message: "Cannot unlink evidence from approved data point."
```

Override: ESG-manager must first rollback data_point to draft.

### Rule 5: Tenant isolation

```
ALL evidence queries MUST filter by:
    evidences.organization_id = current_user.organization_id

Cross-tenant evidence access → FORBIDDEN (403)
```

### Rule 6: File constraints

```
Max file size: 10 MB (configurable via organization settings)
Allowed MIME types: [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  // xlsx
    'application/vnd.ms-excel',  // xls
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  // docx
    'image/jpeg',
    'image/png',
    'text/csv'
]

Violation → EVIDENCE_FILE_TOO_LARGE (422) or EVIDENCE_FILE_TYPE_NOT_ALLOWED (422)
```

---

## Data Model Chain

```
requirement_items
    └── requires_evidence: boolean

evidences
    ├── evidence_files      (1:1, type='file')
    ├── evidence_links      (1:1, type='link')
    ├── data_point_evidences     (M:N → data_points)
    └── requirement_item_evidences (M:N → requirement_items)

Completeness Engine check:
    requirement_item.requires_evidence = true
    + count(linked evidences) = 0
    → status = 'partial' (not 'complete')

Workflow check:
    approve transition
    + requires_evidence = true
    + no evidence
    → block with EVIDENCE_REQUIRED (422)
```

---

## Event Triggers

| Event | Trigger | Consumer |
|-------|---------|----------|
| `EvidenceCreated` | POST /evidences | Audit Service |
| `EvidenceLinkedToDP` | POST /data-points/:id/evidences | Completeness Engine (recalculate) |
| `EvidenceUnlinkedFromDP` | DELETE /data-points/:id/evidences/:eid | Completeness Engine (recalculate) |
| `EvidenceLinkedToRI` | POST /requirement-items/:id/evidences | Completeness Engine (recalculate) |
| `EvidenceUnlinkedFromRI` | DELETE /requirement-items/:id/evidences/:eid | Completeness Engine (recalculate) |
| `EvidenceDeleted` | DELETE /evidences/:id | Audit Service + check approved scope |
