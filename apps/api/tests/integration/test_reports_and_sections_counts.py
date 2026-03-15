"""
Integration tests for list endpoints counts.

Ensures that:
- GET /reports returns sections_count and blocks_count correctly
- GET /sections returns blocks_count per section correctly

This also guards the recent N+1 removal refactor (counts now computed via GROUP BY).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Block, Company, CompanyStatus, Report, Section, SectionI18n
from app.domain.models.enums import BlockType, BlockVariant, Locale


@pytest.mark.asyncio
async def test_list_reports_and_sections_counts(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    company_id = uuid4()
    db_session.add(
        Company(
            company_id=company_id,
            name=f"Counts Co {company_id.hex[:8]}",
            status=CompanyStatus.ACTIVE,
            created_by=None,
        )
    )
    await db_session.flush()

    report = Report(
        company_id=company_id,
        year=2033,
        title="Counts Report",
        slug=f"counts-report-{company_id.hex[:8]}",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()

    # Two sections
    section1 = Section(report_id=report.report_id, order_index=0, depth=0)
    section2 = Section(report_id=report.report_id, order_index=1, depth=0)
    db_session.add_all([section1, section2])
    await db_session.flush()

    db_session.add_all(
        [
            SectionI18n(section_id=section1.section_id, locale=Locale.RU, title="S1", slug="s1"),
            SectionI18n(section_id=section2.section_id, locale=Locale.RU, title="S2", slug="s2"),
        ]
    )
    await db_session.flush()

    # 3 blocks total: 1 in section1, 2 in section2
    db_session.add_all(
        [
            Block(
                report_id=report.report_id,
                section_id=section1.section_id,
                type=BlockType.TEXT,
                variant=BlockVariant.DEFAULT,
                order_index=0,
                data_json={},
            ),
            Block(
                report_id=report.report_id,
                section_id=section2.section_id,
                type=BlockType.TEXT,
                variant=BlockVariant.DEFAULT,
                order_index=0,
                data_json={},
            ),
            Block(
                report_id=report.report_id,
                section_id=section2.section_id,
                type=BlockType.TEXT,
                variant=BlockVariant.DEFAULT,
                order_index=1,
                data_json={},
            ),
        ]
    )
    await db_session.flush()

    # GET /reports should include aggregate counts
    resp = await auth_client.get(
        "/api/v1/reports",
        params={"year": report.year, "page": 1, "page_size": 100},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    items = payload["items"]
    target = next(i for i in items if i["report_id"] == str(report.report_id))

    assert target["sections_count"] == 2
    assert target["blocks_count"] == 3

    # GET /sections should include blocks_count per section
    resp2 = await auth_client.get(
        "/api/v1/sections",
        params={"report_id": str(report.report_id), "page": 1, "page_size": 100},
    )
    assert resp2.status_code == 200, resp2.text
    payload2 = resp2.json()
    sections = payload2["items"]
    by_id = {s["section_id"]: s for s in sections}

    assert by_id[str(section1.section_id)]["blocks_count"] == 1
    assert by_id[str(section2.section_id)]["blocks_count"] == 2



