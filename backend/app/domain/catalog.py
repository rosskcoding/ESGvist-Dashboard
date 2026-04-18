from __future__ import annotations

import re


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_catalog_token(value: str) -> str:
    normalized = _NON_ALNUM_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or "metric"


def build_shared_element_key(
    code: str,
    *,
    owner_layer: str = "internal_catalog",
    organization_id: int | None = None,
) -> str:
    token = normalize_catalog_token(code)
    if owner_layer == "tenant_catalog":
        if organization_id is None:
            raise ValueError("organization_id is required for tenant catalog shared elements")
        return f"tenant:{organization_id}:{token}"
    return f"internal:{token}"


def build_disclosure_key(standard_code: str, disclosure_code: str) -> str:
    return f"{normalize_catalog_token(standard_code)}::{normalize_catalog_token(disclosure_code)}"


def build_requirement_item_key(
    standard_code: str,
    disclosure_code: str,
    item_code: str | None,
    item_name: str | None = None,
) -> str:
    item_token = normalize_catalog_token(item_code or item_name or "item")
    return (
        f"{normalize_catalog_token(standard_code)}::"
        f"{normalize_catalog_token(disclosure_code)}::"
        f"{item_token}"
    )


def prepare_shared_element_defaults(
    *,
    code: str,
    owner_layer: str = "internal_catalog",
    organization_id: int | None = None,
    is_custom: bool | None = None,
    lifecycle_status: str = "active",
    source_element_key: str | None = None,
) -> dict:
    return {
        "element_key": build_shared_element_key(
            code,
            owner_layer=owner_layer,
            organization_id=organization_id,
        ),
        "owner_layer": owner_layer,
        "organization_id": organization_id,
        "source_element_key": source_element_key,
        "lifecycle_status": lifecycle_status,
        "is_custom": owner_layer == "tenant_catalog" if is_custom is None else is_custom,
    }
