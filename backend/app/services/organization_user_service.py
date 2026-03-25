from sqlalchemy import func, select

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.refresh_token_repo import RefreshTokenRepository
from app.repositories.role_binding_repo import RoleBindingRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import OrganizationUsersOut, OrgUserOut, PendingInvitationOut
from app.services.invitation_service import InvitationService

ROLE_PRIORITY = {
    "admin": 0,
    "esg_manager": 1,
    "reviewer": 2,
    "collector": 3,
    "auditor": 4,
}


class OrganizationUserService:
    def __init__(
        self,
        user_repo: UserRepository,
        role_binding_repo: RoleBindingRepository,
        refresh_token_repo: RefreshTokenRepository,
        invitation_service: InvitationService,
        audit_repo: AuditRepository,
    ):
        self.user_repo = user_repo
        self.role_binding_repo = role_binding_repo
        self.refresh_token_repo = refresh_token_repo
        self.invitation_service = invitation_service
        self.audit_repo = audit_repo

    def _ensure_manage_access(self, ctx: RequestContext) -> int:
        AuthPolicy.require_role(ctx, ["admin", "esg_manager", "platform_admin"])
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        return ctx.organization_id

    async def _get_org_binding_or_raise(self, user_id: int, org_id: int):
        binding = await self.role_binding_repo.get_binding(user_id, "organization", org_id)
        if not binding:
            raise AppError("NOT_FOUND", 404, f"User {user_id} is not a member of this organization")
        return binding

    async def _active_admin_count(self, org_id: int, *, exclude_user_id: int | None = None) -> int:
        query = (
            select(func.count())
            .select_from(RoleBinding)
            .join(User, User.id == RoleBinding.user_id)
            .where(
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == org_id,
                RoleBinding.role == "admin",
                User.is_active,
            )
        )
        if exclude_user_id is not None:
            query = query.where(RoleBinding.user_id != exclude_user_id)
        result = await self.user_repo.session.execute(query)
        return int(result.scalar_one())

    async def _guard_last_admin(self, binding, org_id: int, *, removing_admin_access: bool) -> None:
        if binding.role != "admin" or not removing_admin_access:
            return
        remaining = await self._active_admin_count(org_id, exclude_user_id=binding.user_id)
        if remaining == 0:
            raise AppError(
                "LAST_ADMIN_CANNOT_LEAVE",
                422,
                "Cannot remove or deactivate the last admin in this organization",
            )

    def _guard_user_management(
        self,
        ctx: RequestContext,
        target_user_id: int,
        current_role: str,
        next_role: str | None = None,
        *,
        allow_self_target: bool = False,
    ) -> None:
        if not allow_self_target and target_user_id == ctx.user_id:
            raise AppError("FORBIDDEN", 403, "You cannot modify your own organization access here")
        if ctx.role == "esg_manager" and (current_role == "admin" or next_role == "admin"):
            raise AppError("FORBIDDEN", 403, "Only admins can assign or modify admin access")

    async def list_organization_users(self, ctx: RequestContext) -> OrganizationUsersOut:
        org_id = self._ensure_manage_access(ctx)
        bindings = await self.role_binding_repo.list_for_scope("organization", org_id)
        users = await self.user_repo.list_by_ids([binding.user_id for binding in bindings])
        users_by_id = {user.id: user for user in users}

        bindings_by_user: dict[int, list[RoleBinding]] = {}
        for binding in bindings:
            bindings_by_user.setdefault(binding.user_id, []).append(binding)

        org_users = []
        for user_id in sorted(bindings_by_user):
            user = users_by_id.get(user_id)
            if not user:
                continue
            user_bindings = sorted(
                bindings_by_user[user_id],
                key=lambda item: ROLE_PRIORITY.get(item.role, len(ROLE_PRIORITY)),
            )
            roles = [binding.role for binding in user_bindings]
            org_users.append(
                OrgUserOut(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=roles[0],
                    roles=roles,
                    status="active" if user.is_active else "inactive",
                    joined_date=user.created_at.isoformat() if user.created_at else None,
                )
            )

        pending_invitations = [
            PendingInvitationOut.model_validate(invitation)
            for invitation in await self.invitation_service.list_pending(org_id)
        ]
        return OrganizationUsersOut(users=org_users, pending_invitations=pending_invitations)

    async def update_user_role(self, user_id: int, role: str, ctx: RequestContext) -> dict:
        org_id = self._ensure_manage_access(ctx)
        binding = await self._get_org_binding_or_raise(user_id, org_id)
        self._guard_user_management(ctx, user_id, binding.role, role)
        await self._guard_last_admin(
            binding,
            org_id,
            removing_admin_access=(binding.role == "admin" and role != "admin"),
        )

        updated = await self.role_binding_repo.update_role(user_id, "organization", org_id, role)
        if not updated:
            raise AppError("NOT_FOUND", 404, f"User {user_id} is not a member of this organization")

        await self.audit_repo.log(
            entity_type="RoleBinding",
            entity_id=updated.id,
            action="organization_user_role_updated",
            user_id=ctx.user_id,
            organization_id=org_id,
            changes={"user_id": user_id, "role": role},
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return {"id": user_id, "role": updated.role}

    async def update_user_status(self, user_id: int, status: str, ctx: RequestContext) -> dict:
        """Activate or deactivate a user's membership in THIS organization.

        This does NOT affect the user's global account or memberships in
        other organizations.  Deactivation removes the org role binding
        (reversible by re-inviting).
        """
        org_id = self._ensure_manage_access(ctx)
        binding = await self._get_org_binding_or_raise(user_id, org_id)
        self._guard_user_management(ctx, user_id, binding.role, allow_self_target=False)
        if status not in {"active", "inactive"}:
            raise AppError("INVALID_STATUS", 422, "Status must be either 'active' or 'inactive'")

        is_active = status == "active"
        await self._guard_last_admin(binding, org_id, removing_admin_access=not is_active)

        if not is_active:
            # Deactivate = remove org binding (org-scoped, not global)
            await self.role_binding_repo.delete_all_for_scope(user_id, "organization", org_id)
        else:
            # Re-activate = restore the binding if missing
            existing = await self.role_binding_repo.get_binding(user_id, "organization", org_id)
            if not existing:
                await self.role_binding_repo.create(
                    user_id=user_id,
                    role=binding.role,
                    scope_type="organization",
                    scope_id=org_id,
                    created_by=ctx.user_id,
                )

        await self.audit_repo.log(
            entity_type="User",
            entity_id=user_id,
            action="organization_user_status_updated",
            user_id=ctx.user_id,
            organization_id=org_id,
            changes={"user_id": user_id, "status": status},
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return {"id": user_id, "status": status}

    async def remove_user_from_organization(self, user_id: int, ctx: RequestContext) -> dict:
        org_id = self._ensure_manage_access(ctx)
        binding = await self._get_org_binding_or_raise(user_id, org_id)
        self._guard_user_management(ctx, user_id, binding.role)
        await self._guard_last_admin(binding, org_id, removing_admin_access=True)

        deleted_count = await self.role_binding_repo.delete_all_for_scope(
            user_id, "organization", org_id
        )
        if deleted_count == 0:
            raise AppError("NOT_FOUND", 404, f"User {user_id} is not a member of this organization")

        await self.audit_repo.log(
            entity_type="RoleBinding",
            entity_id=binding.id,
            action="organization_user_removed",
            user_id=ctx.user_id,
            organization_id=org_id,
            changes={"user_id": user_id},
            performed_by_platform_admin=ctx.is_platform_admin,
        )
        return {"user_id": user_id, "removed": True}
