"""
Application services package.

Keep this module intentionally lightweight.

Why:
- Importing a submodule like `app.services.pdf_generator` implicitly imports the package
  `app.services` first (executes this file).
- Eager re-exports here used to pull in heavy dependencies (SQLAlchemy models, etc.) even
  for unrelated helpers, slowing startup and making isolated unit tests harder.

We preserve the public API (re-exports) via **lazy imports** (PEP 562) using __getattr__.
"""

from __future__ import annotations

import importlib
from typing import Any

# Public re-exports (backwards compatible)
__all__ = [
    # Migrations
    "migrate_block_data",
    "needs_migration",
    "get_current_version",
    "CURRENT_VERSIONS",
    # Validator
    "BlockValidator",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    "block_validator",
    # Permissions (RBAC)
    "PermissionService",
    "ROLE_PERMISSIONS",
    "PLATFORM_PERMISSIONS",
    "get_report_company_id",
    "get_section_report_id",
    "get_block_section_id",
    # Locks
    "LockService",
    "check_content_editable",
    # Freeze
    "FreezeService",
    "check_structure_editable",
    "require_structure_frozen",
    # Audit
    "AuditAction",
    "AuditLogger",
    "log_audit_event",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Migrations
    "migrate_block_data": ("app.services.block_migrations", "migrate_block_data"),
    "needs_migration": ("app.services.block_migrations", "needs_migration"),
    "get_current_version": ("app.services.block_migrations", "get_current_version"),
    "CURRENT_VERSIONS": ("app.services.block_migrations", "CURRENT_VERSIONS"),
    # Validator
    "BlockValidator": ("app.services.block_validator", "BlockValidator"),
    "ValidationIssue": ("app.services.block_validator", "ValidationIssue"),
    "ValidationResult": ("app.services.block_validator", "ValidationResult"),
    "ValidationSeverity": ("app.services.block_validator", "ValidationSeverity"),
    "block_validator": ("app.services.block_validator", "block_validator"),
    # Permissions (RBAC)
    "PermissionService": ("app.services.permissions", "PermissionService"),
    "ROLE_PERMISSIONS": ("app.services.permissions", "ROLE_PERMISSIONS"),
    "PLATFORM_PERMISSIONS": ("app.services.permissions", "PLATFORM_PERMISSIONS"),
    "get_report_company_id": ("app.services.permissions", "get_report_company_id"),
    "get_section_report_id": ("app.services.permissions", "get_section_report_id"),
    "get_block_section_id": ("app.services.permissions", "get_block_section_id"),
    # Locks
    "LockService": ("app.services.locks", "LockService"),
    "check_content_editable": ("app.services.locks", "check_content_editable"),
    # Freeze
    "FreezeService": ("app.services.freeze", "FreezeService"),
    "check_structure_editable": ("app.services.freeze", "check_structure_editable"),
    "require_structure_frozen": ("app.services.freeze", "require_structure_frozen"),
    # Audit
    "AuditAction": ("app.services.audit_logger", "AuditAction"),
    "AuditLogger": ("app.services.audit_logger", "AuditLogger"),
    "log_audit_event": ("app.services.audit_logger", "log_audit_event"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    attr = getattr(module, attr_name)
    # Cache for subsequent accesses
    globals()[name] = attr
    return attr


def __dir__() -> list[str]:
    return sorted(set(list(globals().keys()) + list(_LAZY_EXPORTS.keys())))
