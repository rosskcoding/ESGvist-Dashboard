from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserRoleBindingCreateRequest
from app.services.user_role_service import UserRoleService

router = APIRouter(prefix="/api/users", tags=["Users"])


def _get_service(session: AsyncSession) -> UserRoleService:
    return UserRoleService(
        user_repo=UserRepository(session),
        role_binding_repo=RoleBindingRepository(session),
        audit_repo=AuditRepository(session),
    )


@router.get("/{user_id}/roles")
async def list_user_roles(
    user_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_roles(user_id, ctx)


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def create_user_role(
    user_id: int,
    payload: UserRoleBindingCreateRequest,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_role(
        user_id,
        role=payload.role,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        ctx=ctx,
    )


@router.delete("/{user_id}/roles/{binding_id}")
async def delete_user_role(
    user_id: int,
    binding_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).delete_role(user_id, binding_id, ctx)
