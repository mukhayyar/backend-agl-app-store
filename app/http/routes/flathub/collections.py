"""
Flathub Collections Routes.
Proxies collection endpoints from Flathub API v2.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.flathub_client import get_flathub_client, MainCategory

router = APIRouter(prefix="/collection", tags=["flathub-collections"])


# ==================== Categories ====================

@router.get("/category")
async def get_categories() -> List[str]:
    """Get list of all available main categories."""
    client = get_flathub_client()
    try:
        return await client.get_categories()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/category/{category}")
async def get_category(
    category: str,
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale"),
    sort_by: Optional[str] = Query(default=None, description="Sort order"),
    exclude_subcategories: Optional[List[str]] = Query(
        default=None, description="Subcategories to exclude"
    )
) -> Dict[str, Any]:
    """
    Get applications in a specific category.
    
    Supports pagination, subcategory exclusion, and custom sorting.
    """
    client = get_flathub_client()
    try:
        return await client.get_category(
            category,
            page=page,
            per_page=per_page,
            locale=locale,
            sort_by=sort_by,
            exclude_subcategories=exclude_subcategories
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/category/{category}/subcategories")
async def get_subcategory(
    category: str,
    subcategory: List[str] = Query(..., description="Subcategories to include"),
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """Get applications in specific subcategories."""
    client = get_flathub_client()
    try:
        return await client.get_subcategory(
            category,
            subcategory=subcategory,
            page=page,
            per_page=per_page,
            locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Recently Updated/Added ====================

@router.get("/recently-updated")
async def get_recently_updated(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """
    Get recently updated applications.
    
    Sorted by most recent release timestamp.
    """
    client = get_flathub_client()
    try:
        return await client.get_recently_updated(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/recently-added")
async def get_recently_added(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """
    Get recently added applications.
    
    Sorted by date the app was first published.
    """
    client = get_flathub_client()
    try:
        return await client.get_recently_added(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Popular/Trending ====================

@router.get("/popular")
async def get_popular(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """
    Get most popular applications.
    
    Based on installs in the last month.
    """
    client = get_flathub_client()
    try:
        return await client.get_popular(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/trending")
async def get_trending(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """
    Get trending applications.
    
    Uses a trending score based on install growth over last two weeks.
    """
    client = get_flathub_client()
    try:
        return await client.get_trending(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Special Collections ====================

@router.get("/verified")
async def get_verified(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """Get verified applications."""
    client = get_flathub_client()
    try:
        return await client.get_verified(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/mobile")
async def get_mobile(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """Get mobile-friendly applications."""
    client = get_flathub_client()
    try:
        return await client.get_mobile(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/favorites")
async def get_favorites(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """Get most favorited applications."""
    client = get_flathub_client()
    try:
        return await client.get_favorites(
            page=page, per_page=per_page, locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Developers ====================

@router.get("/developer")
async def get_developers(
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page")
) -> Dict[str, Any]:
    """Get paginated list of all developers."""
    client = get_flathub_client()
    try:
        return await client.get_developers(page=page, per_page=per_page)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


@router.get("/developer/{developer}")
async def get_developer_apps(
    developer: str,
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """Get all applications by a specific developer."""
    client = get_flathub_client()
    try:
        return await client.get_developer_apps(
            developer,
            page=page,
            per_page=per_page,
            locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")


# ==================== Keyword Search ====================

@router.get("/keyword")
async def get_keyword_apps(
    keyword: str = Query(..., description="Keyword to search"),
    page: Optional[int] = Query(default=None, description="Page number"),
    per_page: Optional[int] = Query(default=None, description="Items per page"),
    locale: str = Query(default="en", description="Locale")
) -> Dict[str, Any]:
    """Search applications by keyword."""
    client = get_flathub_client()
    try:
        return await client.get_keyword_apps(
            keyword,
            page=page,
            per_page=per_page,
            locale=locale
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Flathub API error: {str(e)}")
