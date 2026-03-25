from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes._auth_helpers import (
    resolve_client_ip,
    resolve_user_agent,
    serialize_auth_response,
)
from app.core.auth_cookies import (
    generate_csrf_token,
    set_access_token_cookie,
    set_csrf_token_cookie,
    set_refresh_token_cookie,
)
from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.sso_repo import SSORepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.sso import (
    SSOCallbackRequest,
    SSOProviderCreate,
    SSOProviderListOut,
    SSOProviderOut,
    SSOProviderPublicListOut,
    SSOProviderUpdate,
    SSOStartOut,
    SSOStartRequest,
)
from app.services.sso_service import SSOService

router = APIRouter(prefix="/api/auth/sso", tags=["SSO"])


def _get_service(session: AsyncSession) -> SSOService:
    return SSOService(
        sso_repo=SSORepository(session),
        user_repo=UserRepository(session),
        role_binding_repo=RoleBindingRepository(session),
        refresh_token_repo=RefreshTokenRepository(session),
        audit_repo=AuditRepository(session),
    )


@router.get("/providers", response_model=SSOProviderPublicListOut)
async def list_active_providers(
    organization_id: int = Query(..., ge=1),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_active_providers(organization_id)


@router.get("/providers/manage", response_model=SSOProviderListOut)
async def list_manageable_providers(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_providers(ctx)


@router.post("/providers", response_model=SSOProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: SSOProviderCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_provider(payload, ctx)


@router.patch("/providers/{provider_id}", response_model=SSOProviderOut)
async def update_provider(
    provider_id: int,
    payload: SSOProviderUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_provider(provider_id, payload, ctx)


@router.post("/providers/{provider_id}/start", response_model=SSOStartOut)
async def start_login(
    provider_id: int,
    payload: SSOStartRequest,
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).start_login(provider_id, payload.organization_id)


@router.post(
    "/providers/{provider_id}/callback",
    response_model=TokenResponse,
    response_model_exclude_none=True,
)
async def callback(
    provider_id: int,
    payload: SSOCallbackRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    tokens = await _get_service(session).handle_callback_with_session_metadata(
        provider_id,
        payload,
        client_ip=resolve_client_ip(request),
        user_agent=resolve_user_agent(request),
    )
    set_access_token_cookie(response, tokens.access_token)
    set_csrf_token_cookie(response, generate_csrf_token())
    if tokens.refresh_token:
        set_refresh_token_cookie(response, tokens.refresh_token)
    return serialize_auth_response(request, tokens)
