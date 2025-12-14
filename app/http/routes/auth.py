"""
Authentication routes.
Handles user login, registration, and user management.
"""
import logging
from typing import Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.auth_middleware import (
    TokenClaims, create_access_token, require_auth, get_current_user, token_blacklist
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.roles import UserRole
from database import SessionLocal, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Request/Response Models ====================

class LoginRequest(BaseModel):
    provider: str  # github, gitlab, gnome, kde, google
    access_token: str


class RegisterRequest(BaseModel):
    display_name: str
    provider: str
    provider_user_id: int
    login: str
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    role: str


class UserResponse(BaseModel):
    id: int
    display_name: Optional[str] = None
    role: str
    invite_code: Optional[str] = None
    default_account_provider: Optional[str] = None
    default_account_login: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None


class ChangeRoleRequest(BaseModel):
    user_id: int
    new_role: str


# ==================== OAuth provider validation ====================

OAUTH_PROVIDERS = {
    "github": {
        "user_url": "https://api.github.com/user",
        "headers_fn": lambda token: {"Authorization": f"Bearer {token}", "Accept": "application/json"},
    },
    "gitlab": {
        "user_url": "https://gitlab.com/api/v4/user",
        "headers_fn": lambda token: {"Authorization": f"Bearer {token}"},
    },
    "gnome": {
        "user_url": "https://gitlab.gnome.org/api/v4/user",
        "headers_fn": lambda token: {"Authorization": f"Bearer {token}"},
    },
    "kde": {
        "user_url": "https://invent.kde.org/api/v4/user",
        "headers_fn": lambda token: {"Authorization": f"Bearer {token}"},
    },
    "google": {
        "user_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "headers_fn": lambda token: {"Authorization": f"Bearer {token}"},
    },
}


async def validate_oauth_token(provider: str, access_token: str) -> dict:
    """Validate an OAuth token by calling the provider's user info endpoint."""
    import httpx

    provider_info = OAUTH_PROVIDERS.get(provider)
    if not provider_info:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                provider_info["user_url"],
                headers=provider_info["headers_fn"](access_token),
            )
        except httpx.RequestError as e:
            logger.error(f"OAuth validation request failed for {provider}: {e}")
            raise HTTPException(status_code=502, detail="Could not reach OAuth provider")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid OAuth token")

    return resp.json()


def _extract_oauth_user_info(provider: str, data: dict) -> dict:
    """Extract normalized user info from provider-specific response."""
    if provider == "github":
        return {
            "provider_user_id": data.get("id"),
            "login": data.get("login", ""),
            "display_name": data.get("name") or data.get("login", ""),
            "avatar_url": data.get("avatar_url", ""),
            "email": data.get("email", ""),
        }
    elif provider == "google":
        return {
            "provider_user_id": data.get("id"),
            "login": data.get("email", ""),
            "display_name": data.get("name", ""),
            "avatar_url": data.get("picture", ""),
            "email": data.get("email", ""),
        }
    else:
        # GitLab-based providers (gitlab, gnome, kde)
        return {
            "provider_user_id": data.get("id"),
            "login": data.get("username", ""),
            "display_name": data.get("name") or data.get("username", ""),
            "avatar_url": data.get("avatar_url", ""),
            "email": data.get("email", ""),
        }


# ==================== Endpoints ====================

@router.get("/methods")
async def get_login_methods():
    """Get available login methods."""
    return {
        "methods": [
            {"method": "github", "name": "GitHub"},
            {"method": "gitlab", "name": "GitLab"},
            {"method": "gnome", "name": "GNOME"},
            {"method": "kde", "name": "KDE"},
            {"method": "google", "name": "Google"},
        ]
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request_body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Login with OAuth provider token.
    Validates the token with the provider, then finds or creates the user.
    """
    # Validate token with the OAuth provider
    provider_data = await validate_oauth_token(request_body.provider, request_body.access_token)
    user_info = _extract_oauth_user_info(request_body.provider, provider_data)

    if not user_info.get("provider_user_id"):
        raise HTTPException(status_code=401, detail="Could not identify user from provider")

    # Find existing user by provider + provider_user_id
    from database import ConnectedAccount
    account = (
        db.query(ConnectedAccount)
        .filter(
            ConnectedAccount.provider == request_body.provider,
            ConnectedAccount.provider_user_id == user_info["provider_user_id"],
        )
        .first()
    )

    if account:
        user = account.user
    else:
        # Create new user
        import secrets
        user = User(
            display_name=user_info["display_name"],
            invite_code=secrets.token_urlsafe(8),
            default_account_provider=request_body.provider,
            default_account_login=user_info["login"],
        )
        db.add(user)
        db.flush()

        # Create connected account (OAuth token is NOT stored — only identity info)
        account = ConnectedAccount(
            user_id=user.id,
            provider=request_body.provider,
            provider_user_id=user_info["provider_user_id"],
            login=user_info["login"],
            avatar_url=user_info.get("avatar_url"),
            display_name=user_info["display_name"],
            email=user_info.get("email"),
        )
        db.add(account)
        db.commit()
        db.refresh(user)

    # Get user role
    role = getattr(user, 'role', None) or UserRole.USER.value
    user_role = UserRole(role) if isinstance(role, str) else UserRole.USER

    # Generate access token
    access_token = create_access_token(
        user_id=user.id,
        role=user_role,
        name=f"{request_body.provider}_login",
    )

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=user.id,
        role=user_role.value,
    )


@router.get("/user", response_model=UserResponse)
async def get_user_info(
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Get current user information."""
    user = db.query(User).filter(User.id == claims.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    response = UserResponse.model_validate(user)
    response.role = claims.role
    return response


@router.put("/user", response_model=UserResponse)
async def update_user(
    update_request: UpdateUserRequest,
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Update current user information."""
    user = db.query(User).filter(User.id == claims.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from datetime import datetime
    if update_request.display_name:
        user.display_name = update_request.display_name

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    response = UserResponse.model_validate(user)
    response.role = claims.role
    return response


_security = HTTPBearer()


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    claims: TokenClaims = Depends(require_auth),
):
    """Logout user by blacklisting the current token."""
    token_blacklist.add(credentials.credentials)
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Refresh an access token. Returns a new token and blacklists the old one."""
    user = db.query(User).filter(User.id == claims.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Blacklist the current token
    token_blacklist.add(credentials.credentials)

    # Issue new token with current role from DB
    user_role = UserRole(user.role)
    token = create_access_token(
        user_id=user.id,
        role=user_role,
        name="refresh",
    )

    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user_id=user.id,
        role=user.role,
    )


@router.get("/me")
async def get_me(claims: Optional[TokenClaims] = Depends(get_current_user)):
    """Get current user from token (optional auth)."""
    if claims is None:
        return {"logged_in": False}

    return {
        "logged_in": True,
        "user_id": claims.user_id,
        "role": claims.role,
        "scopes": claims.scope,
    }


# ==================== Publisher Agreement ====================


@router.post("/accept-publisher-agreement")
async def accept_publisher_agreement(
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Accept the publisher agreement. Required before creating builds or uploading."""
    from datetime import datetime
    user = db.query(User).filter(User.id == claims.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.accepted_publisher_agreement_at:
        return {"message": "Publisher agreement already accepted", "accepted_at": str(user.accepted_publisher_agreement_at)}

    user.accepted_publisher_agreement_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Publisher agreement accepted", "accepted_at": str(user.accepted_publisher_agreement_at)}


# ==================== Admin Endpoints ====================

@router.post("/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    role_request: ChangeRoleRequest,
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Change a user's role. Requires admin role."""
    # Check if current user is admin
    if claims.get_user_role() != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    # Validate new role
    try:
        new_role = UserRole(role_request.new_role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}"
        )

    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update role
    if hasattr(user, 'role'):
        user.role = new_role.value
        db.commit()

    return {"message": f"User {user_id} role changed to {new_role.value}"}


@router.get("/users")
async def list_users(
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """List all users. Requires admin role."""
    if claims.get_user_role() != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")

    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "display_name": user.display_name,
            "role": getattr(user, 'role', 'user'),
            "default_account_provider": user.default_account_provider,
        }
        for user in users
    ]
