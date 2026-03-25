"""
Demo-only database seed script for ESGvist.
Uses the running API at http://localhost:8001 via httpx sync client.
Do not treat this flow or its permissive platform toggles as production runtime defaults.
"""

import sys
import httpx

BASE = "http://localhost:8001"
PASSWORD = "Test1234"

client = httpx.Client(base_url=BASE, timeout=30)

# Storage for created IDs
state: dict = {
    "users": {},        # email -> {id, token}
    "org_id": None,
    "root_entity_id": None,
    "boundary_id": None,
    "entities": {},     # name -> id
    "standards": {},    # code -> id
    "sections": {},     # title -> id
    "disclosures": {},  # code -> id
    "req_items": {},    # code -> id
    "shared_elements": {},  # code -> id
    "project_id": None,
}


def headers(token: str, org_id: int | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if org_id:
        h["X-Organization-Id"] = str(org_id)
    return h


def admin_headers(org_id: int | None = None) -> dict:
    return headers(state["users"]["admin@esgvist.com"]["token"], org_id)


def step(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def post(url: str, json: dict, hdrs: dict | None = None) -> dict | None:
    r = client.post(url, json=json, headers=hdrs or {})
    if r.status_code >= 400:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


def get(url: str, hdrs: dict | None = None) -> dict | None:
    r = client.get(url, headers=hdrs or {})
    if r.status_code >= 400:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


def put(url: str, json: dict, hdrs: dict | None = None) -> dict | None:
    r = client.put(url, json=json, headers=hdrs or {})
    if r.status_code >= 400:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


def patch(url: str, json: dict, hdrs: dict | None = None) -> dict | None:
    r = client.patch(url, json=json, headers=hdrs or {})
    if r.status_code >= 400:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return None
    return r.json()


# ── 0. Enable demo self-registration ───────────────────────────
def ensure_demo_self_registration():
    step("0. Enable demo self-registration")
    # Login as admin first
    r = post("/api/auth/login", {"email": "admin@esgvist.com", "password": PASSWORD})
    if not r:
        print("FATAL: Cannot login as admin@esgvist.com")
        sys.exit(1)
    state["users"]["admin@esgvist.com"] = {"id": None, "token": r["access_token"]}

    # Get admin user info
    me = get("/api/auth/me", headers(r["access_token"]))
    if me:
        state["users"]["admin@esgvist.com"]["id"] = me["id"]
        print(f"  Admin user id: {me['id']}")

    # Demo bootstrap intentionally enables self-registration for local seeding only.
    res = patch(
        "/api/platform/config/self-registration",
        {"allow_self_registration": True},
        admin_headers(),
    )
    if res:
        print(f"  Demo self-registration: {res}")
    else:
        print("  WARNING: Could not enable self-registration (may already be enabled)")


# ── 1. Register users ────────────────────────────────────────
def register_users():
    step("1. Register users")
    users_to_register = [
        ("framework@esgvist.com", "Iris Framework"),
        ("manager@greentech.com", "Anna Manager"),
        ("collector1@greentech.com", "Ivan Collector"),
        ("collector2@greentech.com", "Maria Data"),
        ("reviewer@greentech.com", "Dmitry Reviewer"),
        ("auditor@greentech.com", "Elena Auditor"),
    ]

    for email, name in users_to_register:
        r = post("/api/auth/register", {
            "email": email,
            "password": PASSWORD,
            "full_name": name,
        })
        if r:
            print(f"  Registered: {email} (id={r['id']})")
            # Login to get token
            login = post("/api/auth/login", {"email": email, "password": PASSWORD})
            if login:
                state["users"][email] = {"id": r["id"], "token": login["access_token"]}
        else:
            print(f"  Registration failed for {email}, trying login...")
            login = post("/api/auth/login", {"email": email, "password": PASSWORD})
            if login:
                me = get("/api/auth/me", headers(login["access_token"]))
                uid = me["id"] if me else None
                state["users"][email] = {"id": uid, "token": login["access_token"]}
                print(f"  Logged in: {email} (id={uid})")


def assign_platform_roles():
    step("1b. Assign platform roles")
    hdrs = admin_headers()
    framework_user = state["users"].get("framework@esgvist.com")
    if not framework_user:
        print("  WARNING: framework@esgvist.com was not registered")
        return
    user_id = framework_user.get("id")
    if not user_id:
        print("  WARNING: framework@esgvist.com has no user id")
        return
    res = post(
        f"/api/users/{user_id}/roles",
        {"role": "framework_admin", "scope_type": "platform", "scope_id": None},
        hdrs,
    )
    if res:
        print(f"  Assigned framework_admin to framework@esgvist.com (binding={res['id']})")
    else:
        print("  WARNING: Could not assign framework_admin")


# ── 2. Setup organization ────────────────────────────────────
def setup_organization():
    step("2. Setup organization")
    r = post(
        "/api/organizations/setup",
        {
            "name": "GreenTech Holdings",
            "country": "DE",
            "industry": "Manufacturing",
        },
        admin_headers(),
    )
    if r:
        state["org_id"] = r["organization_id"]
        state["root_entity_id"] = r["root_entity_id"]
        state["boundary_id"] = r.get("boundary_id")
        state["entities"]["GreenTech Holdings"] = r["root_entity_id"]
        print(f"  Org ID: {state['org_id']}")
        print(f"  Root Entity ID: {state['root_entity_id']}")
        print(f"  Boundary ID: {state['boundary_id']}")
    else:
        print("  FATAL: Could not setup organization")
        sys.exit(1)


# ── 3. Create subsidiary entities ─────────────────────────────
def create_entities():
    step("3. Create subsidiary entities")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)

    subsidiaries = [
        ("GreenTech Energy GmbH", "legal_entity", "DE"),
        ("GreenTech Chemicals Ltd", "legal_entity", "GB"),
        ("Solar JV Partners", "joint_venture", "US"),
        ("Berlin Manufacturing Plant", "facility", "DE"),
        ("London R&D Center", "facility", "GB"),
    ]

    for name, etype, country in subsidiaries:
        r = post("/api/entities", {
            "name": name,
            "entity_type": etype,
            "country": country,
            "status": "active",
        }, hdrs)
        if r:
            state["entities"][name] = r["id"]
            print(f"  Created: {name} (id={r['id']})")
        else:
            print(f"  Failed: {name}")


# ── 4. Create ownership links ─────────────────────────────────
def create_ownership_links():
    step("4. Create ownership links")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)
    e = state["entities"]

    links = [
        ("GreenTech Holdings", "GreenTech Energy GmbH", 100, "direct"),
        ("GreenTech Holdings", "GreenTech Chemicals Ltd", 85, "direct"),
        ("GreenTech Holdings", "Solar JV Partners", 50, "direct"),
        ("GreenTech Energy GmbH", "Berlin Manufacturing Plant", 100, "direct"),
        ("GreenTech Chemicals Ltd", "London R&D Center", 100, "direct"),
    ]

    for parent, child, pct, otype in links:
        parent_id = e.get(parent)
        child_id = e.get(child)
        if not parent_id or not child_id:
            print(f"  Skipping {parent} -> {child}: missing IDs")
            continue
        r = post("/api/ownership-links", {
            "parent_entity_id": parent_id,
            "child_entity_id": child_id,
            "ownership_percent": pct,
            "ownership_type": otype,
        }, hdrs)
        if r:
            print(f"  {parent} -> {child}: {pct}% ({r['id']})")
        else:
            print(f"  Failed: {parent} -> {child}")


# ── 5. Create standards ───────────────────────────────────────
def create_standards():
    step("5. Create standards")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)

    standards = [
        ("GRI", "GRI Standards", "2024"),
        ("IFRS-S1", "IFRS S1", "2024"),
        ("IFRS-S2", "IFRS S2", "2024"),
        ("ESRS", "ESRS", "2024"),
    ]

    for code, name, version in standards:
        r = post("/api/standards", {
            "code": code,
            "name": name,
            "version": version,
        }, hdrs)
        if r:
            state["standards"][code] = r["id"]
            print(f"  Created: {code} (id={r['id']})")
        else:
            print(f"  Failed: {code}")


# ── 6. Create sections and disclosures ────────────────────────
def create_disclosures():
    step("6. Create sections and disclosures")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)

    # Structure: (standard_code, section_title, disclosures[])
    # disclosures: (code, title, req_type, mandatory_level)
    taxonomy = [
        ("GRI", "GRI 302: Energy", [
            ("GRI 302-1", "Energy consumption within the organization", "quantitative", "mandatory"),
            ("GRI 302-3", "Energy intensity", "quantitative", "mandatory"),
        ]),
        ("GRI", "GRI 305: Emissions", [
            ("GRI 305-1", "Direct (Scope 1) GHG emissions", "quantitative", "mandatory"),
            ("GRI 305-2", "Energy indirect (Scope 2) GHG emissions", "quantitative", "mandatory"),
            ("GRI 305-4", "GHG emissions intensity", "quantitative", "mandatory"),
        ]),
        ("GRI", "GRI 303: Water", [
            ("GRI 303-3", "Water withdrawal", "quantitative", "mandatory"),
        ]),
        ("IFRS-S2", "Climate-related Risks", [
            ("S2.21", "Climate-related risks description", "qualitative", "mandatory"),
            ("S2.29", "GHG emissions (Scope 1, 2, 3)", "quantitative", "mandatory"),
        ]),
        ("IFRS-S2", "Strategy", [
            ("S2.13", "Climate resilience assessment", "qualitative", "mandatory"),
        ]),
        ("ESRS", "ESRS E1: Climate Change", [
            ("E1-6", "Gross Scopes 1, 2, 3 GHG emissions", "quantitative", "mandatory"),
            ("E1-4", "GHG emission reduction targets", "quantitative", "mandatory"),
        ]),
        ("ESRS", "ESRS E3: Water", [
            ("E3-4", "Water consumption", "quantitative", "mandatory"),
        ]),
    ]

    for std_code, section_title, disclosures in taxonomy:
        std_id = state["standards"].get(std_code)
        if not std_id:
            print(f"  Skipping section '{section_title}': standard {std_code} not found")
            continue

        # Create section
        sec = post(f"/api/standards/{std_id}/sections", {
            "title": section_title,
        }, hdrs)
        if sec:
            state["sections"][section_title] = sec["id"]
            print(f"  Section: {section_title} (id={sec['id']})")
        else:
            print(f"  Failed section: {section_title}")
            continue

        # Create disclosures
        for d_code, d_title, d_req_type, d_mandatory in disclosures:
            d = post(f"/api/standards/{std_id}/disclosures", {
                "section_id": sec["id"],
                "code": d_code,
                "title": d_title,
                "requirement_type": d_req_type,
                "mandatory_level": d_mandatory,
            }, hdrs)
            if d:
                state["disclosures"][d_code] = d["id"]
                print(f"    Disclosure: {d_code} (id={d['id']})")
            else:
                print(f"    Failed disclosure: {d_code}")


# ── 6b. Create requirement items for disclosures ──────────────
def create_requirement_items():
    step("6b. Create requirement items for disclosures")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)

    # Each disclosure gets one requirement item with same code
    # (item_code, disclosure_code, name, item_type, value_type, unit_code)
    items = [
        ("GRI 302-1", "GRI 302-1", "Energy consumption within the organization", "metric", "number", "MWh"),
        ("GRI 302-3", "GRI 302-3", "Energy intensity", "metric", "number", "MWh/unit"),
        ("GRI 305-1", "GRI 305-1", "Direct (Scope 1) GHG emissions", "metric", "number", "tCO2e"),
        ("GRI 305-2", "GRI 305-2", "Energy indirect (Scope 2) GHG emissions", "metric", "number", "tCO2e"),
        ("GRI 305-4", "GRI 305-4", "GHG emissions intensity", "metric", "number", "tCO2e/unit"),
        ("GRI 303-3", "GRI 303-3", "Water withdrawal", "metric", "number", "m3"),
        ("S2.21", "S2.21", "Climate-related risks description", "narrative", "text", None),
        ("S2.29", "S2.29", "GHG emissions (Scope 1, 2, 3)", "metric", "number", "tCO2e"),
        ("S2.13", "S2.13", "Climate resilience assessment", "narrative", "text", None),
        ("E1-6", "E1-6", "Gross Scopes 1, 2, 3 GHG emissions", "metric", "number", "tCO2e"),
        ("E1-4", "E1-4", "GHG emission reduction targets", "metric", "number", "tCO2e"),
        ("E3-4", "E3-4", "Water consumption", "metric", "number", "m3"),
    ]

    for item_code, disc_code, name, itype, vtype, unit in items:
        disc_id = state["disclosures"].get(disc_code)
        if not disc_id:
            print(f"  Skipping item {item_code}: disclosure {disc_code} not found")
            continue

        payload: dict = {
            "item_code": item_code,
            "name": name,
            "item_type": itype,
            "value_type": vtype,
            "is_required": True,
        }
        if unit:
            payload["unit_code"] = unit

        r = post(f"/api/disclosures/{disc_id}/items", payload, hdrs)
        if r:
            state["req_items"][item_code] = r["id"]
            print(f"  Item: {item_code} (id={r['id']})")
        else:
            print(f"  Failed item: {item_code}")


# ── 7. Create shared elements ─────────────────────────────────
def create_shared_elements():
    step("7. Create shared elements")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)

    elements = [
        ("SE-GHG-SCOPE1", "GHG Scope 1 emissions", "emissions", "number", "tCO2e"),
        ("SE-GHG-SCOPE2", "GHG Scope 2 emissions", "emissions", "number", "tCO2e"),
        ("SE-ENERGY-TOTAL", "Total energy consumption", "energy", "number", "MWh"),
        ("SE-WATER-WITHDRAWAL", "Water withdrawal", "water", "number", "m3"),
        ("SE-GHG-INTENSITY", "GHG intensity", "emissions", "number", "tCO2e/revenue"),
    ]

    for code, name, domain, vtype, unit in elements:
        r = post("/api/shared-elements", {
            "code": code,
            "name": name,
            "concept_domain": domain,
            "default_value_type": vtype,
            "default_unit_code": unit,
        }, hdrs)
        if r:
            state["shared_elements"][code] = r["id"]
            print(f"  Created: {code} (id={r['id']})")
        else:
            print(f"  Failed: {code}")


# ── 8. Create mappings ────────────────────────────────────────
def create_mappings():
    step("8. Create mappings (shared element -> requirement items)")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)
    se = state["shared_elements"]
    ri = state["req_items"]

    mappings = [
        ("SE-GHG-SCOPE1", "GRI 305-1", "full"),
        ("SE-GHG-SCOPE1", "S2.29", "partial"),
        ("SE-GHG-SCOPE1", "E1-6", "full"),
        ("SE-GHG-SCOPE2", "GRI 305-2", "full"),
        ("SE-GHG-SCOPE2", "S2.29", "partial"),
        ("SE-GHG-SCOPE2", "E1-6", "full"),
        ("SE-ENERGY-TOTAL", "GRI 302-1", "full"),
        ("SE-WATER-WITHDRAWAL", "GRI 303-3", "full"),
        ("SE-WATER-WITHDRAWAL", "E3-4", "full"),
    ]

    for se_code, ri_code, mtype in mappings:
        se_id = se.get(se_code)
        ri_id = ri.get(ri_code)
        if not se_id or not ri_id:
            print(f"  Skipping {se_code} -> {ri_code}: missing IDs (se={se_id}, ri={ri_id})")
            continue
        r = post("/api/mappings", {
            "shared_element_id": se_id,
            "requirement_item_id": ri_id,
            "mapping_type": mtype,
        }, hdrs)
        if r:
            print(f"  {se_code} -> {ri_code} ({mtype}, id={r['id']})")
        else:
            print(f"  Failed: {se_code} -> {ri_code}")


# ── 9. Create reporting project ───────────────────────────────
def create_project():
    step("9. Create reporting project")
    org_id = state["org_id"]
    hdrs = admin_headers(org_id)

    r = post("/api/projects", {
        "name": "ESG Report 2024",
        "reporting_year": 2024,
    }, hdrs)
    if r:
        state["project_id"] = r["id"]
        print(f"  Project ID: {r['id']}")
    else:
        print("  Failed to create project")
        return

    # Attach standards
    for std_code in ["GRI", "IFRS-S2", "ESRS"]:
        std_id = state["standards"].get(std_code)
        if not std_id:
            print(f"  Skipping standard attach: {std_code} not found")
            continue
        r = post(f"/api/projects/{state['project_id']}/standards", {
            "standard_id": std_id,
        }, hdrs)
        if r:
            print(f"  Attached standard: {std_code}")
        else:
            print(f"  Failed to attach: {std_code}")


# ── 10. Apply boundary ────────────────────────────────────────
def apply_boundary():
    step("10. Apply boundary to project")
    org_id = state["org_id"]
    project_id = state["project_id"]
    boundary_id = state["boundary_id"]

    if not project_id or not boundary_id:
        print("  Skipping: missing project or boundary ID")
        return

    hdrs = admin_headers(org_id)

    # Add all entities to the boundary first
    entities_for_boundary = []
    for name, eid in state["entities"].items():
        entities_for_boundary.append({
            "entity_id": eid,
            "included": True,
            "inclusion_source": "manual",
            "consolidation_method": "full",
        })

    if entities_for_boundary:
        r = put(
            f"/api/boundaries/{boundary_id}/memberships",
            {"memberships": entities_for_boundary},
            hdrs,
        )
        if r:
            print(f"  Updated boundary memberships: {len(entities_for_boundary)} entities")
        else:
            print("  Failed to update boundary memberships")

    # Apply boundary to project
    r = client.put(
        f"/api/projects/{project_id}/boundary?boundary_id={boundary_id}",
        headers=hdrs,
    )
    if r.status_code < 400:
        print(f"  Applied boundary {boundary_id} to project {project_id}")
    else:
        print(f"  ERROR applying boundary: {r.status_code} {r.text[:200]}")


# ── 13. Assign roles to all users in the organization ─────────
def assign_org_roles():
    step("13. Assign organization roles to users")
    org_id = state["org_id"]
    hdrs = admin_headers()  # platform admin, no org header needed

    role_assignments = [
        ("manager@greentech.com", "esg_manager"),
        ("collector1@greentech.com", "collector"),
        ("collector2@greentech.com", "collector"),
        ("reviewer@greentech.com", "reviewer"),
        ("auditor@greentech.com", "auditor"),
    ]

    for email, role in role_assignments:
        user_info = state["users"].get(email)
        if not user_info or not user_info.get("id"):
            print(f"  Skipping {email}: no user ID")
            continue

        user_id = user_info["id"]
        r = post(f"/api/users/{user_id}/roles", {
            "role": role,
            "scope_type": "organization",
            "scope_id": org_id,
        }, hdrs)
        if r:
            print(f"  {email} -> {role} (org={org_id})")
        else:
            print(f"  Failed: {email} -> {role}")


# ── 11. Create assignments ────────────────────────────────────
def create_assignments():
    step("11. Create assignments")
    org_id = state["org_id"]
    project_id = state["project_id"]
    if not project_id:
        print("  Skipping: no project")
        return

    hdrs = admin_headers(org_id)
    se = state["shared_elements"]
    root_entity_id = state["root_entity_id"]

    collector1_id = state["users"].get("collector1@greentech.com", {}).get("id")
    collector2_id = state["users"].get("collector2@greentech.com", {}).get("id")
    reviewer_id = state["users"].get("reviewer@greentech.com", {}).get("id")

    assignments = [
        ("SE-GHG-SCOPE1", collector1_id, reviewer_id),
        ("SE-GHG-SCOPE2", collector1_id, None),
        ("SE-ENERGY-TOTAL", collector2_id, None),
        ("SE-WATER-WITHDRAWAL", collector2_id, None),
    ]

    for se_code, coll_id, rev_id in assignments:
        se_id = se.get(se_code)
        if not se_id:
            print(f"  Skipping {se_code}: shared element not found")
            continue

        payload: dict = {
            "shared_element_id": se_id,
            "entity_id": root_entity_id,
        }
        if coll_id:
            payload["collector_id"] = coll_id
        if rev_id:
            payload["reviewer_id"] = rev_id

        r = post(f"/api/projects/{project_id}/assignments", payload, hdrs)
        if r:
            print(f"  {se_code} -> collector={coll_id}, reviewer={rev_id} (id={r['id']})")
        else:
            print(f"  Failed: {se_code}")


# ── 12. Create data points ────────────────────────────────────
def create_data_points():
    step("12. Create data points")
    org_id = state["org_id"]
    project_id = state["project_id"]
    if not project_id:
        print("  Skipping: no project")
        return

    se = state["shared_elements"]
    root_entity_id = state["root_entity_id"]

    # Use collector tokens for creating data points
    collector1_token = state["users"].get("collector1@greentech.com", {}).get("token")
    collector2_token = state["users"].get("collector2@greentech.com", {}).get("token")

    data_points = [
        ("SE-GHG-SCOPE1", 12500, "tCO2e", collector1_token),
        ("SE-GHG-SCOPE2", 8200, "tCO2e", collector1_token),
        ("SE-ENERGY-TOTAL", 45000, "MWh", collector2_token),
        ("SE-WATER-WITHDRAWAL", 125000, "m3", collector2_token),
    ]

    # Use admin token since collectors might not have org role yet
    hdrs_admin = admin_headers(org_id)

    for se_code, value, unit, _token in data_points:
        se_id = se.get(se_code)
        if not se_id:
            print(f"  Skipping {se_code}: shared element not found")
            continue

        r = post(f"/api/projects/{project_id}/data-points", {
            "shared_element_id": se_id,
            "entity_id": root_entity_id,
            "numeric_value": value,
            "unit_code": unit,
        }, hdrs_admin)
        if r:
            print(f"  {se_code}: {value} {unit} (id={r['id']}, status={r.get('status', 'n/a')})")
        else:
            print(f"  Failed: {se_code}")


# ── Summary ───────────────────────────────────────────────────
def print_summary():
    step("SUMMARY")
    print()
    print("  Credentials (all passwords: Test1234)")
    print("  " + "-" * 56)
    print(f"  {'Email':<30} {'Role':<15} {'User ID'}")
    print("  " + "-" * 56)
    creds = [
        ("admin@esgvist.com", "platform_admin"),
        ("framework@esgvist.com", "framework_admin"),
        ("manager@greentech.com", "esg_manager"),
        ("collector1@greentech.com", "collector"),
        ("collector2@greentech.com", "collector"),
        ("reviewer@greentech.com", "reviewer"),
        ("auditor@greentech.com", "auditor"),
    ]
    for email, role in creds:
        uid = state["users"].get(email, {}).get("id", "?")
        print(f"  {email:<30} {role:<15} {uid}")
    print("  " + "-" * 56)
    print()
    print(f"  Organization ID:  {state['org_id']}")
    print(f"  Root Entity ID:   {state['root_entity_id']}")
    print(f"  Boundary ID:      {state['boundary_id']}")
    print(f"  Project ID:       {state['project_id']}")
    print()
    print("  Entities:")
    for name, eid in state["entities"].items():
        print(f"    {name}: {eid}")
    print()
    print("  Standards:")
    for code, sid in state["standards"].items():
        print(f"    {code}: {sid}")
    print()
    print("  Shared Elements:")
    for code, sid in state["shared_elements"].items():
        print(f"    {code}: {sid}")
    print()
    print("  Done!")


def main():
    print("ESGvist Database Seed Script")
    print(f"Target: {BASE}")
    print()

    ensure_demo_self_registration()
    register_users()
    assign_platform_roles()
    setup_organization()
    create_entities()
    create_ownership_links()
    assign_org_roles()
    create_standards()
    create_disclosures()
    create_requirement_items()
    create_shared_elements()
    create_mappings()
    create_project()
    apply_boundary()
    create_assignments()
    create_data_points()
    print_summary()


if __name__ == "__main__":
    main()
