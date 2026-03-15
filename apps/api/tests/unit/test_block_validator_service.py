"""
Unit tests for block validation service (app.services.block_validator).
"""

from uuid import uuid4

from app.domain.models.block import Block, BlockI18n
from app.domain.models.enums import BlockType, BlockVariant, ContentStatus, Locale
from app.services.block_validator import ValidationSeverity, block_validator


class TestBlockValidator:
    def test_text_empty_body_is_warning(self):
        block = Block(
            report_id=uuid4(),
            section_id=uuid4(),
            type=BlockType.TEXT,
            variant=BlockVariant.DEFAULT,
            order_index=0,
            data_json={},
            qa_flags_global=[],
            custom_override_enabled=False,
            owner_user_id=None,
            version=1,
        )
        i18n = BlockI18n(
            block_id=block.block_id,
            locale=Locale.RU,
            status=ContentStatus.DRAFT,
            qa_flags_by_locale=[],
            fields_json={"body_html": ""},
        )

        result = block_validator.validate(block, i18n=i18n, locale=Locale.RU)
        assert result.can_publish is True
        assert result.warning_count == 1
        assert any(i.code == "EMPTY_CONTENT" and i.severity == ValidationSeverity.WARNING for i in result.issues)

    def test_validate_selects_i18n_by_locale(self):
        block = Block(
            report_id=uuid4(),
            section_id=uuid4(),
            type=BlockType.TEXT,
            variant=BlockVariant.DEFAULT,
            order_index=0,
            data_json={},
            qa_flags_global=[],
            custom_override_enabled=False,
            owner_user_id=None,
            version=1,
        )
        i18n_ru = BlockI18n(
            block_id=block.block_id,
            locale=Locale.RU,
            status=ContentStatus.DRAFT,
            qa_flags_by_locale=[],
            fields_json={"body_html": ""},
        )
        i18n_en = BlockI18n(
            block_id=block.block_id,
            locale=Locale.EN,
            status=ContentStatus.DRAFT,
            qa_flags_by_locale=[],
            fields_json={"body_html": "<p>OK</p>"},
        )
        block.i18n = [i18n_ru, i18n_en]

        # Validate EN content (should not produce EMPTY_CONTENT warning)
        result = block_validator.validate(block, i18n=None, locale=Locale.EN)
        assert result.warning_count == 0

    def test_chart_missing_data_is_error(self):
        block = Block(
            report_id=uuid4(),
            section_id=uuid4(),
            type=BlockType.CHART,
            variant=BlockVariant.DEFAULT,
            order_index=0,
            data_json={"chart_type": "bar", "data_source": {"type": "inline"}},
            qa_flags_global=[],
            custom_override_enabled=False,
            owner_user_id=None,
            version=1,
        )
        i18n = BlockI18n(
            block_id=block.block_id,
            locale=Locale.RU,
            status=ContentStatus.DRAFT,
            qa_flags_by_locale=[],
            fields_json={"caption": "C", "insight_text": ""},
        )

        result = block_validator.validate(block, i18n=i18n, locale=Locale.RU)
        assert result.can_publish is False
        assert result.error_count >= 1
        assert any(i.code == "MISSING_DATA" and i.severity == ValidationSeverity.ERROR for i in result.issues)
        assert any(i.code == "REQUIRED_INSIGHT" and i.severity == ValidationSeverity.ERROR for i in result.issues)





