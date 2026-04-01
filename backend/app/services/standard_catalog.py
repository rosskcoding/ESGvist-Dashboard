from dataclasses import dataclass
import re

from app.db.models.standard import Standard
from app.schemas.standards import StandardOut


_SASB_GROUPS: dict[str, tuple[str, str]] = {
    "CG": ("consumer-goods", "Consumer Goods"),
    "EM": ("extractives-minerals", "Extractives & Minerals Processing"),
    "FB": ("food-beverage", "Food & Beverage"),
    "FN": ("financials", "Financials"),
    "HC": ("health-care", "Health Care"),
    "IF": ("infrastructure", "Infrastructure"),
    "RR": ("renewable-resources", "Renewable Resources & Alternative Energy"),
    "RT": ("resource-transformation", "Resource Transformation"),
    "SV": ("services", "Services"),
    "TC": ("technology-communications", "Technology & Communications"),
    "TR": ("transportation", "Transportation"),
}


@dataclass(frozen=True)
class StandardCatalogMeta:
    family_code: str
    family_name: str
    catalog_group_code: str
    catalog_group_name: str
    is_attachable: bool


def resolve_standard_catalog_meta(code: str, name: str) -> StandardCatalogMeta:
    normalized_code = (code or "").strip()
    normalized_name = (name or "").strip()

    if normalized_code == "GRI":
        return StandardCatalogMeta(
            family_code="GRI",
            family_name="GRI Standards",
            catalog_group_code="family",
            catalog_group_name="Family",
            is_attachable=False,
        )

    gri_match = re.fullmatch(r"GRI\s+(\d+)", normalized_code)
    if gri_match:
        gri_number = int(gri_match.group(1))
        if gri_number in {1, 2, 3}:
            group_code = "universal"
            group_name = "Universal Standards"
        elif 11 <= gri_number <= 14:
            group_code = "sector"
            group_name = "Sector Standards"
        else:
            group_code = "topic"
            group_name = "Topic Standards"

        return StandardCatalogMeta(
            family_code="GRI",
            family_name="GRI Standards",
            catalog_group_code=group_code,
            catalog_group_name=group_name,
            is_attachable=True,
        )

    sasb_match = re.fullmatch(r"SASB-([A-Z]{2})-[A-Z0-9]+", normalized_code)
    if sasb_match:
        group_code, group_name = _SASB_GROUPS.get(
            sasb_match.group(1),
            ("industry-standards", "Industry Standards"),
        )
        return StandardCatalogMeta(
            family_code="SASB",
            family_name="SASB Standards",
            catalog_group_code=group_code,
            catalog_group_name=group_name,
            is_attachable=True,
        )

    if normalized_code.startswith("IFRS-S"):
        return StandardCatalogMeta(
            family_code="IFRS",
            family_name="IFRS Sustainability Disclosure Standards",
            catalog_group_code="issb",
            catalog_group_name="ISSB Standards",
            is_attachable=True,
        )

    if normalized_code == "ESRS":
        return StandardCatalogMeta(
            family_code="ESRS",
            family_name="ESRS",
            catalog_group_code="family",
            catalog_group_name="Family",
            is_attachable=False,
        )

    esrs_cross_cutting_match = re.fullmatch(r"ESRS\s+([12])", normalized_code)
    if esrs_cross_cutting_match:
        return StandardCatalogMeta(
            family_code="ESRS",
            family_name="ESRS",
            catalog_group_code="cross-cutting",
            catalog_group_name="Cross-cutting Standards",
            is_attachable=True,
        )

    esrs_match = re.fullmatch(r"ESRS\s+([ESG])(\d+)", normalized_code)
    if esrs_match:
        domain_code = esrs_match.group(1)
        if domain_code == "E":
            group_code = "environmental"
            group_name = "Environmental Standards"
        elif domain_code == "S":
            group_code = "social"
            group_name = "Social Standards"
        else:
            group_code = "governance"
            group_name = "Governance Standards"

        return StandardCatalogMeta(
            family_code="ESRS",
            family_name="ESRS",
            catalog_group_code=group_code,
            catalog_group_name=group_name,
            is_attachable=True,
        )

    if normalized_code.startswith("UAE-LAW-"):
        return StandardCatalogMeta(
            family_code="UAE-LAW",
            family_name="UAE Laws & Regulations",
            catalog_group_code="federal-decree-laws",
            catalog_group_name="Federal Decree-Laws",
            is_attachable=True,
        )

    fallback_family_code = normalized_code.split("-", 1)[0].split(" ", 1)[0] or normalized_code
    fallback_family_name = normalized_name or fallback_family_code
    return StandardCatalogMeta(
        family_code=fallback_family_code,
        family_name=fallback_family_name,
        catalog_group_code="standards",
        catalog_group_name="Standards",
        is_attachable=True,
    )


def build_standard_out(standard: Standard) -> StandardOut:
    meta = resolve_standard_catalog_meta(standard.code, standard.name)
    return StandardOut(
        id=standard.id,
        code=standard.code,
        name=standard.name,
        version=standard.version,
        jurisdiction=standard.jurisdiction,
        effective_from=standard.effective_from,
        effective_to=standard.effective_to,
        is_active=standard.is_active,
        family_code=meta.family_code,
        family_name=meta.family_name,
        catalog_group_code=meta.catalog_group_code,
        catalog_group_name=meta.catalog_group_name,
        is_attachable=meta.is_attachable,
    )
