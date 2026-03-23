# Review & Validation Screen Pack

- Pack: `#16-17 Review & Validation`
- Demo base URL: `http://localhost:3002`
- API base URL: `http://127.0.0.1:8002/api`
- Result: `6 passed`

## Covered screens
- `#16` Review Split Panel
- `#17` Batch Review

## Covered role scenarios
- `reviewer` queue access, comment flow, single approve, batch revision request
- `auditor` read-only queue access
- `collector` forbidden
- `esg_manager` forbidden

## Key fixes shipped
- Added backend review queue endpoint `/api/review/items`
- Added author-enriched threaded comments payload for review threads
- Rebuilt `/validation` onto real review/comments/workflow endpoints
- Added batch review actions inside validation screen
- Locked validation nav and direct access to reviewer/auditor only
- Disabled sidebar prefetch to stop unrelated broken pages from crashing current screen packs during dev runs

## Artifacts
- Playwright report: `artifacts/screens/validation/playwright-report`
- Test results: `artifacts/screens/validation/test-results`
