"""
Role-Based Access Control (RBAC) system for the App Store backend.
Maps application roles to flat-manager scopes.
"""
from enum import Enum
from typing import List, Set


class UserRole(str, Enum):
    """Application user roles."""
    ADMIN = "admin"
    REVIEWER = "reviewer"
    PUBLISHER = "publisher"  # Also known as Developer
    USER = "user"


class FlatManagerScope(str, Enum):
    """flat-manager token scopes from ClaimsScope enum."""
    JOBS = "jobs"                    # List all jobs in the system (admin)
    BUILD = "build"                  # Create/list/purge builds, commit files
    UPLOAD = "upload"                # Upload files and refs to builds
    PUBLISH = "publish"              # Publish builds to repository
    GENERATE = "generate"            # Upload deltas for repo (admin)
    DOWNLOAD = "download"            # List builds and download build repo
    REPUBLISH = "republish"          # Re-run publish hook (admin)
    REVIEW_CHECK = "reviewcheck"     # Change build check status
    TOKEN_MANAGEMENT = "tokenmanagement"  # Manage/revoke tokens (admin)


# Role to flat-manager scopes mapping
ROLE_SCOPES: dict[UserRole, List[FlatManagerScope]] = {
    UserRole.ADMIN: [
        FlatManagerScope.JOBS,
        FlatManagerScope.BUILD,
        FlatManagerScope.UPLOAD,
        FlatManagerScope.PUBLISH,
        FlatManagerScope.GENERATE,
        FlatManagerScope.DOWNLOAD,
        FlatManagerScope.REPUBLISH,
        FlatManagerScope.REVIEW_CHECK,
        FlatManagerScope.TOKEN_MANAGEMENT,
    ],
    UserRole.REVIEWER: [
        FlatManagerScope.REVIEW_CHECK,
        FlatManagerScope.DOWNLOAD,
        FlatManagerScope.BUILD,
    ],
    UserRole.PUBLISHER: [
        FlatManagerScope.BUILD,
        FlatManagerScope.UPLOAD,
        FlatManagerScope.PUBLISH,
        FlatManagerScope.DOWNLOAD,
    ],
    UserRole.USER: [
        FlatManagerScope.DOWNLOAD,
    ],
}


def get_scopes_for_role(role: UserRole) -> List[str]:
    """Get flat-manager scopes for a given role."""
    scopes = ROLE_SCOPES.get(role, [])
    return [scope.value for scope in scopes]


def has_scope(role: UserRole, required_scope: FlatManagerScope) -> bool:
    """Check if a role has a specific scope."""
    return required_scope in ROLE_SCOPES.get(role, [])


def has_any_scope(role: UserRole, required_scopes: List[FlatManagerScope]) -> bool:
    """Check if a role has any of the required scopes."""
    role_scopes = set(ROLE_SCOPES.get(role, []))
    return bool(role_scopes.intersection(set(required_scopes)))


def has_all_scopes(role: UserRole, required_scopes: List[FlatManagerScope]) -> bool:
    """Check if a role has all of the required scopes."""
    role_scopes = set(ROLE_SCOPES.get(role, []))
    return set(required_scopes).issubset(role_scopes)


# Permission decorators helpers
ADMIN_ONLY = [FlatManagerScope.TOKEN_MANAGEMENT]
REVIEWER_OR_ABOVE = [FlatManagerScope.REVIEW_CHECK]
PUBLISHER_OR_ABOVE = [FlatManagerScope.PUBLISH, FlatManagerScope.UPLOAD]
ALL_USERS = [FlatManagerScope.DOWNLOAD]
