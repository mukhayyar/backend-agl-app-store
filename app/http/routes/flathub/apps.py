"""
Flathub Apps Routes.
Proxies app-related endpoints from Flathub API v2.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.flathub_client import (
    get_flathub_client,
    AppType,
    SortBy,
    SearchQuery
)

router = APIRouter(tags=["flathub-apps"])


# ==================== Request/Response Models ====================

class SearchRequest(BaseModel):
    """Search request body."""
    query: str
    filters: Optional[List[Dict[str, Any]]] = None
    page: Optional[int] = 1
    hits_per_page: Optional[int] = 25


# ==================== Appstream Endpoints ====================

@router.get("/appstream")
async def list_appstream(
    filter: AppType = Query(default=AppType.APPS, description="Filter by app type"),
    sort: SortBy = Query(default=SortBy.ALPHABETICAL, description="Sort order")
) -> List[str]:
    """
    Get list of all application IDs from Flathub.
    
    Returns a list of all app IDs in the repository.
    """
    client = get_flathub_client()
    try:
        return await client.list_appstream(filter_type=filter, sort=sort)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/appstream/{app_id}")
async def get_appstream(
    app_id: str,
    locale: str = Query(default="en", description="Locale for translations")
) -> Dict[str, Any]:
    """
    Get AppStream metadata for a specific app.
    
    Returns full appstream data including name, description, screenshots,
    releases, and other metadata.
    """
    client = get_flathub_client()
    try:
        return await client.get_appstream(app_id, locale=locale)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="App not found")
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Search Endpoint ====================

@router.post("/search")
async def search_apps(
    request: SearchRequest,
    locale: str = Query(default="en", description="Locale for translations")
) -> Dict[str, Any]:
    """
    Search for applications on Flathub.
    
    Accepts a search query with filters and returns matching applications.
    """
    client = get_flathub_client()
    try:
        query = SearchQuery(
            query=request.query,
            filters=request.filters,
            page=request.page,
            hits_per_page=request.hits_per_page
        )
        return await client.search(query, locale=locale)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Summary Endpoint ====================

@router.get("/summary/{app_id}")
async def get_summary(
    app_id: str,
    branch: Optional[str] = Query(default=None, description="Branch name")
) -> Dict[str, Any]:
    """
    Get summary information for an app.
    
    Returns information about the app's size, architectures, runtime metadata.
    """
    client = get_flathub_client()
    try:
        return await client.get_summary(app_id, branch=branch)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="App not found")
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Addon Endpoint ====================

@router.get("/addon/{app_id}")
async def get_addons(app_id: str) -> List[str]:
    """
    Get addons for an application.
    
    Returns list of addon IDs compatible with the specified app.
    """
    client = get_flathub_client()
    try:
        return await client.get_addons(app_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Fullscreen Check ====================

@router.get("/is-fullscreen-app/{app_id}")
async def is_fullscreen_app(app_id: str) -> bool:
    """Check if an app is configured for fullscreen mode."""
    client = get_flathub_client()
    try:
        return await client.is_fullscreen_app(app_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Runtimes & Platforms ====================

@router.get("/runtimes")
async def get_runtimes() -> Dict[str, int]:
    """Get list of available runtimes with usage counts."""
    client = get_flathub_client()
    try:
        return await client.get_runtimes()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/platforms")
async def get_platforms() -> Dict[str, Any]:
    """Get platform information."""
    client = get_flathub_client()
    try:
        return await client.get_platforms()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== EOL Endpoints ====================

@router.get("/eol/rebase")
async def get_eol_rebase() -> Dict[str, Any]:
    """Get end-of-life rebase information for all apps."""
    client = get_flathub_client()
    try:
        return await client.get_eol_rebase()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/eol/rebase/{app_id}")
async def get_eol_rebase_app(
    app_id: str,
    branch: str = Query(default="stable", description="Branch name")
) -> Optional[str]:
    """Get end-of-life rebase information for a specific app."""
    client = get_flathub_client()
    try:
        return await client.get_eol_rebase(app_id, branch=branch)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="App not found")
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/eol/message")
async def get_eol_message() -> Dict[str, str]:
    """Get end-of-life messages for all apps."""
    client = get_flathub_client()
    try:
        return await client.get_eol_message()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/eol/message/{app_id}")
async def get_eol_message_app(
    app_id: str,
    branch: str = Query(default="stable", description="Branch name")
) -> Optional[str]:
    """Get end-of-life message for a specific app."""
    client = get_flathub_client()
    try:
        return await client.get_eol_message(app_id, branch=branch)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="App not found")
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")
