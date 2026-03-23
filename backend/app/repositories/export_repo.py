from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.export_job import ExportJob


class ExportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(self, **kwargs) -> ExportJob:
        job = ExportJob(**kwargs)
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: int) -> ExportJob | None:
        result = await self.session.execute(select(ExportJob).where(ExportJob.id == job_id))
        return result.scalar_one_or_none()

    async def get_job_or_raise(self, job_id: int) -> ExportJob:
        job = await self.get_job(job_id)
        if not job:
            raise AppError("NOT_FOUND", 404, f"Export job {job_id} not found")
        return job

    async def list_project_jobs(
        self,
        organization_id: int,
        project_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ExportJob], int]:
        total = (
            await self.session.execute(
                select(func.count()).select_from(ExportJob).where(
                    ExportJob.organization_id == organization_id,
                    ExportJob.reporting_project_id == project_id,
                )
            )
        ).scalar_one()
        result = await self.session.execute(
            select(ExportJob)
            .where(
                ExportJob.organization_id == organization_id,
                ExportJob.reporting_project_id == project_id,
            )
            .order_by(ExportJob.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_due_jobs(self, limit: int = 25) -> list[ExportJob]:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ExportJob)
            .where(
                or_(
                    ExportJob.status == "queued",
                    ExportJob.status == "retry_scheduled",
                ),
                or_(
                    ExportJob.next_retry_at.is_(None),
                    ExportJob.next_retry_at <= now,
                ),
            )
            .order_by(ExportJob.next_retry_at, ExportJob.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_active_jobs(self, project_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(ExportJob).where(
                ExportJob.reporting_project_id == project_id,
                ExportJob.status.in_(("queued", "running", "retry_scheduled")),
            )
        )
        return result.scalar_one()

    async def count_statuses(self) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(ExportJob.status, func.count())
                .group_by(ExportJob.status)
            )
        ).all()
        return {status: count for status, count in rows}

    async def count_due_retries(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(func.count()).select_from(ExportJob).where(
                ExportJob.status == "retry_scheduled",
                ExportJob.next_retry_at.is_not(None),
                ExportJob.next_retry_at <= now,
            )
        )
        return result.scalar_one()
