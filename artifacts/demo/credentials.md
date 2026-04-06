# Demo Credentials

- Web URL: `http://127.0.0.1:3001`
- API URL: `http://127.0.0.1:8003/api`
- Shared password for all seeded accounts: `Test1234`

| Role | Full Name | Email | Notes |
| --- | --- | --- | --- |
| platform_admin | Ross Admin | `admin@esgvist.com` | Full access plus tenant management for the demo org |
| framework_admin | Iris Framework | `framework@esgvist.com` | Maintain ESG standards, shared elements, and mappings without tenant admin access |
| esg_manager | Anna Manager | `manager@greentech.com` | Projects, assignments, boundary, dashboard |
| collector | Ivan Collector | `collector1@greentech.com` | Input for GHG Scope 1 and Scope 2 data |
| collector | Maria Data | `collector2@greentech.com` | Input for Energy and Water style operational data |
| reviewer | Dmitry Reviewer | `reviewer@greentech.com` | Approve or reject data points |
| auditor | Elena Auditor | `auditor@greentech.com` | Read-only access to audit log and snapshots |

Manual verification:

1. Open `http://127.0.0.1:3001/login`.
2. Sign in with any account above.
3. For the consolidated verification view, open `http://127.0.0.1:3001/demo` after login.
