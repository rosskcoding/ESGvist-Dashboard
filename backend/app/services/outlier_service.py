from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.data_point import DataPoint


class OutlierResult:
    __slots__ = ("is_outlier", "reason", "previous_value", "previous_unit", "deviation_pct")

    def __init__(
        self,
        is_outlier: bool = False,
        reason: str | None = None,
        previous_value: Decimal | None = None,
        previous_unit: str | None = None,
        deviation_pct: float | None = None,
    ):
        self.is_outlier = is_outlier
        self.reason = reason
        self.previous_value = previous_value
        self.previous_unit = previous_unit
        self.deviation_pct = deviation_pct


class OutlierService:
    def __init__(self, session: AsyncSession, threshold: float | None = None):
        self.session = session
        self.threshold = threshold or settings.outlier_threshold_percent

    async def check_outliers_batch(
        self, data_points: list[DataPoint],
    ) -> dict[int, OutlierResult]:
        if not data_points:
            return {}

        current_ids = {dp.id for dp in data_points}
        element_ids = sorted({dp.shared_element_id for dp in data_points})
        entity_ids = sorted(
            {eid for dp in data_points for eid in (dp.entity_id, dp.facility_id) if eid is not None}
        )

        # Fetch all approved data points for same elements — candidates for "previous value"
        query = (
            select(DataPoint)
            .where(
                DataPoint.shared_element_id.in_(element_ids),
                DataPoint.status == "approved",
                DataPoint.id.notin_(current_ids),
            )
            .order_by(DataPoint.updated_at.desc())
        )
        result = await self.session.execute(query)
        all_approved = list(result.scalars().all())

        # Group by (shared_element_id, entity_id) — pick most recent per group
        previous_map: dict[tuple[int, int | None], DataPoint] = {}
        for dp in all_approved:
            key = (dp.shared_element_id, dp.entity_id)
            if key not in previous_map:
                previous_map[key] = dp

        # Check each current data point against its previous
        outliers: dict[int, OutlierResult] = {}
        for dp in data_points:
            key = (dp.shared_element_id, dp.entity_id)
            prev = previous_map.get(key)
            if prev is None or dp.numeric_value is None or prev.numeric_value is None:
                outliers[dp.id] = OutlierResult(
                    previous_value=prev.numeric_value if prev else None,
                    previous_unit=prev.unit_code if prev else None,
                )
                continue

            prev_val = float(prev.numeric_value)
            curr_val = float(dp.numeric_value)

            if prev_val == 0:
                if curr_val != 0:
                    outliers[dp.id] = OutlierResult(
                        is_outlier=True,
                        reason=f"Previous value was 0, current is {curr_val}",
                        previous_value=prev.numeric_value,
                        previous_unit=prev.unit_code,
                        deviation_pct=None,
                    )
                else:
                    outliers[dp.id] = OutlierResult(
                        previous_value=prev.numeric_value,
                        previous_unit=prev.unit_code,
                    )
                continue

            deviation = abs(curr_val - prev_val) / abs(prev_val) * 100
            if deviation > self.threshold:
                direction = "increased" if curr_val > prev_val else "decreased"
                outliers[dp.id] = OutlierResult(
                    is_outlier=True,
                    reason=f"Value {direction} by {deviation:.1f}% from previous ({prev_val})",
                    previous_value=prev.numeric_value,
                    previous_unit=prev.unit_code,
                    deviation_pct=deviation,
                )
            else:
                outliers[dp.id] = OutlierResult(
                    previous_value=prev.numeric_value,
                    previous_unit=prev.unit_code,
                    deviation_pct=deviation,
                )

        return outliers
