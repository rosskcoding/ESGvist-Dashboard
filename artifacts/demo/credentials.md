# Demo Credentials

- Web URL: `http://localhost:3002`
- API URL: `http://localhost:8002/api`
- Shared password for all seeded accounts: `DemoPass123!`

| Role | Full Name | Email | Notes |
| --- | --- | --- | --- |
| platform_admin | Paula Platform | `platform.admin@northwind-demo.example.com` | Platform-wide admin only |
| admin | Alice Admin | `admin@northwind-demo.example.com` | Tenant admin for Northwind demo org |
| esg_manager | Ethan ESG Manager | `esg.manager@northwind-demo.example.com` | Owns project and backup collector duties |
| reviewer | Rita Reviewer | `reviewer@northwind-demo.example.com` | Reviews submitted data points |
| auditor | Ava Auditor | `auditor@northwind-demo.example.com` | Audit trail / evidence verification |
| collector | Cole Energy Collector | `collector.energy@northwind-demo.example.com` | GRI 302 energy collection |
| collector | Clara Climate Collector | `collector.climate@northwind-demo.example.com` | GRI 305 / IFRS S2 / ESRS climate collection |

Manual verification:

1. Open `http://localhost:3002/login`.
2. Sign in with any account above.
3. For the consolidated verification view, open `http://localhost:3002/demo` after login.
