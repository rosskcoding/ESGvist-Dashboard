"""
Sample Assets Fixtures for Testing

Placeholder assets for images, documents, and fonts.
"""

from uuid import UUID

# ============================================================================
# IMAGES
# ============================================================================

SAMPLE_IMAGES = [
    {
        "asset_id": UUID("img00001-0000-0000-0000-000000000001"),
        "kind": "image",
        "filename": "solar-plant-turkestan.jpg",
        "storage_path": "assets/images/solar-plant-turkestan.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 2457600,  # ~2.4 MB
        "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
        "metadata": {
            "width": 1920,
            "height": 1080,
            "alt_text_hint": "Solar power plant",
        },
    },
    {
        "asset_id": UUID("img00002-0000-0000-0000-000000000002"),
        "kind": "image",
        "filename": "ceo-portrait.jpg",
        "storage_path": "assets/images/ceo-portrait.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 512000,  # ~500 KB
        "sha256": "b2c3d4e5f67890123456789012345678901abcdef1234567890abcdef1234567",
        "metadata": {
            "width": 800,
            "height": 800,
            "alt_text_hint": "CEO portrait",
        },
    },
    {
        "asset_id": UUID("img00003-0000-0000-0000-000000000003"),
        "kind": "image",
        "filename": "wind-farm-aerial.jpg",
        "storage_path": "assets/images/wind-farm-aerial.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 3145728,  # ~3 MB
        "sha256": "c3d4e5f678901234567890123456789012abcdef1234567890abcdef12345678",
        "metadata": {
            "width": 2560,
            "height": 1440,
            "alt_text_hint": "Wind farm aerial view",
        },
    },
    {
        "asset_id": UUID("img00004-0000-0000-0000-000000000004"),
        "kind": "image",
        "filename": "company-logo.svg",
        "storage_path": "assets/images/company-logo.svg",
        "mime_type": "image/svg+xml",
        "size_bytes": 8192,  # ~8 KB
        "sha256": "d4e5f6789012345678901234567890123abcdef1234567890abcdef123456789",
        "metadata": {
            "width": 200,
            "height": 60,
        },
    },
]

# ============================================================================
# DOCUMENTS
# ============================================================================

SAMPLE_DOCUMENTS = [
    {
        "asset_id": UUID("doc00001-0000-0000-0000-000000000001"),
        "kind": "attachment",
        "filename": "annual-report-2024.pdf",
        "storage_path": "assets/documents/annual-report-2024.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 15728640,  # ~15 MB
        "sha256": "e5f67890123456789012345678901234abcdef1234567890abcdef1234567890",
    },
    {
        "asset_id": UUID("doc00002-0000-0000-0000-000000000002"),
        "kind": "attachment",
        "filename": "esg-data-2024.xlsx",
        "storage_path": "assets/documents/esg-data-2024.xlsx",
        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "size_bytes": 524288,  # ~512 KB
        "sha256": "f6789012345678901234567890123456abcdef1234567890abcdef12345678901",
    },
    {
        "asset_id": UUID("doc00003-0000-0000-0000-000000000003"),
        "kind": "attachment",
        "filename": "gri-content-index.pdf",
        "storage_path": "assets/documents/gri-content-index.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 2097152,  # ~2 MB
        "sha256": "67890123456789012345678901234567abcdef1234567890abcdef123456789012",
    },
]

# ============================================================================
# FONTS
# ============================================================================

SAMPLE_FONTS = [
    {
        "asset_id": UUID("fnt00001-0000-0000-0000-000000000001"),
        "kind": "font",
        "filename": "Inter-Regular.woff2",
        "storage_path": "assets/fonts/Inter-Regular.woff2",
        "mime_type": "font/woff2",
        "size_bytes": 98304,  # ~96 KB
        "sha256": "78901234567890123456789012345678abcdef1234567890abcdef1234567890123",
    },
    {
        "asset_id": UUID("fnt00002-0000-0000-0000-000000000002"),
        "kind": "font",
        "filename": "Inter-SemiBold.woff2",
        "storage_path": "assets/fonts/Inter-SemiBold.woff2",
        "mime_type": "font/woff2",
        "size_bytes": 102400,  # ~100 KB
        "sha256": "89012345678901234567890123456789abcdef1234567890abcdef12345678901234",
    },
    {
        "asset_id": UUID("fnt00003-0000-0000-0000-000000000003"),
        "kind": "font",
        "filename": "JetBrainsMono-Regular.woff2",
        "storage_path": "assets/fonts/JetBrainsMono-Regular.woff2",
        "mime_type": "font/woff2",
        "size_bytes": 81920,  # ~80 KB
        "sha256": "90123456789012345678901234567890abcdef1234567890abcdef123456789012345",
    },
]

# ============================================================================
# ALL ASSETS
# ============================================================================

ALL_SAMPLE_ASSETS = SAMPLE_IMAGES + SAMPLE_DOCUMENTS + SAMPLE_FONTS


# ============================================================================
# PLACEHOLDER IMAGE GENERATOR (for tests without real files)
# ============================================================================


def generate_placeholder_svg(width: int, height: int, text: str = "Placeholder") -> str:
    """Generate a simple SVG placeholder image."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#e2e8f0"/>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle"
        fill="#64748b" font-family="sans-serif" font-size="16">
    {text}
  </text>
</svg>'''


def generate_placeholder_image_data_uri(
    width: int = 400, height: int = 300, text: str = "Image"
) -> str:
    """Generate a data URI for placeholder image."""
    import base64

    svg = generate_placeholder_svg(width, height, text)
    encoded = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{encoded}"
