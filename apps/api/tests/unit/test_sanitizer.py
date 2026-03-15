"""
Unit tests for HTML sanitizer.

Tests sanitization rules from 04_Content_Model.md Section 4.3.
"""

import pytest

from app.services.sanitizer import (
    SanitizationError,
    check_heading_hierarchy,
    extract_text_content,
    sanitize_html,
    sanitize_scoped_css,
    validate_scoped_css,
)


class TestHTMLSanitization:
    """Tests for HTML sanitization."""

    def test_empty_string(self):
        """Empty string returns empty."""
        assert sanitize_html("") == ""

    def test_allowed_tags_preserved(self):
        """Allowed tags are preserved."""
        html = "<p>Hello <strong>world</strong></p>"
        result = sanitize_html(html)
        assert "<p>" in result
        assert "<strong>" in result

    def test_script_tags_removed(self):
        """Script tags are removed."""
        html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        result = sanitize_html(html)
        assert "<script>" not in result
        # Note: bleach strips tags but may leave content; tag is gone

    def test_javascript_protocol_removed(self):
        """javascript: protocol is removed."""
        html = '<a href="javascript:alert(1)">Click me</a>'
        result = sanitize_html(html)
        assert "javascript:" not in result

    def test_onclick_removed(self):
        """Event handlers are removed."""
        html = '<p onclick="alert(1)">Click me</p>'
        result = sanitize_html(html)
        assert "onclick" not in result

    def test_style_attribute_removed(self):
        """Inline style attribute is removed."""
        html = '<p style="color: red">Red text</p>'
        result = sanitize_html(html)
        assert "style=" not in result

    def test_allowed_data_attrs_preserved(self):
        """Allowed data-* attributes are preserved."""
        html = '<div data-block-id="abc123">Content</div>'
        result = sanitize_html(html)
        assert "data-block-id" in result

    def test_disallowed_data_attrs_removed(self):
        """Disallowed data-* attributes are removed."""
        html = '<div data-custom-evil="bad">Content</div>'
        result = sanitize_html(html)
        assert "data-custom-evil" not in result

    def test_table_structure_preserved(self):
        """Table structure is preserved."""
        html = """
        <table>
            <thead><tr><th>Header</th></tr></thead>
            <tbody><tr><td>Cell</td></tr></tbody>
        </table>
        """
        result = sanitize_html(html)
        assert "<table>" in result
        assert "<thead>" in result
        assert "<tbody>" in result
        assert "<th>" in result
        assert "<td>" in result

    def test_figure_structure_preserved(self):
        """Figure/figcaption structure preserved."""
        html = "<figure><img src='x.jpg' alt='test'><figcaption>Caption</figcaption></figure>"
        result = sanitize_html(html)
        assert "<figure>" in result
        assert "<figcaption>" in result

    def test_list_structure_preserved(self):
        """List structure preserved."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = sanitize_html(html)
        assert "<ul>" in result
        assert "<li>" in result

    def test_class_attribute_preserved(self):
        """Class attribute is preserved."""
        html = '<p class="highlight">Text</p>'
        result = sanitize_html(html)
        assert 'class="highlight"' in result

    def test_id_attribute_removed(self):
        """ID attribute is removed (per Design System spec to prevent user-defined IDs)."""
        html = '<div id="section-1">Content</div>'
        result = sanitize_html(html)
        # id should be stripped per spec (stable IDs are generated in normalize_html)
        assert 'id="section-1"' not in result
        assert "<div>Content</div>" in result

    def test_safe_link_preserved(self):
        """Safe links are preserved."""
        html = '<a href="https://example.com" target="_blank" rel="noopener">Link</a>'
        result = sanitize_html(html)
        assert 'href="https://example.com"' in result
        assert "target=" in result

    def test_comments_stripped(self):
        """HTML comments are stripped."""
        html = "<p>Hello</p><!-- secret comment --><p>World</p>"
        result = sanitize_html(html)
        assert "secret comment" not in result


class TestCSSValidation:
    """Tests for CSS validation."""

    def test_valid_scoped_css(self):
        """Valid scoped CSS passes validation."""
        css = ".block-abc123 { color: red; }"
        errors = validate_scoped_css(css, ".block-abc123")
        assert errors == []

    def test_unscoped_selector_rejected(self):
        """Unscoped selectors are rejected."""
        css = "p { color: red; }"
        errors = validate_scoped_css(css, ".block-abc123")
        assert len(errors) > 0
        assert "must start with" in errors[0]

    def test_import_rejected(self):
        """@import is rejected."""
        css = ".block-abc123 { color: red; } @import url('evil.css');"
        errors = validate_scoped_css(css, ".block-abc123")
        assert len(errors) > 0
        assert "@import" in errors[0].lower()

    def test_url_rejected(self):
        """url() is rejected."""
        css = ".block-abc123 { background: url('evil.png'); }"
        errors = validate_scoped_css(css, ".block-abc123")
        assert len(errors) > 0
        assert "url" in errors[0].lower()

    def test_sanitize_scoped_css_removes_patterns(self):
        """Sanitize removes disallowed patterns."""
        css = ".block-abc { color: red; } @import url('x'); expression(alert());"
        result = sanitize_scoped_css(css, ".block-abc", validate=False)
        assert "@import" not in result
        assert "url(" not in result
        assert "expression(" not in result

    def test_sanitize_raises_on_invalid(self):
        """Sanitize raises when validation fails."""
        css = "p { color: red; }"  # Unscoped
        with pytest.raises(SanitizationError):
            sanitize_scoped_css(css, ".block-abc", validate=True)

    def test_media_rule_scoped_passes(self):
        """@media with scoped selectors passes."""
        css = "@media (min-width: 600px) { .block-abc123 { color: red; } }"
        errors = validate_scoped_css(css, ".block-abc123")
        assert errors == []

    def test_media_rule_unscoped_rejected(self):
        """@media with unscoped selectors is rejected."""
        css = "@media (min-width: 600px) { p { color: red; } }"
        errors = validate_scoped_css(css, ".block-abc123")
        assert errors
        assert any("must start with" in e.lower() for e in errors)

    def test_supports_rule_scoped_passes(self):
        """@supports with scoped selectors passes."""
        css = "@supports (display: grid) { .block-abc123 { display: grid; } }"
        errors = validate_scoped_css(css, ".block-abc123")
        assert errors == []

    def test_keyframes_allowed_without_scoping(self):
        """@keyframes blocks do not require selector scoping inside."""
        css = (
            "@keyframes fadein { from { opacity: 0; } to { opacity: 1; } }"
            ".block-abc123 { animation: fadein 1s; }"
        )
        errors = validate_scoped_css(css, ".block-abc123")
        assert errors == []


class TestTextExtraction:
    """Tests for text extraction."""

    def test_extract_simple_text(self):
        """Extract text from simple HTML."""
        html = "<p>Hello <strong>world</strong></p>"
        text = extract_text_content(html)
        assert text == "Hello world"

    def test_extract_empty(self):
        """Empty HTML returns empty text."""
        assert extract_text_content("") == ""

    def test_extract_normalizes_whitespace(self):
        """Whitespace is normalized."""
        html = "<p>Hello    \n\n   world</p>"
        text = extract_text_content(html)
        assert text == "Hello world"


class TestHeadingHierarchy:
    """Tests for heading hierarchy validation."""

    def test_valid_hierarchy(self):
        """h4-h6 headings are allowed."""
        html = "<h4>Title</h4><h5>Subtitle</h5><p>Content</p>"
        issues = check_heading_hierarchy(html)
        assert issues == []

    def test_h1_rejected(self):
        """h1 in block content is rejected."""
        html = "<h1>Big Title</h1><p>Content</p>"
        issues = check_heading_hierarchy(html)
        assert len(issues) > 0
        assert "h1" in issues[0]

    def test_h2_rejected(self):
        """h2 in block content is rejected."""
        html = "<h2>Section</h2><p>Content</p>"
        issues = check_heading_hierarchy(html)
        assert len(issues) > 0

    def test_h3_rejected(self):
        """h3 in block content is rejected."""
        html = "<h3>Subsection</h3><p>Content</p>"
        issues = check_heading_hierarchy(html)
        assert len(issues) > 0

