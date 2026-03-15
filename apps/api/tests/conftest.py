"""
Pytest fixtures for API tests.

Notes:
- Integration tests run against the FastAPI app in-process (ASGI) using httpx.AsyncClient.
- DB writes are isolated per-test using a single transaction that is rolled back after the test.
- Auth is bypassed by overriding `get_current_user_required` to return a seeded superuser.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.api.v1.auth import get_current_user_required
from app.domain.models import Base, Company, CompanyMembership, User
from app.domain.models.enums import CompanyStatus
from app.infra.database import get_session, test_engine
from app.main import create_app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _ensure_schema() -> None:
    """Create DB schema once for the test session (idempotent)."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def db_connection() -> AsyncConnection:
    """Single DB connection + transaction per test (rolled back after)."""
    conn = await test_engine.connect()
    trans = await conn.begin()
    try:
        yield conn
    finally:
        await trans.rollback()
        await conn.close()


@pytest_asyncio.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncSession:
    """AsyncSession bound to the per-test connection/transaction."""
    session_factory = async_sessionmaker(
        bind=db_connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def current_user(db_session: AsyncSession) -> User:
    """
    Seed and return a superuser used by dependency overrides.

    Uses is_superuser=True to bypass all RBAC permission checks.
    This represents a platform admin with full access.
    """
    user = User(
        user_id=uuid4(),
        email="test-admin@example.com",
        password_hash="not-used-in-tests",
        full_name="Test Admin",
        is_active=True,
        is_superuser=True,  # Bypasses all permission checks
        locale_scopes=None,
    )
    db_session.add(user)
    await db_session.flush()

    # Ensure the test user is a member of a company (multi-tenant requirement).
    company = Company(
        company_id=uuid4(),
        name=f"Test Company {uuid4()}",
        status=CompanyStatus.ACTIVE,
        created_by=user.user_id,
    )
    db_session.add(company)
    await db_session.flush()

    membership = CompanyMembership(
        company=company,
        user=user,
        is_active=True,
        created_by=user.user_id,
    )
    db_session.add(membership)
    await db_session.flush()

    # Refresh user to include memberships for video API tenant isolation
    await db_session.refresh(user, ["memberships"])

    return user


@pytest_asyncio.fixture
async def test_user(current_user: User) -> User:
    """
    Compatibility fixture used by dataset tests.

    Returns the seeded user from `current_user`.
    """
    return current_user


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession, current_user: User) -> Company:
    """
    Compatibility fixture used by dataset tests.

    Returns the active company of the seeded user from `current_user`.
    """
    membership_result = await db_session.execute(
        select(CompanyMembership).where(
            CompanyMembership.user_id == current_user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
    )
    membership = membership_result.scalars().first()
    assert membership is not None, "Expected an active CompanyMembership for current_user"

    company = await db_session.get(Company, membership.company_id)
    assert company is not None, "Expected Company to exist for membership.company_id"
    return company


@pytest_asyncio.fixture
async def app(db_session: AsyncSession, current_user: User):
    """FastAPI app with overridden DB session + auth."""
    app = create_app()
    current_user_id = current_user.user_id

    async def _override_get_session():
        # Use a per-request SAVEPOINT so expected HTTP errors (HTTPException, 409, etc.)
        # don't rollback the whole per-test transaction (which would erase seeded fixtures).
        nested = await db_session.begin_nested()
        try:
            yield db_session
        except Exception:
            await nested.rollback()
            raise
        finally:
            # If the endpoint didn't explicitly commit/rollback, close the SAVEPOINT now.
            if nested.is_active:
                await nested.commit()

    async def _override_current_user_required() -> User:
        # Return a fresh ORM instance per request to avoid MissingGreenlet on
        # expired attributes after rollbacks inside request handlers.
        user = await db_session.get(User, current_user_id)
        assert user is not None, "Expected current_user to exist in DB"
        await db_session.refresh(user, ["memberships", "role_assignments"])
        return user

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_current_user_required] = _override_current_user_required

    return app


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    """Unauthenticated client (auth is bypassed by dependency override)."""
    transport = ASGITransport(app=app)
    # NOTE: CSRFMiddleware exempts Bearer-authenticated requests. Since integration tests
    # override auth dependencies to return a seeded user (and don't perform a real login),
    # we attach a dummy Authorization header by default to avoid CSRF blocking every POST.
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": "Bearer test"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Alias for compatibility with existing tests."""
    return client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Compatibility fixture; auth is bypassed in tests."""
    return {}


@pytest_asyncio.fixture
async def unauthenticated_client() -> AsyncClient:
    """
    Truly unauthenticated client without auth dependency overrides.

    Used for testing that endpoints properly reject unauthenticated requests.
    """
    from app.main import create_app

    # Create fresh app without auth overrides
    fresh_app = create_app()
    transport = ASGITransport(app=fresh_app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        # No Authorization header
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def test_report_id(auth_client: AsyncClient) -> str:
    """Create and return a report_id for integration tests."""
    resp = await auth_client.post(
        "/api/v1/reports",
        json={
            "year": 2030,
            "title": "Test Report",
            "source_locale": "ru",
            "default_locale": "ru",
            "enabled_locales": ["ru"],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["report_id"]


@pytest_asyncio.fixture
async def test_section_id(auth_client: AsyncClient, test_report_id: str) -> str:
    """Create and return a section_id for integration tests."""
    resp = await auth_client.post(
        "/api/v1/sections",
        json={
            "report_id": test_report_id,
            "order_index": 0,
            "i18n": [{"locale": "ru", "title": "Test Section", "slug": "test-section"}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["section_id"]


@pytest_asyncio.fixture
async def test_block_id(
    auth_client: AsyncClient,
    test_report_id: str,
    test_section_id: str,
) -> str:
    """Create and return a block_id for integration tests."""
    resp = await auth_client.post(
        "/api/v1/blocks",
        json={
            "report_id": test_report_id,
            "section_id": test_section_id,
            "type": "text",
            "variant": "default",
            # Convention used by other integration tests: 0 means "append"
            "order_index": 0,
            "data_json": {},
            "i18n": [{"locale": "ru", "fields_json": {"body_html": "<p>Test</p>"}}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["block_id"]


@pytest_asyncio.fixture
async def test_sections(auth_client: AsyncClient, test_report_id: str) -> list[dict]:
    """Create a few sections for reorder tests."""
    created: list[dict] = []
    for idx in range(3):
        resp = await auth_client.post(
            "/api/v1/sections",
            json={
                "report_id": test_report_id,
                "order_index": idx,
                "i18n": [
                    {
                        "locale": "ru",
                        "title": f"Section {idx + 1}",
                        "slug": f"section-{idx + 1}",
                    }
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        created.append(resp.json())
    return created
