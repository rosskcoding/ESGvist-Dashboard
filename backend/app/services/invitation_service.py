import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.invitation import UserInvitation
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User


class InvitationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_by_token(self, token: str) -> UserInvitation | None:
        result = await self.session.execute(
            select(UserInvitation).where(UserInvitation.token == token)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _expires_at_utc(invitation: UserInvitation) -> datetime:
        return (
            invitation.expires_at.replace(tzinfo=timezone.utc)
            if invitation.expires_at.tzinfo is None
            else invitation.expires_at
        )

    async def _get_inviter_name(self, invited_by: int) -> str:
        result = await self.session.execute(select(User).where(User.id == invited_by))
        inviter = result.scalar_one_or_none()
        if not inviter:
            return "Unknown inviter"
        return inviter.full_name or inviter.email

    async def get_invitation_info(self, token: str) -> dict:
        invitation = await self._get_by_token(token)
        if not invitation:
            raise AppError("INVALID_INVITATION_TOKEN", 400, "Invalid or already used invitation token")

        if invitation.status != "pending":
            raise AppError("INVALID_INVITATION_TOKEN", 400, "Invalid or already used invitation token")

        if self._expires_at_utc(invitation) < datetime.now(timezone.utc):
            invitation.status = "expired"
            await self.session.flush()
            raise AppError("INVITATION_EXPIRED", 410, "Invitation has expired")

        existing_user = await self.session.execute(
            select(User).where(User.email == invitation.email.lower())
        )
        user = existing_user.scalar_one_or_none()
        org_result = await self.session.execute(
            select(Organization).where(Organization.id == invitation.organization_id)
        )
        organization = org_result.scalar_one_or_none()
        return {
            "organization_id": invitation.organization_id,
            "organization_name": organization.name if organization else f"Organization #{invitation.organization_id}",
            "email": invitation.email,
            "role": invitation.role,
            "inviter_name": await self._get_inviter_name(invitation.invited_by),
            "already_registered": user is not None,
        }

    async def _get_pending_invitation(self, invitation_id: int, org_id: int) -> UserInvitation:
        result = await self.session.execute(
            select(UserInvitation).where(
                UserInvitation.id == invitation_id,
                UserInvitation.organization_id == org_id,
                UserInvitation.status == "pending",
            )
        )
        invitation = result.scalar_one_or_none()
        if not invitation:
            raise AppError("NOT_FOUND", 404, f"Pending invitation {invitation_id} not found")
        return invitation

    async def create_invitation(
        self,
        org_id: int,
        email: str,
        role: str,
        invited_by: int,
        expires_days: int = 7,
    ) -> dict:
        normalized_email = email.lower()
        existing = await self.session.execute(
            select(UserInvitation).where(
                UserInvitation.organization_id == org_id,
                UserInvitation.email == normalized_email,
                UserInvitation.status == "pending",
            )
        )
        if existing.scalar_one_or_none():
            raise AppError("INVITATION_EXISTS", 409, "A pending invitation already exists for this email")

        token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        inv = UserInvitation(
            organization_id=org_id,
            email=normalized_email,
            role=role,
            invited_by=invited_by,
            token=token,
            expires_at=expires_at,
        )
        self.session.add(inv)
        await self.session.flush()

        return {
            "id": inv.id,
            "email": normalized_email,
            "role": role,
            "token": token,
            "expires_at": expires_at.isoformat(),
            "status": "pending",
        }

    async def accept_invitation(self, token: str, user_id: int) -> dict:
        inv = await self._get_by_token(token)

        if not inv or inv.status != "pending":
            raise AppError("INVALID_INVITATION_TOKEN", 400, "Invalid or already used invitation token")

        user_result = await self.session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise AppError("NOT_FOUND", 404, f"User {user_id} not found")
        if user.email.lower() != inv.email.lower():
            raise AppError(
                "INVITATION_EMAIL_MISMATCH",
                403,
                "Invitation email does not match the current user",
            )

        existing_binding = await self.session.execute(
            select(RoleBinding).where(
                RoleBinding.user_id == user_id,
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == inv.organization_id,
            )
        )
        if existing_binding.scalar_one_or_none():
            raise AppError("ROLE_BINDING_EXISTS", 409, "User already has a role in this organization")

        expires = self._expires_at_utc(inv)
        if expires < datetime.now(timezone.utc):
            inv.status = "expired"
            await self.session.flush()
            raise AppError("INVITATION_EXPIRED", 410, "Invitation has expired")

        # Create role binding
        binding = RoleBinding(
            user_id=user_id,
            role=inv.role,
            scope_type="organization",
            scope_id=inv.organization_id,
            created_by=inv.invited_by,
        )
        self.session.add(binding)

        inv.status = "accepted"
        await self.session.flush()

        return {
            "invitation_id": inv.id,
            "organization_id": inv.organization_id,
            "role": inv.role,
            "accepted": True,
        }

    async def decline_invitation(self, token: str) -> dict:
        invitation = await self._get_by_token(token)
        if not invitation or invitation.status != "pending":
            raise AppError("INVALID_INVITATION_TOKEN", 400, "Invalid or already used invitation token")

        if self._expires_at_utc(invitation) < datetime.now(timezone.utc):
            invitation.status = "expired"
            await self.session.flush()
            raise AppError("INVITATION_EXPIRED", 410, "Invitation has expired")

        invitation.status = "declined"
        await self.session.flush()
        return {"id": invitation.id, "declined": True}

    async def list_pending(self, org_id: int) -> list[dict]:
        q = (
            select(UserInvitation, User.full_name, User.email)
            .join(User, User.id == UserInvitation.invited_by)
            .where(
                UserInvitation.organization_id == org_id,
                UserInvitation.status == "pending",
            )
            .order_by(UserInvitation.created_at.desc(), UserInvitation.id.desc())
        )
        result = await self.session.execute(q)
        return [
            {
                "id": inv.id,
                "email": inv.email,
                "role": inv.role,
                "status": inv.status,
                "invited_at": inv.created_at.isoformat() if inv.created_at else None,
                "invited_by": invited_by_name or invited_by_email,
                "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            }
            for inv, invited_by_name, invited_by_email in result.all()
        ]

    async def resend_invitation(
        self,
        invitation_id: int,
        org_id: int,
        invited_by: int,
        expires_days: int = 7,
    ) -> dict:
        invitation = await self._get_pending_invitation(invitation_id, org_id)
        invitation.token = str(uuid.uuid4())
        invitation.invited_by = invited_by
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        invitation.created_at = datetime.now(timezone.utc)
        await self.session.flush()
        return {
            "id": invitation.id,
            "email": invitation.email,
            "role": invitation.role,
            "status": invitation.status,
            "token": invitation.token,
            "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
        }

    async def cancel_invitation(self, invitation_id: int, org_id: int) -> dict:
        invitation = await self._get_pending_invitation(invitation_id, org_id)
        invitation.status = "cancelled"
        await self.session.flush()
        return {"id": invitation.id, "cancelled": True}
