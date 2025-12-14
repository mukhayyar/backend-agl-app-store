"""
Flathub Stats Routes.
Proxies statistics endpoints from Flathub API v2.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.flathub_client import get_flathub_client

router = APIRouter(tags=["flathub-stats"])


@router.get("/stats")
async def get_stats() -> Optional[Dict[str, Any]]:
    """Get overall Flathub statistics."""
    client = get_flathub_client()
    try:
        result = await client.get_stats()
        if result is None:
            raise HTTPException(status_code=404, detail="Statistics not available")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/stats/{app_id}")
async def get_app_stats(
    app_id: str,
    all: bool = Query(default=False, alias="all", description="Get all-time stats"),
    days: int = Query(default=180, description="Number of days for stats")
) -> Optional[Dict[str, Any]]:
    """Get statistics for a specific app."""
    client = get_flathub_client()
    try:
        result = await client.get_app_stats(app_id, all_time=all, days=days)
        if result is None:
            raise HTTPException(status_code=404, detail="App stats not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== App Picks ====================

@router.get("/app-picks/app-of-the-day/{date}")
async def get_app_of_the_day(date: str) -> Optional[Dict[str, Any]]:
    """
    Get app of the day for a specific date.
    
    Date format: YYYY-MM-DD (e.g., 2024-01-15)
    """
    client = get_flathub_client()
    try:
        result = await client.get_app_of_the_day(date)
        if result is None:
            raise HTTPException(status_code=404, detail="No app of the day for this date")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/app-picks/apps-of-the-week/{date}")
async def get_apps_of_the_week(date: str) -> Optional[Dict[str, Any]]:
    """
    Get apps of the week for a specific date.
    
    Date format: YYYY-MM-DD (e.g., 2024-01-15)
    """
    client = get_flathub_client()
    try:
        result = await client.get_apps_of_the_week(date)
        if result is None:
            raise HTTPException(status_code=404, detail="No apps of the week for this date")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Verification ====================

@router.get("/verification/{app_id}/status")
async def get_verification_status(app_id: str) -> Dict[str, Any]:
    """Get verification status of an app."""
    client = get_flathub_client()
    try:
        return await client.get_verification_status(app_id)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="App not found")
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Feeds ====================

@router.get("/feed/recently-updated")
async def get_recently_updated_feed():
    """Get RSS feed of recently updated applications."""
    from fastapi.responses import Response
    
    client = get_flathub_client()
    try:
        content = await client.get_recently_updated_feed()
        return Response(content=content, media_type="application/rss+xml")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/feed/new")
async def get_new_apps_feed():
    """Get RSS feed of newly added applications."""
    from fastapi.responses import Response
    
    client = get_flathub_client()
    try:
        content = await client.get_new_apps_feed()
        return Response(content=content, media_type="application/rss+xml")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Health Check ====================

@router.get("/status")
async def flathub_health_check() -> Dict[str, Any]:
    """Check Flathub API health."""
    client = get_flathub_client()
    is_healthy = await client.health_check()
    return {
        "flathub_api": "healthy" if is_healthy else "unhealthy",
        "proxy": "healthy"
    }
