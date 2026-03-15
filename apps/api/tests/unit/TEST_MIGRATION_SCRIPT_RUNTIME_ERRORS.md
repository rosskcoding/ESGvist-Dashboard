# Migration Script Tests - Runtime Errors

## Test Execution Results

**Date**: 2024-12-27  
**Environment**: Python 3.14.2, pytest 9.0.2  
**Total Tests**: 15  
**Passed**: 7 ✅  
**Failed**: 8 ❌

## Failed Tests Summary

### 1. `test_migrate_reports_without_company_id` ❌

**Error**: `sqlalchemy.exc.IntegrityError: null value in column "company_id" of relation "reports" violates not-null constraint`

**Location**: `test_migration_script.py:133-145`

**Issue**: 
- Test tries to create `Report` object with `company_id=None` using SQLAlchemy ORM
- Database constraint prevents NULL values in `company_id` column
- Code attempts to set `report.company_id = None` but SQLAlchemy enforces NOT NULL constraint

**Root Cause**: 
- Test uses old approach: `report = Report(...); report.company_id = None`
- Should use raw SQL to bypass constraint (as done in other tests)

**Status**: ⚠️ NOT FIXED - Code still uses old approach

---

### 2. `test_migrate_reports_dry_run` ❌

**Error**: `sqlalchemy.exc.IntegrityError: null value in column "company_id" of relation "reports" violates not-null constraint`

**Location**: `test_migration_script.py:195-205`

**Issue**:
- Test uses raw SQL INSERT but doesn't include `company_id` column
- PostgreSQL rejects INSERT without required NOT NULL column
- Even raw SQL cannot bypass NOT NULL constraint without explicitly setting a value

**Root Cause**:
- Raw SQL INSERT statement omits `company_id` column
- Need to either:
  1. Temporarily disable constraint (not recommended)
  2. Insert with dummy company_id then UPDATE to NULL (complex)
  3. Use ALTER TABLE to make column nullable temporarily (risky)

**Status**: ⚠️ NOT FIXED - Raw SQL approach also fails

---

### 3. `test_create_memberships_for_all_users` ❌

**Error**: `assert 3 == 2`

**Location**: `test_migration_script.py:269`

**Issue**:
- Test expects 2 memberships to be created
- Actual: 3 memberships created
- Output: `✓ Created 3 memberships`

**Root Cause**:
- Test creates 2 users but migration creates 3 memberships
- Possible causes:
  1. Existing user in database from previous test (isolation issue)
  2. Migration script finds more users than expected
  3. Test data not properly cleaned up

**Status**: ⚠️ NOT FIXED - Test isolation or data cleanup issue

---

### 4. `test_promote_admin_to_superuser_and_owner` ❌

**Error**: `assert 2 == 1`

**Location**: `test_migration_script.py:303`

**Issue**:
- Test expects 1 membership to be created
- Actual: 2 memberships created
- Output: `✓ Created 2 memberships`

**Root Cause**:
- Test creates 1 admin user but migration creates 2 memberships
- Same isolation issue as test #3

**Status**: ⚠️ NOT FIXED - Test isolation issue

---

### 5. `test_skip_existing_memberships` ❌

**Error**: `assert 1 == 0`

**Location**: `test_migration_script.py:355`

**Issue**:
- Test expects 0 new memberships (existing one should be skipped)
- Actual: 1 membership created
- Output: `✓ Created 1 memberships`

**Root Cause**:
- Test creates membership manually, then runs migration
- Migration still creates a new membership instead of skipping
- Possible causes:
  1. Membership lookup query doesn't match correctly
  2. Transaction isolation - manual membership not visible to migration
  3. Migration logic doesn't properly check for existing memberships

**Status**: ⚠️ NOT FIXED - Migration logic or transaction isolation issue

---

### 6. `test_verify_fails_when_orphan_reports` ❌

**Error**: `sqlalchemy.exc.IntegrityError: null value in column "company_id" of relation "reports" violates not-null constraint`

**Location**: `test_migration_script.py:430-450`

**Issue**:
- Same as test #1 - cannot create Report with company_id=None
- Test cannot set up prerequisite data (orphan report)

**Status**: ⚠️ NOT FIXED - Same constraint violation issue

---

### 7. `test_verify_fails_when_no_superuser` ❌

**Error**: `assert True is False`

**Location**: `test_migration_script.py:525`

**Issue**:
- Test expects `verify_migration()` to return `False` (verification should fail)
- Actual: Returns `True` (verification passed)
- Output: `✅ Migration verification passed!`

**Root Cause**:
- Test creates user with `is_superuser=False` and expects verification to fail
- But verification passes, meaning:
  1. Another superuser exists in database (isolation issue)
  2. Verification logic doesn't check for superuser correctly
  3. Test setup doesn't ensure no superusers exist

**Status**: ⚠️ NOT FIXED - Verification logic or test isolation issue

---

### 8. `test_full_migration_success` ❌

**Error**: `assert 3 == 2`

**Location**: `test_migration_script.py:569`

**Issue**:
- Test expects 2 memberships to be created
- Actual: 3 memberships created
- Output: `✓ Created 3 memberships`

**Root Cause**:
- Same as test #3 - test isolation issue
- Migration finds more users than test creates

**Status**: ⚠️ NOT FIXED - Test isolation issue

---

## Error Categories

### Category 1: Database Constraint Violations (3 tests)
- Cannot create `Report` with `company_id=None` due to NOT NULL constraint
- Affects: `test_migrate_reports_without_company_id`, `test_migrate_reports_dry_run`, `test_verify_fails_when_orphan_reports`

**Solution Options**:
1. Use ALTER TABLE to temporarily make `company_id` nullable in test setup
2. Create reports with dummy company_id, then test migration logic separately
3. Mock the database constraint in tests (not recommended)

### Category 2: Test Isolation Issues (4 tests)
- Tests see data from previous tests or database state
- Affects: `test_create_memberships_for_all_users`, `test_promote_admin_to_superuser_and_owner`, `test_skip_existing_memberships`, `test_full_migration_success`

**Solution Options**:
1. Ensure proper transaction rollback in fixtures
2. Use unique identifiers for each test
3. Clean up test data explicitly before assertions
4. Use separate test database or schema per test

### Category 3: Verification Logic Issue (1 test)
- `verify_migration()` passes when it should fail
- Affects: `test_verify_fails_when_no_superuser`

**Solution Options**:
1. Fix verification logic to properly check for superuser
2. Ensure test setup clears all superusers before test
3. Add explicit check in test before calling verification

---

## Recommendations

1. **Fix Database Constraint Tests**:
   - Use `ALTER TABLE` in test setup to temporarily allow NULL
   - Or refactor tests to not require orphan reports (test migration logic differently)

2. **Fix Test Isolation**:
   - Review `db_session` fixture - ensure proper rollback
   - Use unique company/user names per test
   - Add explicit cleanup in test teardown

3. **Fix Verification Test**:
   - Ensure no superusers exist before test
   - Or fix verification logic if it's incorrect

4. **Add Test Helpers**:
   - Create helper functions for setting up orphan reports
   - Create helper for ensuring clean database state

---

## Test Statistics

| Category | Count | Percentage |
|----------|-------|------------|
| ✅ Passed | 7 | 46.7% |
| ❌ Failed | 8 | 53.3% |
| **Total** | **15** | **100%** |

### Passed Tests:
1. ✅ `test_create_company_when_not_exists`
2. ✅ `test_return_existing_company`
3. ✅ `test_dry_run_does_not_create`
4. ✅ `test_migrate_reports_all_have_company_id`
5. ✅ `test_migrate_users_dry_run`
6. ✅ `test_verify_success_when_all_migrated`
7. ✅ `test_verify_fails_when_user_without_membership`

### Failed Tests:
1. ❌ `test_migrate_reports_without_company_id` - Constraint violation
2. ❌ `test_migrate_reports_dry_run` - Constraint violation
3. ❌ `test_create_memberships_for_all_users` - Isolation issue
4. ❌ `test_promote_admin_to_superuser_and_owner` - Isolation issue
5. ❌ `test_skip_existing_memberships` - Logic/isolation issue
6. ❌ `test_verify_fails_when_orphan_reports` - Constraint violation
7. ❌ `test_verify_fails_when_no_superuser` - Verification logic issue
8. ❌ `test_full_migration_success` - Isolation issue

---

## Next Steps

1. ✅ All errors documented
2. ⚠️ Fix database constraint violation tests
3. ⚠️ Fix test isolation issues
4. ⚠️ Fix verification logic test
5. ⚠️ Re-run tests after fixes
6. ⚠️ Achieve 100% test pass rate


