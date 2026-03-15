"""
Video block schemas.

Supports:
- YouTube/Vimeo embeds
- Self-hosted videos
- External video URLs (feature-flagged)
- Poster generation from timestamps
- Captions/transcripts

Spec reference: VideoBlock spec v2
"""

from enum import Enum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from .base import BlockDataSchema, BlockI18nSchema


class VideoSourceType(str, Enum):
    """Video source type."""

    YOUTUBE = "youtube"
    VIMEO = "vimeo"
    SELF_HOSTED = "self_hosted"
    EXTERNAL = "external"


class VideoEmbedMode(str, Enum):
    """Video embed display mode."""

    INLINE = "inline"
    FULL_WIDTH = "full_width"
    CARD = "card"


class VideoPosterStatus(str, Enum):
    """Poster generation status."""

    NONE = "none"           # No poster set
    PENDING = "pending"     # Generating
    READY = "ready"         # Available
    FAILED = "failed"       # Generation failed


class VideoPosterSource(str, Enum):
    """Poster source type."""

    AUTO = "auto"           # Default frame (3 sec)
    TIMESTAMP = "timestamp" # User-selected timestamp
    UPLOAD = "upload"       # Custom uploaded image
    PROVIDER = "provider"   # YouTube/Vimeo thumbnail


class VideoBlockData(BlockDataSchema):
    """
    Video block data_json schema.

    Stored in blocks.data_json (JSONB).

    Invariants (enforced via @model_validator):
    - INV-1: self_hosted ⇒ video_asset_id required
    - INV-2: youtube/vimeo/external ⇒ source_url required, video_asset_id null
    - INV-3: youtube/vimeo ⇒ provider_video_id required
    - INV-4: poster_time_ms only for self_hosted
    - INV-5: end_at_sec >= start_at_sec
    """

    # === Source ===
    source_type: VideoSourceType = Field(
        description="Video source type"
    )
    source_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Original video URL (youtube/vimeo/external)"
    )
    provider_video_id: str | None = Field(
        default=None,
        max_length=50,
        description="Extracted video ID for youtube/vimeo (normalized)"
    )
    video_asset_id: UUID | None = Field(
        default=None,
        description="Asset ID for self-hosted video"
    )

    # === Poster ===
    poster_asset_id: UUID | None = Field(
        default=None,
        description="Generated or uploaded poster image asset"
    )
    poster_time_ms: int | None = Field(
        default=None,
        ge=0,
        description="Timestamp for poster extraction (self-hosted only, milliseconds)"
    )
    poster_status: VideoPosterStatus = Field(
        default=VideoPosterStatus.NONE,
        description="Poster generation status"
    )
    poster_source: VideoPosterSource = Field(
        default=VideoPosterSource.AUTO,
        description="How poster was obtained"
    )
    poster_job_id: str | None = Field(
        default=None,
        max_length=50,
        description="Current poster generation job ID (idempotency)"
    )

    # === Playback ===
    start_at_sec: int | None = Field(
        default=None,
        ge=0,
        description="Start playback at this second"
    )
    end_at_sec: int | None = Field(
        default=None,
        ge=0,
        description="End playback at this second"
    )
    autoplay: bool = Field(
        default=False,
        description="Autoplay on load (respects browser policies)"
    )
    muted: bool = Field(
        default=False,
        description="Mute audio by default"
    )
    loop: bool = Field(
        default=False,
        description="Loop playback"
    )

    # === Layout ===
    embed_mode: VideoEmbedMode = Field(
        default=VideoEmbedMode.INLINE,
        description="Display mode for video embed"
    )
    aspect_ratio: Literal["16:9", "4:3", "1:1", "9:16", "auto"] = Field(
        default="16:9",
        description="Aspect ratio for embed container"
    )

    # === Privacy & Export ===
    consent_required: bool = Field(
        default=True,
        description="Require user consent before loading external embed (GDPR)"
    )
    show_qr_in_export: bool = Field(
        default=False,
        description="Include QR code in PDF/DOCX exports"
    )
    include_transcript_in_export: bool = Field(
        default=False,
        description="Include transcript text in print exports"
    )

    # === Captions ===
    captions_asset_id: UUID | None = Field(
        default=None,
        description="VTT/SRT captions file asset ID"
    )

    # === Metadata (auto-detected on upload) ===
    duration_sec: int | None = Field(
        default=None,
        ge=0,
        description="Video duration in seconds (auto-detected for self-hosted)"
    )
    width: int | None = Field(
        default=None,
        ge=1,
        description="Video width in pixels"
    )
    height: int | None = Field(
        default=None,
        ge=1,
        description="Video height in pixels"
    )

    # === Status ===
    status: Literal["active", "processing", "broken"] = Field(
        default="active",
        description="Block status"
    )
    last_error: str | None = Field(
        default=None,
        max_length=500,
        description="Last error message"
    )

    # =========================================================================
    # INVARIANTS
    # =========================================================================

    @model_validator(mode="after")
    def validate_source_invariants(self) -> Self:
        """
        Enforce source type invariants.

        Raises:
            ValueError: If invariants are violated
        """

        # INV-1: self_hosted ⇒ video_asset_id required
        if self.source_type == VideoSourceType.SELF_HOSTED:
            if not self.video_asset_id:
                raise ValueError(
                    "video_asset_id is required for self_hosted source type"
                )

        # INV-2: external sources ⇒ source_url required, video_asset_id null
        if self.source_type in (
            VideoSourceType.YOUTUBE,
            VideoSourceType.VIMEO,
            VideoSourceType.EXTERNAL,
        ):
            if not self.source_url:
                raise ValueError(
                    f"source_url is required for {self.source_type.value} source type"
                )
            if self.video_asset_id:
                raise ValueError(
                    f"video_asset_id must be null for {self.source_type.value} source type "
                    f"(use source_url instead)"
                )

        # INV-3: provider_video_id required for youtube/vimeo
        if self.source_type in (VideoSourceType.YOUTUBE, VideoSourceType.VIMEO):
            if not self.provider_video_id:
                raise ValueError(
                    f"provider_video_id is required for {self.source_type.value} "
                    f"(should be extracted from source_url)"
                )

        # INV-4: poster_time_ms only for self_hosted
        if self.poster_time_ms is not None:
            if self.source_type != VideoSourceType.SELF_HOSTED:
                raise ValueError(
                    "poster_time_ms is only allowed for self_hosted videos "
                    "(YouTube/Vimeo use provider thumbnails)"
                )

        # INV-5: end_at_sec >= start_at_sec
        if self.start_at_sec is not None and self.end_at_sec is not None:
            if self.end_at_sec < self.start_at_sec:
                raise ValueError(
                    f"end_at_sec ({self.end_at_sec}) must be >= start_at_sec ({self.start_at_sec})"
                )

        # INV-6: poster_time_ms <= duration (if known)
        # Note: This is clamped on backend, not validated here (duration may not be known yet)

        return self


class VideoBlockI18n(BlockI18nSchema):
    """
    Video block fields_json schema (localized content).

    Stored in block_i18n.fields_json.
    """

    title: str = Field(
        default="",
        max_length=200,
        description="Video title"
    )
    description: str = Field(
        default="",
        max_length=1000,
        description="Video description"
    )
    transcript_text: str | None = Field(
        default=None,
        max_length=50000,
        description="Full transcript for accessibility and export"
    )
    alt_text: str = Field(
        default="",
        max_length=300,
        description="Alt text for poster image (accessibility)"
    )
    cta_text: str = Field(
        default="Watch video",
        max_length=100,
        description="Call-to-action text for print exports (e.g., 'Watch video')"
    )

