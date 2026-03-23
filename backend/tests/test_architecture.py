import ast
import os


FORBIDDEN_IMPORTS_IN_DOMAIN = {"fastapi", "sqlalchemy", "starlette", "uvicorn"}
DOMAIN_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "domain")


def test_domain_has_no_framework_imports():
    """Domain layer must not depend on FastAPI or SQLAlchemy."""
    if not os.path.isdir(DOMAIN_DIR):
        return  # no domain files yet

    for filename in os.listdir(DOMAIN_DIR):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue
        filepath = os.path.join(DOMAIN_DIR, filename)
        with open(filepath) as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                top_level = node.module.split(".")[0]
                assert top_level not in FORBIDDEN_IMPORTS_IN_DOMAIN, (
                    f"{filepath} imports '{node.module}' — domain must not depend on {top_level}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    assert top_level not in FORBIDDEN_IMPORTS_IN_DOMAIN, (
                        f"{filepath} imports '{alias.name}' — domain must not depend on {top_level}"
                    )
