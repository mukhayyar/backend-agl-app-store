"""
flat-manager proxy routes.
All flat-manager API calls go through our backend for centralized access control.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.auth_middleware import (
    TokenClaims, require_auth, require_publisher, require_admin, require_reviewer
)
from app.core.roles import FlatManagerScope
from app.services.flatmanager_client import (
    get_flat_manager_client, get_token_manager, FlatManagerClient, TokenManager
)
from database import SessionLocal, User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/flatmanager", tags=["flat-manager"])

ALLOWED_UPLOAD_EXTENSIONS = {".flatpak", ".flatpakref", ".flatpakrepo", ".bundle", ".tar", ".tar.gz", ".tar.xz"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def require_publisher_agreement(
    claims: TokenClaims = Depends(require_publisher),
    db: Session = Depends(get_db),
) -> TokenClaims:
    """Require publisher role AND accepted publisher agreement."""
    user = db.query(User).filter(User.id == claims.user_id).first()
    if not user or not user.accepted_publisher_agreement_at:
        raise HTTPException(
            status_code=403,
            detail="You must accept the publisher agreement before publishing. "
                   "Update your profile to accept the agreement.",
        )
    return claims


def _raise_for_fm_error(result: dict) -> None:
    """Raise HTTPException for flat-manager errors with sanitized messages."""
    if result.get("error"):
        status = result.get("status", 500)
        logger.error(f"flat-manager error: status={status} message={result.get('message')}")
        if 400 <= status < 500:
            raise HTTPException(status_code=status, detail="Request rejected by build server")
        raise HTTPException(status_code=502, detail="Build server error — please try again later")


# ==================== Request/Response Models ====================

class CreateBuildRequest(BaseModel):
    repo: Optional[str] = None


class CreateBuildRefRequest(BaseModel):
    ref: str
    commit: Optional[str] = None


class AddExtraIdsRequest(BaseModel):
    ids: List[str]


class CommitBuildRequest(BaseModel):
    wait: bool = False


class PublishBuildRequest(BaseModel):
    wait: bool = False


class ReviewCheckRequest(BaseModel):
    status: str  # "passed", "failed", etc.


class RepublishRequest(BaseModel):
    repo: Optional[str] = None
    app_id: Optional[str] = None


class TokenSubsetRequest(BaseModel):
    scopes: List[str]
    prefixes: Optional[List[str]] = None
    repos: Optional[List[str]] = None


class RevokeTokensRequest(BaseModel):
    token_ids: List[str]


class GenerateTokenRequest(BaseModel):
    name: str
    scopes: Optional[List[str]] = None
    prefixes: Optional[List[str]] = None
    repos: Optional[List[str]] = None
    branches: Optional[List[str]] = None
    duration_days: int = 365


# ==================== Status Endpoints ====================

@router.get("/status")
async def get_status():
    """Get flat-manager server status."""
    client = get_flat_manager_client()
    return await client.get_status()


@router.get("/status/{job_id}")
async def get_job_status(job_id: int):
    """Get job status by ID."""
    client = get_flat_manager_client()
    return await client.get_job_status(job_id)


# ==================== Build Endpoints ====================

@router.post("/builds")
async def create_build(
    request: CreateBuildRequest,
    claims: TokenClaims = Depends(require_publisher_agreement)
):
    """Create a new build. Requires publisher role and accepted agreement."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    # Generate a flat-manager token with user's scopes
    fm_token = token_manager.generate_token(
        name=f"build-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.create_build(fm_token, request.repo)
    _raise_for_fm_error(result)
    return result


@router.get("/builds")
async def list_builds(claims: TokenClaims = Depends(require_publisher)):
    """List all builds. Requires publisher role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"list-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.list_builds(fm_token)
    _raise_for_fm_error(result)
    return result


@router.get("/builds/{build_id}")
async def get_build(build_id: int, claims: TokenClaims = Depends(require_publisher)):
    """Get build details."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"get-build-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.get_build(fm_token, build_id)
    _raise_for_fm_error(result)
    return result


@router.get("/builds/{build_id}/extended")
async def get_build_extended(build_id: int, claims: TokenClaims = Depends(require_publisher)):
    """Get extended build details."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"get-build-ext-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.get_build_extended(fm_token, build_id)
    _raise_for_fm_error(result)
    return result


@router.post("/builds/{build_id}/ref")
async def create_build_ref(
    build_id: int,
    request: CreateBuildRefRequest,
    claims: TokenClaims = Depends(require_publisher_agreement)
):
    """Create a build ref. Requires publisher agreement."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"ref-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.create_build_ref(fm_token, build_id, request.model_dump())
    _raise_for_fm_error(result)
    return result


@router.post("/builds/{build_id}/upload")
async def upload_to_build(
    build_id: int,
    file: UploadFile = File(...),
    claims: TokenClaims = Depends(require_publisher_agreement)
):
    """Upload a file to a build. Requires publisher agreement."""
    max_size = settings.max_upload_size_mb * 1024 * 1024

    # Validate file extension
    filename = file.filename or ""
    if not any(filename.endswith(ext) for ext in ALLOWED_UPLOAD_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )

    # Read file with size limit (streaming to avoid loading huge files fully into memory)
    chunks = []
    total_size = 0
    while True:
        chunk = await file.read(1024 * 1024)  # 1 MB chunks
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.max_upload_size_mb} MB",
            )
        chunks.append(chunk)

    file_data = b"".join(chunks)

    client = get_flat_manager_client()
    token_manager = get_token_manager()

    fm_token = token_manager.generate_token(
        name=f"upload-{claims.user_id}",
        scopes=claims.scope,
    )

    result = await client.upload_to_build(fm_token, build_id, file_data, file.filename)
    _raise_for_fm_error(result)
    return result


@router.post("/builds/{build_id}/commit")
async def commit_build(
    build_id: int,
    request: CommitBuildRequest,
    claims: TokenClaims = Depends(require_publisher_agreement)
):
    """Commit a build. Requires publisher agreement."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"commit-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.commit_build(fm_token, build_id, request.wait)
    _raise_for_fm_error(result)
    return result


@router.get("/builds/{build_id}/commit")
async def get_commit_status(build_id: int, claims: TokenClaims = Depends(require_publisher)):
    """Get commit job status."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"commit-status-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.get_commit_job(fm_token, build_id)
    _raise_for_fm_error(result)
    return result


@router.post("/builds/{build_id}/publish")
async def publish_build(
    build_id: int,
    request: PublishBuildRequest,
    claims: TokenClaims = Depends(require_publisher_agreement)
):
    """Publish a build. Requires publisher agreement."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"publish-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.publish_build(fm_token, build_id, request.wait)
    _raise_for_fm_error(result)
    return result


@router.get("/builds/{build_id}/publish")
async def get_publish_status(build_id: int, claims: TokenClaims = Depends(require_publisher)):
    """Get publish job status."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"publish-status-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.get_publish_job(fm_token, build_id)
    _raise_for_fm_error(result)
    return result


@router.post("/builds/{build_id}/purge")
async def purge_build(build_id: int, claims: TokenClaims = Depends(require_admin)):
    """Purge a build. Requires admin role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"purge-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.purge_build(fm_token, build_id)
    _raise_for_fm_error(result)
    return result


# ==================== Job Endpoints ====================

@router.get("/jobs/{job_id}")
async def get_job(job_id: int, claims: TokenClaims = Depends(require_publisher)):
    """Get job details."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"job-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.get_job(fm_token, job_id)
    _raise_for_fm_error(result)
    return result


@router.post("/jobs/{job_id}/review")
async def review_job(
    job_id: int,
    request: ReviewCheckRequest,
    claims: TokenClaims = Depends(require_reviewer)
):
    """Review a check job. Requires reviewer role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"review-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.review_check(fm_token, job_id, request.status)
    _raise_for_fm_error(result)
    return result


# ==================== Repository Endpoints ====================

@router.post("/republish")
async def republish_app(
    request: RepublishRequest,
    claims: TokenClaims = Depends(require_admin)
):
    """Republish an app. Requires admin role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"republish-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.republish(fm_token, request.repo, request.app_id)
    _raise_for_fm_error(result)
    return result


# ==================== Token Management Endpoints ====================

@router.get("/tokens")
async def get_tokens(claims: TokenClaims = Depends(require_admin)):
    """Get list of tokens. Requires admin role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"tokens-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.get_tokens(fm_token)
    _raise_for_fm_error(result)
    return result


@router.post("/tokens/revoke")
async def revoke_tokens(
    request: RevokeTokensRequest,
    claims: TokenClaims = Depends(require_admin)
):
    """Revoke tokens. Requires admin role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"revoke-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.revoke_tokens(fm_token, request.token_ids)
    _raise_for_fm_error(result)
    return result


@router.post("/tokens/subset")
async def create_token_subset(
    request: TokenSubsetRequest,
    claims: TokenClaims = Depends(require_publisher)
):
    """Create a token subset with reduced permissions."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"subset-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.create_token_subset(
        fm_token, request.scopes, request.prefixes, request.repos
    )
    _raise_for_fm_error(result)
    return result


@router.post("/tokens/generate")
async def generate_token(
    request: GenerateTokenRequest,
    claims: TokenClaims = Depends(require_admin)
):
    """Generate a new flat-manager token. Requires admin role."""
    token_manager = get_token_manager()
    
    token = token_manager.generate_token(
        name=request.name,
        scopes=request.scopes,
        prefixes=request.prefixes,
        repos=request.repos,
        branches=request.branches,
        duration_days=request.duration_days,
    )
    
    return {"token": token}


# ==================== Prune Endpoints ====================

@router.post("/prune")
async def prune(claims: TokenClaims = Depends(require_admin)):
    """Trigger prune operation. Requires admin role."""
    client = get_flat_manager_client()
    token_manager = get_token_manager()
    
    fm_token = token_manager.generate_token(
        name=f"prune-{claims.user_id}",
        scopes=claims.scope,
    )
    
    result = await client.prune(fm_token)
    _raise_for_fm_error(result)
    return result
