"""
Unit tests for URL resolver and PageContext.

Tests relative URL computation for portable static exports.
"""

import pytest

from app.services.url_resolver import (
    PageContext,
    compute_assets_base,
    rel_url,
)


class TestRelUrl:
    """Tests for rel_url() function."""

    def test_same_directory(self):
        """Files in same directory."""
        assert rel_url("index.html", "about.html") == "about.html"
        assert rel_url("en/index.html", "en/about.html") == "about.html"

    def test_sibling_directory(self):
        """Files in sibling directories."""
        assert rel_url("en/index.html", "ru/index.html") == "../ru/index.html"

    def test_parent_to_child(self):
        """From parent to child directory."""
        assert rel_url("index.html", "en/index.html") == "en/index.html"
        assert rel_url("index.html", "en/sections/intro.html") == "en/sections/intro.html"

    def test_child_to_parent(self):
        """From child to parent directory."""
        assert rel_url("en/index.html", "index.html") == "../index.html"
        assert rel_url("en/sections/intro.html", "index.html") == "../../index.html"

    def test_deep_nesting(self):
        """Deep directory nesting."""
        result = rel_url("en/sections/01-intro/index.html", "assets/css/app.css")
        assert result == "../../../assets/css/app.css"

    def test_very_deep_to_root(self):
        """Very deep file to root (5 directories up)."""
        # a/b/c/d/e/file.html is 5 directories deep, so need 5 "../"
        result = rel_url("a/b/c/d/e/file.html", "index.html")
        assert result == "../../../../../index.html"

    def test_assets_various_depths(self):
        """Assets from various page depths."""
        # Root level
        assert rel_url("index.html", "assets/app.css") == "assets/app.css"

        # One level deep
        assert rel_url("en/index.html", "assets/css/app.css") == "../assets/css/app.css"

        # Two levels deep
        assert rel_url("en/sections/page.html", "assets/css/app.css") == "../../assets/css/app.css"

        # Three levels deep (section with index.html)
        assert rel_url("en/sections/01-intro/index.html", "assets/css/app.css") == "../../../assets/css/app.css"


class TestComputeAssetsBase:
    """Tests for compute_assets_base() function."""

    def test_root_file(self):
        """Asset base from root file."""
        assert compute_assets_base("index.html") == "assets"

    def test_locale_index(self):
        """Asset base from locale index."""
        assert compute_assets_base("en/index.html") == "../assets"

    def test_section_file(self):
        """Asset base from section file."""
        assert compute_assets_base("en/sections/intro.html") == "../../assets"

    def test_section_index(self):
        """Asset base from section index.html."""
        assert compute_assets_base("en/sections/01-intro/index.html") == "../../../assets"

    def test_deep_section(self):
        """Asset base from deeply nested section."""
        assert compute_assets_base("ru/sections/05-conclusion/index.html") == "../../../assets"


class TestPageContext:
    """Tests for PageContext class."""

    def test_assets_base_property(self):
        """Test assets_base property."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")
        assert ctx.assets_base == "../../../assets"

    def test_asset_url(self):
        """Test asset_url() method."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")
        assert ctx.asset_url("css/app.css") == "../../../assets/css/app.css"
        assert ctx.asset_url("media/logo.png") == "../../../assets/media/logo.png"

    def test_page_url(self):
        """Test page_url() method."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")

        # To another section
        result = ctx.page_url("en/sections/02-data/index.html")
        assert result == "../02-data/index.html"

        # To locale index
        result = ctx.page_url("en/index.html")
        assert result == "../../index.html"

    def test_section_url(self):
        """Test section_url() method."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")

        # Same locale, different section
        result = ctx.section_url("en", 2, "data")
        assert result == "../02-data/index.html"

        # Different locale
        result = ctx.section_url("ru", 0, "intro")
        assert result == "../../../ru/sections/00-intro/index.html"

    def test_locale_home(self):
        """Test locale_home() method."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")

        # Same locale
        result = ctx.locale_home("en")
        assert result == "../../index.html"

        # Different locale
        result = ctx.locale_home("ru")
        assert result == "../../../ru/index.html"

    def test_root_index(self):
        """Test root_index() method."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")
        assert ctx.root_index() == "../../../index.html"

    def test_from_locale_index(self):
        """Test from locale index page."""
        ctx = PageContext("ru/index.html", "ru")

        assert ctx.assets_base == "../assets"
        assert ctx.asset_url("css/app.css") == "../assets/css/app.css"
        assert ctx.section_url("ru", 0, "intro") == "sections/00-intro/index.html"
        assert ctx.locale_home("en") == "../en/index.html"
        assert ctx.root_index() == "../index.html"

    def test_from_root_index(self):
        """Test from root index page."""
        ctx = PageContext("index.html", "ru")

        assert ctx.assets_base == "assets"
        assert ctx.asset_url("css/app.css") == "assets/css/app.css"
        assert ctx.section_url("ru", 0, "intro") == "ru/sections/00-intro/index.html"
        assert ctx.locale_home("ru") == "ru/index.html"
        assert ctx.root_index() == "."


class TestCrossLocaleNavigation:
    """Test navigation between different locales."""

    def test_section_to_other_locale_section(self):
        """Navigate from one locale's section to another locale's section."""
        ctx = PageContext("en/sections/01-intro/index.html", "en")

        # To Russian version of different section
        result = ctx.section_url("ru", 3, "sustainability")
        assert result == "../../../ru/sections/03-sustainability/index.html"

    def test_language_switcher_urls(self):
        """Generate language switcher URLs for same section."""
        # From English section
        ctx_en = PageContext("en/sections/02-data/index.html", "en")

        # Switch to Russian (same section)
        ru_url = ctx_en.section_url("ru", 2, "dannye")  # slug might differ
        assert ru_url == "../../../ru/sections/02-dannye/index.html"

        # Switch to Kazakh
        kk_url = ctx_en.section_url("kk", 2, "derekter")
        assert kk_url == "../../../kk/sections/02-derekter/index.html"

