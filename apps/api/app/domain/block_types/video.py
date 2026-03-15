"""
Video block schemas (validation-layer).

IMPORTANT:
- This module is used by `app.domain.block_types` registry for validating
  `Block.data_json` and `BlockI18n.fields_json` in core CRUD flows.
- Field names are aligned with the HTML template `templates/blocks/video.html`
  and the v2 schemas in `app.domain.schemas.block_types.video`.

Spec reference: VideoBlock spec v2 + 04_Content_Model.md
"""

from typing import Literal, Self

from pydantic import Field, model_validator

from .base import BlockDataSchema, BlockI18nSchema


class VideoBlockData(BlockDataSchema):
    """
    Video block data_json schema (non-localized).

    Expected keys (see `templates/blocks/video.html`):
    - source_type, source_url, provider_video_id, video_asset_id
    - poster_* fields (optional)
    - playback fields (start/end/autoplay/muted/loop)
    - embed_mode/aspect_ratio/consent_required
    """

    # --- Source ---
    source_type: Literal["youtube", "vimeo", "self_hosted", "external"] = Field(
        description="Video source type",
    )
    source_url: str | None = Field(
        default=None,
        max_length=2000,
        description="Original URL for youtube/vimeo/external sources",
    )
    provider_video_id: str | None = Field(
        default=None,
        max_length=50,
        description="Normalized provider video id (youtube/vimeo)",
    )
    video_asset_id: str | None = Field(
        default=None,
        description="Asset UUID for self-hosted video",
    )

    # --- Poster ---
    poster_asset_id: str | None = Field(
        default=None,
        description="Poster image asset UUID (generated/uploaded/provider)",
    )
    poster_time_ms: int | None = Field(
        default=None,
        ge=0,
        description="Timestamp for poster extraction (self_hosted only, milliseconds)",
    )
    poster_status: Literal["none", "pending", "ready", "failed"] = Field(
        default="none",
        description="Poster generation status",
    )
    poster_source: Literal["auto", "timestamp", "upload", "provider"] = Field(
        default="auto",
        description="Poster source type",
    )
    poster_job_id: str | None = Field(
        default=None,
        max_length=50,
        description="Poster generation job id (idempotency key)",
    )

    # --- Playback ---
    start_at_sec: int | None = Field(default=None, ge=0)
    end_at_sec: int | None = Field(default=None, ge=0)
    autoplay: bool = Field(default=False)
    muted: bool = Field(default=False)
    loop: bool = Field(default=False)

    # --- Layout ---
    embed_mode: Literal["inline", "full_width", "card"] = Field(default="inline")
    aspect_ratio: Literal["16:9", "4:3", "1:1", "9:16", "auto"] = Field(default="16:9")

    # --- Privacy & Export ---
    consent_required: bool = Field(
        default=True,
        description="Require consent before loading external embeds (GDPR-friendly)",
    )
    show_qr_in_export: bool = Field(default=False)
    include_transcript_in_export: bool = Field(default=False)

    # --- Optional assets & metadata ---
    captions_asset_id: str | None = Field(default=None, description="Captions asset UUID")
    duration_sec: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)

    # --- Status ---
    status: Literal["active", "processing", "broken"] = Field(default="active")
    last_error: str | None = Field(default=None, max_length=500)

    # =========================================================================
    # INVARIANTS (keep aligned with `app.domain.schemas.block_types.video`)
    # =========================================================================

    @model_validator(mode="after")
    def validate_invariants(self) -> Self:
        # INV-1: self_hosted ⇒ video_asset_id required
        if self.source_type == "self_hosted":
            if not self.video_asset_id:
                raise ValueError("video_asset_id is required for self_hosted source_type")

        # INV-2: youtube/vimeo/external ⇒ source_url required, video_asset_id must be null
        if self.source_type in ("youtube", "vimeo", "external"):
            if not self.source_url:
                raise ValueError(f"source_url is required for {self.source_type} source_type")
            if self.video_asset_id:
                raise ValueError(
                    f"video_asset_id must be null for {self.source_type} (use source_url)"
                )

        # INV-3: provider_video_id required for youtube/vimeo
        if self.source_type in ("youtube", "vimeo"):
            if not self.provider_video_id:
                raise ValueError(f"provider_video_id is required for {self.source_type}")

        # INV-4: poster_time_ms only for self_hosted
        if self.poster_time_ms is not None and self.source_type != "self_hosted":
            raise ValueError("poster_time_ms is only allowed for self_hosted videos")

        # INV-5: end_at_sec >= start_at_sec
        if self.start_at_sec is not None and self.end_at_sec is not None:
            if self.end_at_sec < self.start_at_sec:
                raise ValueError("end_at_sec must be >= start_at_sec")

        return self


class VideoBlockI18n(BlockI18nSchema):
    """Video block fields_json schema (localized)."""

    title: str = Field(default="", max_length=200, description="Video title")
    description: str = Field(default="", max_length=1000, description="Video description")
    transcript_text: str | None = Field(
        default=None,
        max_length=50000,
        description="Accessibility transcript (optional)",
    )
    alt_text: str = Field(default="", max_length=300, description="Alt text for poster image")
    cta_text: str = Field(default="Watch video", max_length=100)
