# Company Structure & Boundary

Status: green

Screens:
- Screen 8: Company Structure
- Screen 9: Boundary Definitions
- Screen 10: Boundary Preview / Compare

Accounts covered:
- admin@esgvist.com (platform_admin)
- manager@greentech.com (esg_manager)
- collector1@greentech.com (collector)
- collector2@greentech.com (collector)
- reviewer@greentech.com (reviewer)
- auditor@greentech.com (auditor)

Scenarios covered:
- platform_admin and esg_manager can open Company Structure
- platform_admin can create an entity in Company Structure
- collector/reviewer/auditor cannot access Company Structure by nav or direct URL
- platform_admin can open Boundary Definitions and create a boundary
- esg_manager/collector/reviewer/auditor cannot access Boundary Definitions by nav or direct URL
- esg_manager can open the Boundary tab in Project Settings and view boundary details

Fixes made:
- added entity update API route and aligned company-structure frontend to real ownership/control endpoints
- enforced company-structure backend access to admin/esg_manager/platform_admin and added forbidden UI state
- restricted Company Structure and Boundaries navigation by role
- aligned Boundaries screen to real backend contracts and replaced broken dynamic membership edits with full membership replacement calls
- added admin-only guard for Boundary Definitions while preserving boundary read access for project settings flows
