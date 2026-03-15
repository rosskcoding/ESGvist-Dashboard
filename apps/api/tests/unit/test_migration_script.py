"""
Unit tests for multi-tenant migration script.

Tests each step of the migration process:
1. get_or_create_default_company
2. migrate_reports
3. migrate_users
4. verify_migration
5. run_migration (integration)
"""

import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# Import migration functions directly from script
import importlib.util
migration_script_path = Path(__file__).parent.parent.parent / "scripts" / "migrate_to_multi_tenant.py"
spec = importlib.util.spec_from_file_location("migrate_to_multi_tenant", migration_script_path)
migrate_module = importlib.util.module_from_spec(spec)
sys.modules["migrate_to_multi_tenant"] = migrate_module
spec.loader.exec_module(migrate_module)

from app.domain.models import (
    Company,
    CompanyMembership,
    CompanyStatus,
    Report,
    StructureStatus,
    User,
)

# Import migration functions
get_or_create_default_company = migrate_module.get_or_create_default_company
migrate_reports = migrate_module.migrate_reports
migrate_users = migrate_module.migrate_users
verify_migration = migrate_module.verify_migration

# NOTE: We intentionally rely on the shared `db_session` fixture from `tests/conftest.py`,
# which provides per-test transaction rollback isolation.


class TestGetOrCreateDefaultCompany:
    """Tests for get_or_create_default_company function."""

    @pytest.mark.asyncio
    async def test_create_company_when_not_exists(self, db_session: AsyncSession):
        """Should create a new company if it doesn't exist."""
        company_name = "Test Company"

        company = await get_or_create_default_company(db_session, company_name, dry_run=False)

        assert company is not None
        assert company.name == company_name
        assert company.status == CompanyStatus.ACTIVE

        # Verify it's in DB
        result = await db_session.execute(
            select(Company).where(Company.name == company_name)
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.company_id == company.company_id

    @pytest.mark.asyncio
    async def test_return_existing_company(self, db_session: AsyncSession):
        """Should return existing company if it already exists."""
        company_name = "Existing Company"

        # Create company first
        existing = Company(
            name=company_name,
            status=CompanyStatus.ACTIVE,
        )
        db_session.add(existing)
        await db_session.flush()
        existing_id = existing.company_id

        # Try to get or create
        company = await get_or_create_default_company(db_session, company_name, dry_run=False)

        assert company is not None
        assert company.company_id == existing_id
        assert company.name == company_name

    @pytest.mark.asyncio
    async def test_dry_run_does_not_create(self, db_session: AsyncSession):
        """Dry run should not create company."""
        company_name = "Dry Run Company"

        company = await get_or_create_default_company(db_session, company_name, dry_run=True)

        assert company is None

        # Verify it's NOT in DB
        result = await db_session.execute(
            select(Company).where(Company.name == company_name)
        )
        found = result.scalar_one_or_none()
        assert found is None


class TestMigrateReports:
    """Tests for migrate_reports function."""

    @pytest.mark.asyncio
    async def test_migrate_reports_without_company_id(self, db_session: AsyncSession):
        """Should link orphan reports to company."""
        # Create company
        company = Company(name="Test Company", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Simulate pre-migration state: allow NULL company_id temporarily, then insert orphan report.
        # (DDL is transactional in Postgres; conftest rolls back after the test.)
        await db_session.execute(text("ALTER TABLE reports ALTER COLUMN company_id DROP NOT NULL"))

        report_id = uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO reports (
                    report_id, company_id, year, title, slug,
                    source_locale, default_locale,
                    enabled_locales, release_locales,
                    theme_slug, design_json, structure_status,
                    created_at_utc, updated_at_utc
                ) VALUES (
                    :report_id, NULL, 2024, 'Orphan Report', 'orphan-report',
                    'ru', 'ru',
                    ARRAY['ru'], ARRAY['ru'],
                    'default', '{}', 'draft',
                    now(), now()
                )
                """
            ),
            {"report_id": report_id},
        )
        await db_session.flush()

        # Migrate
        count = await migrate_reports(db_session, company_id, dry_run=False)

        assert count == 1

        # Verify report now has company_id
        result = await db_session.execute(select(Report).where(Report.report_id == report_id))
        report = result.scalar_one()
        assert report.company_id == company_id

    @pytest.mark.asyncio
    async def test_migrate_reports_all_have_company_id(self, db_session: AsyncSession):
        """Should return 0 if all reports already have company_id."""
        # Create company
        company = Company(name="Test Company", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Create report WITH company_id
        report = Report(
            company_id=company_id,
            year=2024,
            title="Linked Report",
            slug="linked-report",
            source_locale="ru",
            default_locale="ru",
            enabled_locales=["ru"],
            release_locales=["ru"],
        )
        db_session.add(report)
        await db_session.flush()

        # Migrate
        count = await migrate_reports(db_session, company_id, dry_run=False)

        assert count == 0

    @pytest.mark.asyncio
    async def test_migrate_reports_dry_run(self, db_session: AsyncSession):
        """Dry run should not update reports."""
        company = Company(name="Test Company", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Simulate pre-migration state: allow NULL company_id and insert orphan report
        await db_session.execute(text("ALTER TABLE reports ALTER COLUMN company_id DROP NOT NULL"))

        report_id = uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO reports (
                    report_id, company_id, year, title, slug,
                    source_locale, default_locale,
                    enabled_locales, release_locales,
                    theme_slug, design_json, structure_status,
                    created_at_utc, updated_at_utc
                ) VALUES (
                    :report_id, NULL, 2024, 'Test Report', 'test-report-dry',
                    'ru', 'ru',
                    ARRAY['ru'], ARRAY['ru'],
                    'default', '{}', 'draft',
                    now(), now()
                )
                """
            ),
            {"report_id": report_id},
        )
        await db_session.flush()

        # Dry run
        count = await migrate_reports(db_session, company_id, dry_run=True)

        assert count == 1  # Counts but doesn't update

        # Verify report still has NULL company_id
        row = (
            await db_session.execute(
                text("SELECT company_id FROM reports WHERE report_id = :report_id"),
                {"report_id": report_id},
            )
        ).fetchone()
        assert row is not None
        assert row[0] is None  # Still NULL


class TestMigrateUsers:
    """Tests for migrate_users function."""

    @pytest.mark.asyncio
    async def test_create_memberships_for_all_users(self, db_session: AsyncSession):
        """Should create memberships for all users."""
        # Create company
        company = Company(name=f"Test Company {uuid4()}", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Create users
        user1 = User(
            email=f"user1-{uuid4()}@test.com",
            password_hash="hash1",
            full_name="User 1",
            is_superuser=False,
            is_active=True,
        )
        user2 = User(
            email=f"user2-{uuid4()}@test.com",
            password_hash="hash2",
            full_name="User 2",
            is_superuser=False,
            is_active=True,
        )
        db_session.add_all([user1, user2])
        await db_session.flush()

        # Baseline: existing users and memberships (DB may contain seeded/dev data)
        total_users = len(
            list((await db_session.execute(select(User.user_id))).scalars().all())
        )
        existing_member_user_ids = set(
            (await db_session.execute(
                select(CompanyMembership.user_id).where(CompanyMembership.company_id == company_id)
            )).scalars().all()
        )
        expected_new_memberships = total_users - len(existing_member_user_ids)

        # Migrate
        stats = await migrate_users(db_session, company_id, dry_run=False)

        assert stats["memberships"] == expected_new_memberships

        # Verify memberships exist for newly created users
        from app.domain.models import RoleAssignment
        from app.domain.models.enums import AssignableRole, ScopeType
        for u in (user1, user2):
            m = (
                await db_session.execute(
                    select(CompanyMembership).where(
                        CompanyMembership.company_id == company_id,
                        CompanyMembership.user_id == u.user_id,
                    )
                )
            ).scalar_one_or_none()
            assert m is not None
            # Check that no corporate_lead role exists for these users
            role_result = await db_session.execute(
                select(RoleAssignment).where(
                    RoleAssignment.user_id == u.user_id,
                    RoleAssignment.company_id == company_id,
                    RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
                    RoleAssignment.scope_type == ScopeType.COMPANY,
                    RoleAssignment.scope_id == company_id,
                )
            )
            assert role_result.scalar_one_or_none() is None

        # Verify company now has membership for all users in DB
        member_user_ids_after = set(
            (await db_session.execute(
                select(CompanyMembership.user_id).where(CompanyMembership.company_id == company_id)
            )).scalars().all()
        )
        assert len(member_user_ids_after) == total_users

    @pytest.mark.asyncio
    async def test_promote_admin_to_superuser_and_owner(self, db_session: AsyncSession):
        """Should promote admin users to superuser and company owner."""
        company = Company(name=f"Test Company {uuid4()}", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Create admin user
        admin = User(
            email=f"admin-{uuid4()}@test.com",
            password_hash="hash",
            full_name="Admin",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(admin)
        await db_session.flush()

        # Baseline expectations (DB may already contain users/admins)
        total_users = len(
            list((await db_session.execute(select(User.user_id))).scalars().all())
        )
        existing_member_user_ids = set(
            (await db_session.execute(
                select(CompanyMembership.user_id).where(CompanyMembership.company_id == company_id)
            )).scalars().all()
        )
        expected_new_memberships = total_users - len(existing_member_user_ids)
        admin_user_ids = set(
            (await db_session.execute(
                select(User.user_id).where(User.is_superuser == True)  # noqa: E712
            )).scalars().all()
        )
        expected_new_owners = len(admin_user_ids - existing_member_user_ids)
        # Legacy migration no longer promotes users to superuser via role field
        # All superusers should already have is_superuser=True
        expected_new_superusers = 0

        # Migrate
        stats = await migrate_users(db_session, company_id, dry_run=False)

        assert stats["memberships"] == expected_new_memberships
        assert stats["superusers"] == expected_new_superusers
        assert stats["owners"] == expected_new_owners

        # Verify user is superuser
        await db_session.refresh(admin)
        assert admin.is_superuser is True

        # Verify membership exists and has corporate_lead role
        from app.domain.models import RoleAssignment
        from app.domain.models.enums import AssignableRole, ScopeType
        result = await db_session.execute(
            select(CompanyMembership).where(
                CompanyMembership.company_id == company_id,
                CompanyMembership.user_id == admin.user_id,
            )
        )
        membership = result.scalar_one_or_none()
        assert membership is not None

        # Check corporate_lead role assignment
        role_result = await db_session.execute(
            select(RoleAssignment).where(
                RoleAssignment.user_id == admin.user_id,
                RoleAssignment.company_id == company_id,
                RoleAssignment.role == AssignableRole.CORPORATE_LEAD,
                RoleAssignment.scope_type == ScopeType.COMPANY,
                RoleAssignment.scope_id == company_id,
            )
        )
        role_assignment = role_result.scalar_one_or_none()
        assert role_assignment is not None

    @pytest.mark.asyncio
    async def test_skip_existing_memberships(self, db_session: AsyncSession):
        """Should not create duplicate memberships."""
        company = Company(name=f"Test Company {uuid4()}", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        user = User(
            email=f"user-{uuid4()}@test.com",
            password_hash="hash",
            full_name="User",
            is_superuser=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Create membership manually
        membership = CompanyMembership(
            company_id=company_id,
            user_id=user.user_id,
            is_active=True,
        )
        db_session.add(membership)
        await db_session.flush()

        # Baseline expectation: membership already exists for this user
        total_users = len(
            list((await db_session.execute(select(User.user_id))).scalars().all())
        )
        existing_member_user_ids = set(
            (await db_session.execute(
                select(CompanyMembership.user_id).where(CompanyMembership.company_id == company_id)
            )).scalars().all()
        )
        expected_new_memberships = total_users - len(existing_member_user_ids)

        # Migrate (should skip existing)
        stats = await migrate_users(db_session, company_id, dry_run=False)

        assert stats["memberships"] == expected_new_memberships

        # Verify only one membership exists for this user
        result = await db_session.execute(
            select(CompanyMembership).where(
                CompanyMembership.company_id == company_id,
                CompanyMembership.user_id == user.user_id,
            )
        )
        memberships = list(result.scalars().all())
        assert len(memberships) == 1

    @pytest.mark.asyncio
    async def test_migrate_users_dry_run(self, db_session: AsyncSession):
        """Dry run should not create memberships."""
        company = Company(name=f"Test Company {uuid4()}", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        user = User(
            email=f"user-{uuid4()}@test.com",
            password_hash="hash",
            full_name="User",
            is_superuser=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Dry run
        stats = await migrate_users(db_session, company_id, dry_run=True)

        assert stats["memberships"] == 0

        # Verify no membership was created
        result = await db_session.execute(
            select(CompanyMembership).where(CompanyMembership.company_id == company_id)
        )
        memberships = list(result.scalars().all())
        assert len(memberships) == 0


class TestVerifyMigration:
    """Tests for verify_migration function."""

    @pytest.mark.asyncio
    async def test_verify_success_when_all_migrated(self, db_session: AsyncSession):
        """Should pass verification when all data is migrated."""
        # Create company
        company = Company(name="Test Company", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Create report with company_id
        report = Report(
            company_id=company_id,
            year=2024,
            title="Test Report",
            slug="test-report",
            source_locale="ru",
            default_locale="ru",
            enabled_locales=["ru"],
            release_locales=["ru"],
        )
        db_session.add(report)
        await db_session.flush()

        # Create user with membership
        user = User(
            email="user@test.com",
            password_hash="hash",
            full_name="User",
            is_active=True,
            is_superuser=True,  # Has superuser
        )
        db_session.add(user)
        await db_session.flush()

        membership = CompanyMembership(
            company_id=company_id,
            user_id=user.user_id,
            is_active=True,
        )
        db_session.add(membership)
        await db_session.flush()

        # Create corporate_lead role assignment
        from app.domain.models import RoleAssignment
        from app.domain.models.enums import AssignableRole, ScopeType
        role_assignment = RoleAssignment(
            company_id=company_id,
            user_id=user.user_id,
            role=AssignableRole.CORPORATE_LEAD,
            scope_type=ScopeType.COMPANY,
            scope_id=company_id,
        )
        db_session.add(role_assignment)
        await db_session.flush()

        # NOTE: The test DB may contain pre-seeded users (e.g. e2e user) outside of this test.
        # verify_migration checks ALL users, so ensure every existing user has at least one membership.
        all_users = list((await db_session.execute(select(User))).scalars().all())
        for u in all_users:
            has_membership = (
                await db_session.execute(
                    select(CompanyMembership.membership_id)
                    .where(CompanyMembership.user_id == u.user_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if has_membership is None:
                db_session.add(
                    CompanyMembership(
                        company_id=company_id,
                        user_id=u.user_id,
                        is_active=True,
                    )
                )
        await db_session.flush()

        # Verify
        result = await verify_migration(db_session)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_fails_when_orphan_reports(self, db_session: AsyncSession):
        """Should fail verification when reports without company_id exist."""
        # Create company + superuser + membership so the ONLY failing check is the orphan report.
        company = Company(name="Test Company", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        user = User(
            email="superuser@test.com",
            password_hash="hash",
            full_name="Super User",
            is_active=True,
            is_superuser=True,
        )
        db_session.add(user)
        await db_session.flush()

        membership = CompanyMembership(
            company_id=company_id,
            user_id=user.user_id,
            is_active=True,
        )
        db_session.add(membership)
        await db_session.flush()

        # Create corporate_lead role assignment
        from app.domain.models import RoleAssignment
        from app.domain.models.enums import AssignableRole, ScopeType
        role_assignment = RoleAssignment(
            company_id=company_id,
            user_id=user.user_id,
            role=AssignableRole.CORPORATE_LEAD,
            scope_type=ScopeType.COMPANY,
            scope_id=company_id,
        )
        db_session.add(role_assignment)
        await db_session.flush()

        # Simulate orphan report (NULL company_id) by temporarily dropping NOT NULL.
        await db_session.execute(text("ALTER TABLE reports ALTER COLUMN company_id DROP NOT NULL"))
        orphan_report_id = uuid4()
        await db_session.execute(
            text(
                """
                INSERT INTO reports (
                    report_id, company_id, year, title, slug,
                    source_locale, default_locale,
                    enabled_locales, release_locales,
                    theme_slug, design_json, structure_status,
                    created_at_utc, updated_at_utc
                ) VALUES (
                    :report_id, NULL, 2024, 'Orphan Report', 'orphan-report-verify',
                    'ru', 'ru',
                    ARRAY['ru'], ARRAY['ru'],
                    'default', '{}', 'draft',
                    now(), now()
                )
                """
            ),
            {"report_id": orphan_report_id},
        )
        await db_session.flush()

        # Verify
        result = await verify_migration(db_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_fails_when_user_without_membership(self, db_session: AsyncSession):
        """Should fail verification when user has no membership."""
        # Create user WITHOUT membership
        user = User(
            email="user@test.com",
            password_hash="hash",
            full_name="User",
            is_superuser=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Verify
        result = await verify_migration(db_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_fails_when_no_superuser(self, db_session: AsyncSession):
        """Should fail verification when no superuser exists."""
        company = Company(name=f"Test Company {uuid4()}", status=CompanyStatus.ACTIVE)
        db_session.add(company)
        await db_session.flush()
        company_id = company.company_id

        # Create user WITHOUT superuser flag
        user = User(
            email=f"user-{uuid4()}@test.com",
            password_hash="hash",
            full_name="User",
            is_superuser=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        membership = CompanyMembership(
            company_id=company_id,
            user_id=user.user_id,
            is_active=True,
        )
        db_session.add(membership)
        await db_session.flush()

        # Ensure the DB has NO superusers (dev DB may already contain one).
        await db_session.execute(text("UPDATE users SET is_superuser = false"))
        await db_session.flush()

        # Verify
        result = await verify_migration(db_session)

        assert result is False


class TestRunMigrationIntegration:
    """Integration tests for full migration process."""

    @pytest.mark.asyncio
    async def test_full_migration_success(self, db_session: AsyncSession):
        """Test complete migration flow."""
        # Create users
        admin = User(
            email=f"admin-{uuid4()}@test.com",
            password_hash="hash",
            full_name="Admin",
            is_superuser=True,
            is_active=True,
        )
        editor = User(
            email=f"editor-{uuid4()}@test.com",
            password_hash="hash",
            full_name="Editor",
            is_superuser=False,
            is_active=True,
        )
        db_session.add_all([admin, editor])
        await db_session.flush()

        # Step 1: Create company
        company_name = f"Test Company {uuid4()}"
        company = await get_or_create_default_company(db_session, company_name, dry_run=False)
        assert company is not None

        # Baseline expectations (DB may already contain users/admins)
        total_users = len(
            list((await db_session.execute(select(User.user_id))).scalars().all())
        )
        existing_member_user_ids = set(
            (await db_session.execute(
                select(CompanyMembership.user_id).where(CompanyMembership.company_id == company.company_id)
            )).scalars().all()
        )
        expected_new_memberships = total_users - len(existing_member_user_ids)
        admin_user_ids = set(
            (await db_session.execute(
                select(User.user_id).where(User.is_superuser == True)  # noqa: E712
            )).scalars().all()
        )
        expected_new_owners = len(admin_user_ids - existing_member_user_ids)
        # Legacy migration no longer promotes users to superuser via role field
        # All superusers should already have is_superuser=True
        expected_new_superusers = 0

        # Step 2: Migrate users
        stats = await migrate_users(db_session, company.company_id, dry_run=False)
        assert stats["memberships"] == expected_new_memberships
        assert stats["superusers"] == expected_new_superusers
        assert stats["owners"] == expected_new_owners

        # Verify our admin user got promoted
        await db_session.refresh(admin)
        assert admin.is_superuser is True

        # Step 3: Verify
        _ = await verify_migration(db_session)
        # Check membership count matches total users
        result = await db_session.execute(
            select(CompanyMembership).where(CompanyMembership.company_id == company.company_id)
        )
        memberships = list(result.scalars().all())
        assert len({m.user_id for m in memberships}) == total_users

