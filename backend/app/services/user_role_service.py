from sqlalchemy import func, select

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.repositories.audit_repo import AuditRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository


class UserRoleService:
    def __init__(
        self,
        user_repo: UserRepository,
        role_binding_repo: RoleBindingRepository,
        audit_repo: AuditRepository,
    ):
        self.user_repo = user_repo
        self.role_binding_repo = role_binding_repo
        self.audit_repo = audit_repo

    async def _get_user_or_raise(self, user_id: int) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise AppError("NOT_FOUND", 404, f"User {user_id} not found")
        return user

    async def _get_binding_or_raise(self, binding_id: int) -> RoleBinding:
        binding = await self.role_binding_repo.get_binding_by_id(binding_id)
        if not binding:
            raise AppError("NOT_FOUND", 404, f"Role binding {binding_id} not found")
        return binding

    async def _validate_scope(self, scope_type: str, scope_id: int | None) -> None:
        if scope_type == "platform":
            if scope_id is not None:
                raise AppError("INVALID_SCOPE", 422, "Platform-scoped role must not have scope_id")
            return
        if scope_id is None:
            raise AppError("INVALID_SCOPE", 422, "Organization-scoped role requires scope_id")
        org_result = await self.user_repo.session.execute(
            select(Organization.id).where(Organization.id == scope_id)
        )
        if org_result.scalar_one_or_none() is None:
            raise AppError("NOT_FOUND", 404, f"Organization {scope_id} not found")

    async def _active_admin_count(self, org_id: int, *, exclude_user_id: int | None = None) -> int:
        query = (
            select(func.count())
            .select_from(RoleBinding)
            .join(User, User.id == RoleBinding.user_id)
            .where(
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == org_id,
                RoleBinding.role == "admin",
                User.is_active == True,
            )
        )
        if exclude_user_id is not None:
            query = query.where(RoleBinding.user_id != exclude_user_id)
        result = await self.user_repo.session.execute(query)
        return int(result.scalar_one())

    async def _authorize_read(self, ctx: RequestContext, user_id: int) -> tuple[str, int | None]:
        if ctx.is_platform_admin:
            return "platform", None
        if ctx.role != "admin" or not ctx.organization_id:
            raise AppError("FORBIDDEN", 403, "Only admin or platform admin can view role bindings")
        return "organization", ctx.organization_id

    async def _authorize_write(
        self,
        ctx: RequestContext,
        *,
        role: str,
        scope_type: str,
        scope_id: int | None,
    ) -> tuple[str, int | None]:
        if ctx.is_platform_admin:
            return scope_type, scope_id
        if ctx.role != "admin" or not ctx.organization_id:
            raise AppError("FORBIDDEN", 403, "Only admin or platform admin can manage role bindings")
        if scope_type != "organization":
            raise AppError("CANNOT_ASSIGN_PLATFORM_ROLE", 403, "Tenant admin cannot assign platform-scoped roles")
        if role == "platform_admin":
            raise AppError("CANNOT_ASSIGN_PLATFORM_ROLE", 403, "Tenant admin cannot assign platform_admin")
        if scope_id not in (None, ctx.organization_id):
            raise AppError("FORBIDDEN", 403, "Tenant admin can only manage roles in the current organization")
        return "organization", ctx.organization_id

    async def list_roles(self, user_id: int, ctx: RequestContext) -> dict:
        await self._get_user_or_raise(user_id)
        scope_type, scope_id = await self._authorize_read(ctx, user_id)
        bindings = await self.role_binding_repo.get_bindings(user_id)
        if scope_type == "organization":
            bindings = [
                binding
                for binding in bindings
                if binding.scope_type == "organization" and binding.scope_id == scope_id
            ]
        return {
            "user_id": user_id,
            "items": [
                {
                    "id": binding.id,
                    "role": binding.role,
                    "scope_type": binding.scope_type,
                    "scope_id": binding.scope_id,
                }
                for binding in bindings
            ],
        }

    async def create_role(
        self,
        user_id: int,
        *,
        role: str,
        scope_type: str,
        scope_id: int | None,
        ctx: RequestContext,
    ) -> dict:
        await self._get_user_or_raise(user_id)
        resolved_scope_type, resolved_scope_id = await self._authorize_write(
            ctx, role=role, scope_type=scope_type, scope_id=scope_id
        )
        await self._validate_scope(resolved_scope_type, resolved_scope_id)

        existing = await self.role_binding_repo.get_binding(user_id, resolved_scope_type, resolved_scope_id)
        if existing and existing.role == role:
            raise AppError("ROLE_BINDING_EXISTS", 409, "Role binding already exists")
        if existing and existing.role != role:
            raise AppError("ROLE_BINDING_EXISTS", 409, "User already has a role in this scope")

        binding = await self.role_binding_repo.create(
            user_id=user_id,
            role=role,
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            created_by=ctx.user_id,
        )
        await self.audit_repo.log(
            entity_type="RoleBinding",
            entity_id=binding.id,
            action="user_role_binding_created",
            user_id=ctx.user_id,
            organization_id=resolved_scope_id if resolved_scope_type == "organization" else None,
            changes={
                "target_user_id": user_id,
                "role": role,
                "scope_type": resolved_scope_type,
                "scope_id": resolved_scope_id,
            },
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return {
            "id": binding.id,
            "user_id": user_id,
            "role": binding.role,
            "scope_type": binding.scope_type,
            "scope_id": binding.scope_id,
        }

    async def delete_role(self, user_id: int, binding_id: int, ctx: RequestContext) -> dict:
        await self._get_user_or_raise(user_id)
        binding = await self._get_binding_or_raise(binding_id)
        if binding.user_id != user_id:
            raise AppError("FORBIDDEN", 403, "Role binding does not belong to this user")

        if not ctx.is_platform_admin:
            if ctx.role != "admin" or not ctx.organization_id:
                raise AppError("FORBIDDEN", 403, "Only admin or platform admin can remove role bindings")
            if binding.scope_type != "organization" or binding.scope_id != ctx.organization_id:
                raise AppError("FORBIDDEN", 403, "Tenant admin can only remove roles in the current organization")
        if binding.scope_type == "organization" and binding.role == "admin":
            remaining = await self._active_admin_count(binding.scope_id, exclude_user_id=user_id)
            if remaining == 0:
                raise AppError("LAST_ADMIN_CANNOT_LEAVE", 422, "Cannot remove the last admin from this organization")

        await self.role_binding_repo.delete_binding(user_id, binding.scope_type, binding.scope_id)
        await self.audit_repo.log(
            entity_type="RoleBinding",
            entity_id=binding.id,
            action="user_role_binding_deleted",
            user_id=ctx.user_id,
            organization_id=binding.scope_id if binding.scope_type == "organization" else None,
            changes={
                "target_user_id": user_id,
                "role": binding.role,
                "scope_type": binding.scope_type,
                "scope_id": binding.scope_id,
            },
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return {"deleted": True, "binding_id": binding_id}
