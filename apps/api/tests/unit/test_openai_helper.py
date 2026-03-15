"""
Unit tests for OpenAI Helper Service.

Tests verify the per-company OpenAI key selection policy:
1. Company has active key → use company key
2. No company key → fallback to platform key
3. No keys available → raise OpenAIKeyNotAvailableError
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.models import Company, OpenAIKeyStatus
from app.domain.models import PlatformAISettings
from app.domain.models.enums import CompanyStatus
from app.services.openai_helper import (
    OpenAIKeyNotAvailableError,
    get_openai_key_for_company,
)
from app.services.secret_encryption import encrypt_secret


@pytest_asyncio.fixture
async def company_with_key(db_session: AsyncSession) -> Company:
    """Company with active OpenAI key."""
    company = Company(
        company_id=uuid4(),
        name="Company With Key",
        slug="company-with-key",
        status=CompanyStatus.ACTIVE,
        openai_api_key_encrypted=encrypt_secret("sk-company-key-123"),
        openai_key_status=OpenAIKeyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def company_without_key(db_session: AsyncSession) -> Company:
    """Company without OpenAI key."""
    company = Company(
        company_id=uuid4(),
        name="Company Without Key",
        slug="company-without-key",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


@pytest_asyncio.fixture
async def company_with_disabled_key(db_session: AsyncSession) -> Company:
    """Company with disabled OpenAI key."""
    company = Company(
        company_id=uuid4(),
        name="Company With Disabled Key",
        slug="company-disabled-key",
        status=CompanyStatus.ACTIVE,
        openai_api_key_encrypted="sk-disabled-key",
        openai_key_status=OpenAIKeyStatus.DISABLED,
    )
    db_session.add(company)
    await db_session.flush()
    return company


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.asyncio
async def test_company_has_active_key(
    db_session: AsyncSession,
    company_with_key: Company,
) -> None:
    """Test that company's active key is returned."""
    key = await get_openai_key_for_company(
        session=db_session,
        company_id=company_with_key.company_id,
    )

    assert key == "sk-company-key-123"


@pytest.mark.asyncio
async def test_company_without_key_uses_platform_key(
    db_session: AsyncSession,
    company_without_key: Company,
) -> None:
    """Test fallback to platform key when company has no key."""
    # Assuming platform key is configured (check settings.openai_api_key)
    if settings.openai_api_key:
        key = await get_openai_key_for_company(
            session=db_session,
            company_id=company_without_key.company_id,
        )

        assert key == settings.openai_api_key.get_secret_value()
    else:
        # If no platform key, should raise error
        with pytest.raises(OpenAIKeyNotAvailableError):
            await get_openai_key_for_company(
                session=db_session,
                company_id=company_without_key.company_id,
            )


@pytest.mark.asyncio
async def test_company_disabled_key_uses_platform_key(
    db_session: AsyncSession,
    company_with_disabled_key: Company,
) -> None:
    """Test that disabled company key falls back to platform key."""
    if settings.openai_api_key:
        key = await get_openai_key_for_company(
            session=db_session,
            company_id=company_with_disabled_key.company_id,
        )

        # Should NOT return disabled company key
        assert key != "sk-disabled-key"
        # Should return platform key
        assert key == settings.openai_api_key.get_secret_value()
    else:
        with pytest.raises(OpenAIKeyNotAvailableError):
            await get_openai_key_for_company(
                session=db_session,
                company_id=company_with_disabled_key.company_id,
            )


@pytest.mark.asyncio
async def test_platform_usage_no_company_id(
    db_session: AsyncSession,
) -> None:
    """Test platform-level usage (no company_id)."""
    if settings.openai_api_key:
        key = await get_openai_key_for_company(
            session=db_session,
            company_id=None,  # Platform-level
        )

        assert key == settings.openai_api_key.get_secret_value()
    else:
        with pytest.raises(OpenAIKeyNotAvailableError):
            await get_openai_key_for_company(
                session=db_session,
                company_id=None,
            )


@pytest.mark.asyncio
async def test_platform_settings_key_used_when_company_has_no_key(
    db_session: AsyncSession,
    company_without_key: Company,
) -> None:
    """PlatformAISettings active key should be used as platform fallback."""
    platform = await db_session.get(PlatformAISettings, 1)
    if platform is None:
        platform = PlatformAISettings(settings_id=1)
        db_session.add(platform)
        await db_session.flush()

    platform.openai_api_key_encrypted = encrypt_secret("sk-platform-key-123")
    platform.openai_key_status = OpenAIKeyStatus.ACTIVE
    platform.openai_model = "gpt-4o-mini"
    await db_session.flush()

    key = await get_openai_key_for_company(
        session=db_session,
        company_id=company_without_key.company_id,
    )
    assert key == "sk-platform-key-123"


@pytest.mark.asyncio
async def test_nonexistent_company(
    db_session: AsyncSession,
) -> None:
    """Test that nonexistent company_id falls back to platform key."""
    nonexistent_id = uuid4()

    if settings.openai_api_key:
        key = await get_openai_key_for_company(
            session=db_session,
            company_id=nonexistent_id,
        )

        assert key == settings.openai_api_key.get_secret_value()
    else:
        with pytest.raises(OpenAIKeyNotAvailableError):
            await get_openai_key_for_company(
                session=db_session,
                company_id=nonexistent_id,
            )

