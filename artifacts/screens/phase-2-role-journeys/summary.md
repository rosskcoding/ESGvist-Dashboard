# Phase 2 — Deep Role Journeys

## Scenario Pack

1. `collector -> reviewer -> collector revision -> reviewer approve -> auditor audit`
2. `esg_manager -> project settings -> readiness -> export preview -> publish`
3. `admin -> custom disclosure rollout -> assignment -> collector visibility`
4. `platform_admin -> tenant lifecycle -> organization auth policy`

## Results

- `role-journeys-phase2.spec.ts`: `4 passed`
- backend targeted regression: `tests/test_completeness.py tests/test_review_export.py`: `21 passed`

## Fixes landed during run

1. `backend/app/services/completeness_service.py`
   - boundary-wide completeness is now rule-driven instead of implicitly blocking any entity-scoped approved metric
2. `backend/tests/test_completeness.py`
   - added explicit boundary coverage test and updated boundary-context assertions to match the rule-driven behavior
3. `frontend/app/(app)/report/preview/page.tsx`
   - fixed `projectId` scope bug in preview header/back-link
4. `frontend/e2e/role-journeys-phase2.spec.ts`
   - expanded from one journey to four serial cross-role scenario packs
5. `frontend/app/(app)/settings/standards/page.tsx`
   - increased standards list fetch to `page_size=100`, so newly created standards remain visible in seeded regression/demo runs
6. `frontend/app/(app)/projects/page.tsx`
   - increased projects list fetch to `page_size=100`, so newly created projects remain visible immediately after creation

## Artifacts

- HTML report: `artifacts/screens/phase-2-role-journeys/playwright-report/index.html`
- Raw results: `artifacts/screens/phase-2-role-journeys/test-results`

## Notes

- Live demo frontend on `http://localhost:3002`
- Live demo API on `http://127.0.0.1:8002/api`
- Seeded accounts unchanged:
  - `admin@esgvist.com`
  - `manager@greentech.com`
  - `collector1@greentech.com`
  - `collector2@greentech.com`
  - `reviewer@greentech.com`
  - `auditor@greentech.com`
