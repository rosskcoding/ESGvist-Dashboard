"""
Integration tests for Translation RBAC.

Focus:
- `translation:trigger` (create job) is restricted by default (TRANSLATION_TRIGGER_RESTRICTED=true)
- `translation:read` gates read-only translation endpoints (progress, jobs list, per-block status)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user_required
from app.domain.models import Block, Company, CompanyMembership, Report, RoleAssignment, Section, User
from app.domain.models.enums import (
    AssignableRole,
    BlockType,
    BlockVariant,
    CompanyStatus,
    Locale,
    ScopeType,
)
from app.infra.database import get_session
from app.main import create_app


def _create_app_for_user(db_session: AsyncSession, user: User):
    """Create FastAPI app with overridden DB session + current user."""
    app = create_app()

    async def _override_get_session():
        try:
            yield db_session
            await db_session.flush()
        except Exception:
            await db_session.rollback()
            raise

    async def _override_current_user_required() -> User:
        return user

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_current_user_required] = _override_current_user_required
    return app


@pytest_asyncio.fixture
async def company(db_session: AsyncSession) -> Company:
    company = Company(
        company_id=uuid4(),
        name="Translation RBAC Co",
        status=CompanyStatus.ACTIVE,
        created_by=None,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def report(db_session: AsyncSession, company: Company) -> Report:
    report = Report(
        report_id=uuid4(),
        company_id=company.company_id,
        year=2030,
        title="Translation RBAC Report",
        slug=f"translation-rbac-{uuid4()}",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru", "en"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()
    return report


@pytest_asyncio.fixture
async def section(db_session: AsyncSession, report: Report) -> Section:
    section = Section(
        section_id=uuid4(),
        report_id=report.report_id,
        order_index=0,
        depth=0,
    )
    db_session.add(section)
    await db_session.flush()
    return section


@pytest_asyncio.fixture
async def block(db_session: AsyncSession, report: Report, section: Section) -> Block:
    block = Block(
        block_id=uuid4(),
        report_id=report.report_id,
        section_id=section.section_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
        qa_flags_global=[],
    )
    db_session.add(block)
    await db_session.flush()
    return block


async def _create_user_with_role(
    db_session: AsyncSession,
    *,
    company: Company,
    role: AssignableRole,
    email: str,
) -> User:
    user = User(
        user_id=uuid4(),
        email=email,
        password_hash="not-used",
        full_name=email.split("@")[0],
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    membership = CompanyMembership(
        company_id=company.company_id,
        user_id=user.user_id,
        is_active=True,
        created_by=user.user_id,
    )
    db_session.add(membership)

    assignment = RoleAssignment(
        company_id=company.company_id,
        user_id=user.user_id,
        role=role,
        scope_type=ScopeType.COMPANY,
        scope_id=company.company_id,
        created_by=user.user_id,
    )
    db_session.add(assignment)
    await db_session.flush()

    # Ensure relationships exist for RBAC checks
    await db_session.refresh(user, ["memberships", "role_assignments"])
    return user


@pytest_asyncio.fixture
async def translator_user(db_session: AsyncSession, company: Company) -> User:
    return await _create_user_with_role(
        db_session,
        company=company,
        role=AssignableRole.TRANSLATOR,
        email="translator-rbac@example.com",
    )


@pytest_asyncio.fixture
async def content_editor_user(db_session: AsyncSession, company: Company) -> User:
    return await _create_user_with_role(
        db_session,
        company=company,
        role=AssignableRole.CONTENT_EDITOR,
        email="content-editor-rbac@example.com",
    )


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession, company: Company) -> User:
    return await _create_user_with_role(
        db_session,
        company=company,
        role=AssignableRole.VIEWER,
        email="viewer-rbac@example.com",
    )


@pytest_asyncio.fixture
async def internal_auditor_user(db_session: AsyncSession, company: Company) -> User:
    return await _create_user_with_role(
        db_session,
        company=company,
        role=AssignableRole.INTERNAL_AUDITOR,
        email="internal-auditor-rbac@example.com",
    )


@pytest.mark.asyncio
async def test_translator_can_create_translation_job(
    db_session: AsyncSession,
    translator_user: User,
    report: Report,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Avoid broker dependency in tests (create endpoint is best-effort anyway).
    from app.api.v1 import translations as translations_module

    monkeypatch.setattr(translations_module, "send_task", lambda *args, **kwargs: None)

    app = _create_app_for_user(db_session, translator_user)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as client:
        resp = await client.post(
            "/api/v1/translations/jobs",
            json={
                "report_id": str(report.report_id),
                "scope_type": "report",
                "scope_ids": [],
                "target_locales": ["en"],
                "mode": "reporting",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["report_id"] == str(report.report_id)
        assert data["target_locales"] == ["en"]
        assert data["status"] in ("queued", "running", "completed", "failed", "cancelled")


@pytest.mark.asyncio
async def test_content_editor_cannot_create_translation_job_when_restricted(
    db_session: AsyncSession,
    content_editor_user: User,
    report: Report,
) -> None:
    # Default config: TRANSLATION_TRIGGER_RESTRICTED=true
    app = _create_app_for_user(db_session, content_editor_user)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as client:
        resp = await client.post(
            "/api/v1/translations/jobs",
            json={
                "report_id": str(report.report_id),
                "scope_type": "report",
                "scope_ids": [],
                "target_locales": ["en"],
                "mode": "reporting",
            },
        )
        assert resp.status_code == 403, resp.text
        assert "translation:trigger" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_viewer_can_read_translation_progress_and_blocks_status(
    db_session: AsyncSession,
    viewer_user: User,
    report: Report,
    block: Block,
) -> None:
    app = _create_app_for_user(db_session, viewer_user)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as client:
        progress = await client.get(f"/api/v1/translations/progress/{report.report_id}")
        assert progress.status_code == 200, progress.text
        assert progress.json()["report_id"] == str(report.report_id)

        blocks_status = await client.get(f"/api/v1/translations/blocks/{report.report_id}/status")
        assert blocks_status.status_code == 200, blocks_status.text
        data = blocks_status.json()
        assert data["report_id"] == str(report.report_id)
        assert "enabled_locales" in data
        assert any(b["block_id"] == str(block.block_id) for b in data["blocks"])


@pytest.mark.asyncio
async def test_internal_auditor_cannot_read_translation_progress(
    db_session: AsyncSession,
    internal_auditor_user: User,
    report: Report,
) -> None:
    app = _create_app_for_user(db_session, internal_auditor_user)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as client:
        resp = await client.get(f"/api/v1/translations/progress/{report.report_id}")
        assert resp.status_code == 403, resp.text
        assert "translation:read" in resp.json()["detail"]


