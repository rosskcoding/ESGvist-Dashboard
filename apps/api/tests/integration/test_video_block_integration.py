"""
Integration tests for VideoBlock functionality.

Tests:
- Creating video blocks via API
- Schema validation in database context
- Block type registry integration
"""

import pytest
from uuid import uuid4

from app.domain.models.enums import BlockType
from app.domain.schemas.block_types.video import (
    VideoBlockData,
    VideoSourceType,
)
from app.domain.block_types import get_block_type_info
from app.domain.schemas.block_types import BLOCK_TYPE_REGISTRY


class TestVideoBlockTypeRegistry:
    """Test video block is properly registered."""

    def test_video_block_in_type_registry(self):
        """Video block should be registered in block_types registry."""
        info = get_block_type_info(BlockType.VIDEO)

        assert info is not None
        assert info.type == BlockType.VIDEO
        assert info.data_schema.__name__ == "VideoBlockData"
        assert info.description == "Video embed (YouTube/Vimeo/self-hosted)"

    def test_video_block_in_schema_registry(self):
        """Video block should be registered in schema registry."""
        schemas = BLOCK_TYPE_REGISTRY.get(BlockType.VIDEO.value)

        assert schemas is not None
        assert schemas.data_schema == VideoBlockData


class TestVideoBlockDataValidation:
    """Test VideoBlockData validation works in realistic scenarios."""

    def test_create_youtube_video_block(self):
        """Create a YouTube video block with valid data."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            provider_video_id="dQw4w9WgXcQ",
        )

        # Should serialize to dict (for JSONB storage)
        data_dict = data.model_dump()

        assert data_dict["source_type"] == "youtube"
        assert data_dict["source_url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert data_dict["provider_video_id"] == "dQw4w9WgXcQ"
        assert data_dict["consent_required"] is True
        assert data_dict["poster_status"] == "none"

    def test_create_self_hosted_video_block(self):
        """Create a self-hosted video block with valid data."""
        asset_id = uuid4()
        poster_id = uuid4()

        data = VideoBlockData(
            source_type=VideoSourceType.SELF_HOSTED,
            video_asset_id=asset_id,
            poster_asset_id=poster_id,
            poster_time_ms=5000,
            poster_status="ready",
        )

        # Use mode='json' to convert UUIDs to strings
        data_dict = data.model_dump(mode='json')

        assert data_dict["source_type"] == "self_hosted"
        assert data_dict["video_asset_id"] == str(asset_id)
        assert data_dict["poster_asset_id"] == str(poster_id)
        assert data_dict["poster_time_ms"] == 5000
        assert data_dict["consent_required"] is True  # Default

    def test_roundtrip_serialization(self):
        """Test data can be serialized and deserialized."""
        original = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/abc123",
            provider_video_id="abc123",
            start_at_sec=10,
            end_at_sec=60,
            autoplay=True,
            aspect_ratio="4:3",
        )

        # Serialize
        data_dict = original.model_dump()

        # Deserialize
        restored = VideoBlockData.model_validate(data_dict)

        assert restored.source_type == original.source_type
        assert restored.source_url == original.source_url
        assert restored.provider_video_id == original.provider_video_id
        assert restored.start_at_sec == original.start_at_sec
        assert restored.end_at_sec == original.end_at_sec
        assert restored.autoplay == original.autoplay
        assert restored.aspect_ratio == original.aspect_ratio

    def test_validation_error_preserves_context(self):
        """Validation errors should have helpful messages."""
        from pydantic import ValidationError

        try:
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                # Missing required source_url
            )
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            error_msg = str(e)
            assert "source_url is required" in error_msg
            assert "youtube" in error_msg.lower()


class TestVideoBlockEnumValues:
    """Test enum values are correct for database storage."""

    def test_block_type_enum_value(self):
        """BlockType.VIDEO should have correct string value."""
        assert BlockType.VIDEO.value == "video"

    def test_source_type_enum_values(self):
        """VideoSourceType enum should have correct values."""
        assert VideoSourceType.YOUTUBE.value == "youtube"
        assert VideoSourceType.VIMEO.value == "vimeo"
        assert VideoSourceType.SELF_HOSTED.value == "self_hosted"
        assert VideoSourceType.EXTERNAL.value == "external"

    def test_enum_from_string(self):
        """Should be able to create enum from database string value."""
        # This is how it works when loading from DB
        source_type = VideoSourceType("youtube")
        assert source_type == VideoSourceType.YOUTUBE

        block_type = BlockType("video")
        assert block_type == BlockType.VIDEO


class TestVideoBlockDefaults:
    """Test default values are sensible for real-world usage."""

    def test_youtube_video_minimal_data(self):
        """YouTube video with minimal required data should have good defaults."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/test",
            provider_video_id="test",
        )

        # Should have sensible defaults
        assert data.consent_required is True  # GDPR-friendly default
        assert data.autoplay is False  # Good UX
        assert data.muted is False
        assert data.loop is False
        assert data.aspect_ratio == "16:9"  # Most common
        assert data.embed_mode.value == "inline"
        assert data.show_qr_in_export is False
        assert data.include_transcript_in_export is False

    def test_self_hosted_video_consent_default(self):
        """Self-hosted videos should still default to consent=true (can override)."""
        data = VideoBlockData(
            source_type=VideoSourceType.SELF_HOSTED,
            video_asset_id=uuid4(),
        )

        # Even self-hosted defaults to consent_required=true
        # (User can override if they want)
        assert data.consent_required is True


class TestVideoBlockDataCompatibility:
    """Test compatibility with existing block data patterns."""

    def test_can_be_stored_in_jsonb(self):
        """VideoBlockData should be compatible with JSONB storage."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/test",
            provider_video_id="test",
        )

        # Convert to dict for JSONB
        data_dict = data.model_dump()

        # Should be JSON-serializable
        import json
        json_str = json.dumps(data_dict)

        # Should be deserializable
        parsed = json.loads(json_str)

        # Should be valid VideoBlockData
        restored = VideoBlockData.model_validate(parsed)
        assert restored.source_type == VideoSourceType.YOUTUBE

    def test_optional_fields_are_nullable(self):
        """Optional fields should serialize to null, not omitted."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/test",
            provider_video_id="test",
        )

        data_dict = data.model_dump()

        # Optional fields should be present with null values
        assert "poster_asset_id" in data_dict
        assert data_dict["poster_asset_id"] is None
        assert "start_at_sec" in data_dict
        assert data_dict["start_at_sec"] is None

