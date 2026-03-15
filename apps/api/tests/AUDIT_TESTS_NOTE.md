# Audit Support Tests - Implementation Note

## Current state (Code Review #3)

At the time of the review, Phase 12 tests (12.3-12.8) were scaffolds only (placeholders without full assertions).

## Root cause

The repository lacked the fixtures/helpers needed to implement realistic tests for:
- Multi-tenant setup (multiple companies and memberships)
- Role switching (auditor, editor, internal_auditor, audit_lead)
- Audit support data (evidence objects, comment threads)

## Why full tests were not added immediately

Without role-scoped authenticated clients and tenant-aware helpers, RBAC and tenant isolation tests become either:
- brittle (hard-coded IDs and assumptions), or
- superficial (checking only that endpoints exist).

## What can be tested without full fixtures

- Import/collection smoke (`pytest --collect-only`)
- Model-level behavior (CRUD for evidence/comments where possible)
- Endpoint existence and basic authorization wiring

## What requires additional test infrastructure

- Permission matrix behavior across roles
- Cross-tenant access denial
- UI visibility rules (e.g. internal vs external comment controls)
- Full E2E flows (page objects + seeded data)

## Next steps

Implement a small fixture layer that can create:
- companies A/B, users with specific roles, memberships
- reports/sections/blocks bound to a company
- evidence and comment thread factories

Once the fixture layer exists, the placeholder tests can be converted into real RBAC/tenant assertions.

---

Last updated: 2024-12-31 (Code Review #3)

