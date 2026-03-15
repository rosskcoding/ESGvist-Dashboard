# Audit Tests - Required Fixtures (Summary)

## Problem

Code review feedback noted that Phase 12 audit tests (12.3-12.8) were scaffolds and did not perform real RBAC/tenant isolation assertions.

## Root cause

The test `conftest.py` setup used a superuser as the default authenticated user. Superusers bypass:
- tenant access checks, and
- RBAC permission checks

This makes it impossible to validate access denial behavior for non-superuser roles.

## What is needed to implement real RBAC/tenant isolation tests

- Non-superuser user fixtures (auditor/editor/internal_auditor/audit_lead, etc.)
- Role-specific authenticated clients (dependency override or token-based auth)
- Multi-tenant fixtures (company A/B, users belonging to only one company)
- Test data factories for evidence and comment threads

## Why it was not implemented in the referenced review

Adding fixtures and factories is test-infrastructure work (cross-cutting changes), not a minimal one-file patch.

## Recommendation

Build a small, reusable fixture layer first, then convert placeholder tests into real role/tenant assertions.

---

Created: 2024-12-31 (Code Review #4)

