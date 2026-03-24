from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import decode_token, hash_refresh_token, is_hashed_refresh_token
from app.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _normalize_user_agent(user_agent: str | None) -> str | None:
        if not user_agent:
            return None
        normalized = user_agent.strip()
        return normalized[:512] if normalized else None

    @staticmethod
    def _token_jti(refresh_token: str) -> str | None:
        try:
            return decode_token(refresh_token).jti
        except AppError:
            return None

    @staticmethod
    def _token_candidates(token: str) -> list[str]:
        if is_hashed_refresh_token(token):
            return [token]
        return [hash_refresh_token(token), token]

    async def create(
        self,
        user_id: int,
        token: str,
        expires_at: datetime,
        *,
        token_jti: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        rotated_from_id: int | None = None,
        last_used_at: datetime | None = None,
    ) -> RefreshToken:
        rt = RefreshToken(
            user_id=user_id,
            token=hash_refresh_token(token),
            token_jti=token_jti,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=self._normalize_user_agent(user_agent),
            rotated_from_id=rotated_from_id,
            last_used_at=last_used_at,
        )
        self.session.add(rt)
        await self.session.flush()
        return rt

    async def _get_by_identity(
        self,
        *,
        token: str | None = None,
        token_jti: str | None = None,
        include_revoked: bool = False,
        include_expired: bool = False,
    ) -> RefreshToken | None:
        if not token and not token_jti:
            return None

        query = select(RefreshToken)
        if token_jti:
            query = query.where(RefreshToken.token_jti == token_jti)
        else:
            query = query.where(RefreshToken.token.in_(self._token_candidates(token)))

        if not include_revoked:
            query = query.where(RefreshToken.revoked_at.is_(None))
        if not include_expired:
            query = query.where(RefreshToken.expires_at > self._now())

        result = await self.session.execute(query.order_by(RefreshToken.id.desc()))
        return result.scalar_one_or_none()

    async def get_active_by_token(self, token: str) -> RefreshToken | None:
        token_jti = self._token_jti(token)
        session = await self._get_by_identity(token_jti=token_jti)
        if session:
            return session
        return await self._get_by_identity(token=token)

    async def get_any_by_token(self, token: str) -> RefreshToken | None:
        token_jti = self._token_jti(token)
        session = await self._get_by_identity(
            token_jti=token_jti,
            include_revoked=True,
            include_expired=True,
        )
        if session:
            return session
        return await self._get_by_identity(
            token=token,
            include_revoked=True,
            include_expired=True,
        )

    async def get_by_id_for_user(self, session_id: int, user_id: int) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.id == session_id,
                RefreshToken.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: int) -> list[RefreshToken]:
        result = await self.session.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > self._now(),
            )
            .order_by(RefreshToken.created_at.desc(), RefreshToken.id.desc())
        )
        return list(result.scalars().all())

    async def revoke(
        self,
        refresh_session: RefreshToken,
        *,
        reason: str,
        revoked_at: datetime | None = None,
        used_at: datetime | None = None,
    ) -> bool:
        if refresh_session.revoked_at is not None:
            return False
        refresh_session.last_used_at = used_at or self._now()
        refresh_session.revoked_at = revoked_at or self._now()
        refresh_session.revoked_reason = reason
        await self.session.flush()
        return True

    async def revoke_by_token(self, token: str, *, reason: str) -> RefreshToken | None:
        refresh_session = await self.get_active_by_token(token)
        if not refresh_session:
            return None
        await self.revoke(refresh_session, reason=reason)
        return refresh_session

    async def revoke_all_for_user(
        self,
        user_id: int,
        *,
        reason: str,
        except_session_id: int | None = None,
    ) -> int:
        sessions = await self.list_active_for_user(user_id)
        revoked = 0
        for refresh_session in sessions:
            if except_session_id is not None and refresh_session.id == except_session_id:
                continue
            revoked += int(await self.revoke(refresh_session, reason=reason))
        return revoked

    async def delete_all_for_user(self, user_id: int) -> None:
        await self.revoke_all_for_user(user_id, reason="legacy_revoke_all")
