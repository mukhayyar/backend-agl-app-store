"""
Authentication and authorization middleware for HTTP and gRPC servers.
Handles JWT token validation and role-based access control.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, List, Callable, Set
from functools import wraps

import jwt
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.roles import UserRole, FlatManagerScope, has_scope, get_scopes_for_role

logger = logging.getLogger(__name__)
settings = get_settings()

# HTTP Bearer token security
security = HTTPBearer(auto_error=False)


class TokenBlacklist:
    """In-memory token blacklist. For production at scale, replace with Redis."""

    def __init__(self):
        self._blacklisted: Set[str] = set()
        self._lock = threading.Lock()

    def add(self, token: str) -> None:
        with self._lock:
            self._blacklisted.add(token)

    def is_blacklisted(self, token: str) -> bool:
        with self._lock:
            return token in self._blacklisted

    def cleanup_expired(self) -> None:
        """Remove expired tokens from the blacklist to prevent unbounded growth."""
        with self._lock:
            still_valid = set()
            for token in self._blacklisted:
                try:
                    jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
                    still_valid.add(token)
                except jwt.ExpiredSignatureError:
                    pass  # Token expired — no longer needs to be blacklisted
                except jwt.InvalidTokenError:
                    pass
            self._blacklisted = still_valid


token_blacklist = TokenBlacklist()


class TokenClaims:
    """JWT token claims structure compatible with flat-manager."""
    
    def __init__(
        self,
        sub: str,
        name: str,
        scope: List[str],
        prefixes: List[str] = None,
        apps: List[str] = None,
        repos: List[str] = None,
        branches: List[str] = None,
        exp: int = None,
        jti: Optional[str] = None,
        token_type: str = "app",
        user_id: Optional[int] = None,
        role: str = "user",
    ):
        self.sub = sub
        self.name = name
        self.scope = scope
        self.prefixes = prefixes or [""]
        self.apps = apps or []
        self.repos = repos or [""]
        self.branches = branches or ["stable"]
        self.exp = exp or (int(time.time()) + 86400)
        self.jti = jti
        self.token_type = token_type
        self.user_id = user_id
        self.role = role
    
    def to_dict(self) -> dict:
        """Convert claims to dictionary for JWT encoding."""
        d = {
            "sub": self.sub,
            "name": self.name,
            "scope": self.scope,
            "prefixes": self.prefixes,
            "apps": self.apps,
            "repos": self.repos,
            "branches": self.branches,
            "exp": self.exp,
            "token_type": self.token_type,
            "user_id": self.user_id,
            "role": self.role,
        }
        if self.jti is not None:
            d["jti"] = self.jti
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "TokenClaims":
        """Create claims from dictionary."""
        return cls(
            sub=data.get("sub", ""),
            name=data.get("name", ""),
            scope=data.get("scope", []),
            prefixes=data.get("prefixes", [""]),
            apps=data.get("apps", []),
            repos=data.get("repos", [""]),
            branches=data.get("branches", ["stable"]),
            exp=data.get("exp"),
            jti=data.get("jti"),
            token_type=data.get("token_type", "app"),
            user_id=data.get("user_id"),
            role=data.get("role", "user"),
        )
    
    def has_scope(self, required_scope: str) -> bool:
        """Check if token has a specific scope."""
        return required_scope in self.scope
    
    def get_user_role(self) -> UserRole:
        """Get UserRole enum from role string."""
        try:
            return UserRole(self.role)
        except ValueError:
            return UserRole.USER


def create_access_token(
    user_id: int,
    role: UserRole,
    name: str = "access_token",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token for a user."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    exp = int(time.time()) + int(expires_delta.total_seconds())
    scopes = get_scopes_for_role(role)

    claims = TokenClaims(
        sub=f"user/{user_id}",
        name=name,
        scope=scopes,
        exp=exp,
        user_id=user_id,
        role=role.value,
    )
    
    token = jwt.encode(
        claims.to_dict(),
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def decode_token(token: str) -> Optional[TokenClaims]:
    """Decode and validate a JWT token."""
    if token_blacklist.is_blacklisted(token):
        logger.warning("Attempted use of blacklisted token")
        return None

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenClaims.from_dict(payload)
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenClaims]:
    """Get current user from JWT token (optional auth)."""
    if credentials is None:
        return None
    
    claims = decode_token(credentials.credentials)
    return claims


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenClaims:
    """Require valid JWT authentication."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    claims = decode_token(credentials.credentials)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return claims


def require_scope(required_scope: FlatManagerScope):
    """Decorator to require a specific scope for an endpoint."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, claims: TokenClaims = Depends(require_auth), **kwargs):
            if not claims.has_scope(required_scope.value):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required scope: {required_scope.value}"
                )
            return await func(*args, claims=claims, **kwargs)
        return wrapper
    return decorator


def require_role(required_role: UserRole):
    """Decorator to require a specific role for an endpoint."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, claims: TokenClaims = Depends(require_auth), **kwargs):
            user_role = claims.get_user_role()
            
            # Admin can access everything
            if user_role == UserRole.ADMIN:
                return await func(*args, claims=claims, **kwargs)
            
            # Check role hierarchy
            role_hierarchy = [UserRole.USER, UserRole.PUBLISHER, UserRole.REVIEWER, UserRole.ADMIN]
            if role_hierarchy.index(user_role) < role_hierarchy.index(required_role):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required role: {required_role.value}"
                )
            
            return await func(*args, claims=claims, **kwargs)
        return wrapper
    return decorator


# Convenience dependencies for common role checks
async def require_admin(claims: TokenClaims = Depends(require_auth)) -> TokenClaims:
    """Require admin role."""
    if claims.get_user_role() != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return claims


async def require_reviewer(claims: TokenClaims = Depends(require_auth)) -> TokenClaims:
    """Require reviewer or higher role."""
    role = claims.get_user_role()
    if role not in [UserRole.ADMIN, UserRole.REVIEWER]:
        raise HTTPException(status_code=403, detail="Reviewer access required")
    return claims


async def require_publisher(claims: TokenClaims = Depends(require_auth)) -> TokenClaims:
    """Require publisher or higher role."""
    role = claims.get_user_role()
    if role not in [UserRole.ADMIN, UserRole.REVIEWER, UserRole.PUBLISHER]:
        raise HTTPException(status_code=403, detail="Publisher access required")
    return claims
