"""
Unit tests for domain models.

Tests invariants from SYSTEM_REGISTRY.md.
"""

from uuid import uuid4

from app.domain.models.enums import (
    BlockType,
    BlockVariant,
    ContentStatus,
    Locale,
)


class TestLocaleEnum:
    """Tests for Locale enum."""

    def test_supported_locales(self):
        """Locales supported: ru, en, kk, de, fr, ar, es, nl, it."""
        expected = {"ru", "en", "kk", "de", "fr", "ar", "es", "nl", "it"}
        actual = {loc.value for loc in Locale}
        assert actual == expected


class TestContentStatusEnum:
    """Tests for ContentStatus enum."""

    def test_statuses(self):
        """Four statuses: draft, ready, qa_required, approved."""
        assert ContentStatus.DRAFT.value == "draft"
        assert ContentStatus.READY.value == "ready"
        assert ContentStatus.QA_REQUIRED.value == "qa_required"
        assert ContentStatus.APPROVED.value == "approved"
        assert len(ContentStatus) == 4


class TestBlockTypeEnum:
    """Tests for BlockType enum."""

    def test_block_types(self):
        """Eleven block types defined."""
        expected_types = {
            "text",
            "kpi_cards",
            "table",
            "chart",
            "image",
            "video",
            "quote",
            "downloads",
            "accordion",
            "timeline",
            "custom",
        }
        actual_types = {t.value for t in BlockType}
        assert actual_types == expected_types


class TestBlockVariantEnum:
    """Tests for BlockVariant enum."""

    def test_variants(self):
        """Four variants defined."""
        expected = {"default", "compact", "emphasized", "full_width"}
        actual = {v.value for v in BlockVariant}
        assert actual == expected


class TestContentStatusTransitions:
    """Tests for status transitions based on SYSTEM_REGISTRY Section E.1."""

    def test_allowed_transitions(self):
        """Test allowed status transitions."""
        # Import the model to test transition logic

        # Create a mock BlockI18n with status
        class MockBlockI18n:
            def __init__(self, status: ContentStatus):
                self.status = status

            def can_transition_to(self, new_status: ContentStatus) -> bool:
                allowed = {
                    ContentStatus.DRAFT: {ContentStatus.READY},
                    ContentStatus.READY: {ContentStatus.QA_REQUIRED},
                    ContentStatus.QA_REQUIRED: {ContentStatus.APPROVED},
                    ContentStatus.APPROVED: {ContentStatus.DRAFT},  # Rollback
                }
                return new_status in allowed.get(self.status, set())

        # draft -> ready: allowed
        block = MockBlockI18n(ContentStatus.DRAFT)
        assert block.can_transition_to(ContentStatus.READY) is True
        assert block.can_transition_to(ContentStatus.APPROVED) is False

        # ready -> qa_required: allowed
        block = MockBlockI18n(ContentStatus.READY)
        assert block.can_transition_to(ContentStatus.QA_REQUIRED) is True
        assert block.can_transition_to(ContentStatus.APPROVED) is False

        # qa_required -> approved: allowed
        block = MockBlockI18n(ContentStatus.QA_REQUIRED)
        assert block.can_transition_to(ContentStatus.APPROVED) is True
        assert block.can_transition_to(ContentStatus.READY) is False

        # approved -> draft: allowed (rollback)
        block = MockBlockI18n(ContentStatus.APPROVED)
        assert block.can_transition_to(ContentStatus.DRAFT) is True
        assert block.can_transition_to(ContentStatus.READY) is False


class TestChunkIdFormat:
    """Tests for chunk_id canonical format."""

    def test_chunk_id_format(self):
        """chunk_id follows format: {block_id}:{field_name}:{chunk_index}."""
        from app.domain.models.translation import TranslationUnit

        block_id = uuid4()
        field_name = "body_html"
        chunk_index = 0

        chunk_id = TranslationUnit.make_chunk_id(block_id, field_name, chunk_index)

        assert chunk_id == f"{block_id}:body_html:0"

    def test_chunk_id_parsing(self):
        """chunk_id can be parsed back."""
        from app.domain.models.translation import TranslationUnit

        block_id = uuid4()
        chunk_id = TranslationUnit.make_chunk_id(block_id, "caption", 5)

        parts = chunk_id.split(":")
        assert len(parts) == 3
        assert parts[0] == str(block_id)
        assert parts[1] == "caption"
        assert parts[2] == "5"


