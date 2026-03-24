from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.calculation_rule import CalculationRule
from app.db.models.data_point import DataPoint
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.calculation_rule_repo import CalculationRuleRepository
from app.schemas.calculations import (
    CalculationRuleCreate,
    CalculationRuleListOut,
    CalculationRuleOut,
    RecalculateResult,
)

logger = logging.getLogger(__name__)


class CalculationService:
    def __init__(
        self,
        repo: CalculationRuleRepository,
        session: AsyncSession,
        audit_repo: AuditRepository | None = None,
    ):
        self.repo = repo
        self.session = session
        self.audit_repo = audit_repo

    async def create_rule(
        self, payload: CalculationRuleCreate, ctx: RequestContext
    ) -> CalculationRuleOut:
        AuthPolicy.require_manager_or_admin(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        rule = await self.repo.create(
            organization_id=ctx.organization_id,
            output_element_id=payload.output_element_id,
            name=payload.name,
            description=payload.description,
            formula=payload.formula,
            input_element_ids=payload.input_element_ids,
            is_active=payload.is_active,
            created_by=ctx.user_id,
        )
        return CalculationRuleOut.model_validate(rule)

    async def list_rules(
        self, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> CalculationRuleListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items, total = await self.repo.list_by_org(ctx.organization_id, page, page_size)
        return CalculationRuleListOut(
            items=[CalculationRuleOut.model_validate(r) for r in items],
            total=total,
        )

    async def recalculate_for_project(
        self, project_id: int, ctx: RequestContext
    ) -> RecalculateResult:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")

        # Get all active rules for this org
        rules, _ = await self.repo.list_by_org(ctx.organization_id, page=1, page_size=1000)
        active_rules = [r for r in rules if r.is_active]

        if not active_rules:
            return RecalculateResult(recalculated=0)

        # Get all data points for this project
        result = await self.session.execute(
            select(DataPoint).where(
                DataPoint.reporting_project_id == project_id,
            )
        )
        all_dp = list(result.scalars().all())

        # Build lookup: element_id -> latest numeric_value
        element_values: dict[int, Decimal | None] = {}
        for dp in all_dp:
            if dp.numeric_value is not None:
                # Keep latest by preferring approved, then most recent
                existing = element_values.get(dp.shared_element_id)
                if existing is None or dp.status == "approved":
                    element_values[dp.shared_element_id] = dp.numeric_value

        recalculated = 0
        errors: list[str] = []

        for rule in active_rules:
            try:
                computed = self._evaluate_formula(rule.formula, element_values)
                if computed is None:
                    continue

                # Find or create a derived data point for this rule's output element
                existing_dp = None
                for dp in all_dp:
                    if (
                        dp.shared_element_id == rule.output_element_id
                        and dp.is_derived
                    ):
                        existing_dp = dp
                        break

                if existing_dp:
                    existing_dp.numeric_value = Decimal(str(computed))
                else:
                    new_dp = DataPoint(
                        reporting_project_id=project_id,
                        shared_element_id=rule.output_element_id,
                        status="draft",
                        numeric_value=Decimal(str(computed)),
                        is_derived=True,
                        calculation_rule_id=rule.id,
                        created_by=ctx.user_id,
                    )
                    self.session.add(new_dp)

                recalculated += 1
            except Exception as e:
                errors.append(f"Rule '{rule.name}' (id={rule.id}): {e}")
                logger.warning("Calculation error for rule %d: %s", rule.id, e)

        await self.session.flush()
        return RecalculateResult(recalculated=recalculated, errors=errors)

    @staticmethod
    def _evaluate_formula(
        formula: dict, values: dict[int, Decimal | None]
    ) -> float | None:
        op = formula.get("op")
        inputs = formula.get("inputs", [])

        resolved: list[float] = []
        for inp in inputs:
            if "literal" in inp:
                resolved.append(float(inp["literal"]))
            elif "element_id" in inp:
                val = values.get(inp["element_id"])
                if val is None:
                    return None  # Cannot compute if any input is missing
                resolved.append(float(val))
            else:
                return None

        if not resolved:
            return None

        if op == "sum":
            return sum(resolved)
        elif op == "subtract":
            result = resolved[0]
            for v in resolved[1:]:
                result -= v
            return result
        elif op == "multiply":
            result = resolved[0]
            for v in resolved[1:]:
                result *= v
            return result
        elif op == "divide":
            if len(resolved) < 2 or resolved[1] == 0:
                return None
            return resolved[0] / resolved[1]
        elif op == "percentage":
            if len(resolved) < 2 or resolved[1] == 0:
                return None
            return (resolved[0] / resolved[1]) * 100
        else:
            return None
