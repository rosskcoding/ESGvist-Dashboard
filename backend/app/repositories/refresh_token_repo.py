from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, token: str, expires_at: datetime) -> RefreshToken:
        rt = RefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.session.add(rt)
        await self.session.flush()
        return rt

    async def get_by_token(self, token: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token == token,
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_token(self, token: str) -> None:
        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.token == token)
        )

    async def delete_all_for_user(self, user_id: int) -> None:
        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
