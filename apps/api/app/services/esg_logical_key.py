"""
ESG Fact logical key hashing helpers.

We use a logical key hash (sha256 hex) to group versions of the "same" fact.
See docs/product/spec/22_ESG_Dashboard.md for the canonical key definition.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from uuid import UUID


def _norm_str(v: str | None) -> str | None:
    if v is None:
        return None
    vv = v.strip()
    return vv or None


def normalize_tags(tags: list[str] | None) -> list[str]:
    """
    Canonicalize tags for hashing.

    Rules (MVP):
    - trim whitespace
    - drop empty
    - lowercase
    - sort + uniq
    """
    if not tags:
        return []
    normalized: set[str] = set()
    for t in tags:
        if not isinstance(t, str):
            continue
        tt = t.strip()
        if not tt:
            continue
        normalized.add(tt.lower())
    return sorted(normalized)


def compute_fact_logical_key_hash(
    *,
    metric_id: UUID,
    period_start: date,
    period_end: date,
    period_type: str,
    is_ytd: bool,
    entity_id: UUID | None,
    location_id: UUID | None,
    segment_id: UUID | None,
    consolidation_approach: str | None,
    ghg_scope: str | None,
    scope2_method: str | None,
    scope3_category: str | None,
    tags: list[str] | None,
) -> str:
    """
    Compute sha256 hex hash for ESG fact logical key.

    Important:
    - `None` and missing keys must map to the same representation.
    - UUIDs and dates must be serialized canonically.
    """
    payload = {
        "metric_id": str(metric_id),
        "period_type": _norm_str(period_type) or "",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "is_ytd": bool(is_ytd),
        "entity_id": str(entity_id) if entity_id else None,
        "location_id": str(location_id) if location_id else None,
        "segment_id": str(segment_id) if segment_id else None,
        "consolidation_approach": _norm_str(consolidation_approach),
        "ghg_scope": _norm_str(ghg_scope),
        "scope2_method": _norm_str(scope2_method),
        "scope3_category": _norm_str(scope3_category),
        "tags": normalize_tags(tags),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

