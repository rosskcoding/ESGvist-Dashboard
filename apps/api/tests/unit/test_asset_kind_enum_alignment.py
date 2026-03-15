from app.domain.models.enums import AssetKind
from app.domain.schemas.enums import AssetKindEnum


def test_asset_kind_model_and_schema_enums_are_aligned() -> None:
    assert {item.value for item in AssetKind} == {item.value for item in AssetKindEnum}


def test_asset_kind_supports_captions() -> None:
    assert AssetKind.CAPTIONS.value == "captions"
    assert AssetKindEnum.CAPTIONS.value == "captions"
