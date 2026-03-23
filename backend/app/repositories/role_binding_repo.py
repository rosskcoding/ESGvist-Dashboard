from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.role_binding import RoleBinding


class RoleBindingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_bindings(self, user_id: int) -> list[RoleBinding]:
        result = await self.session.execute(
            select(RoleBinding).where(RoleBinding.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_binding_by_id(self, binding_id: int) -> RoleBinding | None:
        result = await self.session.execute(
            select(RoleBinding).where(RoleBinding.id == binding_id)
        )
        return result.scalar_one_or_none()

    async def get_binding(
        self, user_id: int, scope_type: str, scope_id: int | None
    ) -> RoleBinding | None:
        q = select(RoleBinding).where(
            RoleBinding.user_id == user_id,
            RoleBinding.scope_type == scope_type,
        )
        if scope_id is not None:
            q = q.where(RoleBinding.scope_id == scope_id)
        else:
            q = q.where(RoleBinding.scope_id.is_(None))
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: int,
        role: str,
        scope_type: str,
        scope_id: int | None = None,
        created_by: int | None = None,
    ) -> RoleBinding:
        binding = RoleBinding(
            user_id=user_id,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            created_by=created_by,
        )
        self.session.add(binding)
        await self.session.flush()
        return binding

    async def list_for_scope(self, scope_type: str, scope_id: int | None) -> list[RoleBinding]:
        query = select(RoleBinding).where(RoleBinding.scope_type == scope_type)
        if scope_id is None:
            query = query.where(RoleBinding.scope_id.is_(None))
        else:
            query = query.where(RoleBinding.scope_id == scope_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_role(
        self,
        user_id: int,
        scope_type: str,
        scope_id: int | None,
        role: str,
    ) -> RoleBinding | None:
        binding = await self.get_binding(user_id, scope_type, scope_id)
        if not binding:
            return None
        binding.role = role
        await self.session.flush()
        return binding

    async def delete_binding(
        self,
        user_id: int,
        scope_type: str,
        scope_id: int | None,
    ) -> bool:
        binding = await self.get_binding(user_id, scope_type, scope_id)
        if not binding:
            return False
        await self.session.delete(binding)
        await self.session.flush()
        return True
