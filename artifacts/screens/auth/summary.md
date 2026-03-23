# Auth Screens Summary

- Screens: `#1 Login`, `#2 Registration`, `#3 Invite Acceptance`
- Routes: `/login`, `/register`, `/invite/:token`
- Demo base URL: `http://localhost:3002`
- Playwright config: `frontend/playwright.auth-screens.config.ts`
- Result: `18 passed`

## Covered scenarios
1. Login page render, invalid credentials, all seeded role logins, footer navigation.
2. Registration page render, password mismatch, terms required, successful registration, footer navigation.
3. Invite acceptance invalid token state, valid token render, accept with account creation, decline flow.

## Product fixes made
1. Fixed Login pre-hydration submit behavior.
2. Fixed auth API client so `/auth/login` preserves backend 401 messages.
3. Added stable registration form submit/hydration handling and autocomplete attrs.
4. Implemented invitation token validation/accept/decline contract in backend.
5. Fixed invite acceptance frontend to use the real backend contract and preserve organization context after acceptance.

## Output artifacts
- HTML report: `artifacts/screens/auth/playwright-report/index.html`
- Test output: `artifacts/screens/auth/test-results/`
- Login summary: `artifacts/screens/login/summary.md`
