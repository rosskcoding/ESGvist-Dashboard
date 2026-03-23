# Demo Scenarios

Seeded organization: `Northwind Renewables Group` with UK parent, UK/DE subsidiaries, ES branch, DE facility, UK business unit, and one excluded JV.

Playwright scenarios are designed to cover:

1. Admin creates a custom reporting standard/disclosure/item/mapping and assigns it to a collector.
2. Energy collector submits a GRI 302-1 energy metric with evidence.
3. Climate collector submits a shared Scope 1 metric reused across GRI 305-1, IFRS S2 and ESRS E1 plus a custom disclosure metric.
4. ESG manager submits an IFRS S1 governance narrative.
5. Reviewer approves quantitative submissions and requests revision on the governance narrative.
6. Auditor verifies audit log and completeness state after the workflow run.

Artifacts are written under `artifacts/demo/` and Playwright output is kept separate from the existing frontend test results.
