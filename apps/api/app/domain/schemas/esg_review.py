"""
ESG Fact Review schemas.

Includes:
- Review comments (threaded per logical key)
- Timeline events (audit log projection)
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .common import BaseSchema, TimestampSchema


class EsgFactReviewCommentCreate(BaseSchema):
    body_md: str = Field(min_length=1, max_length=8000)


class EsgFactReviewCommentDTO(TimestampSchema):
    comment_id: UUID
    company_id: UUID
    logical_key_hash: str
    fact_id: UUID
    body_md: str
    created_by: UUID | None = None

    created_by_name: str | None = None
    created_by_email: str | None = None


class EsgFactTimelineEventDTO(BaseSchema):
    event_id: UUID
    timestamp_utc: datetime
    actor_type: str
    actor_id: str
    actor_name: str | None = None
    actor_email: str | None = None

    action: str
    entity_type: str
    entity_id: str

    metadata_json: dict | None = None

