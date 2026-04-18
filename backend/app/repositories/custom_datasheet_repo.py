from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.custom_datasheet import CustomDatasheet, CustomDatasheetItem


CUSTOM_DATASHEET_EDITABLE_FIELDS = {"name", "description", "status"}
CUSTOM_DATASHEET_ITEM_EDITABLE_FIELDS = {
    "assignment_id",
    "category",
    "collection_scope",
    "display_group",
    "label_override",
    "help_text",
    "entity_id",
    "facility_id",
    "is_required",
    "sort_order",
    "status",
}


class CustomDatasheetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_datasheet(self, **kwargs) -> CustomDatasheet:
        datasheet = CustomDatasheet(**kwargs)
        self.session.add(datasheet)
        await self.session.flush()
        return datasheet

    async def get_datasheet(self, datasheet_id: int) -> CustomDatasheet | None:
        result = await self.session.execute(
            select(CustomDatasheet).where(CustomDatasheet.id == datasheet_id)
        )
        return result.scalar_one_or_none()

    async def get_datasheet_or_raise(self, datasheet_id: int) -> CustomDatasheet:
        datasheet = await self.get_datasheet(datasheet_id)
        if not datasheet:
            raise AppError("NOT_FOUND", 404, f"Custom datasheet {datasheet_id} not found")
        return datasheet

    async def list_project_datasheets(
        self,
        project_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CustomDatasheet], int]:
        count_result = await self.session.execute(
            select(func.count()).select_from(CustomDatasheet).where(
                CustomDatasheet.reporting_project_id == project_id
            )
        )
        total = int(count_result.scalar_one() or 0)
        result = await self.session.execute(
            select(CustomDatasheet)
            .where(CustomDatasheet.reporting_project_id == project_id)
            .order_by(desc(CustomDatasheet.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def update_datasheet(self, datasheet_id: int, **kwargs) -> CustomDatasheet:
        datasheet = await self.get_datasheet_or_raise(datasheet_id)
        invalid_fields = sorted(set(kwargs) - CUSTOM_DATASHEET_EDITABLE_FIELDS)
        if invalid_fields:
            raise AppError(
                "CUSTOM_DATASHEET_FIELD_NOT_EDITABLE",
                422,
                f"Custom datasheet fields are not editable: {', '.join(invalid_fields)}",
            )
        for key, value in kwargs.items():
            if value is not None:
                setattr(datasheet, key, value)
        await self.session.flush()
        return datasheet

    async def create_datasheet_item(self, **kwargs) -> CustomDatasheetItem:
        item = CustomDatasheetItem(**kwargs)
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_datasheet_item(self, item_id: int) -> CustomDatasheetItem | None:
        result = await self.session.execute(
            select(CustomDatasheetItem).where(CustomDatasheetItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def get_datasheet_item_or_raise(self, item_id: int) -> CustomDatasheetItem:
        item = await self.get_datasheet_item(item_id)
        if not item:
            raise AppError("NOT_FOUND", 404, f"Custom datasheet item {item_id} not found")
        return item

    async def list_datasheet_items(
        self,
        datasheet_id: int,
        *,
        include_archived: bool = False,
    ) -> list[CustomDatasheetItem]:
        query = select(CustomDatasheetItem).where(CustomDatasheetItem.custom_datasheet_id == datasheet_id)
        if not include_archived:
            query = query.where(CustomDatasheetItem.status == "active")
        result = await self.session.execute(
            query
            .order_by(
                CustomDatasheetItem.category,
                CustomDatasheetItem.sort_order,
                CustomDatasheetItem.id,
            )
        )
        return list(result.scalars().all())

    async def update_datasheet_item(self, item_id: int, **kwargs) -> CustomDatasheetItem:
        item = await self.get_datasheet_item_or_raise(item_id)
        invalid_fields = sorted(set(kwargs) - CUSTOM_DATASHEET_ITEM_EDITABLE_FIELDS)
        if invalid_fields:
            raise AppError(
                "CUSTOM_DATASHEET_ITEM_FIELD_NOT_EDITABLE",
                422,
                f"Custom datasheet item fields are not editable: {', '.join(invalid_fields)}",
            )
        for key, value in kwargs.items():
            setattr(item, key, value)
        await self.session.flush()
        return item

    async def archive_datasheet_item(self, item_id: int) -> CustomDatasheetItem:
        return await self.update_datasheet_item(item_id, status="archived")

    async def find_item_duplicate(
        self,
        *,
        datasheet_id: int,
        shared_element_id: int,
        collection_scope: str,
        entity_id: int | None,
        facility_id: int | None,
    ) -> CustomDatasheetItem | None:
        query = select(CustomDatasheetItem).where(
            CustomDatasheetItem.custom_datasheet_id == datasheet_id,
            CustomDatasheetItem.shared_element_id == shared_element_id,
            CustomDatasheetItem.collection_scope == collection_scope,
            CustomDatasheetItem.status == "active",
        )
        if entity_id is None:
            query = query.where(CustomDatasheetItem.entity_id.is_(None))
        else:
            query = query.where(CustomDatasheetItem.entity_id == entity_id)
        if facility_id is None:
            query = query.where(CustomDatasheetItem.facility_id.is_(None))
        else:
            query = query.where(CustomDatasheetItem.facility_id == facility_id)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none()
