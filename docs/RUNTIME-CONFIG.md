# Runtime Config Safety

## APP_ENV

`APP_ENV` controls runtime safety mode:

- `local`
- `staging`
- `production`

`local` is the only environment that permits developer defaults.

## Non-local startup validation

When `APP_ENV` is `staging` or `production`, API startup fails if any of the following remain unsafe:

- `DEBUG=true`
- `JWT_SECRET=change-me-in-production`
- `EMAIL_FAIL_SILENTLY=true`
- `STORAGE_BACKEND=minio|s3` with default `minioadmin` credentials

## Self-registration default

`ALLOW_SELF_REGISTRATION` is resolved as:

- `local`: enabled by default
- `staging` / `production`: disabled by default unless explicitly enabled at runtime

The platform config endpoint can still toggle self-registration explicitly.

## CORS_ORIGINS

`CORS_ORIGINS` now also feeds the cookie-auth origin trust policy for unsafe requests.

Use exact frontend origins only:

- `https://app.example.com`
- `https://ops.example.com:8443`

Avoid:

- `*`
- entries with path/query/fragment
- `http://...` outside `local`
- `localhost` origins outside `local`

## Browser auth policy

The Next.js UI now runs in cookie-first session mode:

- browser `login`, `refresh` and SSO callback set `access_token` / `refresh_token` as `HttpOnly` cookies
- browser responses return `session_mode=cookie`; bearer tokens in JSON are reserved for non-browser callers
- unsafe cookie-auth requests must pass all of:
  - `X-CSRF-Token`
  - trusted `Origin` or `Referer`
  - allowed `Sec-Fetch-Site`

Bearer auth remains supported for tests, automation and non-browser integrations.

## Support mode policy

Support mode is server-validated, not client-derived:

- source of truth is `GET /api/platform/support-session/current`
- frontend `localStorage` only caches tenant label/id for banner rendering
- invalid or expired support session cookies are cleared on bootstrap
- an active support session constrains tenant-scoped `/api/platform/tenants/{tenant_id}/...`
  routes to the support tenant; crossing to another tenant requires ending support mode first

## Demo bootstrap

`backend/seed.py` is demo-only bootstrap code.

- it may temporarily enable self-registration for local/demo seeding
- it must not be used as a production runtime template
- production-like environments should rely on `APP_ENV`, runtime validation and schema checks instead
