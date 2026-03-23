# Assignments & Users

Status: green

Screens:
- Screen 19: Assignments Matrix
- Screen 20: User Management

Accounts covered:
- admin@esgvist.com (platform_admin)
- manager@greentech.com (esg_manager)
- collector1@greentech.com (collector)
- collector2@greentech.com (collector)
- reviewer@greentech.com (reviewer)
- auditor@greentech.com (auditor)

Scenarios covered:
- platform_admin can open Assignments Matrix and create an assignment
- esg_manager can open Assignments Matrix
- collector/reviewer/auditor cannot access Assignments Matrix by nav or direct URL
- platform_admin can open User Management
- platform_admin can invite and cancel a pending invitation
- esg_manager/collector/reviewer/auditor cannot access User Management by nav or direct URL

Fixes made:
- linked Add Assignment dialog labels to inputs for accessible field targeting
- fixed broken dynamic resend/cancel/status mutations on User Management that were incorrectly calling `/api`
- tightened assignment access so only admin/esg_manager/platform_admin can fetch the management matrix
- hardened Playwright selectors to target exact screen elements instead of ambiguous text matches
