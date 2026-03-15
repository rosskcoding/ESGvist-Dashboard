"""
Unit tests for deterministic SourceSnapshot hashing and reuse.

We want:
- Same report content => same content_root_hash
- Same content_root_hash => reuse existing SourceSnapshot (dedupe)
- Content change => new SourceSnapshot
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    Block,
    BlockI18n,
    Company,
    CompanyStatus,
    ReleaseBuild,
    Report,
    Section,
    SectionI18n,
    SourceSnapshot,
)
from app.domain.models.enums import (
    BlockType,
    BlockVariant,
    BuildScope,
    BuildStatus,
    BuildType,
    Locale,
    PackageMode,
)
from app.services.build_pipeline import BuildPipeline


@pytest.mark.asyncio
async def test_snapshot_reuse_same_content(db_session: AsyncSession) -> None:
    company_id = uuid4()
    db_session.add(
        Company(
            company_id=company_id,
            name=f"Snapshot Hash Test Co {company_id.hex[:8]}",
            status=CompanyStatus.ACTIVE,
            created_by=None,
        )
    )
    await db_session.flush()

    report = Report(
        company_id=company_id,
        year=2031,
        title="Snapshot Hash Test Report",
        slug=f"snapshot-hash-{company_id.hex[:8]}",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()

    section = Section(report_id=report.report_id, order_index=0, depth=0)
    db_session.add(section)
    await db_session.flush()
    db_session.add(
        SectionI18n(
            section_id=section.section_id,
            locale=Locale.RU,
            title="Intro",
            slug="intro",
            summary="Summary",
        )
    )
    await db_session.flush()

    block = Block(
        report_id=report.report_id,
        section_id=section.section_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
    )
    db_session.add(block)
    await db_session.flush()
    db_session.add(
        BlockI18n(
            block_id=block.block_id,
            locale=Locale.RU,
            fields_json={"body_html": "<p>Hello</p>"},
        )
    )
    await db_session.flush()

    build1 = ReleaseBuild(
        report_id=report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=report.theme_slug,
        base_path="/",
        locales=["ru"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build1)
    await db_session.flush()

    pipeline1 = BuildPipeline(build1, db_session)
    hash1 = await pipeline1._compute_content_hash()
    snap1 = await pipeline1._create_snapshot()

    build2 = ReleaseBuild(
        report_id=report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=report.theme_slug,
        base_path="/",
        locales=["ru"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build2)
    await db_session.flush()

    pipeline2 = BuildPipeline(build2, db_session)
    hash2 = await pipeline2._compute_content_hash()
    snap2 = await pipeline2._create_snapshot()

    assert hash1 == hash2
    assert snap1.snapshot_id == snap2.snapshot_id
    assert snap1.content_root_hash == snap2.content_root_hash
    assert build1.source_snapshot_id == snap1.snapshot_id
    assert build2.source_snapshot_id == snap1.snapshot_id

    count_res = await db_session.execute(
        select(func.count()).select_from(SourceSnapshot).where(SourceSnapshot.report_id == report.report_id)
    )
    assert (count_res.scalar() or 0) == 1


@pytest.mark.asyncio
async def test_snapshot_new_when_content_changes(db_session: AsyncSession) -> None:
    company_id = uuid4()
    db_session.add(
        Company(
            company_id=company_id,
            name=f"Snapshot Hash Change Co {company_id.hex[:8]}",
            status=CompanyStatus.ACTIVE,
            created_by=None,
        )
    )
    await db_session.flush()

    report = Report(
        company_id=company_id,
        year=2032,
        title="Snapshot Hash Change Report",
        slug=f"snapshot-hash-change-{company_id.hex[:8]}",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()

    section = Section(report_id=report.report_id, order_index=0, depth=0)
    db_session.add(section)
    await db_session.flush()
    db_session.add(
        SectionI18n(section_id=section.section_id, locale=Locale.RU, title="S", slug="s")
    )
    await db_session.flush()

    block = Block(
        report_id=report.report_id,
        section_id=section.section_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
    )
    db_session.add(block)
    await db_session.flush()
    block_i18n = BlockI18n(
        block_id=block.block_id,
        locale=Locale.RU,
        fields_json={"body_html": "<p>v1</p>"},
    )
    db_session.add(block_i18n)
    await db_session.flush()

    build1 = ReleaseBuild(
        report_id=report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=report.theme_slug,
        base_path="/",
        locales=["ru"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build1)
    await db_session.flush()

    pipeline1 = BuildPipeline(build1, db_session)
    snap1 = await pipeline1._create_snapshot()

    # Change localized content
    block_i18n.fields_json = {"body_html": "<p>v2</p>"}
    await db_session.flush()

    build2 = ReleaseBuild(
        report_id=report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.QUEUED,
        theme_slug=report.theme_slug,
        base_path="/",
        locales=["ru"],
        package_mode=PackageMode.PORTABLE,
        scope=BuildScope.FULL,
    )
    db_session.add(build2)
    await db_session.flush()

    pipeline2 = BuildPipeline(build2, db_session)
    snap2 = await pipeline2._create_snapshot()

    assert snap2.snapshot_id != snap1.snapshot_id
    assert snap2.content_root_hash != snap1.content_root_hash

    count_res = await db_session.execute(
        select(func.count()).select_from(SourceSnapshot).where(SourceSnapshot.report_id == report.report_id)
    )
    assert (count_res.scalar() or 0) == 2



