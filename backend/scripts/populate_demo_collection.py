#!/usr/bin/env python3

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.dashboard_cache import invalidate_dashboard_project
from app.core.dependencies import RequestContext
from app.db.models.company_entity import CompanyEntity
from app.db.models.data_point import DataPoint
from app.db.models.project import MetricAssignment, ReportingProject
from app.db.models.shared_element import SharedElement
from app.db.models.user import User
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.form_config_repo import FormConfigRepository
from app.repositories.project_repo import ProjectRepository
from app.services.form_config_service import FormConfigService


DEFAULT_PROJECT_ID = 1


@dataclass(frozen=True)
class DataPointSpec:
    kind: Literal["numeric", "text"]
    value: float | str
    unit_code: str | None
    status: str
    created_by_email: str


@dataclass(frozen=True)
class DemoAssignmentSpec:
    shared_element_code: str
    entity_name: str
    facility_name: str | None
    collector_email: str
    reviewer_email: str
    backup_collector_email: str | None
    deadline: date
    assignment_status: str
    data_point: DataPointSpec | None = None


DEMO_ASSIGNMENTS: list[DemoAssignmentSpec] = [
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-305-1-2-3",
        entity_name="GreenTech Energy GmbH",
        facility_name=None,
        collector_email="collector1@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 15),
        assignment_status="completed",
        data_point=DataPointSpec(
            kind="text",
            value="12,450 tCO2e",
            unit_code=None,
            status="approved",
            created_by_email="collector1@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-305-1-C",
        entity_name="GreenTech Energy GmbH",
        facility_name="Berlin Manufacturing Plant",
        collector_email="collector1@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 18),
        assignment_status="assigned",
        data_point=None,
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-305-1-F",
        entity_name="GreenTech Energy GmbH",
        facility_name=None,
        collector_email="collector1@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 20),
        assignment_status="in_progress",
        data_point=DataPointSpec(
            kind="text",
            value="Operational control approach applied across owned generation assets.",
            unit_code=None,
            status="submitted",
            created_by_email="collector1@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-405-1-A-2",
        entity_name="GreenTech Holdings",
        facility_name=None,
        collector_email="collector2@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 22),
        assignment_status="completed",
        data_point=DataPointSpec(
            kind="numeric",
            value=42.0,
            unit_code="%",
            status="approved",
            created_by_email="collector2@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-405-1-B-2",
        entity_name="GreenTech Holdings",
        facility_name=None,
        collector_email="collector2@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 24),
        assignment_status="in_progress",
        data_point=DataPointSpec(
            kind="numeric",
            value=48.0,
            unit_code="%",
            status="draft",
            created_by_email="collector2@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-405-2-A-3",
        entity_name="GreenTech Holdings",
        facility_name=None,
        collector_email="collector2@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 25),
        assignment_status="assigned",
        data_point=None,
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-GRI-405-2-A-4",
        entity_name="GreenTech Holdings",
        facility_name=None,
        collector_email="collector2@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 25),
        assignment_status="completed",
        data_point=DataPointSpec(
            kind="text",
            value="0.97",
            unit_code=None,
            status="approved",
            created_by_email="collector2@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-SV-AD-220A-1-POLICY-PRACTICES",
        entity_name="GreenTech Chemicals Ltd",
        facility_name=None,
        collector_email="collector1@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 26),
        assignment_status="in_progress",
        data_point=DataPointSpec(
            kind="text",
            value=(
                "Consumer privacy controls were refreshed in Q1 2026, including consent review, "
                "retention policy updates, and quarterly checks on custom audience usage."
            ),
            unit_code=None,
            status="submitted",
            created_by_email="collector1@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-SV-AD-270A-1-MONETARY-LOSSES",
        entity_name="GreenTech Chemicals Ltd",
        facility_name=None,
        collector_email="collector1@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 28),
        assignment_status="completed",
        data_point=DataPointSpec(
            kind="numeric",
            value=120000.0,
            unit_code="EUR",
            status="approved",
            created_by_email="collector1@greentech.com",
        ),
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-SV-AD-270A-1-NATURE-CONTEXT",
        entity_name="GreenTech Chemicals Ltd",
        facility_name=None,
        collector_email="collector1@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 28),
        assignment_status="assigned",
        data_point=None,
    ),
    DemoAssignmentSpec(
        shared_element_code="SE-SV-AD-000-D",
        entity_name="GreenTech Chemicals Ltd",
        facility_name=None,
        collector_email="collector2@greentech.com",
        reviewer_email="reviewer@greentech.com",
        backup_collector_email="manager@greentech.com",
        deadline=date(2026, 4, 30),
        assignment_status="completed",
        data_point=DataPointSpec(
            kind="numeric",
            value=1860.0,
            unit_code="COUNT",
            status="approved",
            created_by_email="collector2@greentech.com",
        ),
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Populate a demo project with sample collection assignments and data points."
    )
    parser.add_argument("project_id", type=int, nargs="?", default=DEFAULT_PROJECT_ID)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist the demo data. Without this flag the script runs as dry-run.",
    )
    return parser


async def main() -> None:
    args = build_parser().parse_args()

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        project = await session.scalar(
            select(ReportingProject).where(ReportingProject.id == args.project_id)
        )
        if project is None:
            raise RuntimeError(f"Project {args.project_id} not found")

        user_result = await session.execute(
            select(User.id, User.email).where(User.is_active == True)
        )
        users_by_email = {email: user_id for user_id, email in user_result.all()}

        org_id = project.organization_id

        entity_result = await session.execute(
            select(CompanyEntity.id, CompanyEntity.name)
            .where(CompanyEntity.organization_id == org_id)
        )
        entities_by_name = {name: entity_id for entity_id, name in entity_result.all()}

        shared_element_codes = sorted({spec.shared_element_code for spec in DEMO_ASSIGNMENTS})
        shared_result = await session.execute(
            select(SharedElement.id, SharedElement.code).where(SharedElement.code.in_(shared_element_codes))
        )
        shared_elements_by_code = {code: shared_element_id for shared_element_id, code in shared_result.all()}

        missing_users = sorted(
            {
                email
                for spec in DEMO_ASSIGNMENTS
                for email in (
                    spec.collector_email,
                    spec.reviewer_email,
                    spec.backup_collector_email,
                    spec.data_point.created_by_email if spec.data_point else None,
                )
                if email and email not in users_by_email
            }
        )
        if missing_users:
            raise RuntimeError(f"Demo users not found: {', '.join(missing_users)}")

        missing_entities = sorted(
            {
                name
                for spec in DEMO_ASSIGNMENTS
                for name in (spec.entity_name, spec.facility_name)
                if name and name not in entities_by_name
            }
        )
        if missing_entities:
            raise RuntimeError(f"Demo entities not found: {', '.join(missing_entities)}")

        missing_elements = sorted(
            code for code in shared_element_codes if code not in shared_elements_by_code
        )
        if missing_elements:
            raise RuntimeError(f"Shared elements not found: {', '.join(missing_elements)}")

        assignment_repo = ProjectRepository(session)
        data_point_repo = DataPointRepository(session)

        existing_assignments = (
            await session.execute(
                select(MetricAssignment).where(MetricAssignment.reporting_project_id == args.project_id)
            )
        ).scalars().all()
        assignments_by_key = {
            (assignment.shared_element_id, assignment.entity_id, assignment.facility_id): assignment
            for assignment in existing_assignments
        }

        existing_points = (
            await session.execute(
                select(DataPoint).where(DataPoint.reporting_project_id == args.project_id)
            )
        ).scalars().all()
        data_points_by_key: dict[tuple[int, int | None, int | None], list[DataPoint]] = {}
        for point in existing_points:
            key = (point.shared_element_id, point.entity_id, point.facility_id)
            data_points_by_key.setdefault(key, []).append(point)

        created_assignments = 0
        updated_assignments = 0
        created_points = 0
        updated_points = 0
        deleted_points = 0

        for spec in DEMO_ASSIGNMENTS:
            shared_element_id = shared_elements_by_code[spec.shared_element_code]
            entity_id = entities_by_name[spec.entity_name]
            facility_id = entities_by_name[spec.facility_name] if spec.facility_name else None
            assignment_key = (shared_element_id, entity_id, facility_id)

            assignment = assignments_by_key.get(assignment_key)
            assignment_payload = {
                "shared_element_id": shared_element_id,
                "entity_id": entity_id,
                "facility_id": facility_id,
                "collector_id": users_by_email[spec.collector_email],
                "reviewer_id": users_by_email[spec.reviewer_email],
                "backup_collector_id": (
                    users_by_email[spec.backup_collector_email]
                    if spec.backup_collector_email
                    else None
                ),
                "deadline": spec.deadline,
                "escalation_after_days": 3,
                "status": spec.assignment_status,
            }

            if assignment is None:
                created_assignments += 1
                if args.apply:
                    assignment = await assignment_repo.create_assignment(args.project_id, **assignment_payload)
                    assignments_by_key[assignment_key] = assignment
            else:
                updated_assignments += 1
                if args.apply:
                    await assignment_repo.update_assignment(assignment.id, **assignment_payload)

            matching_points = data_points_by_key.get(assignment_key, [])
            primary_point = matching_points[0] if matching_points else None
            extra_points = matching_points[1:] if len(matching_points) > 1 else []

            if spec.data_point is None:
                deleted_points += len(matching_points)
                if args.apply:
                    for point in matching_points:
                        await session.delete(point)
                continue

            if args.apply:
                for point in extra_points:
                    await session.delete(point)
                    deleted_points += 1

            point_payload = {
                "shared_element_id": shared_element_id,
                "entity_id": entity_id,
                "facility_id": facility_id,
                "created_by": users_by_email[spec.data_point.created_by_email],
                "status": spec.data_point.status,
                "unit_code": spec.data_point.unit_code,
                "numeric_value": spec.data_point.value if spec.data_point.kind == "numeric" else None,
                "text_value": spec.data_point.value if spec.data_point.kind == "text" else None,
            }

            if primary_point is None:
                created_points += 1
                if args.apply:
                    await data_point_repo.create(args.project_id, **point_payload)
            else:
                updated_points += 1
                if args.apply:
                    update_payload = {
                        "entity_id": entity_id,
                        "facility_id": facility_id,
                        "status": spec.data_point.status,
                        "unit_code": spec.data_point.unit_code,
                        "numeric_value": point_payload["numeric_value"],
                        "text_value": point_payload["text_value"],
                        "review_comment": None,
                    }
                    await data_point_repo.update(primary_point.id, **update_payload)
                    primary_point.created_by = users_by_email[spec.data_point.created_by_email]

        if args.apply:
            manager_email = "manager@greentech.com"
            if manager_email not in users_by_email:
                raise RuntimeError("manager@greentech.com not found; cannot resync demo config")

            ctx = RequestContext(
                user_id=users_by_email[manager_email],
                email=manager_email,
                organization_id=org_id,
                role="esg_manager",
            )
            form_config_service = FormConfigService(
                repo=FormConfigRepository(session),
                session=session,
            )
            resynced = await form_config_service.resync_project_config(args.project_id, ctx)
            await session.commit()
            await invalidate_dashboard_project(args.project_id)
            field_count = sum(len(step.get("fields", [])) for step in resynced.config.get("steps", []))
        else:
            await session.rollback()
            field_count = 0

    await engine.dispose()

    mode = "apply" if args.apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"Project: {args.project_id}")
    print(f"  Assignments created: {created_assignments}")
    print(f"  Assignments updated: {updated_assignments}")
    print(f"  Data points created: {created_points}")
    print(f"  Data points updated: {updated_points}")
    print(f"  Data points deleted: {deleted_points}")
    if args.apply:
        print(f"  Guided config field count: {field_count}")


if __name__ == "__main__":
    asyncio.run(main())
