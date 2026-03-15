"""
Integration tests for Multi-Tenant Security (Tenant Isolation).

Tests verify that users from Company A cannot access resources from Company B.

Security principle: "Secure by Default" — all resource access must be scoped to tenant.

See: ADR-005-multi-tenant-security.md, 12_IAM.md section 12.8
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user_required
from app.domain.models import (
    Block,
    Company,
    CompanyMembership,
    Report,
    RoleAssignment,
    Section,
    SectionI18n,
    User,
)
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


# =============================================================================
# Fixtures: Two companies with users
# =============================================================================


@pytest_asyncio.fixture
async def company_a(db_session: AsyncSession) -> Company:
    """Company A — owns the test resources."""
    company = Company(
        company_id=uuid4(),
        name="Company A (Tenant Owner)",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def company_b(db_session: AsyncSession) -> Company:
    """Company B — different tenant, should NOT have access to Company A resources."""
    company = Company(
        company_id=uuid4(),
        name="Company B (Other Tenant)",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession, company_a: Company) -> User:
    """User belonging to Company A with EDITOR role."""
    user = User(
        user_id=uuid4(),
        email="user-a@company-a.com",
        password_hash="not-used",
        full_name="User A",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    # Membership in Company A
    membership = CompanyMembership(
        company_id=company_a.company_id,
        user_id=user.user_id,
        is_active=True,
        created_by=user.user_id,
    )
    db_session.add(membership)

    # EDITOR role in Company A (company-scoped)
    role = RoleAssignment(
        user_id=user.user_id,
        company_id=company_a.company_id,
        role=AssignableRole.EDITOR,
        scope_type=ScopeType.COMPANY,
        scope_id=company_a.company_id,
        created_by=user.user_id,
    )
    db_session.add(role)
    await db_session.flush()

    # Reload user with relationships
    await db_session.refresh(user, ["memberships", "role_assignments"])
    return user


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession, company_b: Company) -> User:
    """User belonging to Company B with EDITOR role — should NOT access Company A."""
    user = User(
        user_id=uuid4(),
        email="user-b@company-b.com",
        password_hash="not-used",
        full_name="User B",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()

    # Membership in Company B
    membership = CompanyMembership(
        company_id=company_b.company_id,
        user_id=user.user_id,
        is_active=True,
        created_by=user.user_id,
    )
    db_session.add(membership)

    # EDITOR role in Company B (company-scoped)
    role = RoleAssignment(
        user_id=user.user_id,
        company_id=company_b.company_id,
        role=AssignableRole.EDITOR,
        scope_type=ScopeType.COMPANY,
        scope_id=company_b.company_id,
        created_by=user.user_id,
    )
    db_session.add(role)
    await db_session.flush()

    # Reload user with relationships
    await db_session.refresh(user, ["memberships", "role_assignments"])
    return user


@pytest_asyncio.fixture
async def report_company_a(db_session: AsyncSession, company_a: Company) -> Report:
    """Report belonging to Company A."""
    report = Report(
        report_id=uuid4(),
        company_id=company_a.company_id,
        year=2025,
        title="Company A Report",
        slug="company-a-report-2025",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru"],
        release_locales=["ru"],
        theme_slug="default",
    )
    db_session.add(report)
    await db_session.flush()
    return report


@pytest_asyncio.fixture
async def section_company_a(
    db_session: AsyncSession, report_company_a: Report
) -> Section:
    """Section in Company A's report."""
    section = Section(
        section_id=uuid4(),
        report_id=report_company_a.report_id,
        order_index=0,
        depth=0,
    )
    db_session.add(section)
    await db_session.flush()

    # Add i18n
    i18n = SectionI18n(
        section_id=section.section_id,
        locale=Locale.RU,
        title="Test Section",
        slug="test-section",
    )
    db_session.add(i18n)
    await db_session.flush()

    return section


@pytest_asyncio.fixture
async def block_company_a(
    db_session: AsyncSession, report_company_a: Report, section_company_a: Section
) -> Block:
    """Block in Company A's report."""
    block = Block(
        block_id=uuid4(),
        report_id=report_company_a.report_id,
        section_id=section_company_a.section_id,
        type=BlockType.TEXT,
        variant=BlockVariant.DEFAULT,
        order_index=0,
        data_json={},
        qa_flags_global=[],
    )
    db_session.add(block)
    await db_session.flush()
    return block


# =============================================================================
# Helper: Create client for specific user
# =============================================================================


def create_client_for_user(db_session: AsyncSession, user: User):
    """Create AsyncClient with auth override for specific user."""
    app = create_app()

    async def _override_get_session():
        try:
            yield db_session
            await db_session.flush()
        except Exception:
            await db_session.rollback()
            raise

    async def _override_current_user() -> User:
        return user

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_current_user_required] = _override_current_user

    return app


# =============================================================================
# Tests: Reports Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_a_can_read_own_report(
    db_session: AsyncSession,
    user_a: User,
    report_company_a: Report,
):
    """User A (Company A) CAN read report from Company A."""
    app = create_client_for_user(db_session, user_a)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/reports/{report_company_a.report_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["report_id"] == str(report_company_a.report_id)


@pytest.mark.asyncio
async def test_user_b_cannot_read_company_a_report(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT read report from Company A — tenant isolation."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/reports/{report_company_a.report_id}")
        assert resp.status_code == 403, f"Expected 403 (forbidden), got {resp.status_code}: {resp.text}"
        assert "No access to this company" in resp.text or "Permission denied" in resp.text


@pytest.mark.asyncio
async def test_user_b_cannot_update_company_a_report(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT update report from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/v1/reports/{report_company_a.report_id}",
            json={"title": "Hacked Title"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_delete_company_a_report(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT delete report from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/reports/{report_company_a.report_id}")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Sections Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_b_cannot_read_company_a_section(
    db_session: AsyncSession,
    user_b: User,
    section_company_a: Section,
):
    """User B (Company B) CANNOT read section from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/sections/{section_company_a.section_id}")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_create_section_in_company_a_report(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT create section in Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/sections",
            json={
                "report_id": str(report_company_a.report_id),
                "order_index": 99,
                "i18n": [{"locale": "ru", "title": "Hacked Section", "slug": "hacked"}],
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Blocks Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_b_cannot_read_company_a_block(
    db_session: AsyncSession,
    user_b: User,
    block_company_a: Block,
):
    """User B (Company B) CANNOT read block from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/blocks/{block_company_a.block_id}")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_update_company_a_block(
    db_session: AsyncSession,
    user_b: User,
    block_company_a: Block,
):
    """User B (Company B) CANNOT update block from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/v1/blocks/{block_company_a.block_id}",
            json={"data_json": {"hacked": True}},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Releases Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_b_cannot_create_release_for_company_a_report(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT create release build for Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/releases",
            json={
                "report_id": str(report_company_a.report_id),
                "build_type": "draft",
                "locales": ["ru"],
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_list_releases_for_company_a_report(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT list releases for Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/releases?report_id={report_company_a.report_id}"
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Translations Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_b_cannot_create_translation_job_for_company_a(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT create translation job for Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/translations/jobs",
            json={
                "report_id": str(report_company_a.report_id),
                "scope_type": "report",
                "target_locales": ["en"],
            },
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_get_translation_progress_for_company_a(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT get translation progress for Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/translations/progress/{report_company_a.report_id}"
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Design Settings Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_b_cannot_read_design_settings_company_a(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT read design settings for Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/reports/{report_company_a.report_id}/design"
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_update_design_settings_company_a(
    db_session: AsyncSession,
    user_b: User,
    report_company_a: Report,
):
    """User B (Company B) CANNOT update design settings for Company A's report."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(
            f"/api/v1/reports/{report_company_a.report_id}/design",
            json={"theme_slug": "hacked-theme"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Preview Tenant Isolation
# =============================================================================


@pytest.mark.asyncio
async def test_user_b_cannot_preview_company_a_section(
    db_session: AsyncSession,
    user_b: User,
    section_company_a: Section,
):
    """User B (Company B) CANNOT preview section from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/preview/ru/sections-by-id/{section_company_a.section_id}"
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_user_b_cannot_preview_company_a_block(
    db_session: AsyncSession,
    user_b: User,
    block_company_a: Block,
):
    """User B (Company B) CANNOT preview block from Company A."""
    app = create_client_for_user(db_session, user_b)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/preview/ru/blocks/{block_company_a.block_id}"
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# =============================================================================
# Tests: Superuser Bypass
# =============================================================================


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession) -> User:
    """Superuser (Platform Admin) — can access all tenants."""
    user = User(
        user_id=uuid4(),
        email="superadmin@platform.com",
        password_hash="not-used",
        full_name="Super Admin",
        is_active=True,
        is_superuser=True,  # Platform admin bypasses tenant checks
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_superuser_can_access_any_company_report(
    db_session: AsyncSession,
    superuser: User,
    report_company_a: Report,
):
    """Superuser CAN access any tenant's resources (platform admin)."""
    app = create_client_for_user(db_session, superuser)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/v1/reports/{report_company_a.report_id}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

