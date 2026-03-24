from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.form_config import FormConfiguration


class FormConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> FormConfiguration:
        fc = FormConfiguration(**kwargs)
        self.session.add(fc)
        await self.session.flush()
        return fc

    async def deactivate_scope(
        self,
        organization_id: int,
        project_id: int | None,
        *,
        exclude_config_id: int | None = None,
    ) -> None:
        filters = [
            FormConfiguration.organization_id == organization_id,
            FormConfiguration.is_active == True,  # noqa: E712
        ]
        if project_id is None:
            filters.append(FormConfiguration.project_id.is_(None))
        else:
            filters.append(FormConfiguration.project_id == project_id)
        if exclude_config_id is not None:
            filters.append(FormConfiguration.id != exclude_config_id)

        await self.session.execute(
            update(FormConfiguration)
            .where(*filters)
            .values(is_active=False)
        )

    async def get_by_id(self, config_id: int) -> FormConfiguration | None:
        result = await self.session.execute(
            select(FormConfiguration).where(FormConfiguration.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, config_id: int) -> FormConfiguration:
        fc = await self.get_by_id(config_id)
        if not fc:
            raise AppError("NOT_FOUND", 404, f"Form configuration {config_id} not found")
        return fc

    async def list_by_org(
        self, org_id: int, page: int = 1, page_size: int = 50
    ) -> tuple[list[FormConfiguration], int]:
        filters = [FormConfiguration.organization_id == org_id]
        count_q = select(func.count()).select_from(FormConfiguration).where(*filters)
        total = (await self.session.execute(count_q)).scalar_one()
        q = (
            select(FormConfiguration)
            .where(*filters)
            .order_by(FormConfiguration.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def get_active_for_project(
        self, project_id: int, organization_id: int
    ) -> FormConfiguration | None:
        result = await self.session.execute(
            select(FormConfiguration).where(
                FormConfiguration.organization_id == organization_id,
                FormConfiguration.is_active == True,  # noqa: E712
                or_(
                    FormConfiguration.project_id == project_id,
                    FormConfiguration.project_id.is_(None),
                ),
            ).order_by(
                case((FormConfiguration.project_id == project_id, 0), else_=1),
                FormConfiguration.id.desc(),
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def update(self, config_id: int, **kwargs) -> FormConfiguration:
        fc = await self.get_or_raise(config_id)
        for key, value in kwargs.items():
            if hasattr(fc, key):
                setattr(fc, key, value)
        await self.session.flush()
        return fc
