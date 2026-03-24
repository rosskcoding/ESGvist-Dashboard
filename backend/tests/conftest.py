from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.ai_cache import ai_cache
from app.core.rate_limit import RateLimitMiddleware
from app.db.models import Base
from app.db.session import get_session
from app.events.registry import configure_event_session_factory, register_event_handlers
from app.main import app
from app.policies.ai_gate import AIRateGate

TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_db():
    RateLimitMiddleware._buckets.clear()
    AIRateGate._minute_events.clear()
    AIRateGate._hour_events.clear()
    AIRateGate._question_hashes.clear()
    AIRateGate._banned_until.clear()
    ai_cache.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    RateLimitMiddleware._buckets.clear()
    AIRateGate._minute_events.clear()
    AIRateGate._hour_events.clear()
    AIRateGate._question_hashes.clear()
    AIRateGate._banned_until.clear()
    ai_cache.clear()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_session] = override_get_session
configure_event_session_factory(TestSessionLocal)
register_event_handlers()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "password123", "full_name": "Test User"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
