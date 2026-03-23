import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.invitation import UserInvitation
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User


class InvitationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_invitation(
        self,
        org_id: int,
        email: str,
        role: str,
        invited_by: int,
        expires_days: int = 7,
    ) -> dict:
        token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

        inv = UserInvitation(
            organization_id=org_id,
            email=email,
            role=role,
            invited_by=invited_by,
            token=token,
            expires_at=expires_at,
        )
        self.session.add(inv)
        await self.session.flush()

        return {
            "id": inv.id,
            "email": email,
            "role": role,
            "token": token,
            "expires_at": expires_at.isoformat(),
            "status": "pending",
        }

    async def accept_invitation(self, token: str, user_id: int) -> dict:
        result = await self.session.execute(
            select(UserInvitation).where(
                UserInvitation.token == token,
                UserInvitation.status == "pending",
            )
        )
        inv = result.scalar_one_or_none()

        if not inv:
            raise AppError("INVALID_INVITATION_TOKEN", 400, "Invalid or already used invitation token")

        expires = inv.expires_at.replace(tzinfo=timezone.utc) if inv.expires_at.tzinfo is None else inv.expires_at
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

    async def list_pending(self, org_id: int) -> list[dict]:
        q = select(UserInvitation).where(
            UserInvitation.organization_id == org_id,
            UserInvitation.status == "pending",
        )
        result = await self.session.execute(q)
        return [
            {
                "id": inv.id,
                "email": inv.email,
                "role": inv.role,
                "status": inv.status,
                "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
            }
            for inv in result.scalars().all()
        ]
