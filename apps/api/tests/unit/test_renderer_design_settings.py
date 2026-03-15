"""Unit tests for design settings application in page renderer."""

from unittest.mock import MagicMock
from uuid import uuid4

from app.domain.models.enums import BlockType, BlockVariant
from app.services.renderer import Renderer


def _make_section(section_id=None, title: str = "Section 1", slug: str = "section-1"):
    section = MagicMock()
    section.section_id = section_id or uuid4()
    section.order_index = 0
    section.depth = 0
    section.label_prefix = "1."

    i18n = MagicMock()
    i18n.title = title
    i18n.summary = "Summary"
    i18n.slug = slug
    section.get_i18n = MagicMock(side_effect=lambda locale: i18n if locale == "en" else None)
    return section


def _make_block():
    block = MagicMock()
    block.block_id = uuid4()
    block.type = BlockType.TEXT
    block.variant = BlockVariant.DEFAULT
    block.data_json = {}

    i18n = MagicMock()
    i18n.fields_json = {"body_html": "<p>Body text</p>"}
    block.get_i18n = MagicMock(side_effect=lambda locale: i18n if locale == "en" else None)
    return block


def _make_report(design_json):
    report = MagicMock()
    report.report_id = uuid4()
    report.title = "Design Test Report"
    report.year = 2026
    report.enabled_locales = ["en"]
    report.design_json = design_json
    return report


def test_render_page_applies_layout_and_typography_css_variables():
    renderer = Renderer()
    section = _make_section()
    block = _make_block()
    report = _make_report(
        {
            "layout": {
                "preset": "topnav",
                "container_width": "narrow",
                "section_spacing": "airy",
                "show_toc": False,
            },
            "typography": {
                "font_family_body": "Georgia",
                "font_family_heading": "Merriweather",
                "font_family_mono": "Fira Code",
                "base_font_size": 18,
                "heading_scale": "large",
            },
        }
    )

    html = renderer.render_page(
        report=report,
        section=section,
        blocks=[block],
        all_sections=[section],
        locale="en",
    )

    assert "rpt-layout--topnav" in html
    assert "--container-max-width: 980px;" in html
    assert "--content-max-width: 62ch;" in html
    assert "--content-padding-y: 48px;" in html
    assert "--section-header-gap: 48px;" in html
    assert "--block-gap: 48px;" in html
    assert "--font-sans: Georgia, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;" in html
    assert "--font-heading: Merriweather, var(--font-sans);" in html
    assert "--font-mono: Fira Code, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace;" in html
    assert "--text-md: 18px;" in html
    assert "--text-2xl: 45px;" in html
    assert "rpt-topnav" not in html  # show_toc=false should hide top navigation


def test_render_page_sanitizes_font_values_and_clamps_typography_sizes():
    renderer = Renderer()
    section = _make_section()
    block = _make_block()
    report = _make_report(
        {
            "layout": {
                "preset": "sidebar",
                "container_width": "wide",
                "section_spacing": "compact",
                "show_toc": True,
            },
            "typography": {
                "font_family_body": "Inter; color:red",
                "font_family_heading": "",
                "font_family_mono": None,
                "base_font_size": 999,
                "heading_scale": "not-real",
            },
        }
    )

    html = renderer.render_page(
        report=report,
        section=section,
        blocks=[block],
        all_sections=[section],
        locale="en",
    )

    assert "--container-max-width: 1440px;" in html
    assert "--content-padding-y: 24px;" in html
    assert "color:red" not in html
    assert "--font-sans: Inter colorred, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;" in html
    assert "--font-heading: Inter, var(--font-sans);" in html  # empty value -> fallback
    assert "--font-mono: JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace;" in html
    assert "--text-md: 20px;" in html  # clamped max
    assert "--text-2xl: 40px;" in html  # fallback heading scale (2.0)


def test_render_page_applies_block_type_preset_class():
    renderer = Renderer()
    section = _make_section()
    block = _make_block()
    report = _make_report(
        {
            "block_type_presets": {
                "text": "lead",
            }
        }
    )

    html = renderer.render_page(
        report=report,
        section=section,
        blocks=[block],
        all_sections=[section],
        locale="en",
    )

    assert "rpt-block--text" in html
    assert "rpt-preset--lead" in html


def test_render_page_block_override_wins_over_block_type_preset():
    renderer = Renderer()
    section = _make_section()
    block = _make_block()
    report = _make_report(
        {
            "block_type_presets": {
                "text": "lead",
            },
            "block_overrides": {
                str(block.block_id): "highlight",
            },
        }
    )

    html = renderer.render_page(
        report=report,
        section=section,
        blocks=[block],
        all_sections=[section],
        locale="en",
    )

    assert "rpt-preset--highlight" in html
    assert "rpt-preset--lead" not in html


def test_render_page_builds_google_fonts_url_in_web_mode():
    renderer = Renderer()
    section = _make_section()
    block = _make_block()
    report = _make_report(
        {
            "font_mode": "web",
            "typography": {
                "font_family_body": "Roboto, sans-serif",
                "font_family_heading": "Merriweather",
                "font_family_mono": "Fira Code",
                "base_font_size": 16,
                "heading_scale": "default",
            },
        }
    )

    html = renderer.render_page(
        report=report,
        section=section,
        blocks=[block],
        all_sections=[section],
        locale="en",
    )

    assert "fonts.googleapis.com" in html
    assert "Roboto%3Awght%40400%3B500%3B700" in html
    assert "Merriweather%3Awght%40400%3B700" in html
    assert "Fira%2BCode%3Awght%40400%3B500%3B700" in html


def test_render_page_skips_google_fonts_url_in_portable_mode():
    renderer = Renderer()
    section = _make_section()
    block = _make_block()
    report = _make_report(
        {
            "font_mode": "portable",
            "typography": {
                "font_family_body": "Roboto",
                "font_family_heading": "Merriweather",
                "font_family_mono": "Fira Code",
                "base_font_size": 16,
                "heading_scale": "default",
            },
        }
    )

    html = renderer.render_page(
        report=report,
        section=section,
        blocks=[block],
        all_sections=[section],
        locale="en",
    )

    assert "fonts.googleapis.com" not in html
