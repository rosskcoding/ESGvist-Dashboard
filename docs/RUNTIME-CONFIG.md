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
