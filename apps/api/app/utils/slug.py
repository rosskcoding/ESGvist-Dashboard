"""
Slug generation utilities.
"""

import re


# Cyrillic to Latin transliteration map
TRANSLIT_MAP = {
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
    # Ukrainian
    "\u0456": "i",
    "\u0457": "yi",
    "\u0454": "ye",
    # Kazakh
    "\u0493": "g",
    "\u049b": "q",
    "\u04a3": "n",
    "\u04e9": "o",
    "\u04b1": "u",
    "\u04af": "u",
    "\u04bb": "h",
    "\u04d9": "a",
}


def slugify(text: str, max_length: int = 100) -> str:
    """
    Convert text to URL-friendly slug.

    - Transliterates Cyrillic to Latin
    - Converts to lowercase
    - Replaces spaces/special chars with dashes
    - Removes multiple consecutive dashes

    Args:
        text: Input text to slugify
        max_length: Maximum length of resulting slug

    Returns:
        URL-friendly slug string
    """
    text = text.lower()
    result = []

    for char in text:
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif char.isalnum():
            result.append(char)
        elif char in ' -_':
            result.append('-')

    slug = ''.join(result)
    # Remove multiple dashes
    slug = re.sub(r'-+', '-', slug)
    # Remove leading/trailing dashes
    slug = slug.strip('-')

    return slug[:max_length]


def generate_report_slug(year: int, title: str) -> str:
    """
    Generate a report slug from year and title.

    Format: {year}-{slugified_title}
    Example: 2025-kap, 2024-annual-report

    Args:
        year: Report year
        title: Report title

    Returns:
        URL-friendly report slug
    """
    title_slug = slugify(title, max_length=90)
    return f"{year}-{title_slug}"



