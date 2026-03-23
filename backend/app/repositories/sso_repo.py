from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.sso import ExternalIdentity, SSOLoginState, SSOProvider


class SSORepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_provider(self, **kwargs) -> SSOProvider:
        provider = SSOProvider(**kwargs)
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def get_provider(self, provider_id: int) -> SSOProvider | None:
        result = await self.session.execute(select(SSOProvider).where(SSOProvider.id == provider_id))
        return result.scalar_one_or_none()

    async def get_provider_or_raise(self, provider_id: int) -> SSOProvider:
        provider = await self.get_provider(provider_id)
        if not provider:
            raise AppError("NOT_FOUND", 404, f"SSO provider {provider_id} not found")
        return provider

    async def list_active_providers(self, organization_id: int) -> list[SSOProvider]:
        result = await self.session.execute(
            select(SSOProvider)
            .where(
                SSOProvider.organization_id == organization_id,
                SSOProvider.is_active == True,
            )
            .order_by(SSOProvider.id)
        )
        return list(result.scalars().all())

    async def list_providers(self, organization_id: int) -> list[SSOProvider]:
        result = await self.session.execute(
            select(SSOProvider)
            .where(SSOProvider.organization_id == organization_id)
            .order_by(SSOProvider.id)
        )
        return list(result.scalars().all())

    async def create_login_state(self, **kwargs) -> SSOLoginState:
        state = SSOLoginState(**kwargs)
        self.session.add(state)
        await self.session.flush()
        return state

    async def get_login_state(self, state: str) -> SSOLoginState | None:
        result = await self.session.execute(select(SSOLoginState).where(SSOLoginState.state == state))
        return result.scalar_one_or_none()

    async def get_identity(self, provider_id: int, external_subject: str) -> ExternalIdentity | None:
        result = await self.session.execute(
            select(ExternalIdentity).where(
                ExternalIdentity.sso_provider_id == provider_id,
                ExternalIdentity.external_subject == external_subject,
            )
        )
        return result.scalar_one_or_none()

    async def create_identity(self, **kwargs) -> ExternalIdentity:
        identity = ExternalIdentity(**kwargs)
        self.session.add(identity)
        await self.session.flush()
        return identity
