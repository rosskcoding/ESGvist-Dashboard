"""
Unit tests for SVG sanitization.

Tests that dangerous XSS vectors are removed from SVG files
while preserving valid SVG content.
"""

import pytest

from app.services.sanitizer import SanitizationError, sanitize_svg


class TestSanitizeSvg:
    """Tests for sanitize_svg function."""

    def test_basic_svg_preserved(self):
        """Valid SVG elements should be preserved."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
            <rect x="10" y="10" width="80" height="80" fill="red"/>
            <circle cx="50" cy="50" r="30" fill="blue"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<rect" in result
        assert b"<circle" in result
        assert b'fill="red"' in result
        assert b'fill="blue"' in result

    def test_script_tags_removed(self):
        """<script> tags must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <script>alert('XSS')</script>
            <rect width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<script" not in result
        assert b"alert" not in result
        assert b"<rect" in result

    def test_foreign_object_removed(self):
        """<foreignObject> must be removed (can contain HTML/JS)."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <foreignObject width="100" height="100">
                <div xmlns="http://www.w3.org/1999/xhtml">
                    <script>alert('XSS')</script>
                </div>
            </foreignObject>
            <rect width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<foreignObject" not in result.lower()
        assert b"alert" not in result
        assert b"<rect" in result

    def test_onclick_handler_removed(self):
        """onclick and other event handlers must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect onclick="alert('XSS')" width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"onclick" not in result
        assert b"alert" not in result
        assert b"<rect" in result

    def test_onload_handler_removed(self):
        """onload must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg" onload="alert('XSS')">
            <rect width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"onload" not in result
        assert b"alert" not in result

    def test_onerror_handler_removed(self):
        """onerror must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <image onerror="alert('XSS')" href="invalid.png"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"onerror" not in result
        assert b"alert" not in result

    def test_javascript_href_removed(self):
        """javascript: URLs in href must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <a href="javascript:alert('XSS')">
                <rect width="100" height="100"/>
            </a>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"javascript:" not in result
        assert b"alert" not in result

    def test_javascript_xlink_href_removed(self):
        """javascript: URLs in xlink:href must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg"
             xmlns:xlink="http://www.w3.org/1999/xlink">
            <use xlink:href="javascript:alert('XSS')"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"javascript:" not in result

    def test_data_uri_in_href_removed(self):
        """data: URIs in href must be removed (can contain scripts)."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <a href="data:image/svg+xml;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=">
                <rect width="100" height="100"/>
            </a>
        </svg>'''

        result = sanitize_svg(svg)

        # data: href should be removed
        assert b'href="data:' not in result

    def test_style_with_javascript_removed(self):
        """style attributes with javascript: must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect style="background:url(javascript:alert('XSS'))" width="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"javascript:" not in result

    def test_style_with_expression_removed(self):
        """style attributes with expression() must be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect style="width:expression(alert('XSS'))" width="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"expression(" not in result

    def test_animate_elements_removed(self):
        """animate elements should be removed (can trigger events)."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect width="100" height="100">
                <animate attributeName="x" to="100" onend="alert('XSS')"/>
            </rect>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<animate" not in result

    def test_valid_gradients_preserved(self):
        """Valid gradient definitions should be preserved."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="grad1">
                    <stop offset="0%" style="stop-color:rgb(255,255,0)"/>
                    <stop offset="100%" style="stop-color:rgb(255,0,0)"/>
                </linearGradient>
            </defs>
            <rect fill="url(#grad1)" width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<linearGradient" in result
        assert b"<stop" in result
        assert b"<defs" in result

    def test_valid_filters_preserved(self):
        """Valid filter definitions should be preserved."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <defs>
                <filter id="blur">
                    <feGaussianBlur stdDeviation="5"/>
                </filter>
            </defs>
            <rect filter="url(#blur)" width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<filter" in result
        assert b"<feGaussianBlur" in result

    def test_text_elements_preserved(self):
        """Text elements should be preserved."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <text x="10" y="50" font-size="20">Hello World</text>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"<text" in result
        assert b"Hello World" in result

    def test_string_input_accepted(self):
        """Function should accept string input."""
        svg = '''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <rect width="100" height="100"/>
        </svg>'''

        result = sanitize_svg(svg)

        assert isinstance(result, bytes)
        assert b"<rect" in result

    def test_invalid_svg_raises_error(self):
        """Invalid XML should raise SanitizationError."""
        svg = b"<svg><rect></svg></rect>"  # Malformed

        with pytest.raises(SanitizationError):
            sanitize_svg(svg)

    def test_multiple_event_handlers_all_removed(self):
        """All event handler types should be removed."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg"
             onload="a()" onmouseover="b()" onfocus="c()">
            <rect onclick="d()" ondblclick="e()" onmousedown="f()"/>
        </svg>'''

        result = sanitize_svg(svg)

        # Check none of the event handlers remain
        assert b"onload" not in result
        assert b"onmouseover" not in result
        assert b"onfocus" not in result
        assert b"onclick" not in result
        assert b"ondblclick" not in result
        assert b"onmousedown" not in result

    def test_case_insensitive_protocol_check(self):
        """Protocol checks should be case-insensitive."""
        svg = b'''<?xml version="1.0"?>
        <svg xmlns="http://www.w3.org/2000/svg">
            <a href="JAVASCRIPT:alert('XSS')">
                <rect width="100" height="100"/>
            </a>
        </svg>'''

        result = sanitize_svg(svg)

        assert b"JAVASCRIPT:" not in result
        assert b"javascript:" not in result.lower()

