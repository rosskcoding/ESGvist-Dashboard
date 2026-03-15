"""
Unit tests for Pydantic schemas.

Tests validation rules from SYSTEM_REGISTRY.md.
"""

import pytest
from pydantic import ValidationError

from app.domain.schemas import (
    BlockCreate,
    BlockI18nCreate,
    ReportCreate,
    SectionCreate,
    SectionI18nCreate,
    UserCreate,
)
from app.domain.schemas.enums import (
    BlockTypeEnum,
    ContentStatusEnum,
    LocaleEnum,
)


class TestReportSchemas:
    """Tests for Report schemas."""

    def test_report_create_valid(self):
        """Valid report creation."""
        report = ReportCreate(
            year=2024,
            title="ESG Report 2024",
            source_locale=LocaleEnum.RU,
            default_locale=LocaleEnum.RU,
            enabled_locales=["ru", "en"],
            release_locales=["ru"],
        )
        assert report.year == 2024
        assert report.title == "ESG Report 2024"

    def test_report_year_validation(self):
        """Year must be between 2000 and 2100."""
        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=1999,
                title="Test",
                enabled_locales=["ru"],
            )
        assert "year" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=2101,
                title="Test",
                enabled_locales=["ru"],
            )
        assert "year" in str(exc_info.value)

    def test_report_title_max_length(self):
        """Title max length is 200."""
        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=2024,
                title="x" * 201,
                enabled_locales=["ru"],
            )
        assert "title" in str(exc_info.value)

    def test_report_source_locale_in_enabled(self):
        """source_locale must be in enabled_locales."""
        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=2024,
                title="Test",
                source_locale=LocaleEnum.KK,
                enabled_locales=["ru", "en"],
            )
        assert "source_locale" in str(exc_info.value)

    def test_report_default_locale_in_enabled(self):
        """default_locale must be in enabled_locales."""
        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=2024,
                title="Test",
                default_locale=LocaleEnum.KK,
                enabled_locales=["ru", "en"],
            )
        assert "default_locale" in str(exc_info.value)

    def test_report_release_locales_subset(self):
        """release_locales must be subset of enabled_locales."""
        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=2024,
                title="Test",
                enabled_locales=["ru", "en"],
                release_locales=["ru", "kk"],  # kk not in enabled
            )
        assert "release_locales" in str(exc_info.value)

    def test_report_invalid_locale(self):
        """Invalid locale rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ReportCreate(
                year=2024,
                title="Test",
                enabled_locales=["ru", "xx"],  # xx invalid
            )
        assert "Invalid locales" in str(exc_info.value)


class TestUserSchemas:
    """Tests for User schemas."""

    def test_user_create_valid(self):
        """Valid user creation."""
        user = UserCreate(
            email="test@example.com",
            full_name="Test User",
            password="SecurePassword123!",
        )
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"

    def test_user_email_validation(self):
        """Email must be valid."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="not-an-email",
                full_name="Test",
                password="securepassword123",
            )
        assert "email" in str(exc_info.value)

    def test_user_password_min_length(self):
        """Password must be at least 12 characters."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                full_name="Test",
                password="Short1!",
            )
        assert "password" in str(exc_info.value)

    def test_user_password_requires_uppercase(self):
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                full_name="Test",
                password="lowercasepassword123!",
            )
        assert "uppercase" in str(exc_info.value)

    def test_user_password_requires_lowercase(self):
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                full_name="Test",
                password="UPPERCASEPASSWORD123!",
            )
        assert "lowercase" in str(exc_info.value)

    def test_user_password_requires_digit(self):
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                full_name="Test",
                password="SecurePasswordNoDigits!",
            )
        assert "digit" in str(exc_info.value)

    def test_user_password_requires_special(self):
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                full_name="Test",
                password="SecurePassword1234",
            )
        assert "special" in str(exc_info.value)

    def test_user_locale_scopes_validation(self):
        """locale_scopes must contain valid locales."""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                full_name="Test",
                password="securepassword123",
                locale_scopes=["ru", "xx"],  # xx invalid
            )
        assert "Invalid locales" in str(exc_info.value)

    def test_user_locale_scopes_valid(self):
        """Valid locale_scopes accepted."""
        user = UserCreate(
            email="test@example.com",
            full_name="Test",
            password="SecurePassword123!",
            locale_scopes=["en", "kk"],
        )
        assert user.locale_scopes == ["en", "kk"]


class TestBlockSchemas:
    """Tests for Block schemas."""

    def test_block_create_valid(self):
        """Valid block creation."""
        from uuid import uuid4

        block = BlockCreate(
            report_id=uuid4(),
            section_id=uuid4(),
            type=BlockTypeEnum.TEXT,
            data_json={},
        )
        assert block.type == BlockTypeEnum.TEXT
        assert block.variant.value == "default"

    def test_block_data_json_forbids_inline_locale_map(self):
        """Block.data_json must not contain localized maps (SYSTEM_REGISTRY F.3)."""
        from uuid import uuid4

        with pytest.raises(ValidationError) as exc_info:
            BlockCreate(
                report_id=uuid4(),
                section_id=uuid4(),
                type=BlockTypeEnum.TABLE,
                data_json={
                    "caption": {"ru": "Caption", "en": "Caption"},
                    "rows": 1,
                },
            )
        assert "Forbidden inline locale map" in str(exc_info.value)

    def test_block_i18n_create_valid(self):
        """Valid block i18n creation."""
        i18n = BlockI18nCreate(
            locale=LocaleEnum.EN,
            status=ContentStatusEnum.DRAFT,
            fields_json={"body_html": "<p>Test</p>"},
        )
        assert i18n.locale == LocaleEnum.EN
        assert i18n.status == ContentStatusEnum.DRAFT


class TestSectionSchemas:
    """Tests for Section schemas."""

    def test_section_create_valid(self):
        """Valid section creation."""
        from uuid import uuid4

        section = SectionCreate(
            report_id=uuid4(),
            i18n=[
                SectionI18nCreate(
                    locale=LocaleEnum.EN,
                    title="About company",
                    slug="about-company",
                )
            ],
        )
        assert len(section.i18n) == 1
        assert section.i18n[0].title == "About company"

    def test_section_requires_i18n(self):
        """Section requires at least one i18n."""
        from uuid import uuid4

        with pytest.raises(ValidationError) as exc_info:
            SectionCreate(
                report_id=uuid4(),
                i18n=[],  # Empty
            )
        assert "i18n" in str(exc_info.value)

    def test_section_slug_pattern(self):
        """Slug must match pattern."""
        with pytest.raises(ValidationError) as exc_info:
            SectionI18nCreate(
                locale=LocaleEnum.EN,
                title="Test",
                slug="Invalid Slug!",  # Invalid chars
            )
        assert "slug" in str(exc_info.value)

    def test_section_slug_valid(self):
        """Valid slug accepted."""
        i18n = SectionI18nCreate(
            locale=LocaleEnum.EN,
            title="Test",
            slug="valid-slug-123",
        )
        assert i18n.slug == "valid-slug-123"
