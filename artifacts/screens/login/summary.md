# Screen 1 - Login

- Screen: `#1 Login`
- Route: `/login`
- Demo base URL: `http://localhost:3002`
- Playwright config: `frontend/playwright.login-screen.config.ts`
- Result: `9 passed`

## Covered scenarios
1. Login form renders correctly.
2. Seeded demo personas are visible on the page.
3. Invalid credentials show backend message and stay on Login.
4. Successful login works for `platform_admin`.
5. Successful login works for `esg_manager`.
6. Successful login works for both `collector` accounts.
7. Successful login works for `reviewer`.
8. Successful login works for `auditor`.
9. Footer link navigates to `/register`.

## Fixes made during this screen
1. Prevented pre-hydration native form submit on Login screen.
2. Added proper `autocomplete` attributes.
3. Preserved backend auth errors instead of redirecting away on `/auth/login` 401.
4. Improved Login page error rendering to use the thrown error message.

## Output artifacts
- HTML report: `artifacts/screens/login/playwright-report/index.html`
- Test output: `artifacts/screens/login/test-results/`
