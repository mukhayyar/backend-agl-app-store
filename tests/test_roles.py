"""Tests for RBAC roles and scopes."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.roles import (
    UserRole, FlatManagerScope, ROLE_SCOPES,
    get_scopes_for_role, has_scope, has_any_scope, has_all_scopes,
)

class TestUserRole:
    def test_role_values(self):
        assert UserRole.ADMIN == "admin"
        assert UserRole.REVIEWER == "reviewer"
        assert UserRole.PUBLISHER == "publisher"
        assert UserRole.USER == "user"

    def test_role_from_string(self):
        assert UserRole("admin") == UserRole.ADMIN
        assert UserRole("user") == UserRole.USER

    def test_invalid_role(self):
        with pytest.raises(ValueError):
            UserRole("superadmin")

class TestFlatManagerScope:
    def test_scope_values(self):
        assert FlatManagerScope.JOBS == "jobs"
        assert FlatManagerScope.BUILD == "build"
        assert FlatManagerScope.UPLOAD == "upload"
        assert FlatManagerScope.PUBLISH == "publish"
        assert FlatManagerScope.DOWNLOAD == "download"
        assert FlatManagerScope.REPUBLISH == "republish"
        assert FlatManagerScope.REVIEW_CHECK == "reviewcheck"
        assert FlatManagerScope.TOKEN_MANAGEMENT == "tokenmanagement"

class TestRoleScopes:
    def test_admin_has_all_scopes(self):
        admin_scopes = ROLE_SCOPES[UserRole.ADMIN]
        assert FlatManagerScope.JOBS in admin_scopes
        assert FlatManagerScope.BUILD in admin_scopes
        assert FlatManagerScope.TOKEN_MANAGEMENT in admin_scopes
        assert len(admin_scopes) == 9

    def test_reviewer_scopes(self):
        scopes = ROLE_SCOPES[UserRole.REVIEWER]
        assert FlatManagerScope.REVIEW_CHECK in scopes
        assert FlatManagerScope.DOWNLOAD in scopes
        assert FlatManagerScope.BUILD in scopes
        assert FlatManagerScope.PUBLISH not in scopes

    def test_publisher_scopes(self):
        scopes = ROLE_SCOPES[UserRole.PUBLISHER]
        assert FlatManagerScope.BUILD in scopes
        assert FlatManagerScope.UPLOAD in scopes
        assert FlatManagerScope.PUBLISH in scopes
        assert FlatManagerScope.DOWNLOAD in scopes
        assert FlatManagerScope.JOBS not in scopes

    def test_user_scopes(self):
        scopes = ROLE_SCOPES[UserRole.USER]
        assert FlatManagerScope.DOWNLOAD in scopes
        assert len(scopes) == 1

class TestGetScopesForRole:
    def test_admin_scopes_as_strings(self):
        scopes = get_scopes_for_role(UserRole.ADMIN)
        assert "jobs" in scopes
        assert "tokenmanagement" in scopes
        assert isinstance(scopes[0], str)

    def test_user_scopes_as_strings(self):
        scopes = get_scopes_for_role(UserRole.USER)
        assert scopes == ["download"]

class TestHasScope:
    def test_admin_has_jobs(self):
        assert has_scope(UserRole.ADMIN, FlatManagerScope.JOBS) is True

    def test_user_no_build(self):
        assert has_scope(UserRole.USER, FlatManagerScope.BUILD) is False

    def test_publisher_has_upload(self):
        assert has_scope(UserRole.PUBLISHER, FlatManagerScope.UPLOAD) is True

class TestHasAnyScope:
    def test_publisher_has_any_build_or_jobs(self):
        assert has_any_scope(UserRole.PUBLISHER, [FlatManagerScope.BUILD, FlatManagerScope.JOBS]) is True

    def test_user_has_none_of_build_upload(self):
        assert has_any_scope(UserRole.USER, [FlatManagerScope.BUILD, FlatManagerScope.UPLOAD]) is False

class TestHasAllScopes:
    def test_admin_has_all(self):
        assert has_all_scopes(UserRole.ADMIN, [FlatManagerScope.BUILD, FlatManagerScope.JOBS]) is True

    def test_publisher_missing_jobs(self):
        assert has_all_scopes(UserRole.PUBLISHER, [FlatManagerScope.BUILD, FlatManagerScope.JOBS]) is False

    def test_publisher_has_build_upload(self):
        assert has_all_scopes(UserRole.PUBLISHER, [FlatManagerScope.BUILD, FlatManagerScope.UPLOAD]) is True
