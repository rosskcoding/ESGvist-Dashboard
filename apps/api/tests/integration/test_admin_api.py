"""
Integration tests for Superuser Admin API.

Tests verify:
- Platform overview stats
- Attention inbox incidents
- Build retry/cancel actions
- Artifacts/translations listing
- Audit log export
- AI incident help
- Per-company OpenAI key management
- AI usage tracking

All endpoints require is_superuser = True.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import (
    AIUsageEvent,
    AuditEvent,
    BuildStatus,
    Company,
    CompanyStatus,
    JobStatus,
    OpenAIKeyStatus,
    PlatformAISettings,
    ReleaseBuild,
    ReleaseBuildArtifact,
    Report,
    TranslationJob,
    User,
    AIFeature,
    ArtifactStatus,
)
from app.domain.models.enums import BuildType, Locale


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession) -> User:
    """Create a superuser for testing admin endpoints."""
    user = User(
        user_id=uuid4(),
        email="superuser@example.com",
        password_hash="not-used",
        full_name="Super User",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a regular user (non-superuser) to test access denial."""
    user = User(
        user_id=uuid4(),
        email="regular@example.com",
        password_hash="not-used",
        full_name="Regular User",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession) -> Company:
    """Create a test company."""
    company = Company(
        company_id=uuid4(),
        name="Test Company",
        slug="test-company",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def test_report(db_session: AsyncSession, test_company: Company) -> Report:
    """Create a test report."""
    report = Report(
        report_id=uuid4(),
        company_id=test_company.company_id,
        year=2024,
        title="Test Report",
        source_locale=Locale.RU,
        default_locale=Locale.RU,
        enabled_locales=["ru", "en"],  # Use string list, not Locale enum
        release_locales=["ru"],  # Use string list
        # Must be unique due to reports.slug unique constraint
        slug=f"test-report-{uuid4()}",
    )
    db_session.add(report)
    await db_session.flush()
    return report


# =============================================================================
# Test: Platform Overview
# =============================================================================


@pytest.mark.asyncio
async def test_platform_overview_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_company: Company,
    superuser: User,
) -> None:
    """Test GET /admin/overview returns platform stats."""
    response = await client.get("/api/v1/admin/overview")
    assert response.status_code == 200

    data = response.json()
    assert "companies" in data
    assert "users" in data
    assert "reports" in data
    assert "builds_last_24h" in data
    assert "health" in data

    # Check structure
    assert data["companies"]["total"] >= 1  # At least test_company
    assert data["users"]["superusers"] >= 1  # At least current_user


@pytest.mark.asyncio
async def test_platform_overview_non_superuser_denied(
    db_session: AsyncSession,
    regular_user: User,
) -> None:
    """Test that regular users cannot access overview."""
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app
    from app.api.v1.auth import get_current_user_required
    from app.infra.database import get_session

    # Create app with regular user override
    app = create_app()

    async def _override_get_session():
        try:
            yield db_session
            await db_session.flush()
        except Exception:
            await db_session.rollback()
            raise

    async def _override_current_user() -> User:
        return regular_user

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_current_user_required] = _override_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as client:
        response = await client.get("/api/v1/admin/overview")
        assert response.status_code == 403
        assert "superuser" in response.json()["detail"].lower()


# =============================================================================
# Test: Attention Inbox
# =============================================================================


@pytest.mark.asyncio
async def test_attention_inbox_empty(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test attention inbox with no incidents."""
    response = await client.get("/api/v1/admin/attention-inbox")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_attention_inbox_failed_build(
    client: AsyncClient,
    db_session: AsyncSession,
    test_report: Report,
    test_company: Company,
) -> None:
    """Test attention inbox shows failed builds."""
    # Create a failed build
    failed_build = ReleaseBuild(
        build_id=uuid4(),
        report_id=test_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.FAILED,
        theme_slug="default",
        base_path="/",
        locales=["ru"],
        error_message="Test error",
        created_at_utc=datetime.now(UTC),
    )
    db_session.add(failed_build)
    await db_session.flush()

    response = await client.get("/api/v1/admin/attention-inbox")
    assert response.status_code == 200

    data = response.json()
    assert len(data["items"]) > 0

    # Find our failed build
    failed_items = [item for item in data["items"] if item["type"] == "build_failed"]
    assert len(failed_items) > 0
    assert failed_items[0]["company_slug"] == test_company.slug


# =============================================================================
# Test: Builds Management
# =============================================================================


@pytest.mark.asyncio
async def test_list_builds(
    client: AsyncClient,
    db_session: AsyncSession,
    test_report: Report,
) -> None:
    """Test GET /admin/builds lists builds."""
    # Create a build
    build = ReleaseBuild(
        build_id=uuid4(),
        report_id=test_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.SUCCESS,
        theme_slug="default",
        base_path="/",
        locales=["ru"],
        created_at_utc=datetime.now(UTC),
    )
    db_session.add(build)
    await db_session.flush()

    response = await client.get("/api/v1/admin/builds?page=1&page_size=10")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_retry_build(
    client: AsyncClient,
    db_session: AsyncSession,
    test_report: Report,
) -> None:
    """Test POST /admin/builds/{id}/retry."""
    # Create a failed build
    build = ReleaseBuild(
        build_id=uuid4(),
        report_id=test_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.FAILED,
        theme_slug="default",
        base_path="/",
        locales=["ru"],
        error_message="Test error",
        created_at_utc=datetime.now(UTC),
    )
    db_session.add(build)
    await db_session.flush()

    response = await client.post(f"/api/v1/admin/builds/{build.build_id}/retry")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True

    # Verify build status changed
    await db_session.refresh(build)
    assert build.status == BuildStatus.QUEUED


@pytest.mark.asyncio
async def test_cancel_build(
    client: AsyncClient,
    db_session: AsyncSession,
    test_report: Report,
) -> None:
    """Test POST /admin/builds/{id}/cancel."""
    # Create a running build
    build = ReleaseBuild(
        build_id=uuid4(),
        report_id=test_report.report_id,
        build_type=BuildType.DRAFT,
        status=BuildStatus.RUNNING,
        theme_slug="default",
        base_path="/",
        locales=["ru"],
        created_at_utc=datetime.now(UTC),
    )
    db_session.add(build)
    await db_session.flush()

    response = await client.post(f"/api/v1/admin/builds/{build.build_id}/cancel")
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True

    # Verify build status changed
    await db_session.refresh(build)
    assert build.status == BuildStatus.FAILED
    assert "Cancelled" in build.error_message


# =============================================================================
# Test: Audit Events
# =============================================================================


@pytest.mark.asyncio
async def test_list_audit_events(
    client: AsyncClient,
    db_session: AsyncSession,
    test_company: Company,
    superuser: User,
) -> None:
    """Test GET /admin/audit-events lists events."""
    # Create an audit event
    event = AuditEvent.create(
        actor_type="user",
        actor_id=str(superuser.user_id),
        action="test_action",
        entity_type="test_entity",
        entity_id="test123",
        company_id=test_company.company_id,
    )
    db_session.add(event)
    await db_session.flush()

    response = await client.get("/api/v1/admin/audit-events?page=1&page_size=10")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_export_audit_events_csv(
    client: AsyncClient,
    db_session: AsyncSession,
    superuser: User,
) -> None:
    """Test GET /admin/audit-events/export returns CSV."""
    # Create an audit event
    event = AuditEvent.create(
        actor_type="user",
        actor_id=str(superuser.user_id),
        action="test_export",
        entity_type="test",
        entity_id="test123",
    )
    db_session.add(event)
    await db_session.flush()

    response = await client.get("/api/v1/admin/audit-events/export?limit=100")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "audit_events_" in response.headers["content-disposition"]

    # Verify CSV content
    csv_content = response.text
    assert "event_id" in csv_content
    assert "test_export" in csv_content


# =============================================================================
# Test: AI Incident Help
# =============================================================================


@pytest.mark.asyncio
async def test_incident_help_fallback(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test POST /admin/incidents/help returns static help when no OpenAI key."""
    response = await client.post(
        "/api/v1/admin/incidents/help",
        json={
            "incident_type": "build_failed",
            "error_code": "PDF_RENDER_ERROR",
            "status": "failed",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert "meaning" in data
    assert "possible_causes" in data
    assert "recommended_checks" in data
    assert "safe_actions" in data

    # Verify structure
    assert isinstance(data["possible_causes"], list)
    assert len(data["possible_causes"]) > 0


# =============================================================================
# Test: Company OpenAI Keys
# =============================================================================


@pytest.mark.asyncio
async def test_set_company_openai_key(
    client: AsyncClient,
    db_session: AsyncSession,
    test_company: Company,
) -> None:
    """Test POST /admin/companies/{id}/openai-key sets key."""
    response = await client.post(
        f"/api/v1/admin/companies/{test_company.company_id}/openai-key",
        json={"api_key": "sk-test-key-12345"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["status"] == "disabled"

    # Verify DB
    await db_session.refresh(test_company)
    assert test_company.openai_api_key_encrypted is not None
    assert test_company.openai_api_key_encrypted != "sk-test-key-12345"
    assert test_company.openai_api_key_encrypted.startswith("enc:")
    assert test_company.openai_key_status == OpenAIKeyStatus.DISABLED

    # Ensure decrypt returns original
    from app.services.secret_encryption import decrypt_secret

    assert decrypt_secret(test_company.openai_api_key_encrypted) == "sk-test-key-12345"


@pytest.mark.asyncio
async def test_disable_company_openai_key(
    client: AsyncClient,
    db_session: AsyncSession,
    test_company: Company,
) -> None:
    """Test POST /admin/companies/{id}/openai-key/disable."""
    # Set a key first
    test_company.openai_api_key_encrypted = "sk-test"
    test_company.openai_key_status = OpenAIKeyStatus.ACTIVE
    await db_session.flush()

    response = await client.post(
        f"/api/v1/admin/companies/{test_company.company_id}/openai-key/disable"
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["status"] == "disabled"

    # Verify DB
    await db_session.refresh(test_company)
    assert test_company.openai_key_status == OpenAIKeyStatus.DISABLED


# =============================================================================
# Test: Platform OpenAI Settings (global key + model)
# =============================================================================


@pytest.mark.asyncio
async def test_get_platform_openai_settings_default(
    client: AsyncClient,
) -> None:
    """GET /admin/openai/settings returns defaults."""
    response = await client.get("/api/v1/admin/openai/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["has_key"] is False
    assert data["key_status"] in ("disabled", "invalid", "active")
    assert data["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_set_platform_openai_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /admin/openai/key stores encrypted key and disables until validated."""
    response = await client.post(
        "/api/v1/admin/openai/key",
        json={"api_key": "sk-platform-test-12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_key"] is True
    assert data["key_status"] == "disabled"

    row = await db_session.get(PlatformAISettings, 1)
    assert row is not None
    assert row.openai_api_key_encrypted is not None
    assert row.openai_api_key_encrypted.startswith("enc:")
    assert row.openai_key_status == OpenAIKeyStatus.DISABLED

    from app.services.secret_encryption import decrypt_secret

    assert decrypt_secret(row.openai_api_key_encrypted) == "sk-platform-test-12345"


@pytest.mark.asyncio
async def test_set_platform_openai_model(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /admin/openai/model updates default model."""
    response = await client.post(
        "/api/v1/admin/openai/model",
        json={"model": "gpt-4o"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gpt-4o"

    row = await db_session.get(PlatformAISettings, 1)
    assert row is not None
    assert row.openai_model == "gpt-4o"


@pytest.mark.asyncio
async def test_delete_platform_openai_key(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """DELETE /admin/openai/key clears key."""
    # Set a key first
    await client.post("/api/v1/admin/openai/key", json={"api_key": "sk-platform-test-12345"})

    response = await client.delete("/api/v1/admin/openai/key")
    assert response.status_code == 200
    data = response.json()
    assert data["has_key"] is False
    assert data["key_status"] == "disabled"

    row = await db_session.get(PlatformAISettings, 1)
    assert row is not None
    assert row.openai_api_key_encrypted is None


# =============================================================================
# Test: AI Usage Tracking
# =============================================================================


@pytest.mark.asyncio
async def test_ai_usage_stats(
    client: AsyncClient,
    db_session: AsyncSession,
    test_company: Company,
) -> None:
    """Test GET /admin/ai-usage returns usage stats."""
    # Create usage events
    event1 = AIUsageEvent.create(
        feature=AIFeature.TRANSLATION,
        model="gpt-4o-mini",
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=Decimal("0.001"),
        company_id=test_company.company_id,
    )
    event2 = AIUsageEvent.create(
        feature=AIFeature.INCIDENT_HELP,
        model="gpt-4o-mini",
        input_tokens=200,
        output_tokens=100,
        estimated_cost_usd=Decimal("0.002"),
        company_id=None,  # Platform usage
    )
    db_session.add(event1)
    db_session.add(event2)
    await db_session.flush()

    response = await client.get("/api/v1/admin/ai-usage")
    assert response.status_code == 200

    data = response.json()
    assert "total_events" in data
    assert "total_cost_usd" in data
    assert "by_feature" in data
    assert "by_company" in data

    assert data["total_events"] >= 2
    assert "translation" in data["by_feature"]
    assert "incident_help" in data["by_feature"]


# =============================================================================
# Test: Health Check
# =============================================================================


@pytest.mark.asyncio
async def test_admin_health(client: AsyncClient) -> None:
    """Test GET /admin/health returns OK."""
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"

