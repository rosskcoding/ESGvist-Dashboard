"""
Unit tests for slug utilities.
"""

import pytest

from app.utils.slug import slugify, generate_report_slug


class TestSlugify:
    """Tests for slugify function."""

    def test_basic_latin(self):
        """Basic Latin text is lowercased and cleaned."""
        assert slugify("Hello World") == "hello-world"

    def test_cyrillic_transliteration(self):
        """Cyrillic text is transliterated to Latin."""
        assert slugify("\u041a\u0440\u0430\u0442\u043a\u0438\u0439 \u043f\u0440\u043e\u0444\u0438\u043b\u044c") == "kratkiy-profil"

    def test_mixed_text(self):
        """Mixed Cyrillic and Latin text."""
        assert slugify("\u041a\u043e\u043c\u043f\u0430\u043d\u0438\u044f KAP 2024") == "kompaniya-kap-2024"

    def test_special_characters_removed(self):
        """Special characters are removed."""
        assert slugify("Hello! @World#") == "hello-world"

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces become single dash."""
        assert slugify("Hello   World") == "hello-world"

    def test_leading_trailing_dashes_removed(self):
        """Leading and trailing dashes are stripped."""
        assert slugify("  Hello World  ") == "hello-world"
        assert slugify("---Hello---") == "hello"

    def test_numbers_preserved(self):
        """Numbers are preserved."""
        assert slugify("Report 2024") == "report-2024"

    def test_ukrainian_chars(self):
        """Ukrainian characters are transliterated."""
        # U+0438 -> i (Cyrillic small letter i), U+0457 -> yi (Ukrainian yi)
        assert slugify("\u041a\u0438\u0457\u0432") == "kiyiv"

    def test_kazakh_chars(self):
        """Kazakh characters are transliterated."""
        assert slugify("\u049a\u0430\u0437\u0430\u049b\u0441\u0442\u0430\u043d") == "qazaqstan"

    def test_max_length(self):
        """Slug is truncated to max_length."""
        long_text = "A" * 200
        result = slugify(long_text, max_length=50)
        assert len(result) <= 50

    def test_empty_string(self):
        """Empty string returns empty slug."""
        assert slugify("") == ""

    def test_only_special_chars(self):
        """String with only special chars returns empty slug."""
        assert slugify("@#$%^&*()") == ""


class TestGenerateReportSlug:
    """Tests for generate_report_slug function."""

    def test_year_and_title(self):
        """Generates slug from year and title."""
        result = generate_report_slug(2024, "Annual Report")
        assert result == "2024-annual-report"

    def test_cyrillic_title(self):
        """Generates slug from year and Cyrillic title."""
        result = generate_report_slug(2025, "\u0413\u043e\u0434\u043e\u0432\u043e\u0439 \u043e\u0442\u0447\u0451\u0442")
        assert result == "2025-godovoy-otchyot"

    def test_short_title(self):
        """Short title abbreviation."""
        result = generate_report_slug(2025, "\u041a\u0410\u041f")
        assert result == "2025-kap"

    def test_long_title_truncated(self):
        """Long title is truncated."""
        long_title = "A" * 200
        result = generate_report_slug(2024, long_title)
        assert len(result) <= 100  # year- (5 chars) + max 90 chars
        assert result.startswith("2024-")
