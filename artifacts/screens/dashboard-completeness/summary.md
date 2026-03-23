# Dashboard + Completeness Screen Pack

## Scope

- Screen 6: `/dashboard`
- Screen 7: `/completeness`

## Seeded accounts used

- `admin@esgvist.com` (`platform_admin`)
- `manager@greentech.com` (`esg_manager`)
- `collector1@greentech.com` (`collector`)
- `collector2@greentech.com` (`collector`)
- `reviewer@greentech.com` (`reviewer`)
- `auditor@greentech.com` (`auditor`)

Password for all demo accounts: `Test1234`

## Scenarios covered

### Dashboard

1. Loads dashboard for `platform_admin`
2. Loads dashboard for `esg_manager`
3. Loads dashboard for both `collector` users
4. Loads dashboard for `reviewer`
5. Loads dashboard for `auditor`
6. Verifies core zones:
   - `Overall Completion`
   - `Overdue Assignments`
   - `Completion by Standard`
   - `Boundary Summary`
   - `Priority Tasks`
   - active boundary name

### Completeness

1. Renders completeness for `platform_admin`
2. Renders completeness for `esg_manager`
3. Renders completeness for `auditor`
4. Hides nav and blocks direct access for both `collector` users
5. Hides nav and blocks direct access for `reviewer`
6. Verifies completeness zones:
   - overall completeness summary
   - completion by standard
   - disclosure details
   - active boundary name

## Defects found and fixed

1. Collectors could not open dashboard because dashboard aggregation called merge analytics with collector-forbidden access checks.
   - Fixed in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/services/dashboard_service.py`
   - Dashboard now returns merge sections only for roles allowed to access merge views.
2. Dashboard Playwright locator for `Priority Tasks` was ambiguous because the empty state text also matched the same substring.
   - Fixed in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/frontend/e2e/dashboard-screen.spec.ts`
3. Completeness screen/backend alignment and nav role filtering were already completed in this pack and validated green.

## Result

- `12 passed` for `playwright.dashboard-completeness.config.ts`
- Screen pack moved into regression baseline.

## Artifacts

- HTML report: `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/artifacts/screens/dashboard-completeness/playwright-report/index.html`
- Test output: `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/artifacts/screens/dashboard-completeness/test-results`
