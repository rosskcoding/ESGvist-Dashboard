"""Unit tests for PDF generator service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile
import zipfile

from app.services.pdf_generator import (
    PDFProfile,
    PDFGeneratorError,
    _extract_print_bundle,
)


class TestPDFProfile:
    """Tests for PDF profile settings."""

    def test_audit_profile(self):
        """Test audit profile settings."""
        settings = PDFProfile.get("audit")

        assert settings["format"] == "A4"
        assert settings["margin"]["top"] == "20mm"
        assert settings["margin"]["bottom"] == "25mm"
        assert settings["print_background"] is True
        assert settings["prefer_css_page_size"] is True

    def test_screen_profile(self):
        """Test screen profile settings."""
        settings = PDFProfile.get("screen")

        assert settings["format"] == "A4"
        assert settings["margin"]["top"] == "10mm"
        assert settings["prefer_css_page_size"] is False

    def test_unknown_profile_defaults_to_audit(self):
        """Test unknown profile falls back to audit."""
        settings = PDFProfile.get("unknown")

        assert settings == PDFProfile.AUDIT

    def test_profiles_are_different(self):
        """Test audit and screen profiles differ."""
        audit = PDFProfile.get("audit")
        screen = PDFProfile.get("screen")

        assert audit != screen
        assert audit["margin"] != screen["margin"]


class TestExtractPrintBundle:
    """Tests for print bundle extraction."""

    @pytest.fixture
    def sample_zip(self, tmp_path):
        """Create sample ZIP with print bundle."""
        zip_path = tmp_path / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            # Print bundle
            zf.writestr("print/ru.html", "<html>Print content</html>")
            zf.writestr("print/en.html", "<html>Print content EN</html>")

            # Assets
            zf.writestr("assets/css/app.css", "body { color: black; }")
            zf.writestr("assets/css/print.css", "@page { size: A4; }")
            zf.writestr("assets/media/image.png", b"\x89PNG\r\n\x1a\n")

            # Other files (should not be extracted for print)
            zf.writestr("ru/index.html", "<html>Russian</html>")
            zf.writestr("en/index.html", "<html>English</html>")

        return zip_path

    @pytest.mark.asyncio
    async def test_extract_print_bundle_ru(self, sample_zip, tmp_path):
        """Test extracting Russian print bundle."""
        dest = tmp_path / "extracted"
        dest.mkdir()

        await _extract_print_bundle(sample_zip, dest, "ru")

        # Check print HTML exists
        assert (dest / "print" / "ru.html").exists()

        # Check assets extracted
        assert (dest / "assets" / "css" / "app.css").exists()
        assert (dest / "assets" / "css" / "print.css").exists()
        assert (dest / "assets" / "media" / "image.png").exists()

        # Check non-print files not extracted
        assert not (dest / "ru" / "index.html").exists()

    @pytest.mark.asyncio
    async def test_extract_print_bundle_missing_locale(self, sample_zip, tmp_path):
        """Test error when locale print HTML missing."""
        dest = tmp_path / "extracted"
        dest.mkdir()

        with pytest.raises(PDFGeneratorError, match="Print HTML not found"):
            await _extract_print_bundle(sample_zip, dest, "kk")

    @pytest.mark.asyncio
    async def test_extract_print_bundle_bad_zip(self, tmp_path):
        """Test error with invalid ZIP file."""
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_text("not a zip file")

        dest = tmp_path / "extracted"
        dest.mkdir()

        with pytest.raises(PDFGeneratorError, match="Invalid ZIP file"):
            await _extract_print_bundle(bad_zip, dest, "ru")


class TestGeneratePDF:
    """Tests for PDF generation (mocked Playwright)."""

    @pytest.fixture
    def sample_zip_with_print(self, tmp_path):
        """Create sample ZIP with complete print bundle."""
        zip_path = tmp_path / "report.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("print/ru.html", """
<!DOCTYPE html>
<html lang="ru">
<head><title>Test Report</title></head>
<body><h1>Test Report</h1></body>
</html>
            """)
            zf.writestr("assets/css/print.css", "@page { size: A4; }")

        return zip_path

    @pytest.mark.asyncio
    async def test_generate_pdf_zip_not_found(self, tmp_path):
        """Test error when ZIP doesn't exist."""
        from app.services.pdf_generator import generate_pdf

        with pytest.raises(PDFGeneratorError, match="ZIP file not found"):
            await generate_pdf(
                zip_path=tmp_path / "nonexistent.zip",
                locale="ru",
            )

    @pytest.mark.asyncio
    async def test_generate_pdf_locale_not_in_zip(self, sample_zip_with_print, tmp_path):
        """Test error when locale not in ZIP."""
        from app.services.pdf_generator import generate_pdf

        with pytest.raises(PDFGeneratorError, match="Print HTML not found"):
            await generate_pdf(
                zip_path=sample_zip_with_print,
                locale="kk",  # Not in ZIP
                output_dir=tmp_path,
            )

    @pytest.mark.asyncio
    async def test_generate_pdf_playwright_not_installed(self, sample_zip_with_print, tmp_path):
        """Test error when Playwright not installed."""
        from app.services.pdf_generator import generate_pdf

        # Mock playwright import to fail
        with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
            with pytest.raises(PDFGeneratorError, match="Playwright not installed"):
                await generate_pdf(
                    zip_path=sample_zip_with_print,
                    locale="ru",
                    output_dir=tmp_path,
                )

    @pytest.mark.asyncio
    async def test_render_pdf_forces_lazy_images_to_load(self, tmp_path):
        """_render_pdf should force-load <img loading=\"lazy\"> before generating PDF."""
        from app.services.pdf_generator import _render_pdf

        # Make this test independent from having Playwright installed locally.
        # We inject a minimal fake `playwright.async_api` module into sys.modules so that
        # `_render_pdf` can import `async_playwright` and use our mocked async CM.
        import sys
        import types

        html_path = tmp_path / "ru.html"
        html_path.write_text("<html><body>ok</body></html>", encoding="utf-8")
        output_path = tmp_path / "out.pdf"

        # Build a minimal fake Playwright stack
        page = MagicMock()
        page.set_default_timeout = MagicMock()
        page.goto = AsyncMock()
        page.evaluate = AsyncMock()
        page.pdf = AsyncMock()

        context = AsyncMock()
        context.new_page.return_value = page

        browser = AsyncMock()
        browser.new_context.return_value = context
        browser.close = AsyncMock()

        chromium = AsyncMock()
        chromium.launch.return_value = browser

        pw = MagicMock()
        pw.chromium = chromium

        ap_cm = AsyncMock()
        ap_cm.__aenter__.return_value = pw
        ap_cm.__aexit__.return_value = AsyncMock()

        fake_playwright = types.ModuleType("playwright")
        # Mark as a package so `import playwright.async_api` works.
        setattr(fake_playwright, "__path__", [])
        fake_async_api = types.ModuleType("playwright.async_api")
        fake_async_api.async_playwright = lambda: ap_cm  # type: ignore[assignment]

        with patch.dict("sys.modules", {"playwright": fake_playwright, "playwright.async_api": fake_async_api}):
            with patch("app.services.pdf_generator.asyncio.sleep", new=AsyncMock()):
                await _render_pdf(
                    html_path=html_path,
                    output_path=output_path,
                    profile_settings=PDFProfile.get("audit"),
                    timeout_ms=1000,
                )

        # One evaluate is for fonts; another must contain our lazy-image loader
        scripts = [c.args[0] for c in page.evaluate.call_args_list]
        assert any('img[loading="lazy"]' in s for s in scripts)
        page.pdf.assert_awaited_once()


class TestPDFGeneratorError:
    """Tests for PDFGeneratorError exception."""

    def test_error_message(self):
        """Test error message stored correctly."""
        error = PDFGeneratorError("Test error message")
        assert str(error) == "Test error message"

    def test_error_is_exception(self):
        """Test PDFGeneratorError is an Exception."""
        assert issubclass(PDFGeneratorError, Exception)


