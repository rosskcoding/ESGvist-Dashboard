"""
AuditLogger — Centralized audit event logging.

Provides type-safe event creation for all auditable actions.
"""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AuditEvent, User


class AuditAction(str, Enum):
    """Audit action types."""

    # === Platform actions ===
    COMPANY_CREATE = "company.create"
    COMPANY_UPDATE = "company.update"
    COMPANY_DELETE = "company.delete"
    COMPANY_DISABLE = "company.disable"
    COMPANY_ENABLE = "company.enable"

    # === Member management ===
    MEMBER_INVITE = "member.invite"
    MEMBER_UPDATE = "member.update"
    MEMBER_REMOVE = "member.remove"
    MEMBER_DEACTIVATE = "member.deactivate"
    MEMBER_REACTIVATE = "member.reactivate"

    # === Role assignments ===
    ROLE_ASSIGN = "role.assign"
    ROLE_UPDATE = "role.update"
    ROLE_REVOKE = "role.revoke"

    # === Content locks ===
    LOCK_APPLY = "lock.apply"
    LOCK_RELEASE = "lock.release"
    LOCK_OVERRIDE = "lock.override"

    # === Structure freeze ===
    STRUCTURE_FREEZE = "structure.freeze"
    STRUCTURE_UNFREEZE = "structure.unfreeze"

    # === Reports ===
    REPORT_CREATE = "report.create"
    REPORT_UPDATE = "report.update"
    REPORT_DELETE = "report.delete"

    # === Sections ===
    SECTION_CREATE = "section.create"
    SECTION_UPDATE = "section.update"
    SECTION_DELETE = "section.delete"
    SECTION_REORDER = "section.reorder"

    # === Blocks ===
    BLOCK_CREATE = "block.create"
    BLOCK_UPDATE = "block.update"
    BLOCK_DELETE = "block.delete"
    BLOCK_REORDER = "block.reorder"

    # === Content status ===
    STATUS_CHANGE = "status.change"
    STATUS_APPROVE = "status.approve"
    STATUS_REJECT = "status.reject"

    # === Evidence ===
    EVIDENCE_CREATE = "evidence.create"
    EVIDENCE_UPDATE = "evidence.update"
    EVIDENCE_DELETE = "evidence.delete"

    # === Audit checks ===
    AUDIT_CHECK_CREATE = "audit_check.create"
    AUDIT_CHECK_UPDATE = "audit_check.update"
    AUDIT_CHECK_DELETE = "audit_check.delete"
    AUDIT_FINALIZE = "audit.finalize"

    # === Releases ===
    RELEASE_CREATE = "release.create"
    RELEASE_BUILD = "release.build"
    RELEASE_DOWNLOAD = "release.download"

    # === Auth ===
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_PASSWORD_CHANGE = "auth.password_change"
    AUTH_PASSWORD_RESET = "auth.password_reset"

    # === ESG Dashboard (pillar) ===
    ESG_ENTITY_CREATE = "esg.entity.create"
    ESG_ENTITY_UPDATE = "esg.entity.update"
    ESG_LOCATION_CREATE = "esg.location.create"
    ESG_LOCATION_UPDATE = "esg.location.update"
    ESG_SEGMENT_CREATE = "esg.segment.create"
    ESG_SEGMENT_UPDATE = "esg.segment.update"
    ESG_METRIC_CREATE = "esg.metric.create"
    ESG_METRIC_UPDATE = "esg.metric.update"
    ESG_METRIC_DELETE = "esg.metric.delete"
    ESG_FACT_CREATE = "esg.fact.create"
    ESG_FACT_UPDATE = "esg.fact.update"
    ESG_FACT_SUBMIT_REVIEW = "esg.fact.submit_review"
    ESG_FACT_REQUEST_CHANGES = "esg.fact.request_changes"
    ESG_FACT_RESTATEMENT = "esg.fact.restatement"
    ESG_FACT_PUBLISH = "esg.fact.publish"
    ESG_FACT_EVIDENCE_CREATE = "esg.fact_evidence.create"
    ESG_FACT_EVIDENCE_UPDATE = "esg.fact_evidence.update"
    ESG_FACT_EVIDENCE_DELETE = "esg.fact_evidence.delete"


class AuditLogger:
    """
    Audit event logger service.

    Usage:
        logger = AuditLogger(session)
        await logger.log_action(
            actor=current_user,
            action=AuditAction.REPORT_CREATE,
            entity_type="report",
            entity_id=report.report_id,
            company_id=company_id,
            metadata={"title": report.title},
        )
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_action(
        self,
        actor: User | str,
        action: AuditAction,
        entity_type: str,
        entity_id: UUID | str,
        company_id: UUID | None = None,
        metadata: dict | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            actor: User performing action or system identifier
            action: Action type from AuditAction enum
            entity_type: Type of entity affected
            entity_id: ID of entity affected
            company_id: Tenant scope (None for platform events)
            metadata: Additional context
            ip_address: Client IP address

        Returns:
            Created AuditEvent
        """
        if isinstance(actor, User):
            actor_type = "user"
            actor_id = str(actor.user_id)
        else:
            actor_type = "system"
            actor_id = str(actor)

        event = AuditEvent.create(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action.value,
            entity_type=entity_type,
            entity_id=str(entity_id),
            company_id=company_id,
            metadata=metadata,
            ip_address=ip_address,
        )

        self.session.add(event)
        # Don't flush here - let the caller control transaction

        return event

    # =========================================================================
    # Convenience methods for common events
    # =========================================================================

    async def log_company_create(
        self,
        actor: User,
        company_id: UUID,
        company_name: str,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log company creation (platform event)."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.COMPANY_CREATE,
            entity_type="company",
            entity_id=company_id,
            company_id=None,  # Platform event
            metadata={"name": company_name},
            ip_address=ip_address,
        )

    async def log_company_delete(
        self,
        actor: User,
        company_id: UUID,
        company_name: str,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log company deletion (platform event)."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.COMPANY_DELETE,
            entity_type="company",
            entity_id=company_id,
            company_id=None,  # Platform event
            metadata={"name": company_name},
            ip_address=ip_address,
        )

    async def log_member_invite(
        self,
        actor: User,
        company_id: UUID,
        user_id: UUID,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log member invitation."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.MEMBER_INVITE,
            entity_type="membership",
            entity_id=user_id,
            company_id=company_id,
            metadata={},
            ip_address=ip_address,
        )

    async def log_role_assign(
        self,
        actor: User,
        company_id: UUID,
        user_id: UUID,
        role: str,
        scope_type: str,
        scope_id: UUID,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log role assignment."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.ROLE_ASSIGN,
            entity_type="role_assignment",
            entity_id=user_id,
            company_id=company_id,
            metadata={
                "role": role,
                "scope_type": scope_type,
                "scope_id": str(scope_id),
            },
            ip_address=ip_address,
        )

    async def log_lock_apply(
        self,
        actor: User,
        company_id: UUID,
        lock_id: UUID,
        scope_type: str,
        scope_id: UUID,
        lock_layer: str,
        reason: str,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log content lock application."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.LOCK_APPLY,
            entity_type="content_lock",
            entity_id=lock_id,
            company_id=company_id,
            metadata={
                "scope_type": scope_type,
                "scope_id": str(scope_id),
                "lock_layer": lock_layer,
                "reason": reason,
            },
            ip_address=ip_address,
        )

    async def log_lock_release(
        self,
        actor: User,
        company_id: UUID,
        lock_id: UUID,
        lock_layer: str,
        override: bool = False,
        override_reason: str | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log content lock release."""
        action = AuditAction.LOCK_OVERRIDE if override else AuditAction.LOCK_RELEASE
        metadata = {"lock_layer": lock_layer}
        if override and override_reason:
            metadata["override_reason"] = override_reason

        return await self.log_action(
            actor=actor,
            action=action,
            entity_type="content_lock",
            entity_id=lock_id,
            company_id=company_id,
            metadata=metadata,
            ip_address=ip_address,
        )

    async def log_structure_freeze(
        self,
        actor: User,
        company_id: UUID,
        report_id: UUID,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log structure freeze."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.STRUCTURE_FREEZE,
            entity_type="report",
            entity_id=report_id,
            company_id=company_id,
            ip_address=ip_address,
        )

    async def log_structure_unfreeze(
        self,
        actor: User,
        company_id: UUID,
        report_id: UUID,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log structure unfreeze."""
        return await self.log_action(
            actor=actor,
            action=AuditAction.STRUCTURE_UNFREEZE,
            entity_type="report",
            entity_id=report_id,
            company_id=company_id,
            ip_address=ip_address,
        )

    async def log_audit_check(
        self,
        actor: User,
        company_id: UUID,
        check_id: UUID,
        action: AuditAction,
        target_type: str,
        target_id: UUID,
        status: str,
        severity: str | None = None,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log audit check action."""
        metadata = {
            "target_type": target_type,
            "target_id": str(target_id),
            "status": status,
        }
        if severity:
            metadata["severity"] = severity

        return await self.log_action(
            actor=actor,
            action=action,
            entity_type="audit_check",
            entity_id=check_id,
            company_id=company_id,
            metadata=metadata,
            ip_address=ip_address,
        )

    async def log_evidence(
        self,
        actor: User,
        company_id: UUID,
        evidence_id: UUID,
        action: AuditAction,
        evidence_type: str,
        title: str,
        ip_address: str | None = None,
    ) -> AuditEvent:
        """Log evidence action."""
        return await self.log_action(
            actor=actor,
            action=action,
            entity_type="evidence_item",
            entity_id=evidence_id,
            company_id=company_id,
            metadata={"type": evidence_type, "title": title},
            ip_address=ip_address,
        )

    async def log_auth(
        self,
        user_id: UUID | None,
        email: str,
        action: AuditAction,
        success: bool = True,
        ip_address: str | None = None,
        failure_reason: str | None = None,
    ) -> AuditEvent:
        """Log authentication action."""
        metadata = {"email": email, "success": success}
        if failure_reason:
            metadata["failure_reason"] = failure_reason

        return await self.log_action(
            actor=str(user_id) if user_id else email,
            action=action,
            entity_type="auth",
            entity_id=str(user_id) if user_id else email,
            company_id=None,  # Auth events are platform-level
            metadata=metadata,
            ip_address=ip_address,
        )


# =============================================================================
# Helper Functions
# =============================================================================


async def log_audit_event(
    session: AsyncSession,
    actor: User | str,
    action: AuditAction,
    entity_type: str,
    entity_id: UUID | str,
    company_id: UUID | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """
    Convenience function for logging audit events.

    Shorthand for AuditLogger(session).log_action(...).
    """
    logger = AuditLogger(session)
    return await logger.log_action(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        company_id=company_id,
        metadata=metadata,
        ip_address=ip_address,
    )
