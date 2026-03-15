# Test Coverage Note - Audit Support

## Status

Phase 12 (tests) was implemented as structured scaffolding per the original TODO.

## Current state

Done (unit-level):
- `test_evidence_crud.py` - model behavior (ORM properties/methods)
- `test_comment_threads.py` - model behavior (ORM properties/methods)
- `test_audit_pack_csv.py` - CSV structure and service import smoke

Needs work (integration/E2E):
- Integration tests (RBAC, tenant isolation, internal visibility) require real fixtures:
  - companies, users, memberships, and role assignments
  - real HTTP requests via the test client
- E2E tests require Playwright steps and data setup

## Rationale

The scope at the time was to create the test structure and document scenarios. Full coverage requires a fixture layer and helper utilities.

## Next steps

1. Add non-superuser fixtures (roles, memberships, multi-tenant)
2. Convert integration scaffolds into real HTTP assertions
3. Add Playwright helpers and deterministic data setup
4. Measure coverage with `pytest-cov`

---

Created: 2024-12-31

