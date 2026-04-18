import asyncio
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.catalog import prepare_shared_element_defaults
from app.core.schema_runtime import stamp_database_async
from app.core.security import hash_password
from app.db.models import Base
from app.db.models.boundary import BoundaryDefinition, BoundaryMembership
from app.db.models.boundary_snapshot import BoundarySnapshot
from app.db.models.company_entity import CompanyEntity, ControlLink, OwnershipLink
from app.db.models.invitation import UserInvitation
from app.db.models.organization import Organization
from app.db.models.project import MetricAssignment, ReportingProject, ReportingProjectStandard
from app.db.models.requirement_item import RequirementItem
from app.db.models.role_binding import RoleBinding
from app.db.models.shared_element import SharedElement
from app.db.models.standard import DisclosureRequirement, Standard, StandardSection
from app.db.models.unit_reference import BoundaryApproach, Methodology, UnitReference
from app.db.models.user import User

ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "demo"
STATE_PATH = ARTIFACTS_DIR / "demo-state.json"
CREDENTIALS_PATH = ARTIFACTS_DIR / "credentials.md"
SCENARIOS_PATH = ARTIFACTS_DIR / "scenarios.md"


@dataclass(frozen=True)
class DemoUserSpec:
    key: str
    email: str
    full_name: str
    org_role: str | None = None
    platform_admin: bool = False
    framework_admin: bool = False


PASSWORD = os.getenv("DEMO_PASSWORD", "Test1234")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/esgdashboard_demo_20260323",
)
BASE_URL = os.getenv("DEMO_BASE_URL", "http://localhost:3002")
API_URL = os.getenv("DEMO_API_URL", "http://localhost:8002/api")

USER_SPECS = [
    DemoUserSpec(
        key="admin",
        email="admin@esgvist.com",
        full_name="Ross Admin",
        org_role="admin",
        platform_admin=True,
    ),
    DemoUserSpec(
        key="framework_admin",
        email="framework@esgvist.com",
        full_name="Iris Framework",
        framework_admin=True,
    ),
    DemoUserSpec(
        key="esg_manager",
        email="manager@greentech.com",
        full_name="Anna Manager",
        org_role="esg_manager",
    ),
    DemoUserSpec(
        key="reviewer",
        email="reviewer@greentech.com",
        full_name="Dmitry Reviewer",
        org_role="reviewer",
    ),
    DemoUserSpec(
        key="auditor",
        email="auditor@greentech.com",
        full_name="Elena Auditor",
        org_role="auditor",
    ),
    DemoUserSpec(
        key="collector_energy",
        email="collector1@greentech.com",
        full_name="Ivan Collector",
        org_role="collector",
    ),
    DemoUserSpec(
        key="collector_climate",
        email="collector2@greentech.com",
        full_name="Maria Data",
        org_role="collector",
    ),
]


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


async def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
        else:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await stamp_database_async(DATABASE_URL)

    async with session_factory() as session:
        users: dict[str, User] = {}
        for spec in USER_SPECS:
            user = User(
                email=spec.email,
                full_name=spec.full_name,
                password_hash=hash_password(PASSWORD),
                is_active=True,
                notification_prefs={
                    "email": True,
                    "in_app": True,
                    "email_info_level": False,
                },
            )
            session.add(user)
            await session.flush()
            users[spec.key] = user

        org = Organization(
            name="Northwind Renewables Group",
            legal_name="Northwind Renewables Group plc",
            country="GB",
            jurisdiction="UK",
            industry="Renewable Energy & Grid Services",
            default_currency="GBP",
            default_reporting_year=2025,
            allow_password_login=True,
            allow_sso_login=True,
            enforce_sso=False,
            setup_completed=True,
            status="active",
        )
        session.add(org)
        await session.flush()

        for spec in USER_SPECS:
            if spec.platform_admin:
                session.add(
                    RoleBinding(
                        user_id=users[spec.key].id,
                        role="platform_admin",
                        scope_type="platform",
                        scope_id=None,
                        created_by=users[spec.key].id,
                    )
                )
            if spec.framework_admin:
                session.add(
                    RoleBinding(
                        user_id=users[spec.key].id,
                        role="framework_admin",
                        scope_type="platform",
                        scope_id=None,
                        created_by=users["admin"].id,
                    )
                )
            if spec.org_role:
                session.add(
                    RoleBinding(
                        user_id=users[spec.key].id,
                        role=spec.org_role,
                        scope_type="organization",
                        scope_id=org.id,
                        created_by=users["admin"].id,
                    )
                )
        await session.flush()

        root = CompanyEntity(
            organization_id=org.id,
            name="Northwind Renewables Group plc",
            code="NW-ROOT",
            entity_type="parent_company",
            country="GB",
            jurisdiction="UK",
            status="active",
        )
        session.add(root)
        await session.flush()

        generation = CompanyEntity(
            organization_id=org.id,
            parent_entity_id=root.id,
            name="Northwind Generation Ltd",
            code="NW-GEN",
            entity_type="legal_entity",
            country="GB",
            jurisdiction="UK",
            status="active",
        )
        grid = CompanyEntity(
            organization_id=org.id,
            parent_entity_id=root.id,
            name="Northwind Grid Services GmbH",
            code="NW-GRID",
            entity_type="legal_entity",
            country="DE",
            jurisdiction="DE",
            status="active",
        )
        session.add_all([generation, grid])
        await session.flush()

        iberia = CompanyEntity(
            organization_id=org.id,
            parent_entity_id=generation.id,
            name="Northwind Solar Iberia Branch",
            code="NW-IB",
            entity_type="branch",
            country="ES",
            jurisdiction="ES",
            status="active",
        )
        hamburg = CompanyEntity(
            organization_id=org.id,
            parent_entity_id=grid.id,
            name="Hamburg Wind Farm",
            code="NW-HAM-WF",
            entity_type="facility",
            country="DE",
            jurisdiction="DE",
            status="active",
        )
        leeds = CompanyEntity(
            organization_id=org.id,
            parent_entity_id=generation.id,
            name="Leeds Service Operations",
            code="NW-LEEDS",
            entity_type="business_unit",
            country="GB",
            jurisdiction="UK",
            status="active",
        )
        baltic_jv = CompanyEntity(
            organization_id=org.id,
            parent_entity_id=root.id,
            name="Baltic Storage JV",
            code="NW-BALTIC-JV",
            entity_type="joint_venture",
            country="PL",
            jurisdiction="PL",
            status="active",
        )
        session.add_all([iberia, hamburg, leeds, baltic_jv])
        await session.flush()

        session.add_all(
            [
                OwnershipLink(
                    parent_entity_id=root.id,
                    child_entity_id=generation.id,
                    ownership_percent=100,
                    ownership_type="direct",
                    comment="Wholly owned UK generation entity",
                ),
                OwnershipLink(
                    parent_entity_id=root.id,
                    child_entity_id=grid.id,
                    ownership_percent=100,
                    ownership_type="direct",
                    comment="Wholly owned EU grid services entity",
                ),
                OwnershipLink(
                    parent_entity_id=generation.id,
                    child_entity_id=iberia.id,
                    ownership_percent=100,
                    ownership_type="direct",
                    comment="Spanish branch for solar operations",
                ),
                OwnershipLink(
                    parent_entity_id=grid.id,
                    child_entity_id=hamburg.id,
                    ownership_percent=100,
                    ownership_type="direct",
                    comment="Primary onshore wind facility",
                ),
                OwnershipLink(
                    parent_entity_id=generation.id,
                    child_entity_id=leeds.id,
                    ownership_percent=100,
                    ownership_type="direct",
                    comment="Shared services business unit",
                ),
                OwnershipLink(
                    parent_entity_id=root.id,
                    child_entity_id=baltic_jv.id,
                    ownership_percent=49,
                    ownership_type="beneficial",
                    comment="JV excluded from default reporting boundary",
                ),
            ]
        )
        session.add_all(
            [
                ControlLink(
                    controlling_entity_id=root.id,
                    controlled_entity_id=generation.id,
                    control_type="financial_control",
                    is_controlled=True,
                    rationale="Group financial consolidation",
                ),
                ControlLink(
                    controlling_entity_id=root.id,
                    controlled_entity_id=grid.id,
                    control_type="operational_control",
                    is_controlled=True,
                    rationale="Centralized operating model",
                ),
                ControlLink(
                    controlling_entity_id=grid.id,
                    controlled_entity_id=hamburg.id,
                    control_type="management_control",
                    is_controlled=True,
                    rationale="Facility management reporting line",
                ),
            ]
        )
        await session.flush()

        default_boundary = BoundaryDefinition(
            organization_id=org.id,
            name="Financial Reporting Default",
            boundary_type="financial_reporting_default",
            description="Auto-generated financial reporting boundary",
            is_default=True,
        )
        sustainability_boundary = BoundaryDefinition(
            organization_id=org.id,
            name="FY2025 Sustainability Boundary",
            boundary_type="operational_control",
            description="Operational-control boundary for FY2025 ESG reporting",
            is_default=False,
        )
        session.add_all([default_boundary, sustainability_boundary])
        await session.flush()

        session.add_all(
            [
                BoundaryMembership(
                    boundary_definition_id=default_boundary.id,
                    entity_id=root.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Root entity",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=root.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Consolidated parent",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=generation.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Full control",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=grid.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Full control",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=iberia.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Branch in scope",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=hamburg.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Material operational facility",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=leeds.id,
                    included=True,
                    inclusion_source="automatic",
                    consolidation_method="full",
                    inclusion_reason="Corporate services in scope",
                ),
                BoundaryMembership(
                    boundary_definition_id=sustainability_boundary.id,
                    entity_id=baltic_jv.id,
                    included=False,
                    inclusion_source="manual",
                    consolidation_method="equity_share",
                    inclusion_reason="JV excluded from operational control boundary",
                ),
            ]
        )
        await session.flush()

        session.add_all(
            [
                UnitReference(code="MWH", name="Megawatt hour", category="energy"),
                UnitReference(code="TCO2E", name="Tonnes CO2e", category="emissions"),
                UnitReference(code="COUNT", name="Count", category="generic"),
                Methodology(
                    code="UTILITY_BILL_RECON",
                    name="Utility bill reconciliation",
                    description="Monthly utility invoices reconciled against finance ledger",
                ),
                Methodology(
                    code="GHG_PROTOCOL_STATIONARY",
                    name="GHG Protocol stationary combustion",
                    description="GHG Protocol stationary combustion factors with meter data",
                ),
                Methodology(
                    code="QUALITATIVE_DISCLOSURE_REVIEW",
                    name="Qualitative disclosure review",
                    description="Narrative disclosure drafted and signed off by ESG management",
                ),
                BoundaryApproach(
                    code="OP_CONTROL",
                    name="Operational control",
                    description="Entities controlled operationally are included",
                ),
            ]
        )
        await session.flush()

        gri = Standard(code="GRI", name="Global Reporting Initiative", version="2021", jurisdiction="Global")
        ifrs_s1 = Standard(code="IFRS-S1", name="IFRS S1 General Requirements", version="2024", jurisdiction="Global")
        ifrs_s2 = Standard(code="IFRS-S2", name="IFRS S2 Climate-related Disclosures", version="2024", jurisdiction="Global")
        esrs = Standard(code="ESRS", name="European Sustainability Reporting Standards", version="2024", jurisdiction="EU")
        session.add_all([gri, ifrs_s1, ifrs_s2, esrs])
        await session.flush()

        gri_env = StandardSection(standard_id=gri.id, code="300", title="Environmental", sort_order=10)
        ifrs_s1_gov = StandardSection(standard_id=ifrs_s1.id, code="GOV", title="Governance", sort_order=10)
        ifrs_s2_metrics = StandardSection(standard_id=ifrs_s2.id, code="MET", title="Metrics and Targets", sort_order=10)
        esrs_e1 = StandardSection(standard_id=esrs.id, code="E1", title="Climate Change", sort_order=10)
        session.add_all([gri_env, ifrs_s1_gov, ifrs_s2_metrics, esrs_e1])
        await session.flush()
        gri_energy_sec = StandardSection(
            standard_id=gri.id,
            parent_section_id=gri_env.id,
            code="302",
            title="Energy",
            sort_order=20,
        )
        gri_emissions_sec = StandardSection(
            standard_id=gri.id,
            parent_section_id=gri_env.id,
            code="305",
            title="Emissions",
            sort_order=30,
        )
        session.add_all([gri_energy_sec, gri_emissions_sec])
        await session.flush()

        gri_302_1 = DisclosureRequirement(
            standard_id=gri.id,
            section_id=gri_energy_sec.id,
            code="GRI 302-1",
            title="Energy consumption within the organization",
            description="Total energy consumption by source",
            requirement_type="quantitative",
            mandatory_level="mandatory",
            sort_order=10,
        )
        gri_305_1 = DisclosureRequirement(
            standard_id=gri.id,
            section_id=gri_emissions_sec.id,
            code="GRI 305-1",
            title="Direct (Scope 1) GHG emissions",
            description="Gross direct greenhouse gas emissions",
            requirement_type="quantitative",
            mandatory_level="mandatory",
            sort_order=20,
        )
        ifrs_s1_gov_1 = DisclosureRequirement(
            standard_id=ifrs_s1.id,
            section_id=ifrs_s1_gov.id,
            code="IFRS S1 GOV-1",
            title="Governance oversight of sustainability risks and opportunities",
            description="Narrative governance disclosure",
            requirement_type="qualitative",
            mandatory_level="mandatory",
            sort_order=10,
        )
        ifrs_s2_ghg = DisclosureRequirement(
            standard_id=ifrs_s2.id,
            section_id=ifrs_s2_metrics.id,
            code="IFRS S2 MET-4",
            title="Greenhouse gas emissions metrics",
            description="Scope 1 and Scope 2 climate metrics",
            requirement_type="mixed",
            mandatory_level="mandatory",
            sort_order=10,
        )
        esrs_e1_6 = DisclosureRequirement(
            standard_id=esrs.id,
            section_id=esrs_e1.id,
            code="ESRS E1-6",
            title="Gross Scope 1, 2 and 3 GHG emissions",
            description="Climate metrics under ESRS E1",
            requirement_type="quantitative",
            mandatory_level="mandatory",
            sort_order=10,
        )
        session.add_all([gri_302_1, gri_305_1, ifrs_s1_gov_1, ifrs_s2_ghg, esrs_e1_6])
        await session.flush()

        energy_total_item = RequirementItem(
            disclosure_requirement_id=gri_302_1.id,
            item_code="ENERGY_TOTAL_MWH",
            name="Total energy consumption",
            description="Total purchased and self-generated energy for the reporting period",
            item_type="metric",
            value_type="number",
            unit_code="MWH",
            is_required=True,
            requires_evidence=True,
            sort_order=10,
        )
        scope1_gri_item = RequirementItem(
            disclosure_requirement_id=gri_305_1.id,
            item_code="SCOPE1_TCO2E",
            name="Gross Scope 1 emissions",
            description="Direct GHG emissions from controlled sources",
            item_type="metric",
            value_type="number",
            unit_code="TCO2E",
            is_required=True,
            requires_evidence=True,
            sort_order=10,
        )
        gov_narrative_item = RequirementItem(
            disclosure_requirement_id=ifrs_s1_gov_1.id,
            item_code="SUSTAINABILITY_GOVERNANCE_NARRATIVE",
            name="Governance oversight narrative",
            description="Describe board and management oversight",
            item_type="narrative",
            value_type="text",
            is_required=True,
            requires_evidence=False,
            sort_order=10,
        )
        scope1_ifrs_item = RequirementItem(
            disclosure_requirement_id=ifrs_s2_ghg.id,
            item_code="SCOPE1_TCO2E",
            name="Scope 1 greenhouse gas emissions",
            description="IFRS S2 Scope 1 metric",
            item_type="metric",
            value_type="number",
            unit_code="TCO2E",
            is_required=True,
            requires_evidence=True,
            sort_order=10,
        )
        scope2_ifrs_item = RequirementItem(
            disclosure_requirement_id=ifrs_s2_ghg.id,
            item_code="SCOPE2_TCO2E",
            name="Scope 2 greenhouse gas emissions",
            description="IFRS S2 Scope 2 metric",
            item_type="metric",
            value_type="number",
            unit_code="TCO2E",
            is_required=True,
            requires_evidence=True,
            sort_order=20,
        )
        scope1_esrs_item = RequirementItem(
            disclosure_requirement_id=esrs_e1_6.id,
            item_code="SCOPE1_TCO2E",
            name="Gross Scope 1 emissions",
            description="ESRS E1 scope 1 emissions",
            item_type="metric",
            value_type="number",
            unit_code="TCO2E",
            is_required=True,
            requires_evidence=True,
            sort_order=10,
        )
        scope2_esrs_item = RequirementItem(
            disclosure_requirement_id=esrs_e1_6.id,
            item_code="SCOPE2_TCO2E",
            name="Gross Scope 2 emissions",
            description="ESRS E1 scope 2 emissions",
            item_type="metric",
            value_type="number",
            unit_code="TCO2E",
            is_required=True,
            requires_evidence=True,
            sort_order=20,
        )
        session.add_all(
            [
                energy_total_item,
                scope1_gri_item,
                gov_narrative_item,
                scope1_ifrs_item,
                scope2_ifrs_item,
                scope1_esrs_item,
                scope2_esrs_item,
            ]
        )
        await session.flush()

        energy_total = SharedElement(
            code="ENERGY_TOTAL_MWH",
            name="Total Energy Consumption",
            description="Total energy consumption in MWh",
            concept_domain="energy",
            default_value_type="number",
            default_unit_code="MWH",
            **prepare_shared_element_defaults(code="ENERGY_TOTAL_MWH"),
        )
        scope1 = SharedElement(
            code="SCOPE1_TCO2E",
            name="Scope 1 GHG Emissions",
            description="Gross scope 1 emissions in tonnes CO2e",
            concept_domain="emissions",
            default_value_type="number",
            default_unit_code="TCO2E",
            **prepare_shared_element_defaults(code="SCOPE1_TCO2E"),
        )
        scope2 = SharedElement(
            code="SCOPE2_TCO2E",
            name="Scope 2 GHG Emissions",
            description="Gross scope 2 emissions in tonnes CO2e",
            concept_domain="emissions",
            default_value_type="number",
            default_unit_code="TCO2E",
            **prepare_shared_element_defaults(code="SCOPE2_TCO2E"),
        )
        governance = SharedElement(
            code="SUSTAINABILITY_GOVERNANCE_NARRATIVE",
            name="Governance Oversight Narrative",
            description="Narrative on board and management oversight",
            concept_domain="governance",
            default_value_type="text",
            **prepare_shared_element_defaults(code="SUSTAINABILITY_GOVERNANCE_NARRATIVE"),
        )
        session.add_all([energy_total, scope1, scope2, governance])
        await session.flush()

        from app.db.models.mapping import RequirementItemSharedElement

        session.add_all(
            [
                RequirementItemSharedElement(
                    requirement_item_id=energy_total_item.id,
                    shared_element_id=energy_total.id,
                    mapping_type="full",
                ),
                RequirementItemSharedElement(
                    requirement_item_id=scope1_gri_item.id,
                    shared_element_id=scope1.id,
                    mapping_type="full",
                ),
                RequirementItemSharedElement(
                    requirement_item_id=gov_narrative_item.id,
                    shared_element_id=governance.id,
                    mapping_type="full",
                ),
                RequirementItemSharedElement(
                    requirement_item_id=scope1_ifrs_item.id,
                    shared_element_id=scope1.id,
                    mapping_type="full",
                ),
                RequirementItemSharedElement(
                    requirement_item_id=scope2_ifrs_item.id,
                    shared_element_id=scope2.id,
                    mapping_type="full",
                ),
                RequirementItemSharedElement(
                    requirement_item_id=scope1_esrs_item.id,
                    shared_element_id=scope1.id,
                    mapping_type="full",
                ),
                RequirementItemSharedElement(
                    requirement_item_id=scope2_esrs_item.id,
                    shared_element_id=scope2.id,
                    mapping_type="full",
                ),
            ]
        )
        await session.flush()

        project = ReportingProject(
            organization_id=org.id,
            name="FY2025 Sustainability Reporting",
            status="active",
            deadline=date(2026, 6, 30),
            reporting_year=2025,
            boundary_definition_id=sustainability_boundary.id,
        )
        session.add(project)
        await session.flush()

        session.add_all(
            [
                ReportingProjectStandard(reporting_project_id=project.id, standard_id=gri.id, is_base_standard=True),
                ReportingProjectStandard(reporting_project_id=project.id, standard_id=ifrs_s1.id, is_base_standard=False),
                ReportingProjectStandard(reporting_project_id=project.id, standard_id=ifrs_s2.id, is_base_standard=False),
                ReportingProjectStandard(reporting_project_id=project.id, standard_id=esrs.id, is_base_standard=False),
            ]
        )
        await session.flush()

        session.add(
            BoundarySnapshot(
                reporting_project_id=project.id,
                boundary_definition_id=sustainability_boundary.id,
                created_by=users["admin"].id,
                snapshot_data={
                    "boundary_name": sustainability_boundary.name,
                    "entity_ids": [root.id, generation.id, grid.id, iberia.id, hamburg.id, leeds.id],
                    "excluded_entity_ids": [baltic_jv.id],
                },
            )
        )
        await session.flush()

        session.add_all(
            [
                MetricAssignment(
                    reporting_project_id=project.id,
                    shared_element_id=energy_total.id,
                    entity_id=generation.id,
                    collector_id=users["collector_energy"].id,
                    reviewer_id=users["reviewer"].id,
                    backup_collector_id=users["esg_manager"].id,
                    deadline=date(2026, 4, 10),
                    escalation_after_days=3,
                    status="assigned",
                ),
                MetricAssignment(
                    reporting_project_id=project.id,
                    shared_element_id=scope1.id,
                    entity_id=grid.id,
                    facility_id=hamburg.id,
                    collector_id=users["collector_climate"].id,
                    reviewer_id=users["reviewer"].id,
                    backup_collector_id=users["esg_manager"].id,
                    deadline=date(2026, 4, 12),
                    escalation_after_days=2,
                    status="assigned",
                ),
                MetricAssignment(
                    reporting_project_id=project.id,
                    shared_element_id=scope2.id,
                    entity_id=grid.id,
                    collector_id=users["collector_climate"].id,
                    reviewer_id=users["reviewer"].id,
                    backup_collector_id=users["esg_manager"].id,
                    deadline=date(2026, 4, 15),
                    escalation_after_days=2,
                    status="assigned",
                ),
                MetricAssignment(
                    reporting_project_id=project.id,
                    shared_element_id=governance.id,
                    collector_id=users["esg_manager"].id,
                    reviewer_id=users["reviewer"].id,
                    deadline=date(2026, 4, 20),
                    escalation_after_days=5,
                    status="assigned",
                ),
            ]
        )
        await session.flush()

        pending_invitation = UserInvitation(
            organization_id=org.id,
            email="pending.facility@greentech.com",
            role="collector",
            invited_by=users["admin"].id,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        session.add(pending_invitation)
        await session.commit()

        state = {
            "base_url": BASE_URL,
            "api_url": API_URL,
            "password": PASSWORD,
            "organization": {
                "id": org.id,
                "name": org.name,
            },
            "project": {
                "id": project.id,
                "name": project.name,
                "reporting_year": project.reporting_year,
            },
            "boundaries": {
                "default": {"id": default_boundary.id, "name": default_boundary.name},
                "sustainability": {"id": sustainability_boundary.id, "name": sustainability_boundary.name},
            },
            "users": {
                spec.key: {
                    "id": users[spec.key].id,
                    "email": spec.email,
                    "full_name": spec.full_name,
                    "role": "platform_admin" if spec.platform_admin else spec.org_role,
                }
                for spec in USER_SPECS
            },
            "pending_invitation": {
                "email": pending_invitation.email,
                "role": pending_invitation.role,
                "token": pending_invitation.token,
            },
            "entities": {
                "root": {"id": root.id, "name": root.name},
                "generation": {"id": generation.id, "name": generation.name},
                "grid": {"id": grid.id, "name": grid.name},
                "iberia": {"id": iberia.id, "name": iberia.name},
                "hamburg": {"id": hamburg.id, "name": hamburg.name},
                "leeds": {"id": leeds.id, "name": leeds.name},
                "baltic_jv": {"id": baltic_jv.id, "name": baltic_jv.name},
            },
            "shared_elements": {
                "energy_total_mwh": {"id": energy_total.id, "code": energy_total.code},
                "scope1_tco2e": {"id": scope1.id, "code": scope1.code},
                "scope2_tco2e": {"id": scope2.id, "code": scope2.code},
                "governance_narrative": {"id": governance.id, "code": governance.code},
            },
            "standards": {
                "gri": {
                    "id": gri.id,
                    "code": gri.code,
                    "disclosures": {
                        "gri_302_1": {
                            "id": gri_302_1.id,
                            "items": {"energy_total_mwh": energy_total_item.id},
                        },
                        "gri_305_1": {
                            "id": gri_305_1.id,
                            "items": {"scope1_tco2e": scope1_gri_item.id},
                        },
                    },
                },
                "ifrs_s1": {
                    "id": ifrs_s1.id,
                    "code": ifrs_s1.code,
                    "disclosures": {
                        "gov_1": {"id": ifrs_s1_gov_1.id, "items": {"governance_narrative": gov_narrative_item.id}},
                    },
                },
                "ifrs_s2": {
                    "id": ifrs_s2.id,
                    "code": ifrs_s2.code,
                    "disclosures": {
                        "met_4": {
                            "id": ifrs_s2_ghg.id,
                            "items": {
                                "scope1_tco2e": scope1_ifrs_item.id,
                                "scope2_tco2e": scope2_ifrs_item.id,
                            },
                        },
                    },
                },
                "esrs": {
                    "id": esrs.id,
                    "code": esrs.code,
                    "disclosures": {
                        "e1_6": {
                            "id": esrs_e1_6.id,
                            "items": {
                                "scope1_tco2e": scope1_esrs_item.id,
                                "scope2_tco2e": scope2_esrs_item.id,
                            },
                        },
                    },
                },
            },
        }

    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    write_markdown(
        CREDENTIALS_PATH,
        [
            "# Demo Credentials",
            "",
            f"- Web URL: `{BASE_URL}`",
            f"- API URL: `{API_URL}`",
            f"- Shared password for all seeded accounts: `{PASSWORD}`",
            "",
            "| Role | Full Name | Email | Notes |",
            "| --- | --- | --- | --- |",
            "| platform_admin | Ross Admin | `admin@esgvist.com` | Full access plus tenant management for the demo org |",
            "| framework_admin | Iris Framework | `framework@esgvist.com` | Maintain ESG standards, shared elements, and mappings without tenant admin access |",
            "| esg_manager | Anna Manager | `manager@greentech.com` | Projects, assignments, boundary, dashboard |",
            "| collector | Ivan Collector | `collector1@greentech.com` | Input for GHG Scope 1 and Scope 2 data |",
            "| collector | Maria Data | `collector2@greentech.com` | Input for Energy and Water style operational data |",
            "| reviewer | Dmitry Reviewer | `reviewer@greentech.com` | Approve or reject data points |",
            "| auditor | Elena Auditor | `auditor@greentech.com` | Read-only access to audit log and snapshots |",
            "",
            "Manual verification:",
            "",
            f"1. Open `{BASE_URL}/login`.",
            "2. Sign in with any account above.",
            f"3. For the consolidated verification view, open `{BASE_URL}/demo` after login.",
        ],
    )
    write_markdown(
        SCENARIOS_PATH,
        [
            "# Demo Scenarios",
            "",
            "Seeded organization: `Northwind Renewables Group` with UK parent, UK/DE subsidiaries, ES branch, DE facility, UK business unit, and one excluded JV.",
            "",
            "Playwright scenarios are designed to cover:",
            "",
            "1. Admin creates a custom reporting standard/disclosure/item/mapping and assigns it to a collector.",
            "2. Energy collector submits a GRI 302-1 energy metric with evidence.",
            "3. Climate collector submits a shared Scope 1 metric reused across GRI 305-1, IFRS S2 and ESRS E1 plus a custom disclosure metric.",
            "4. ESG manager submits an IFRS S1 governance narrative.",
            "5. Reviewer approves quantitative submissions and requests revision on the governance narrative.",
            "6. Auditor verifies audit log and completeness state after the workflow run.",
            "",
            "Artifacts are written under `artifacts/demo/` and Playwright output is kept separate from the existing frontend test results.",
        ],
    )
    print(f"Wrote state to {STATE_PATH}")
    print(f"Wrote credentials to {CREDENTIALS_PATH}")
    print(f"Wrote scenarios to {SCENARIOS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
