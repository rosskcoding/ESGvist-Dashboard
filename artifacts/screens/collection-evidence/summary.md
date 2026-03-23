# Collection & Evidence Screen Pack

- Pack: `#13-15 Data Collection & Evidence`
- Demo base URL: `http://localhost:3002`
- API base URL: `http://127.0.0.1:8002/api`
- Result: `20 passed`

## Covered screens
- `#13` Collection Table
- `#14` Data Entry Wizard
- `#15` Evidence Repository

## Covered role scenarios
- `collector` happy path for collection and wizard submit
- `esg_manager` readable collection/evidence access
- `auditor` read-only evidence access
- `reviewer` forbidden on collection/evidence views

## Key fixes shipped
- Collection table switched to real `/projects/{id}/data-points` contract
- Data entry wizard switched to real `GET/PATCH/submit` flow for data points
- Evidence upload/link flow aligned to backend JSON contract
- Forbidden/read-only states added for reviewer and auditor
- Evidence-aware submit flow uploads and links evidence before gate-check

## Artifacts
- Playwright report: `artifacts/screens/collection-evidence/playwright-report`
- Test results: `artifacts/screens/collection-evidence/test-results`
