from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, RequestContext, get_current_context, get_current_user
from app.db.session import get_session
from app.policies.auth_policy import AuthPolicy
from app.services.invitation_service import InvitationService

router = APIRouter(prefix="/api/invitations", tags=["Invitations"])


class InviteRequest(BaseModel):
    email: EmailStr
    role: str


class InvitationTokenRequest(BaseModel):
    token: str


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: InviteRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_manager_or_admin(ctx)
    service = InvitationService(session)
    return await service.create_invitation(
        org_id=ctx.organization_id,
        email=payload.email,
        role=payload.role,
        invited_by=ctx.user_id,
    )


@router.get("/accept")
async def get_invitation_info(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    service = InvitationService(session)
    return await service.get_invitation_info(token)


@router.post("/accept")
async def accept_invitation(
    payload: InvitationTokenRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = InvitationService(session)
    return await service.accept_invitation(payload.token, user.id)


@router.post("/accept/{token}")
async def accept_invitation_by_path(
    token: str,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Backward-compatible alias for existing clients and tests.
    service = InvitationService(session)
    return await service.accept_invitation(token, user.id)


@router.post("/decline")
async def decline_invitation(
    payload: InvitationTokenRequest,
    session: AsyncSession = Depends(get_session),
):
    service = InvitationService(session)
    return await service.decline_invitation(payload.token)


@router.post("/decline/{token}")
async def decline_invitation_by_path(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    service = InvitationService(session)
    return await service.decline_invitation(token)


@router.get("")
async def list_pending(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    AuthPolicy.require_manager_or_admin(ctx)
    service = InvitationService(session)
    return await service.list_pending(ctx.organization_id)
