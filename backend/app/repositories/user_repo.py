from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, password_hash: str, full_name: str) -> User:
        user = User(email=email, password_hash=password_hash, full_name=full_name)
        self.session.add(user)
        await self.session.flush()
        return user

    async def list_by_ids(self, user_ids: list[int]) -> list[User]:
        if not user_ids:
            return []
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)))
        return list(result.scalars().all())

    async def set_active(self, user_id: int, is_active: bool) -> User:
        user = await self.get_by_id(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, f"User {user_id} not found")
        user.is_active = is_active
        await self.session.flush()
        return user

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(User))
        return result.scalar_one()
