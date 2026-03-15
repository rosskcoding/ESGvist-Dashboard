"""
Unit tests for VideoBlock schemas and validators.

Tests all invariants and edge cases.
"""

import pytest
from pydantic import ValidationError
from uuid import uuid4

from app.domain.schemas.block_types.video import (
    VideoBlockData,
    VideoBlockI18n,
    VideoSourceType,
    VideoPosterStatus,
    VideoPosterSource,
    VideoEmbedMode,
)


class TestVideoBlockDataInvariants:
    """Test VideoBlockData invariants."""

    def test_self_hosted_requires_video_asset_id(self):
        """INV-1: self_hosted => video_asset_id required."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.SELF_HOSTED,
                # Missing video_asset_id
            )
        assert "video_asset_id is required" in str(exc_info.value)

    def test_self_hosted_with_asset_id_ok(self):
        """self_hosted with video_asset_id is valid."""
        data = VideoBlockData(
            source_type=VideoSourceType.SELF_HOSTED,
            video_asset_id=uuid4(),
        )
        assert data.source_type == VideoSourceType.SELF_HOSTED
        assert data.video_asset_id is not None

    def test_youtube_requires_source_url(self):
        """INV-2: youtube => source_url required."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                # Missing source_url
            )
        assert "source_url is required" in str(exc_info.value)

    def test_youtube_rejects_video_asset_id(self):
        """INV-2: youtube => video_asset_id must be null."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                source_url="https://youtu.be/abc123",
                provider_video_id="abc123",
                video_asset_id=uuid4(),  # Should be null
            )
        assert "video_asset_id must be null" in str(exc_info.value)

    def test_youtube_requires_provider_video_id(self):
        """INV-3: youtube => provider_video_id required."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                source_url="https://youtu.be/abc123",
                # Missing provider_video_id
            )
        assert "provider_video_id is required" in str(exc_info.value)

    def test_youtube_valid(self):
        """Valid YouTube video."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/dQw4w9WgXcQ",
            provider_video_id="dQw4w9WgXcQ",
        )
        assert data.source_type == VideoSourceType.YOUTUBE
        assert data.provider_video_id == "dQw4w9WgXcQ"

    def test_vimeo_requires_source_url(self):
        """INV-2: vimeo => source_url required."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.VIMEO,
            )
        assert "source_url is required" in str(exc_info.value)

    def test_vimeo_requires_provider_video_id(self):
        """INV-3: vimeo => provider_video_id required."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.VIMEO,
                source_url="https://vimeo.com/123456",
            )
        assert "provider_video_id is required" in str(exc_info.value)

    def test_poster_time_ms_only_for_self_hosted(self):
        """INV-4: poster_time_ms only for self_hosted."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                source_url="https://youtu.be/abc",
                provider_video_id="abc",
                poster_time_ms=5000,  # Not allowed for YouTube
            )
        assert "poster_time_ms is only allowed for self_hosted" in str(exc_info.value)

    def test_poster_time_ms_valid_for_self_hosted(self):
        """poster_time_ms is valid for self_hosted."""
        data = VideoBlockData(
            source_type=VideoSourceType.SELF_HOSTED,
            video_asset_id=uuid4(),
            poster_time_ms=5000,
        )
        assert data.poster_time_ms == 5000

    def test_end_at_sec_must_be_after_start(self):
        """INV-5: end_at_sec >= start_at_sec."""
        with pytest.raises(ValidationError) as exc_info:
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                source_url="https://youtu.be/abc",
                provider_video_id="abc",
                start_at_sec=100,
                end_at_sec=50,  # Before start!
            )
        assert "end_at_sec" in str(exc_info.value)
        assert "must be >=" in str(exc_info.value)

    def test_equal_start_end_valid(self):
        """Equal start and end times are valid."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/abc",
            provider_video_id="abc",
            start_at_sec=100,
            end_at_sec=100,
        )
        assert data.start_at_sec == data.end_at_sec


class TestVideoBlockDataDefaults:
    """Test VideoBlockData default values."""

    def test_defaults(self):
        """Test default field values."""
        data = VideoBlockData(
            source_type=VideoSourceType.YOUTUBE,
            source_url="https://youtu.be/abc",
            provider_video_id="abc",
        )

        # Poster defaults
        assert data.poster_status == VideoPosterStatus.NONE
        assert data.poster_source == VideoPosterSource.AUTO
        assert data.poster_asset_id is None
        assert data.poster_time_ms is None
        assert data.poster_job_id is None

        # Playback defaults
        assert data.start_at_sec is None
        assert data.end_at_sec is None
        assert data.autoplay is False
        assert data.muted is False
        assert data.loop is False

        # Layout defaults
        assert data.embed_mode == VideoEmbedMode.INLINE
        assert data.aspect_ratio == "16:9"

        # Privacy defaults
        assert data.consent_required is True
        assert data.show_qr_in_export is False
        assert data.include_transcript_in_export is False

        # Status defaults
        assert data.status == "active"
        assert data.last_error is None
        assert data.duration_sec is None


class TestVideoBlockI18n:
    """Test VideoBlockI18n schema."""

    def test_defaults(self):
        """Test i18n default values."""
        i18n = VideoBlockI18n()

        assert i18n.title == ""
        assert i18n.description == ""
        assert i18n.transcript_text is None
        assert i18n.alt_text == ""
        assert i18n.cta_text == "Watch video"

    def test_custom_values(self):
        """Test custom i18n values."""
        i18n = VideoBlockI18n(
            title="My Video",
            description="A great video",
            transcript_text="Full transcript here",
            alt_text="Video poster image",
            cta_text="Watch now",
        )

        assert i18n.title == "My Video"
        assert i18n.description == "A great video"
        assert i18n.transcript_text == "Full transcript here"
        assert i18n.alt_text == "Video poster image"
        assert i18n.cta_text == "Watch now"

    def test_max_lengths(self):
        """Test field max lengths."""
        # Title max 200
        with pytest.raises(ValidationError):
            VideoBlockI18n(title="x" * 201)

        # Description max 1000
        with pytest.raises(ValidationError):
            VideoBlockI18n(description="x" * 1001)

        # Transcript max 50000
        with pytest.raises(ValidationError):
            VideoBlockI18n(transcript_text="x" * 50001)

        # Alt text max 300
        with pytest.raises(ValidationError):
            VideoBlockI18n(alt_text="x" * 301)

        # CTA text max 100
        with pytest.raises(ValidationError):
            VideoBlockI18n(cta_text="x" * 101)


class TestVideoBlockDataEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_external_source_type(self):
        """Test EXTERNAL source type."""
        data = VideoBlockData(
            source_type=VideoSourceType.EXTERNAL,
            source_url="https://cdn.example.com/video.mp4",
        )
        assert data.source_type == VideoSourceType.EXTERNAL
        assert data.source_url is not None

    def test_negative_poster_time_rejected(self):
        """Test negative poster_time_ms is rejected."""
        with pytest.raises(ValidationError):
            VideoBlockData(
                source_type=VideoSourceType.SELF_HOSTED,
                video_asset_id=uuid4(),
                poster_time_ms=-100,
            )

    def test_zero_poster_time_valid(self):
        """Test poster_time_ms=0 is valid."""
        data = VideoBlockData(
            source_type=VideoSourceType.SELF_HOSTED,
            video_asset_id=uuid4(),
            poster_time_ms=0,
        )
        assert data.poster_time_ms == 0

    def test_all_aspect_ratios(self):
        """Test all valid aspect ratios."""
        ratios = ["16:9", "4:3", "1:1", "9:16", "auto"]
        for ratio in ratios:
            data = VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                source_url="https://youtu.be/abc",
                provider_video_id="abc",
                aspect_ratio=ratio,
            )
            assert data.aspect_ratio == ratio

    def test_invalid_aspect_ratio(self):
        """Test invalid aspect ratio is rejected."""
        with pytest.raises(ValidationError):
            VideoBlockData(
                source_type=VideoSourceType.YOUTUBE,
                source_url="https://youtu.be/abc",
                provider_video_id="abc",
                aspect_ratio="21:9",  # Not in allowed list
            )

