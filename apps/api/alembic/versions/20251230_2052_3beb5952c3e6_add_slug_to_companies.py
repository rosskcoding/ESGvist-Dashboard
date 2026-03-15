"""add_slug_to_companies

Revision ID: 3beb5952c3e6
Revises: 20251230_0001
Create Date: 2025-12-30 20:52:47.807692+00:00

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3beb5952c3e6'
down_revision: Union[str, None] = '20251230_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from company name."""
    # Transliteration map for Cyrillic
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
        "\u0445": "h",
        "\u0446": "ts",
        "\u0447": "ch",
        "\u0448": "sh",
        "\u0449": "sch",
        "\u044a": "",
        "\u044b": "y",
        "\u044c": "",
        "\u044d": "e",
        "\u044e": "yu",
        "\u044f": "ya",
        "\u0410": "A",
        "\u0411": "B",
        "\u0412": "V",
        "\u0413": "G",
        "\u0414": "D",
        "\u0415": "E",
        "\u0401": "Yo",
        "\u0416": "Zh",
        "\u0417": "Z",
        "\u0418": "I",
        "\u0419": "Y",
        "\u041a": "K",
        "\u041b": "L",
        "\u041c": "M",
        "\u041d": "N",
        "\u041e": "O",
        "\u041f": "P",
        "\u0420": "R",
        "\u0421": "S",
        "\u0422": "T",
        "\u0423": "U",
        "\u0424": "F",
        "\u0425": "H",
        "\u0426": "Ts",
        "\u0427": "Ch",
        "\u0428": "Sh",
        "\u0429": "Sch",
        "\u042a": "",
        "\u042b": "Y",
        "\u042c": "",
        "\u042d": "E",
        "\u042e": "Yu",
        "\u042f": "Ya",
        "\u049a": "Q",
        "\u049b": "q",
        "\u0492": "Gh",
        "\u0493": "gh",
        "\u04a2": "Ng",
        "\u04a3": "ng",
        "\u04e8": "O",
        "\u04e9": "o",
        "\u04b0": "U",
        "\u04b1": "u",
        "\u04ae": "U",
        "\u04af": "u",
        "\u04ba": "H",
        "\u04bb": "h",
        "\u0406": "I",
        "\u0456": "i",
    }

    # Transliterate
    slug = ''.join(translit_map.get(c, c) for c in name)

    # Convert to lowercase
    slug = slug.lower()

    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)

    # Remove leading/trailing hyphens
    slug = slug.strip('-')

    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)

    # Ensure not empty
    if not slug:
        slug = 'company'

    return slug


def upgrade() -> None:
    """Upgrade database schema."""
    # Add slug column (nullable first to allow data population)
    op.add_column('companies', sa.Column('slug', sa.String(length=255), nullable=True))

    # Populate slug for existing companies
    connection = op.get_bind()
    companies = connection.execute(sa.text("SELECT company_id, name FROM companies")).fetchall()

    used_slugs = set()
    for company_id, name in companies:
        base_slug = generate_slug(name)
        slug = base_slug
        counter = 1

        # Ensure unique slug
        while slug in used_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1

        used_slugs.add(slug)
        connection.execute(
            sa.text("UPDATE companies SET slug = :slug WHERE company_id = :company_id"),
            {"slug": slug, "company_id": company_id}
        )

    # Make slug non-nullable and add unique constraint
    op.alter_column('companies', 'slug', nullable=False)
    op.create_index(op.f('ix_companies_slug'), 'companies', ['slug'], unique=True)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index(op.f('ix_companies_slug'), table_name='companies')
    op.drop_column('companies', 'slug')





