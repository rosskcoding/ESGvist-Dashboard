# Demo E2E Run Summary

- Run date: 2026-03-23
- Backend URL: `http://127.0.0.1:8002/api`
- Frontend URL: `http://localhost:3002`
- Database: `esgdashboard_demo_20260323`
- Playwright suite: `frontend/playwright.demo.config.ts`
- Result: `4 passed`

## Seeded Demo Scope
- Organization: `Northwind Renewables Group`
- Project: `FY2025 Sustainability Reporting`
- Standards covered: `GRI`, `IFRS S1`, `IFRS S2`, `ESRS`, plus one custom Northwind disclosure
- Roles covered: `platform_admin`, `admin`, `esg_manager`, `reviewer`, `auditor`, `collector`

## Scenario Coverage
1. Admin provisions custom standard/disclosure/item/mapping/assignment.
2. Energy and climate collectors submit GRI / IFRS S2 / ESRS metrics with evidence.
3. ESG manager submits IFRS S1 governance narrative.
4. Reviewer approves quantitative data and requests revision on narrative content.
5. Auditor validates completeness and audit trail.

## Output Artifacts
- Credentials: `artifacts/demo/credentials.md`
- Scenario description: `artifacts/demo/scenarios.md`
- Seed state: `artifacts/demo/demo-state.json`
- Runtime IDs: `artifacts/demo/runtime-state.json`
- Final business summary: `artifacts/demo/final-summary.json`
- API artifacts: `artifacts/demo/api-artifacts/`
- HTML report: `artifacts/demo/playwright-report/index.html`
- Test metadata: `artifacts/demo/test-results/.last-run.json`
