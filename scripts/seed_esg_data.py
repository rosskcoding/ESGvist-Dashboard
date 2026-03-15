#!/usr/bin/env python3
"""
Seed ESG data for ESGvist Dashboard.
Creates metrics, dimensions, and facts for KazEnergo JSC.
"""

import json
import urllib.request
from datetime import datetime

API = "http://localhost:8000/api/v1"


def api(method, path, data=None, token=None):
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API}{path}", data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ERROR {e.code}: {path} → {err[:200]}")
        return None


def login(email, password):
    result = api("POST", "/auth/login", {"email": email, "password": password})
    if result:
        print(f"  Logged in as {email}")
        return result["access_token"]
    return None


def main():
    print("=== ESGvist Data Seeding ===\n")

    # Login as superuser
    token = login("e2e-test@example.com", "TestPassword123!")
    if not token:
        print("FATAL: Cannot login")
        return

    # Get KazEnergo company
    companies = api("GET", "/companies", token=token)
    kazenergo = next((c for c in companies if "kazenergo" in c["slug"].lower()), None)
    if not kazenergo:
        print("FATAL: KazEnergo not found")
        return
    cid = kazenergo["company_id"]
    print(f"  Company: {kazenergo['name']} ({cid})\n")

    # === ENTITIES ===
    print("Creating entities...")
    entities = [
        {"name": "KazEnergo Head Office", "code": "HQ", "description": "Corporate headquarters in Astana"},
        {"name": "Ekibastuz Power Plant", "code": "EPP", "description": "Coal-fired power plant, 4000 MW capacity"},
        {"name": "Almaty Distribution", "code": "ALM-DIST", "description": "Electricity distribution network"},
        {"name": "Karaganda Wind Farm", "code": "KRG-WIND", "description": "Renewable wind energy facility, 150 MW"},
    ]
    entity_ids = []
    for e in entities:
        result = api("POST", f"/esg/entities?company_id={cid}", e, token=token)
        if result:
            entity_ids.append(result["entity_id"])
            print(f"  + Entity: {e['name']}")

    # === LOCATIONS ===
    print("\nCreating locations...")
    locations = [
        {"name": "Astana", "code": "AST", "country": "KZ", "region": "Akmola"},
        {"name": "Ekibastuz", "code": "EKB", "country": "KZ", "region": "Pavlodar"},
        {"name": "Almaty", "code": "ALA", "country": "KZ", "region": "Almaty"},
        {"name": "Karaganda", "code": "KRG", "country": "KZ", "region": "Karaganda"},
    ]
    location_ids = []
    for loc in locations:
        result = api("POST", f"/esg/locations?company_id={cid}", loc, token=token)
        if result:
            location_ids.append(result["location_id"])
            print(f"  + Location: {loc['name']}")

    # === SEGMENTS ===
    print("\nCreating segments...")
    segments = [
        {"name": "Power Generation", "code": "GEN"},
        {"name": "Distribution", "code": "DIST"},
        {"name": "Renewables", "code": "REN"},
        {"name": "Corporate", "code": "CORP"},
    ]
    segment_ids = []
    for seg in segments:
        result = api("POST", f"/esg/segments?company_id={cid}", seg, token=token)
        if result:
            segment_ids.append(result["segment_id"])
            print(f"  + Segment: {seg['name']}")

    # Fetch existing entity/location IDs (paginated responses have "items" key)
    existing_entities = (api("GET", f"/esg/entities?company_id={cid}&page_size=100", token=token) or {}).get("items", [])
    if existing_entities:
        entity_ids = [e["entity_id"] for e in existing_entities]
        print(f"  (found {len(entity_ids)} existing entities)")
    existing_locations = (api("GET", f"/esg/locations?company_id={cid}&page_size=100", token=token) or {}).get("items", [])
    if existing_locations:
        location_ids = [loc["location_id"] for loc in existing_locations]
        print(f"  (found {len(location_ids)} existing locations)")
    existing_segments = (api("GET", f"/esg/segments?company_id={cid}&page_size=100", token=token) or {}).get("items", [])
    if existing_segments:
        segment_ids = [s["segment_id"] for s in existing_segments]
        print(f"  (found {len(segment_ids)} existing segments)")

    # === METRICS ===
    print("\nCreating metrics...")
    metrics_data = [
        # Environmental
        {"code": "GHG-SCOPE1", "name": "GHG Emissions - Scope 1", "description": "Direct greenhouse gas emissions from owned sources", "value_type": "number", "unit": "tCO2e", "category": "E"},
        {"code": "GHG-SCOPE2", "name": "GHG Emissions - Scope 2", "description": "Indirect emissions from purchased electricity", "value_type": "number", "unit": "tCO2e", "category": "E"},
        {"code": "GHG-SCOPE3", "name": "GHG Emissions - Scope 3", "description": "Other indirect emissions in value chain", "value_type": "number", "unit": "tCO2e", "category": "E"},
        {"code": "ENERGY-TOTAL", "name": "Total Energy Consumption", "description": "Total energy consumed across all operations", "value_type": "number", "unit": "MWh", "category": "E"},
        {"code": "ENERGY-RENEW", "name": "Renewable Energy Share", "description": "Percentage of energy from renewable sources", "value_type": "number", "unit": "%", "category": "E"},
        {"code": "WATER-WITHDRAWAL", "name": "Water Withdrawal", "description": "Total water withdrawn from all sources", "value_type": "number", "unit": "m³", "category": "E"},
        {"code": "WATER-RECYCLED", "name": "Water Recycled", "description": "Volume of water recycled and reused", "value_type": "number", "unit": "m³", "category": "E"},
        {"code": "WASTE-TOTAL", "name": "Total Waste Generated", "description": "Total waste generated across operations", "value_type": "number", "unit": "tonnes", "category": "E"},
        {"code": "WASTE-RECYCLED", "name": "Waste Recycled Rate", "description": "Percentage of waste diverted from disposal", "value_type": "number", "unit": "%", "category": "E"},
        {"code": "EMISSIONS-NOX", "name": "NOx Emissions", "description": "Nitrogen oxide emissions from combustion", "value_type": "number", "unit": "tonnes", "category": "E"},
        {"code": "EMISSIONS-SO2", "name": "SO2 Emissions", "description": "Sulfur dioxide emissions", "value_type": "number", "unit": "tonnes", "category": "E"},
        {"code": "LAND-REHABILITATED", "name": "Land Rehabilitated", "description": "Area of disturbed land rehabilitated", "value_type": "number", "unit": "hectares", "category": "E"},

        # Social
        {"code": "EMPLOYEES-TOTAL", "name": "Total Employees", "description": "Total number of employees at year end", "value_type": "integer", "unit": "people", "category": "S"},
        {"code": "EMPLOYEES-FEMALE", "name": "Female Employees", "description": "Percentage of female employees", "value_type": "number", "unit": "%", "category": "S"},
        {"code": "MGMT-FEMALE", "name": "Women in Management", "description": "Percentage of women in management positions", "value_type": "number", "unit": "%", "category": "S"},
        {"code": "TURNOVER", "name": "Employee Turnover Rate", "description": "Annual voluntary and involuntary turnover rate", "value_type": "number", "unit": "%", "category": "S"},
        {"code": "TRAINING-HOURS", "name": "Training Hours per Employee", "description": "Average training hours per employee per year", "value_type": "number", "unit": "hours", "category": "S"},
        {"code": "SAFETY-LTIR", "name": "Lost Time Injury Rate (LTIR)", "description": "Number of lost time injuries per million hours worked", "value_type": "number", "unit": "per 1M hours", "category": "S"},
        {"code": "SAFETY-FATALITIES", "name": "Workplace Fatalities", "description": "Number of work-related fatalities", "value_type": "integer", "unit": "cases", "category": "S"},
        {"code": "COMMUNITY-INVEST", "name": "Community Investment", "description": "Total community investment spending", "value_type": "number", "unit": "USD", "category": "S"},
        {"code": "LOCAL-HIRING", "name": "Local Hiring Rate", "description": "Percentage of employees hired from local communities", "value_type": "number", "unit": "%", "category": "S"},

        # Governance
        {"code": "BOARD-SIZE", "name": "Board Size", "description": "Total number of board members", "value_type": "integer", "unit": "people", "category": "G"},
        {"code": "BOARD-INDEPENDENT", "name": "Independent Directors", "description": "Percentage of independent board members", "value_type": "number", "unit": "%", "category": "G"},
        {"code": "BOARD-FEMALE", "name": "Board Gender Diversity", "description": "Percentage of female board members", "value_type": "number", "unit": "%", "category": "G"},
        {"code": "ETHICS-VIOLATIONS", "name": "Ethics Violations", "description": "Number of confirmed ethics code violations", "value_type": "integer", "unit": "cases", "category": "G"},
        {"code": "ANTI-CORRUPTION", "name": "Anti-Corruption Training", "description": "Percentage of employees completed anti-corruption training", "value_type": "number", "unit": "%", "category": "G"},
        {"code": "CYBER-INCIDENTS", "name": "Cybersecurity Incidents", "description": "Number of material cybersecurity incidents", "value_type": "integer", "unit": "cases", "category": "G"},
        {"code": "TAX-PAID", "name": "Total Tax Paid", "description": "Total taxes paid to governments", "value_type": "number", "unit": "USD", "category": "G"},
    ]

    metric_ids = {}
    # First fetch existing metrics
    existing_metrics = (api("GET", f"/esg/metrics?company_id={cid}&page_size=100", token=token) or {}).get("items", [])
    for em in existing_metrics:
        if em.get("code"):
            metric_ids[em["code"]] = em["metric_id"]
    if metric_ids:
        print(f"  (found {len(metric_ids)} existing metrics)")

    for m in metrics_data:
        cat = m.pop("category")
        if m["code"] in metric_ids:
            continue  # already exists
        result = api("POST", f"/esg/metrics?company_id={cid}", m, token=token)
        if result:
            metric_ids[m["code"]] = result["metric_id"]
            print(f"  + [{cat}] {m['name']}")

    # === FACTS (2024 data) ===
    print("\nCreating facts for 2024...")
    facts_2024 = [
        # Environmental
        ("GHG-SCOPE1", 2_450_000, "2024-01-01", "2024-12-31"),
        ("GHG-SCOPE2", 890_000, "2024-01-01", "2024-12-31"),
        ("GHG-SCOPE3", 1_200_000, "2024-01-01", "2024-12-31"),
        ("ENERGY-TOTAL", 18_500_000, "2024-01-01", "2024-12-31"),
        ("ENERGY-RENEW", 8.2, "2024-01-01", "2024-12-31"),
        ("WATER-WITHDRAWAL", 12_500_000, "2024-01-01", "2024-12-31"),
        ("WATER-RECYCLED", 3_750_000, "2024-01-01", "2024-12-31"),
        ("WASTE-TOTAL", 145_000, "2024-01-01", "2024-12-31"),
        ("WASTE-RECYCLED", 32.5, "2024-01-01", "2024-12-31"),
        ("EMISSIONS-NOX", 8_900, "2024-01-01", "2024-12-31"),
        ("EMISSIONS-SO2", 12_300, "2024-01-01", "2024-12-31"),
        ("LAND-REHABILITATED", 45, "2024-01-01", "2024-12-31"),

        # Social
        ("EMPLOYEES-TOTAL", 12_450, "2024-01-01", "2024-12-31"),
        ("EMPLOYEES-FEMALE", 28.3, "2024-01-01", "2024-12-31"),
        ("MGMT-FEMALE", 19.5, "2024-01-01", "2024-12-31"),
        ("TURNOVER", 11.2, "2024-01-01", "2024-12-31"),
        ("TRAINING-HOURS", 42, "2024-01-01", "2024-12-31"),
        ("SAFETY-LTIR", 1.8, "2024-01-01", "2024-12-31"),
        ("SAFETY-FATALITIES", 0, "2024-01-01", "2024-12-31"),
        ("COMMUNITY-INVEST", 2_800_000, "2024-01-01", "2024-12-31"),
        ("LOCAL-HIRING", 87.5, "2024-01-01", "2024-12-31"),

        # Governance
        ("BOARD-SIZE", 9, "2024-01-01", "2024-12-31"),
        ("BOARD-INDEPENDENT", 44.4, "2024-01-01", "2024-12-31"),
        ("BOARD-FEMALE", 22.2, "2024-01-01", "2024-12-31"),
        ("ETHICS-VIOLATIONS", 3, "2024-01-01", "2024-12-31"),
        ("ANTI-CORRUPTION", 94.5, "2024-01-01", "2024-12-31"),
        ("CYBER-INCIDENTS", 1, "2024-01-01", "2024-12-31"),
        ("TAX-PAID", 156_000_000, "2024-01-01", "2024-12-31"),
    ]

    fact_count = 0
    for code, value, start, end in facts_2024:
        mid = metric_ids.get(code)
        if not mid:
            continue
        fact = {
            "metric_id": mid,
            "value_json": value,
            "period_type": "year",
            "period_start": start,
            "period_end": end,
            "source_note": "KazEnergo 2024 Annual ESG Report",
        }
        # Add entity/location if available
        if entity_ids:
            fact["entity_id"] = entity_ids[0]  # HQ
        if location_ids:
            fact["location_id"] = location_ids[0]  # Astana

        result = api("POST", f"/esg/facts?company_id={cid}", fact, token=token)
        if result:
            fact_count += 1

    print(f"  Created {fact_count} facts for 2024")

    # === FACTS (2023 data for comparison) ===
    print("\nCreating facts for 2023...")
    facts_2023 = [
        ("GHG-SCOPE1", 2_680_000, "2023-01-01", "2023-12-31"),
        ("GHG-SCOPE2", 950_000, "2023-01-01", "2023-12-31"),
        ("ENERGY-TOTAL", 19_200_000, "2023-01-01", "2023-12-31"),
        ("ENERGY-RENEW", 5.1, "2023-01-01", "2023-12-31"),
        ("WATER-WITHDRAWAL", 13_100_000, "2023-01-01", "2023-12-31"),
        ("WASTE-TOTAL", 158_000, "2023-01-01", "2023-12-31"),
        ("EMPLOYEES-TOTAL", 11_800, "2023-01-01", "2023-12-31"),
        ("EMPLOYEES-FEMALE", 26.1, "2023-01-01", "2023-12-31"),
        ("SAFETY-LTIR", 2.3, "2023-01-01", "2023-12-31"),
        ("SAFETY-FATALITIES", 1, "2023-01-01", "2023-12-31"),
        ("TRAINING-HOURS", 36, "2023-01-01", "2023-12-31"),
        ("BOARD-INDEPENDENT", 33.3, "2023-01-01", "2023-12-31"),
        ("ANTI-CORRUPTION", 88.0, "2023-01-01", "2023-12-31"),
        ("TAX-PAID", 142_000_000, "2023-01-01", "2023-12-31"),
    ]

    fact_count_2023 = 0
    for code, value, start, end in facts_2023:
        mid = metric_ids.get(code)
        if not mid:
            continue
        fact = {
            "metric_id": mid,
            "value_json": value,
            "period_type": "year",
            "period_start": start,
            "period_end": end,
            "source_note": "KazEnergo 2023 Annual ESG Report",
        }
        result = api("POST", f"/esg/facts?company_id={cid}", fact, token=token)
        if result:
            fact_count_2023 += 1

    print(f"  Created {fact_count_2023} facts for 2023")

    # === Summary ===
    print(f"\n{'='*40}")
    print(f"SEED COMPLETE:")
    print(f"  Entities:  {len(entity_ids)}")
    print(f"  Locations: {len(location_ids)}")
    print(f"  Segments:  {len(segment_ids)}")
    print(f"  Metrics:   {len(metric_ids)}")
    print(f"  Facts:     {fact_count + fact_count_2023} (2024: {fact_count}, 2023: {fact_count_2023})")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
