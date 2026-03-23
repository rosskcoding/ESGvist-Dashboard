import json
import re
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_data_point_for_ctx, get_project_for_ctx
from app.core.config import settings
from app.core.dependencies import RequestContext
from app.db.models.ai_interaction import AIInteraction
from app.db.models.boundary import BoundaryMembership
from app.db.models.completeness import RequirementItemDataPoint, RequirementItemStatus
from app.db.models.data_point import DataPoint
from app.db.models.evidence import DataPointEvidence
from app.db.models.requirement_item import RequirementItem
from app.db.models.standard import DisclosureRequirement, Standard
from app.db.models.shared_element import SharedElement
from app.policies.ai_gate import (
    AIActionGate,
    AIContextGate,
    AIOutputGate,
    AIPermissionGate,
    AIPromptGate,
    AIRateGate,
)
from app.schemas.ai import (
    AIResponse,
    AIStatusOut,
    AskRequest,
    ExplainRequest,
    Reference,
    ReviewAssistResponse,
    SuggestedAction,
)


class BaseAIProvider:
    provider_name = "base"
    capabilities = [
        "explain_field",
        "explain_completeness",
        "explain_boundary",
        "ask",
        "review_assist",
    ]

    def __init__(self, model_name: str):
        self.model_name = model_name


class StaticAIProvider(BaseAIProvider):
    provider_name = "static"

    def __init__(self, model_name: str):
        super().__init__(model_name)

    async def explain_field(self, context: dict) -> AIResponse:
        item = context.get("requirement_item", {})
        requires_evidence = item.get("requires_evidence")
        reasons = [
            f"Field type: {item.get('item_type', 'unknown')}",
            f"Expected value type: {item.get('value_type', 'unknown')}",
        ]
        if requires_evidence:
            reasons.append("Supporting evidence is required for this item")
        return AIResponse(
            text=(
                f"'{item.get('name', 'This field')}' captures a required ESG disclosure input for the "
                f"current reporting workflow."
            ),
            reasons=reasons,
            references=[
                Reference(
                    title=item.get("name", "Requirement item"),
                    source="Requirement Item Registry",
                )
            ],
            confidence="high",
            provider=self.provider_name,
        )

    async def explain_completeness(self, context: dict) -> AIResponse:
        status_counts = context.get("status_counts", {})
        reasons = []
        if status_counts.get("missing"):
            reasons.append(f"{status_counts['missing']} requirement items are still missing")
        if status_counts.get("partial"):
            reasons.append(f"{status_counts['partial']} requirement items are only partially complete")
        if not reasons:
            reasons.append("No completeness blockers were detected in the visible scope")
        return AIResponse(
            text=(
                f"Project completeness is {context.get('completion_percent', 0)}% "
                f"for the visible scope."
            ),
            reasons=reasons,
            next_actions=[
                SuggestedAction(
                    label="Open collection workspace",
                    action_type="navigate",
                    target="/collection",
                    description="Review missing or partial data points",
                )
            ],
            confidence="high" if context.get("completion_percent", 0) >= 80 else "medium",
            provider=self.provider_name,
        )

    async def explain_boundary(self, context: dict) -> AIResponse:
        if context.get("visibility") == "collector_limited":
            return AIResponse(
                text="Boundary details are limited for your role. Use your assigned collection scope as the source of truth.",
                reasons=["Collector AI view does not expose full boundary rules"],
                confidence="medium",
                provider=self.provider_name,
            )

        inclusion = context.get("inclusion_status")
        if inclusion is None:
            text = "Boundary explanation requires a project and entity context."
            reasons = ["No boundary decision could be verified from the provided context"]
        elif inclusion:
            text = "This entity is included in the active project boundary."
            reasons = [context.get("boundary_reason", "A matching boundary membership includes this entity.")]
        else:
            text = "This entity is excluded from the active project boundary."
            reasons = [context.get("boundary_reason", "No active inclusion rule was found for this entity.")]
        return AIResponse(
            text=text,
            reasons=reasons,
            confidence="high" if inclusion is not None else "low",
            provider=self.provider_name,
        )

    async def ask(self, question: str, context: dict) -> AIResponse:
        screen = context.get("screen") or "current workspace"
        actions = [
            SuggestedAction(
                label="Open current workspace",
                action_type="navigate",
                target=f"/{screen}" if not str(screen).startswith("/") else str(screen),
                description="Stay in the current UI flow while resolving the issue",
            )
        ]
        references = []
        if context.get("project_name"):
            references.append(Reference(title=context["project_name"], source="Reporting Project"))
        return AIResponse(
            text=f"AI guidance is based on the '{screen}' screen context. Question received: {question}",
            reasons=["Response was generated from filtered backend context", "No write action was executed"],
            next_actions=actions,
            references=references or None,
            confidence="medium",
            provider=self.provider_name,
        )

    async def review_assist(self, context: dict) -> ReviewAssistResponse:
        missing_evidence = []
        if context.get("evidence_count", 0) == 0:
            missing_evidence.append("No evidence linked to this data point")

        anomalies = []
        if context.get("status") != "in_review":
            anomalies.append(f"Status is '{context.get('status')}', not 'in_review'")
        if context.get("numeric_value") is None and not context.get("text_value"):
            anomalies.append("Data point has no reported value")

        draft_comment = None
        if context.get("status") == "in_review" and missing_evidence:
            draft_comment = "Please attach supporting evidence before approval."

        summary = (
            f"Data point #{context['data_point_id']} records "
            f"{context.get('shared_element_name', 'an ESG metric')}."
        )
        if context.get("numeric_value") is not None:
            summary += f" Current numeric value: {context['numeric_value']}."

        return ReviewAssistResponse(
            summary=summary,
            anomalies=anomalies,
            missing_evidence=missing_evidence,
            draft_comment=draft_comment,
            reuse_impact=f"Reused in {context.get('binding_count', 0)} requirement item(s).",
            provider=self.provider_name,
        )


class GroundedAIProvider(StaticAIProvider):
    provider_name = "grounded"

    async def explain_field(self, context: dict) -> AIResponse:
        item = context.get("requirement_item", {})
        reasons = []
        if item.get("description"):
            reasons.append(item["description"])
        if item.get("is_required"):
            reasons.append("This field is marked as required in the active disclosure")
        if item.get("requires_evidence"):
            reasons.append("Approved values for this field require supporting evidence")
        if item.get("standard_code"):
            reasons.append(f"Grounded in {item['standard_code']} / {item.get('disclosure_code', 'disclosure')}")
        if not reasons:
            reasons = ["Field guidance was generated from the available requirement metadata"]
        return AIResponse(
            text=(
                f"{item.get('name', 'This field')} expects a "
                f"{item.get('value_type', 'structured')} value for the current ESG disclosure."
            ),
            reasons=reasons[:4],
            references=[
                Reference(
                    title=item.get("name", "Requirement item"),
                    source=item.get("standard_code", "Requirement Item Registry"),
                )
            ],
            next_actions=[
                SuggestedAction(
                    label="Open field details",
                    action_type="open_dialog",
                    target="/requirements",
                    description="Review the requirement definition before entering data",
                )
            ],
            confidence="high",
            provider=self.provider_name,
        )

    async def explain_completeness(self, context: dict) -> AIResponse:
        missing_items = context.get("missing_items", [])
        partial_items = context.get("partial_items", [])
        reasons = []
        if missing_items:
            reasons.append(f"Missing items: {', '.join(missing_items[:3])}")
        if partial_items:
            reasons.append(f"Partial items: {', '.join(partial_items[:3])}")
        if context.get("scope_note"):
            reasons.append(f"Visible scope: {context['scope_note']}")
        if not reasons:
            reasons.append("No completeness blockers were detected in the grounded project state")
        return AIResponse(
            text=(
                f"Project '{context.get('project_name', 'project')}' is {context.get('completion_percent', 0)}% complete."
            ),
            reasons=reasons,
            next_actions=[
                SuggestedAction(
                    label="Review blockers",
                    action_type="navigate",
                    target="/dashboard",
                    description="Open the dashboard and resolve missing or partial requirements",
                )
            ],
            references=[
                Reference(title=context.get("project_name", "Project"), source="Reporting Project")
            ],
            confidence="high" if not missing_items and not partial_items else "medium",
            provider=self.provider_name,
        )

    async def ask(self, question: str, context: dict) -> AIResponse:
        lowered = question.lower()
        reasons = ["Answer grounded in backend context and current screen state"]
        references = []
        if context.get("project_name"):
            references.append(Reference(title=context["project_name"], source="Reporting Project"))
        if "boundary" in lowered and context.get("project_name"):
            text = f"Boundary questions should be resolved in the context of project '{context['project_name']}'."
            if context.get("project_status"):
                reasons.append(f"Current project status: {context['project_status']}")
        elif "complete" in lowered or "missing" in lowered:
            text = (
                f"Use the completeness workspace for '{context.get('project_name', 'the project')}' "
                "to inspect missing and partial items."
            )
            if context.get("project_status"):
                reasons.append(f"Project status: {context['project_status']}")
        else:
            text = f"AI guidance is grounded in the '{context.get('screen') or 'current'}' workspace context."
        return AIResponse(
            text=text,
            reasons=reasons,
            next_actions=[
                SuggestedAction(
                    label="Open current workspace",
                    action_type="navigate",
                    target=f"/{context.get('screen')}" if context.get("screen") else "/dashboard",
                    description="Continue from the active workflow context",
                )
            ],
            references=references or None,
            confidence="medium",
            provider=self.provider_name,
        )

    async def review_assist(self, context: dict) -> ReviewAssistResponse:
        anomalies = list(context.get("anomaly_flags", []))
        if context.get("value_delta_percent") is not None:
            anomalies.append(f"Value delta vs peer baseline: {context['value_delta_percent']}%")
        response = await super().review_assist(context)
        response.anomalies = sorted(set(response.anomalies + anomalies))
        response.provider = self.provider_name
        return response


class UnavailableAIProvider(BaseAIProvider):
    provider_name = "unavailable"

    async def explain_field(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def explain_completeness(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def explain_boundary(self, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def ask(self, question: str, context: dict) -> AIResponse:
        raise RuntimeError("Primary AI provider unavailable")

    async def review_assist(self, context: dict) -> ReviewAssistResponse:
        raise RuntimeError("Primary AI provider unavailable")


class AIAssistantService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_gate = AIPermissionGate()
        self.context_gate = AIContextGate()
        self.prompt_gate = AIPromptGate()
        self.action_gate = AIActionGate()
        self.output_gate = AIOutputGate()
        self.rate_gate = AIRateGate()
        self.configured_provider = getattr(settings, "ai_provider", "static")
        model_name = settings.ai_model if hasattr(settings, "ai_model") else "static-ai"
        self.primary_provider = self._build_provider(self.configured_provider, model_name)
        self.fallback_provider = StaticAIProvider(model_name="static-fallback")

    @staticmethod
    def _build_provider(provider_name: str, model_name: str) -> BaseAIProvider:
        normalized = (provider_name or "static").lower()
        if not getattr(settings, "ai_enabled", False):
            return StaticAIProvider(model_name="static-ai")
        if normalized == "grounded":
            return GroundedAIProvider(model_name=model_name)
        if normalized == "unavailable":
            return UnavailableAIProvider(model_name=model_name)
        return StaticAIProvider(model_name=model_name)

    async def _invoke_provider(self, method_name: str, *args):
        provider = self.primary_provider
        try:
            result = await getattr(provider, method_name)(*args)
            return result, provider.model_name, False
        except Exception:
            if provider.model_name == self.fallback_provider.model_name:
                raise
            fallback_result = await getattr(self.fallback_provider, method_name)(*args)
            if isinstance(fallback_result, AIResponse):
                fallback_result.reasons = list(fallback_result.reasons or []) + ["Fallback provider was used"]
            elif isinstance(fallback_result, ReviewAssistResponse):
                fallback_result.anomalies = list(fallback_result.anomalies or []) + ["Fallback provider was used"]
            return fallback_result, self.fallback_provider.model_name, True

    def get_status(self) -> AIStatusOut:
        return AIStatusOut(
            enabled=getattr(settings, "ai_enabled", False),
            configured_provider=self.configured_provider,
            effective_provider=self.primary_provider.provider_name,
            model=self.primary_provider.model_name,
            fallback_model=self.fallback_provider.model_name,
            capabilities=list(self.primary_provider.capabilities),
        )

    async def _log(
        self,
        *,
        ctx: RequestContext,
        action: str,
        screen: str | None,
        question: str | None,
        safe_context: dict | None,
        response_summary: str | None,
        latency_ms: int,
        gate_blocked: bool = False,
        gate_reason: str | None = None,
        tools_blocked: list[str] | None = None,
        output_filtered: bool = False,
        output_filter_reason: str | None = None,
        model_name: str | None = None,
    ) -> None:
        interaction = AIInteraction(
            user_id=ctx.user_id,
            organization_id=ctx.organization_id,
            role=ctx.role or "unknown",
            screen=screen,
            action=action,
            context_summary=json.dumps(safe_context or {}, default=str)[:500],
            question=question[:500] if question else None,
            response_summary=response_summary[:500] if response_summary else None,
            model=model_name or self.primary_provider.model_name,
            latency_ms=latency_ms,
            gate_blocked=gate_blocked,
            gate_reason=gate_reason,
            tools_blocked=",".join(tools_blocked or []) if tools_blocked else None,
            output_filtered=output_filtered,
            output_filter_reason=output_filter_reason,
        )
        self.session.add(interaction)
        await self.session.flush()
        await self.session.commit()

    async def _run_ai_action(
        self,
        *,
        action: str,
        ctx: RequestContext,
        screen: str | None,
        question: str | None,
        raw_context_builder,
        response_builder,
    ):
        started = perf_counter()
        safe_context: dict | None = None
        clean_question = None
        try:
            self.rate_gate.check(ctx)
            self.permission_gate.check(action, ctx)
            raw_context = await raw_context_builder()
            safe_context = await self.context_gate.filter(raw_context, ctx)
            if question is not None:
                clean_question = self.prompt_gate.sanitize_question(question)
            provider_response = await response_builder(safe_context, clean_question)
            if isinstance(provider_response, tuple):
                response, model_name, used_fallback = provider_response
            else:
                response = provider_response
                model_name = self.primary_provider.model_name
                used_fallback = False
            if isinstance(response, AIResponse):
                response, output_filtered, filter_reason = self.output_gate.validate(response, ctx)
                if response.next_actions:
                    original_count = len(response.next_actions)
                    response.next_actions = self.action_gate.filter_actions(response.next_actions, ctx)
                    if len(response.next_actions) != original_count:
                        output_filtered = True
                        filter_reason = ",".join(
                            value for value in [filter_reason, "action_gate"] if value
                        )
                if used_fallback:
                    output_filtered = True
                    filter_reason = ",".join(value for value in [filter_reason, "provider_fallback"] if value)
                await self._log(
                    ctx=ctx,
                    action=action,
                    screen=screen,
                    question=clean_question,
                    safe_context=safe_context,
                    response_summary=response.text,
                    latency_ms=int((perf_counter() - started) * 1000),
                    output_filtered=output_filtered,
                    output_filter_reason=filter_reason,
                    model_name=model_name,
                )
            else:
                await self._log(
                    ctx=ctx,
                    action=action,
                    screen=screen,
                    question=clean_question,
                    safe_context=safe_context,
                    response_summary=response.summary,
                    latency_ms=int((perf_counter() - started) * 1000),
                    model_name=model_name,
                )
            return response
        except Exception as exc:
            if hasattr(exc, "code"):
                await self._log(
                    ctx=ctx,
                    action=action,
                    screen=screen,
                    question=clean_question or question,
                    safe_context=safe_context,
                    response_summary=None,
                    latency_ms=int((perf_counter() - started) * 1000),
                    gate_blocked=True,
                    gate_reason=getattr(exc, "code", None),
                )
                raise

            fallback = self.output_gate.fallback("AI backend failed to produce a verified response.")
            await self._log(
                ctx=ctx,
                action=action,
                screen=screen,
                question=clean_question or question,
                safe_context=safe_context,
                response_summary=fallback.text,
                latency_ms=int((perf_counter() - started) * 1000),
                gate_blocked=True,
                gate_reason="AI_UNAVAILABLE",
                output_filtered=True,
                output_filter_reason="fallback",
            )
            return fallback

    async def explain_field(self, payload: ExplainRequest, ctx: RequestContext) -> AIResponse:
        async def raw_context_builder() -> dict:
            requirement_item = None
            disclosure = None
            standard = None
            if payload.requirement_item_id:
                result = await self.session.execute(
                    select(RequirementItem).where(RequirementItem.id == payload.requirement_item_id)
                )
                requirement_item = result.scalar_one_or_none()
                if requirement_item:
                    disclosure = (
                        await self.session.execute(
                            select(DisclosureRequirement).where(
                                DisclosureRequirement.id == requirement_item.disclosure_requirement_id
                            )
                        )
                    ).scalar_one_or_none()
                if disclosure:
                    standard = (
                        await self.session.execute(select(Standard).where(Standard.id == disclosure.standard_id))
                    ).scalar_one_or_none()
            return {
                "organization_id": ctx.organization_id,
                "requirement_item": {
                    "id": requirement_item.id if requirement_item else None,
                    "name": requirement_item.name if requirement_item else "Field",
                    "item_type": requirement_item.item_type if requirement_item else None,
                    "value_type": requirement_item.value_type if requirement_item else None,
                    "requires_evidence": requirement_item.requires_evidence if requirement_item else False,
                    "is_required": requirement_item.is_required if requirement_item else False,
                    "description": requirement_item.description if requirement_item else None,
                    "standard_code": standard.code if standard else None,
                    "disclosure_code": disclosure.code if disclosure else None,
                },
            }

        return await self._run_ai_action(
            action="explain_field",
            ctx=ctx,
            screen="field_explain",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_field", safe_context
            ),
        )

    async def explain_completeness(self, payload: ExplainRequest, ctx: RequestContext) -> AIResponse:
        async def raw_context_builder() -> dict:
            project = await get_project_for_ctx(self.session, payload.project_id or 0, ctx)
            status_rows = (
                await self.session.execute(
                    select(RequirementItemStatus.status, func.count())
                    .where(RequirementItemStatus.reporting_project_id == project.id)
                    .group_by(RequirementItemStatus.status)
                )
            ).all()
            status_counts = {status: count for status, count in status_rows}
            total = sum(status_counts.values())
            completion_percent = round((status_counts.get("complete", 0) / total) * 100, 1) if total else 0
            detail_rows = (
                await self.session.execute(
                    select(RequirementItem.name, RequirementItemStatus.status)
                    .join(RequirementItem, RequirementItem.id == RequirementItemStatus.requirement_item_id)
                    .where(RequirementItemStatus.reporting_project_id == project.id)
                    .order_by(RequirementItem.id)
                )
            ).all()
            return {
                "organization_id": project.organization_id,
                "project_id": project.id,
                "project_name": project.name,
                "status_counts": status_counts,
                "completion_percent": completion_percent,
                "scope_note": "own scope" if ctx.role == "collector" else "assigned scope" if ctx.role == "reviewer" else "project scope",
                "missing_items": [name for name, status in detail_rows if status == "missing"],
                "partial_items": [name for name, status in detail_rows if status == "partial"],
                "complete_items": [name for name, status in detail_rows if status == "complete"],
            }

        return await self._run_ai_action(
            action="explain_completeness",
            ctx=ctx,
            screen="completeness",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_completeness", safe_context
            ),
        )

    async def explain_boundary(self, payload: ExplainRequest, ctx: RequestContext) -> AIResponse:
        async def raw_context_builder() -> dict:
            raw_context = {
                "organization_id": ctx.organization_id,
                "entity_id": payload.entity_id,
            }
            if payload.project_id:
                project = await get_project_for_ctx(self.session, payload.project_id, ctx)
                raw_context["project_id"] = project.id
                raw_context["project_name"] = project.name
                raw_context["organization_id"] = project.organization_id
                if payload.entity_id and project.boundary_definition_id:
                    membership = (
                        await self.session.execute(
                            select(BoundaryMembership).where(
                                BoundaryMembership.boundary_definition_id == project.boundary_definition_id,
                                BoundaryMembership.entity_id == payload.entity_id,
                            )
                        )
                    ).scalar_one_or_none()
                    raw_context["inclusion_status"] = membership.included if membership else False
                    raw_context["boundary_reason"] = (
                        f"Inclusion source: {membership.inclusion_source}"
                        if membership
                        else "No boundary membership includes this entity"
                    )
                    raw_context["boundary_rules"] = {
                        "boundary_id": project.boundary_definition_id,
                    }
            return raw_context

        return await self._run_ai_action(
            action="explain_boundary",
            ctx=ctx,
            screen="boundary",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "explain_boundary", safe_context
            ),
        )

    async def ask(self, payload: AskRequest, ctx: RequestContext) -> AIResponse:
        async def raw_context_builder() -> dict:
            raw_context = dict(payload.context or {})
            raw_context["organization_id"] = ctx.organization_id
            raw_context["screen"] = payload.screen
            if payload.context and payload.context.get("project_id"):
                project = await get_project_for_ctx(self.session, payload.context["project_id"], ctx)
                raw_context["project_name"] = project.name
                raw_context["project_status"] = project.status
            return raw_context

        return await self._run_ai_action(
            action="ask",
            ctx=ctx,
            screen=payload.screen,
            question=payload.question,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, clean_question: self._invoke_provider(
                "ask",
                clean_question or "",
                safe_context,
            ),
        )

    async def review_assist(self, data_point_id: int, ctx: RequestContext) -> ReviewAssistResponse | AIResponse:
        async def raw_context_builder() -> dict:
            data_point, project, _ = await get_data_point_for_ctx(self.session, data_point_id, ctx)
            shared_element = (
                await self.session.execute(
                    select(SharedElement).where(SharedElement.id == data_point.shared_element_id)
                )
            ).scalar_one_or_none()
            evidence_count = (
                await self.session.execute(
                    select(func.count()).select_from(DataPointEvidence).where(
                        DataPointEvidence.data_point_id == data_point.id
                    )
                )
            ).scalar_one()
            binding_count = (
                await self.session.execute(
                    select(func.count()).select_from(RequirementItemDataPoint).where(
                        RequirementItemDataPoint.data_point_id == data_point.id
                    )
                )
            ).scalar_one()
            peer_numeric_values = (
                await self.session.execute(
                    select(DataPoint.numeric_value).where(
                        DataPoint.reporting_project_id == project.id,
                        DataPoint.shared_element_id == data_point.shared_element_id,
                        DataPoint.id != data_point.id,
                        DataPoint.numeric_value.is_not(None),
                    )
                )
            ).scalars().all()
            anomaly_flags = []
            value_delta_percent = None
            if data_point.numeric_value is not None and peer_numeric_values:
                peer_average = sum(float(value) for value in peer_numeric_values) / len(peer_numeric_values)
                if peer_average:
                    value_delta_percent = round(((float(data_point.numeric_value) - peer_average) / peer_average) * 100, 1)
                    if abs(value_delta_percent) >= 50:
                        anomaly_flags.append("Value differs materially from peer entries in the same project")
            return {
                "organization_id": project.organization_id,
                "project_id": project.id,
                "data_point_id": data_point.id,
                "status": data_point.status,
                "numeric_value": float(data_point.numeric_value) if data_point.numeric_value is not None else None,
                "text_value": data_point.text_value,
                "shared_element_name": shared_element.name if shared_element else None,
                "evidence_count": evidence_count,
                "binding_count": binding_count,
                "anomaly_flags": anomaly_flags,
                "value_delta_percent": value_delta_percent,
            }

        return await self._run_ai_action(
            action="review_assist",
            ctx=ctx,
            screen="review_assist",
            question=None,
            raw_context_builder=raw_context_builder,
            response_builder=lambda safe_context, _question: self._invoke_provider(
                "review_assist", safe_context
            ),
        )
