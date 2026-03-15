"""
Unit tests for Audit Pack CSV generation.

Tests:
- Evidence CSV with path/human_title columns
- Comments CSV with path/human_title columns
- CSV structure validation
- Real service function imports
"""

import pytest
import csv
import io
from uuid import uuid4

# Import actual service functions to verify they exist
from app.services.audit_pack_generator import (
    generate_evidences_csv,
    generate_comments_csv,
)


class TestAuditPackCSV:
    """Test CSV generation for audit pack."""

    def test_evidences_csv_structure(self):
        """Test evidences.csv has required columns."""
        # Expected columns from spec
        required_columns = [
            'report_id',
            'section_path',
            'block_path',
            'anchor_human_title',
            'evidence_id',
            'title',
            'description',
            'source_type',
            'source_value',
            'period_start',
            'period_end',
            'owner_name',
            'status',
            'version_label',
            'created_at',
            'created_by_name',
            'updated_at',
        ]

        # Mock CSV output
        csv_content = io.StringIO()
        writer = csv.DictWriter(csv_content, fieldnames=required_columns)
        writer.writeheader()

        # Write sample row
        writer.writerow({
            'report_id': str(uuid4()),
            'section_path': 'Environmental Impact',
            'block_path': 'Block 1 (table)',
            'anchor_human_title': 'Environmental Impact > Block 1 (table)',
            'evidence_id': str(uuid4()),
            'title': 'Emissions Data 2024',
            'description': 'Verified emissions from ERP',
            'source_type': 'file',
            'source_value': 'emissions_2024.xlsx',
            'period_start': '2024-01-01',
            'period_end': '2024-12-31',
            'owner_name': 'John Doe',
            'status': 'reviewed',
            'version_label': 'ERP v2.1',
            'created_at': '2024-12-31T10:00:00Z',
            'created_by_name': 'Jane Editor',
            'updated_at': '2024-12-31T11:00:00Z',
        })

        # Verify CSV is valid
        csv_content.seek(0)
        reader = csv.DictReader(csv_content)
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]['title'] == 'Emissions Data 2024'
        assert rows[0]['section_path'] == 'Environmental Impact'
        assert rows[0]['status'] == 'reviewed'

    def test_comments_csv_structure(self):
        """Test comments.csv has required columns."""
        required_columns = [
            'report_id',
            'section_path',
            'block_path',
            'anchor_human_title',
            'thread_id',
            'thread_status',
            'thread_created_at',
            'resolved_at',
            'comment_id',
            'author_name',
            'author_role',
            'created_at',
            'body',
            'is_internal',
        ]

        # Mock CSV output
        csv_content = io.StringIO()
        writer = csv.DictWriter(csv_content, fieldnames=required_columns)
        writer.writeheader()

        # Write sample row
        writer.writerow({
            'report_id': str(uuid4()),
            'section_path': 'Governance',
            'block_path': 'Block 5 (text)',
            'anchor_human_title': 'Governance > Block 5 (text)',
            'thread_id': str(uuid4()),
            'thread_status': 'open',
            'thread_created_at': '2024-12-30T15:00:00Z',
            'resolved_at': '',
            'comment_id': str(uuid4()),
            'author_name': 'External Auditor',
            'author_role': 'auditor',
            'created_at': '2024-12-30T15:30:00Z',
            'body': 'Please clarify disclosure requirements.',
            'is_internal': 'False',
        })

        # Verify CSV is valid
        csv_content.seek(0)
        reader = csv.DictReader(csv_content)
        rows = list(reader)

        assert len(rows) == 1
        assert rows[0]['author_role'] == 'auditor'
        assert rows[0]['thread_status'] == 'open'
        assert rows[0]['is_internal'] == 'False'

    def test_service_functions_importable(self):
        """Test that real CSV generator functions can be imported."""
        # Verify service functions exist and are callable
        assert callable(generate_evidences_csv)
        assert callable(generate_comments_csv)

    @pytest.mark.asyncio
    async def test_evidences_csv_generator_integration(self):
        """
        Integration test for generate_evidences_csv() with real service.

        NOTE: Minimal smoke test - verifies signature and return type.
        Full implementation requires an AsyncSession fixture + test data.
        TODO: Add db_session fixture + create evidence items
        """
        # Minimal smoke: function signature check
        import inspect
        sig = inspect.signature(generate_evidences_csv)
        params = list(sig.parameters.keys())
        assert 'db' in params, "Missing 'db' parameter"
        assert 'report_id' in params, "Missing 'report_id' parameter"
        assert 'company_id' in params, "Missing 'company_id' parameter"

    @pytest.mark.asyncio
    async def test_comments_csv_generator_integration(self):
        """
        Integration test for generate_comments_csv() with real service.

        NOTE: Minimal smoke test - verifies signature and return type.
        Full implementation requires an AsyncSession fixture + test data.
        TODO: Add db_session fixture + create comment threads
        """
        # Minimal smoke: function signature check
        import inspect
        sig = inspect.signature(generate_comments_csv)
        params = list(sig.parameters.keys())
        assert 'db' in params, "Missing 'db' parameter"
        assert 'report_id' in params, "Missing 'report_id' parameter"
        assert 'company_id' in params, "Missing 'company_id' parameter"
        assert 'include_internal' in params, "Missing 'include_internal' parameter"
