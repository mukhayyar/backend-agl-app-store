"""
Flathub API Client.
Proxies requests to Flathub.org API v2.
"""
import logging
from typing import Any, Dict, List, Optional
from enum import Enum

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AppType(str, Enum):
    """App type filter for Flathub."""
    APPS = "apps"
    DESKTOP = "desktop"
    DESKTOP_APPLICATION = "desktop-application"
    CONSOLE_APPLICATION = "console-application"
    LOCALIZATION = "localization"
    GENERIC = "generic"
    EXTENSION = "extension"
    ADDON = "addon"
    RUNTIME = "runtime"


class SortBy(str, Enum):
    """Sort options for app listings."""
    ALPHABETICAL = "alphabetical"
    CREATED_AT = "created-at"
    LAST_UPDATED_AT = "last-updated-at"


class MainCategory(str, Enum):
    """Main category options."""
    AUDIOVIDEO = "AudioVideo"
    DEVELOPMENT = "Development"
    EDUCATION = "Education"
    GAME = "Game"
    GRAPHICS = "Graphics"
    NETWORK = "Network"
    OFFICE = "Office"
    SCIENCE = "Science"
    SYSTEM = "System"
    UTILITY = "Utility"


class SearchQuery(BaseModel):
    """Search query model for Flathub."""
    query: str
    filters: Optional[List[Dict[str, Any]]] = None
    page: Optional[int] = 1
    hits_per_page: Optional[int] = 25


class FlathubClient:
    """
    HTTP client for proxying Flathub API v2 requests.
    Base URL: https://flathub.org/api/v2
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.flathub_api_url
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                headers={
                    "User-Agent": "AGL-AppStore/1.0",
                    "Accept": "application/json"
                }
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # ==================== App Endpoints ====================
    
    async def list_appstream(
        self,
        filter_type: AppType = AppType.APPS,
        sort: SortBy = SortBy.ALPHABETICAL
    ) -> List[str]:
        """Get list of all application IDs."""
        response = await self.client.get(
            "/appstream",
            params={"filter": filter_type.value, "sort": sort.value}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_appstream(
        self,
        app_id: str,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get AppStream metadata for a specific app."""
        response = await self.client.get(
            f"/appstream/{app_id}",
            params={"locale": locale}
        )
        response.raise_for_status()
        return response.json()
    
    async def search(
        self,
        query: SearchQuery,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Search for applications."""
        response = await self.client.post(
            "/search",
            params={"locale": locale},
            json=query.model_dump(exclude_none=True)
        )
        response.raise_for_status()
        return response.json()
    
    async def get_summary(
        self,
        app_id: str,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get summary information for an app."""
        params = {}
        if branch:
            params["branch"] = branch
        response = await self.client.get(
            f"/summary/{app_id}",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_addons(self, app_id: str) -> List[str]:
        """Get addons for an app."""
        response = await self.client.get(f"/addon/{app_id}")
        response.raise_for_status()
        return response.json()
    
    async def is_fullscreen_app(self, app_id: str) -> bool:
        """Check if app is fullscreen."""
        response = await self.client.get(f"/is-fullscreen-app/{app_id}")
        response.raise_for_status()
        return response.json()
    
    async def get_runtimes(self) -> Dict[str, int]:
        """Get list of runtimes with usage counts."""
        response = await self.client.get("/runtimes")
        response.raise_for_status()
        return response.json()
    
    async def get_platforms(self) -> Dict[str, Any]:
        """Get platform information."""
        response = await self.client.get("/platforms")
        response.raise_for_status()
        return response.json()
    
    # ==================== EOL Endpoints ====================
    
    async def get_eol_rebase(self, app_id: Optional[str] = None, branch: str = "stable") -> Any:
        """Get end-of-life rebase information."""
        if app_id:
            response = await self.client.get(
                f"/eol/rebase/{app_id}",
                params={"branch": branch}
            )
        else:
            response = await self.client.get("/eol/rebase")
        response.raise_for_status()
        return response.json()
    
    async def get_eol_message(self, app_id: Optional[str] = None, branch: str = "stable") -> Any:
        """Get end-of-life message."""
        if app_id:
            response = await self.client.get(
                f"/eol/message/{app_id}",
                params={"branch": branch}
            )
        else:
            response = await self.client.get("/eol/message")
        response.raise_for_status()
        return response.json()
    
    # ==================== Collection Endpoints ====================
    
    async def get_categories(self) -> List[str]:
        """Get list of all categories."""
        response = await self.client.get("/collection/category")
        response.raise_for_status()
        return response.json()
    
    async def get_category(
        self,
        category: str,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en",
        sort_by: Optional[str] = None,
        exclude_subcategories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get apps in a category."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        if sort_by:
            params["sort_by"] = sort_by
        if exclude_subcategories:
            params["exclude_subcategories"] = exclude_subcategories
        
        response = await self.client.get(
            f"/collection/category/{category}",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_subcategory(
        self,
        category: str,
        subcategory: List[str],
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get apps in subcategories."""
        params = {"subcategory": subcategory, "locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            f"/collection/category/{category}/subcategories",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_recently_updated(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get recently updated apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/recently-updated",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_recently_added(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get recently added apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/recently-added",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_popular(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get popular apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/popular",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_trending(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get trending apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/trending",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_verified(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get verified apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/verified",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_mobile(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get mobile-friendly apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/mobile",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_favorites(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get most favorited apps."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/favorites",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_developers(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get list of developers."""
        params = {}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/developer",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_developer_apps(
        self,
        developer: str,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get apps by a developer."""
        params = {"locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            f"/collection/developer/{developer}",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    async def get_keyword_apps(
        self,
        keyword: str,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        locale: str = "en"
    ) -> Dict[str, Any]:
        """Get apps by keyword."""
        params = {"keyword": keyword, "locale": locale}
        if page:
            params["page"] = page
        if per_page:
            params["per_page"] = per_page
        
        response = await self.client.get(
            "/collection/keyword",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    # ==================== Stats Endpoints ====================
    
    async def get_stats(self) -> Optional[Dict[str, Any]]:
        """Get overall statistics."""
        response = await self.client.get("/stats/")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    
    async def get_app_stats(
        self,
        app_id: str,
        all_time: bool = False,
        days: int = 180
    ) -> Optional[Dict[str, Any]]:
        """Get statistics for an app."""
        response = await self.client.get(
            f"/stats/{app_id}",
            params={"all": all_time, "days": days}
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    
    # ==================== App Picks Endpoints ====================
    
    async def get_app_of_the_day(self, date: str) -> Optional[Dict[str, Any]]:
        """Get app of the day for a date."""
        response = await self.client.get(f"/app-picks/app-of-the-day/{date}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    
    async def get_apps_of_the_week(self, date: str) -> Optional[Dict[str, Any]]:
        """Get apps of the week for a date."""
        response = await self.client.get(f"/app-picks/apps-of-the-week/{date}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    
    # ==================== Verification Endpoints ====================
    
    async def get_verification_status(self, app_id: str) -> Dict[str, Any]:
        """Get verification status of an app."""
        response = await self.client.get(f"/verification/{app_id}/status")
        response.raise_for_status()
        return response.json()
    
    # ==================== Feed Endpoints ====================
    
    async def get_recently_updated_feed(self) -> str:
        """Get RSS feed of recently updated apps."""
        response = await self.client.get("/feed/recently-updated")
        response.raise_for_status()
        return response.text
    
    async def get_new_apps_feed(self) -> str:
        """Get RSS feed of new apps."""
        response = await self.client.get("/feed/new")
        response.raise_for_status()
        return response.text
    
    # ==================== Health Check ====================
    
    async def health_check(self) -> bool:
        """Check Flathub API health."""
        try:
            response = await self.client.get("/status")
            return response.status_code == 200
        except Exception:
            return False


# Singleton instance
_flathub_client: Optional[FlathubClient] = None


def get_flathub_client() -> FlathubClient:
    """Get singleton Flathub client instance."""
    global _flathub_client
    if _flathub_client is None:
        _flathub_client = FlathubClient()
    return _flathub_client


async def close_flathub_client():
    """Close the Flathub client."""
    global _flathub_client
    if _flathub_client:
        await _flathub_client.close()
        _flathub_client = None
