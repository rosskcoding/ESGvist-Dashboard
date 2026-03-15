"""
Unit tests for DatasetImportService.
"""

import pytest

from app.services.dataset_import import DatasetImportService


@pytest.mark.asyncio
async def test_detect_csv_delimiter():
    """Test CSV delimiter detection."""
    service = DatasetImportService()

    # Comma-separated
    csv_comma = b"col1,col2,col3\nval1,val2,val3"
    assert service.detect_csv_delimiter(csv_comma) == ','

    # Semicolon-separated
    csv_semi = b"col1;col2;col3\nval1;val2;val3"
    assert service.detect_csv_delimiter(csv_semi) == ';'

    # Tab-separated
    csv_tab = b"col1\tcol2\tcol3\nval1\tval2\tval3"
    assert service.detect_csv_delimiter(csv_tab) == '\t'


@pytest.mark.asyncio
async def test_detect_encoding():
    """Test encoding detection."""
    service = DatasetImportService()

    # UTF-8
    utf8_content = "Hello world".encode('utf-8')
    assert service.detect_encoding(utf8_content) == 'utf-8'

    # UTF-8 with BOM
    utf8_bom = b'\xef\xbb\xbf' + "Hello".encode('utf-8')
    assert service.detect_encoding(utf8_bom) == 'utf-8-sig'


@pytest.mark.asyncio
async def test_infer_column_type():
    """Test column type inference."""
    service = DatasetImportService()

    # Number column
    numbers = [100, 200, 300, 400]
    assert service.infer_column_type(numbers) == "number"

    # Percent column
    percents = ["15%", "20%", "25%", "30%"]
    assert service.infer_column_type(percents) == "percent"

    # Text column
    texts = ["Apple", "Banana", "Cherry"]
    assert service.infer_column_type(texts) == "text"

    # Date column (year)
    years = ["2020", "2021", "2022", "2023"]
    assert service.infer_column_type(years) == "date"

    # Date column (ISO format)
    dates = ["2024-01-01", "2024-02-01", "2024-03-01"]
    assert service.infer_column_type(dates) == "date"


@pytest.mark.asyncio
async def test_parse_value_number():
    """Test parsing numeric values."""
    service = DatasetImportService()

    # Simple number
    assert service.parse_value("123", "number") == 123.0

    # Decimal with comma (European format)
    assert service.parse_value("123,45", "number") == 123.45

    # Thousand separator (space)
    assert service.parse_value("1 000", "number") == 1000.0

    # Combined
    assert service.parse_value("1 234,56", "number") == 1234.56

    # Percent
    assert service.parse_value("15%", "percent") == 15.0

    # N/A values
    assert service.parse_value("N/A", "number") is None
    assert service.parse_value("—", "number") is None


@pytest.mark.asyncio
async def test_import_csv_preview():
    """Test CSV import preview."""
    service = DatasetImportService()

    csv_content = b"""year,revenue,profit
2022,1000,100
2023,1200,150
2024,1500,200"""

    preview = await service.import_csv_preview(csv_content, "test.csv")

    assert len(preview.detected_columns) == 3
    assert preview.detected_columns[0].key == "col_0"
    assert preview.total_rows == 3
    assert len(preview.preview_rows) == 3
    assert preview.errors == []


@pytest.mark.asyncio
async def test_import_csv_with_warnings():
    """Test CSV import with large dataset warning."""
    service = DatasetImportService()

    # Generate large CSV
    rows = ["col1,col2\n"]
    for i in range(11000):
        rows.append(f"{i},value{i}\n")

    csv_content = "".join(rows).encode('utf-8')

    preview = await service.import_csv_preview(csv_content, "large.csv")

    assert len(preview.warnings) > 0
    assert any("Large dataset" in w for w in preview.warnings)

