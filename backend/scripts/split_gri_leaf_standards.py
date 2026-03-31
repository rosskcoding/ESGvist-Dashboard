#!/usr/bin/env python3

import argparse
import asyncio
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models.mapping import RequirementItemSharedElement
from app.db.models.requirement_item import RequirementItem, RequirementItemDependency
from app.db.models.standard import DisclosureRequirement, Standard, StandardSection


@dataclass
class SplitStats:
    created_standards: int = 0
    updated_standards: int = 0
    created_sections: int = 0
    updated_sections: int = 0
    created_disclosures: int = 0
    updated_disclosures: int = 0
    created_items: int = 0
    updated_items: int = 0
    created_mappings: int = 0
    created_dependencies: int = 0


def item_key(item: RequirementItem) -> str:
    if item.item_code:
        return item.item_code
    return f"name::{item.sort_order}::{item.name}"


def clone_json(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return {key: clone_json(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [clone_json(entry) for entry in value]
    return value


async def get_or_create_target_standard(
    session,
    *,
    code: str,
    name: str,
    source_standard: Standard,
    stats: SplitStats,
) -> Standard:
    existing = await session.scalar(select(Standard).where(Standard.code == code))
    if existing is None:
        target = Standard(
            code=code,
            name=name,
            version=None,
            jurisdiction=source_standard.jurisdiction,
            effective_from=None,
            effective_to=None,
            is_active=source_standard.is_active,
        )
        session.add(target)
        await session.flush()
        stats.created_standards += 1
        return target

    changed = False
    if existing.name != name:
        existing.name = name
        changed = True
    if existing.jurisdiction != source_standard.jurisdiction:
        existing.jurisdiction = source_standard.jurisdiction
        changed = True
    if existing.is_active != source_standard.is_active:
        existing.is_active = source_standard.is_active
        changed = True
    if existing.version is not None:
        existing.version = None
        changed = True
    if existing.effective_from is not None:
        existing.effective_from = None
        changed = True
    if existing.effective_to is not None:
        existing.effective_to = None
        changed = True

    if changed:
        await session.flush()
        stats.updated_standards += 1

    return existing


async def load_sections_for_standard(session, standard_id: int) -> list[StandardSection]:
    result = await session.execute(
        select(StandardSection)
        .where(StandardSection.standard_id == standard_id)
        .order_by(StandardSection.sort_order, StandardSection.id)
    )
    return list(result.scalars().all())


async def load_disclosures_for_standard(session, standard_id: int) -> list[DisclosureRequirement]:
    result = await session.execute(
        select(DisclosureRequirement)
        .where(DisclosureRequirement.standard_id == standard_id)
        .order_by(DisclosureRequirement.sort_order, DisclosureRequirement.id)
    )
    return list(result.scalars().all())


async def load_current_items_for_disclosure(session, disclosure_id: int) -> list[RequirementItem]:
    result = await session.execute(
        select(RequirementItem)
        .where(
            RequirementItem.disclosure_requirement_id == disclosure_id,
            RequirementItem.is_current.is_(True),
        )
        .order_by(RequirementItem.sort_order, RequirementItem.id)
    )
    return list(result.scalars().all())


async def ensure_section(
    session,
    *,
    target_standard_id: int,
    source_section: StandardSection,
    target_parent_id: int | None,
    stats: SplitStats,
) -> StandardSection:
    existing_query: Select[tuple[StandardSection]] = select(StandardSection).where(
        StandardSection.standard_id == target_standard_id,
        StandardSection.parent_section_id == target_parent_id,
    )
    if source_section.code:
        existing_query = existing_query.where(StandardSection.code == source_section.code)
    else:
        existing_query = existing_query.where(StandardSection.title == source_section.title)

    existing = await session.scalar(existing_query)
    if existing is None:
        section = StandardSection(
            standard_id=target_standard_id,
            parent_section_id=target_parent_id,
            code=source_section.code,
            title=source_section.title,
            sort_order=source_section.sort_order,
        )
        session.add(section)
        await session.flush()
        stats.created_sections += 1
        return section

    changed = False
    if existing.code != source_section.code:
        existing.code = source_section.code
        changed = True
    if existing.title != source_section.title:
        existing.title = source_section.title
        changed = True
    if existing.sort_order != source_section.sort_order:
        existing.sort_order = source_section.sort_order
        changed = True

    if changed:
        await session.flush()
        stats.updated_sections += 1

    return existing


async def ensure_disclosure(
    session,
    *,
    target_standard_id: int,
    target_section_id: int | None,
    source_disclosure: DisclosureRequirement,
    stats: SplitStats,
) -> DisclosureRequirement:
    existing = await session.scalar(
        select(DisclosureRequirement).where(
            DisclosureRequirement.standard_id == target_standard_id,
            DisclosureRequirement.code == source_disclosure.code,
        )
    )
    if existing is None:
        disclosure = DisclosureRequirement(
            standard_id=target_standard_id,
            section_id=target_section_id,
            code=source_disclosure.code,
            title=source_disclosure.title,
            description=source_disclosure.description,
            requirement_type=source_disclosure.requirement_type,
            mandatory_level=source_disclosure.mandatory_level,
            applicability_rule=clone_json(source_disclosure.applicability_rule),
            sort_order=source_disclosure.sort_order,
        )
        session.add(disclosure)
        await session.flush()
        stats.created_disclosures += 1
        return disclosure

    changed = False
    desired_values = {
        "section_id": target_section_id,
        "title": source_disclosure.title,
        "description": source_disclosure.description,
        "requirement_type": source_disclosure.requirement_type,
        "mandatory_level": source_disclosure.mandatory_level,
        "applicability_rule": clone_json(source_disclosure.applicability_rule),
        "sort_order": source_disclosure.sort_order,
    }
    for field_name, value in desired_values.items():
        if getattr(existing, field_name) != value:
            setattr(existing, field_name, value)
            changed = True

    if changed:
        await session.flush()
        stats.updated_disclosures += 1

    return existing


async def copy_requirement_items(
    session,
    *,
    source_disclosure_id: int,
    target_disclosure_id: int,
    stats: SplitStats,
) -> None:
    source_items = await load_current_items_for_disclosure(session, source_disclosure_id)
    target_items = await load_current_items_for_disclosure(session, target_disclosure_id)
    target_by_key = {item_key(item): item for item in target_items}

    source_to_target_item_id: dict[int, int] = {}
    for source_item in source_items:
        key = item_key(source_item)
        target_item = target_by_key.get(key)
        if target_item is None:
            target_item = RequirementItem(
                disclosure_requirement_id=target_disclosure_id,
                parent_item_id=None,
                item_code=source_item.item_code,
                name=source_item.name,
                description=source_item.description,
                item_type=source_item.item_type,
                value_type=source_item.value_type,
                unit_code=source_item.unit_code,
                is_required=source_item.is_required,
                requires_evidence=source_item.requires_evidence,
                cardinality_min=source_item.cardinality_min,
                cardinality_max=source_item.cardinality_max,
                granularity_rule=clone_json(source_item.granularity_rule),
                validation_rule=clone_json(source_item.validation_rule),
                sort_order=source_item.sort_order,
                version=source_item.version,
                is_current=source_item.is_current,
                valid_from=source_item.valid_from,
                valid_to=source_item.valid_to,
            )
            session.add(target_item)
            await session.flush()
            stats.created_items += 1
        else:
            changed = False
            desired_values = {
                "item_code": source_item.item_code,
                "name": source_item.name,
                "description": source_item.description,
                "item_type": source_item.item_type,
                "value_type": source_item.value_type,
                "unit_code": source_item.unit_code,
                "is_required": source_item.is_required,
                "requires_evidence": source_item.requires_evidence,
                "cardinality_min": source_item.cardinality_min,
                "cardinality_max": source_item.cardinality_max,
                "granularity_rule": clone_json(source_item.granularity_rule),
                "validation_rule": clone_json(source_item.validation_rule),
                "sort_order": source_item.sort_order,
                "version": source_item.version,
                "is_current": source_item.is_current,
                "valid_from": source_item.valid_from,
                "valid_to": source_item.valid_to,
            }
            for field_name, value in desired_values.items():
                if getattr(target_item, field_name) != value:
                    setattr(target_item, field_name, value)
                    changed = True
            if changed:
                await session.flush()
                stats.updated_items += 1

        source_to_target_item_id[source_item.id] = target_item.id
        target_by_key[key] = target_item

    for source_item in source_items:
        target_item_id = source_to_target_item_id[source_item.id]
        target_item = target_by_key[item_key(source_item)]
        desired_parent_id = source_to_target_item_id.get(source_item.parent_item_id)
        if target_item.parent_item_id != desired_parent_id:
            target_item.parent_item_id = desired_parent_id
            await session.flush()

    source_item_ids = [item.id for item in source_items]
    if not source_item_ids:
        return

    source_mappings = (
        await session.execute(
            select(RequirementItemSharedElement).where(
                RequirementItemSharedElement.requirement_item_id.in_(source_item_ids),
                RequirementItemSharedElement.is_current.is_(True),
            )
        )
    ).scalars().all()
    for source_mapping in source_mappings:
        target_item_id = source_to_target_item_id[source_mapping.requirement_item_id]
        existing_mapping = await session.scalar(
            select(RequirementItemSharedElement).where(
                RequirementItemSharedElement.requirement_item_id == target_item_id,
                RequirementItemSharedElement.shared_element_id == source_mapping.shared_element_id,
                RequirementItemSharedElement.version == source_mapping.version,
            )
        )
        if existing_mapping is None:
            mapping = RequirementItemSharedElement(
                requirement_item_id=target_item_id,
                shared_element_id=source_mapping.shared_element_id,
                mapping_type=source_mapping.mapping_type,
                version=source_mapping.version,
                is_current=source_mapping.is_current,
                valid_from=source_mapping.valid_from,
                valid_to=source_mapping.valid_to,
            )
            session.add(mapping)
            await session.flush()
            stats.created_mappings += 1

    source_dependencies = (
        await session.execute(
            select(RequirementItemDependency).where(
                RequirementItemDependency.requirement_item_id.in_(source_item_ids),
                RequirementItemDependency.depends_on_item_id.in_(source_item_ids),
            )
        )
    ).scalars().all()
    for source_dependency in source_dependencies:
        target_requirement_item_id = source_to_target_item_id[source_dependency.requirement_item_id]
        target_depends_on_item_id = source_to_target_item_id[source_dependency.depends_on_item_id]
        existing_dependency = await session.scalar(
            select(RequirementItemDependency).where(
                RequirementItemDependency.requirement_item_id == target_requirement_item_id,
                RequirementItemDependency.depends_on_item_id == target_depends_on_item_id,
                RequirementItemDependency.dependency_type == source_dependency.dependency_type,
            )
        )
        if existing_dependency is None:
            dependency = RequirementItemDependency(
                requirement_item_id=target_requirement_item_id,
                depends_on_item_id=target_depends_on_item_id,
                dependency_type=source_dependency.dependency_type,
                condition_expression=clone_json(source_dependency.condition_expression),
            )
            session.add(dependency)
            await session.flush()
            stats.created_dependencies += 1


async def split_gri_leaf_standards(apply_changes: bool) -> SplitStats:
    stats = SplitStats()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        source_standard = await session.scalar(select(Standard).where(Standard.code == "GRI"))
        if source_standard is None:
            raise RuntimeError("Umbrella GRI standard not found")

        source_sections = await load_sections_for_standard(session, source_standard.id)
        sections_by_parent: dict[int | None, list[StandardSection]] = {}
        for section in source_sections:
            sections_by_parent.setdefault(section.parent_section_id, []).append(section)

        source_disclosures = await load_disclosures_for_standard(session, source_standard.id)
        disclosures_by_section: dict[int | None, list[DisclosureRequirement]] = {}
        for disclosure in source_disclosures:
            disclosures_by_section.setdefault(disclosure.section_id, []).append(disclosure)

        async def clone_section_branch(
            source_section: StandardSection,
            target_standard: Standard,
            target_parent_id: int | None,
            source_to_target_sections: dict[int, StandardSection],
        ) -> None:
            target_section = await ensure_section(
                session,
                target_standard_id=target_standard.id,
                source_section=source_section,
                target_parent_id=target_parent_id,
                stats=stats,
            )
            source_to_target_sections[source_section.id] = target_section

            for disclosure in disclosures_by_section.get(source_section.id, []):
                target_disclosure = await ensure_disclosure(
                    session,
                    target_standard_id=target_standard.id,
                    target_section_id=target_section.id,
                    source_disclosure=disclosure,
                    stats=stats,
                )
                await copy_requirement_items(
                    session,
                    source_disclosure_id=disclosure.id,
                    target_disclosure_id=target_disclosure.id,
                    stats=stats,
                )

            for child_section in sections_by_parent.get(source_section.id, []):
                await clone_section_branch(
                    child_section,
                    target_standard,
                    target_section.id,
                    source_to_target_sections,
                )

        for root_section in sections_by_parent.get(None, []):
            target_standard = await get_or_create_target_standard(
                session,
                code=root_section.code or root_section.title,
                name=root_section.title,
                source_standard=source_standard,
                stats=stats,
            )
            await clone_section_branch(root_section, target_standard, None, {})

        if apply_changes:
            await session.commit()
        else:
            await session.rollback()

    await engine.dispose()
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split umbrella GRI standard into attachable leaf standards."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag the script runs as dry-run.",
    )
    return parser


async def main() -> None:
    args = build_parser().parse_args()
    stats = await split_gri_leaf_standards(apply_changes=args.apply)
    mode = "apply" if args.apply else "dry-run"
    print(f"Mode: {mode}")
    print(f"  Standards:    +{stats.created_standards} new, {stats.updated_standards} updated")
    print(f"  Sections:     +{stats.created_sections} new, {stats.updated_sections} updated")
    print(f"  Disclosures:  +{stats.created_disclosures} new, {stats.updated_disclosures} updated")
    print(f"  Items:        +{stats.created_items} new, {stats.updated_items} updated")
    print(f"  Mappings:     +{stats.created_mappings} new")
    print(f"  Dependencies: +{stats.created_dependencies} new")


if __name__ == "__main__":
    asyncio.run(main())
