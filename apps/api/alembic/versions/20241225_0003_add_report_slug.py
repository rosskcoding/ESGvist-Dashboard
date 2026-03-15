"""Add slug column to reports table.

Revision ID: 20241225_0003
Revises: 20241225_0001
Create Date: 2024-12-25

"""

from typing import Sequence
import re

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20241225_0003"
down_revision: str | None = "20241225_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    # Cyrillic to Latin transliteration
    translit_map = {
        "\u0430": "a",
        "\u0431": "b",
        "\u0432": "v",
        "\u0433": "g",
        "\u0434": "d",
        "\u0435": "e",
        "\u0451": "yo",
        "\u0436": "zh",
        "\u0437": "z",
        "\u0438": "i",
        "\u0439": "y",
        "\u043a": "k",
        "\u043b": "l",
        "\u043c": "m",
        "\u043d": "n",
        "\u043e": "o",
        "\u043f": "p",
        "\u0440": "r",
        "\u0441": "s",
        "\u0442": "t",
        "\u0443": "u",
        "\u0444": "f",
        "\u0445": "kh",
        "\u0446": "ts",
        "\u0447": "ch",
        "\u0448": "sh",
        "\u0449": "shch",
        "\u044a": "",
        "\u044b": "y",
        "\u044c": "",
        "\u044d": "e",
        "\u044e": "yu",
        "\u044f": "ya",
        "\u0456": "i",
        "\u0457": "yi",
        "\u0454": "ye",
        "\u0493": "g",
        "\u049b": "q",
        "\u04a3": "n",
        "\u04e9": "o",
        "\u04b1": "u",
        "\u04af": "u",
        "\u04bb": "h",
        "\u04d9": "a",
    }
    text = text.lower()
    result = []
    for char in text:
        if char in translit_map:
            result.append(translit_map[char])
        elif char.isalnum():
            result.append(char)
        elif char in ' -_':
            result.append('-')
    slug = ''.join(result)
    # Remove multiple dashes
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing dashes
    slug = slug.strip('-')
    return slug[:100]


def upgrade() -> None:
    # Add column as nullable first
    op.add_column(
        "reports",
        sa.Column("slug", sa.String(100), nullable=True),
    )

    # Populate existing rows with generated slugs
    conn = op.get_bind()
    reports = conn.execute(sa.text("SELECT report_id, year, title FROM reports")).fetchall()

    used_slugs = set()
    for report_id, year, title in reports:
        base_slug = f"{year}-{slugify(title)}"
        slug = base_slug
        counter = 1
        while slug in used_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        used_slugs.add(slug)

        conn.execute(
            sa.text("UPDATE reports SET slug = :slug WHERE report_id = :report_id"),
            {"slug": slug, "report_id": report_id}
        )

    # Make column not nullable and add unique constraint
    op.alter_column("reports", "slug", nullable=False)
    op.create_unique_constraint("uq_reports_slug", "reports", ["slug"])
    op.create_index("ix_reports_slug", "reports", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_reports_slug", table_name="reports")
    op.drop_constraint("uq_reports_slug", "reports", type_="unique")
    op.drop_column("reports", "slug")
