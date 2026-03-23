# Projects Screen Pack

## Scope

- Screen 11: `/projects`
- Screen 12: `/projects/:id/settings`

## Seeded accounts used

- `admin@esgvist.com` (`platform_admin`)
- `manager@greentech.com` (`esg_manager`)
- `collector1@greentech.com` (`collector`)
- `collector2@greentech.com` (`collector`)
- `reviewer@greentech.com` (`reviewer`)
- `auditor@greentech.com` (`auditor`)

Password for all demo accounts: `Test1234`

## Scenarios covered

### Project List

1. Render project list for `platform_admin`
2. Render project list for `esg_manager`
3. Create a new project from the list as `platform_admin`
4. Hide Projects nav and block direct access for both `collector` users
5. Hide Projects nav and block direct access for `reviewer`
6. Hide Projects nav and block direct access for `auditor`

### Project Settings

1. Open seeded project settings as `esg_manager`
2. Block direct access for both `collector` users
3. Block direct access for `reviewer`
4. Block direct access for `auditor`
5. End-to-end project configuration as `platform_admin`:
   - create project
   - open settings
   - add `GRI`
   - assign `FY2025 Sustainability Boundary`
   - save boundary snapshot
   - activate project

## Defects found and fixed

1. `Project Settings` expected backend endpoints that did not exist or were named differently.
   - Added additive backend endpoints and aliases in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/api/routes/projects.py`
   - Added project standards summary and assignment summary read-models in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/services/project_service.py`
2. Project pages were not enforcing screen-level role access from the spec.
   - Restricted project list/detail access to manager/admin roles in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/services/project_service.py`
   - Hid `Projects` nav for non-manager roles in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/frontend/app/(app)/layout.tsx`
   - Added explicit access denied states in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/frontend/app/(app)/projects/page.tsx` and `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/frontend/app/(app)/projects/[id]/settings/page.tsx`
3. Boundary apply flow failed because the frontend sent `boundary_id` in request body while backend accepted only query param.
   - Fixed additively by accepting both query and body in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/api/routes/projects.py`
4. Boundary/project read models were too thin for the screen.
   - Extended project and boundary response models in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/schemas/projects.py`
   - Added boundary entity counts and snapshot status fields in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/backend/app/services/boundary_service.py`
5. Playwright locators for dialog actions were initially ambiguous (`Create`, `Add`, `Draft`).
   - Tightened selectors in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/frontend/e2e/projects-screen.spec.ts`
   - Tightened selectors in `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/frontend/e2e/project-settings-screen.spec.ts`
6. Browser launch for this pack required running Playwright outside the sandbox on this host due macOS headless permission limits.
   - Validation completed successfully with escalated Playwright run.

## Result

- `13 passed` for `playwright.projects.config.ts`
- Screen pack moved into regression baseline.

## Artifacts

- HTML report: `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/artifacts/screens/projects/playwright-report/index.html`
- Test output: `/Users/ross.kurinko/Desktop/Code/ESGDashBoard/artifacts/screens/projects/test-results`
