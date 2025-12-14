"""
flat-manager API client service.
Proxies all flat-manager API calls through our backend.
"""
import logging
import base64
import subprocess
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import aiohttp
import jwt

from app.core.config import get_settings
from app.core.roles import UserRole, get_scopes_for_role

logger = logging.getLogger(__name__)
settings = get_settings()


class FlatManagerClient:
    """
    Client for interacting with flat-manager API.
    All endpoints are proxied through this service so the frontend
    only needs to communicate with our backend.
    """
    
    def __init__(self, token: Optional[str] = None):
        self.base_url = settings.flat_manager_api_url
        self.repo_url = settings.flat_manager_url
        self.default_repo = settings.flat_manager_repo
        self.default_branch = settings.flat_manager_branch
        self.token = token
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Get request headers with authorization."""
        headers = {"Content-Type": "application/json"}
        auth_token = token or self.token
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        token: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make a request to flat-manager API."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(token)
        
        try:
            async with session.request(method, url, headers=headers, **kwargs) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"flat-manager API error: {response.status} - {error_text}")
                    return {
                        "error": True,
                        "status": response.status,
                        "message": error_text
                    }
                
                if response.content_type == "application/json":
                    return await response.json()
                return {"data": await response.text()}
        except aiohttp.ClientError as e:
            logger.error(f"flat-manager connection error: {e}")
            return {"error": True, "message": str(e)}
    
    # ==================== Token Management ====================
    
    async def get_tokens(self, token: str) -> Dict[str, Any]:
        """Get list of tokens (POST /api/v1/tokens/get_list)."""
        return await self._request("POST", "/tokens/get_list", token=token)
    
    async def revoke_tokens(self, token: str, token_ids: List[str]) -> Dict[str, Any]:
        """Revoke tokens (POST /api/v1/tokens/revoke)."""
        return await self._request(
            "POST", "/tokens/revoke",
            token=token,
            json={"tokens": token_ids}
        )
    
    async def create_token_subset(
        self,
        token: str,
        scopes: List[str],
        prefixes: List[str] = None,
        repos: List[str] = None
    ) -> Dict[str, Any]:
        """Create a subset token with reduced permissions (POST /api/v1/token_subset)."""
        payload = {"scope": scopes}
        if prefixes:
            payload["prefixes"] = prefixes
        if repos:
            payload["repos"] = repos
        return await self._request("POST", "/token_subset", token=token, json=payload)
    
    # ==================== Build Operations ====================
    
    async def create_build(
        self,
        token: str,
        repo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new build (POST /api/v1/build)."""
        payload = {"repo": repo or self.default_repo}
        return await self._request("POST", "/build", token=token, json=payload)
    
    async def list_builds(self, token: str) -> Dict[str, Any]:
        """List all builds (GET /api/v1/build)."""
        return await self._request("GET", "/build", token=token)
    
    async def get_build(self, token: str, build_id: int) -> Dict[str, Any]:
        """Get build details (GET /api/v1/build/{id})."""
        return await self._request("GET", f"/build/{build_id}", token=token)
    
    async def get_build_extended(self, token: str, build_id: int) -> Dict[str, Any]:
        """Get extended build details (GET /api/v1/build/{id}/extended)."""
        return await self._request("GET", f"/build/{build_id}/extended", token=token)
    
    async def create_build_ref(
        self,
        token: str,
        build_id: int,
        ref_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a build ref (POST /api/v1/build/{id}/build_ref)."""
        return await self._request(
            "POST", f"/build/{build_id}/build_ref",
            token=token,
            json=ref_data
        )
    
    async def get_build_ref(
        self,
        token: str,
        build_id: int,
        ref_id: int
    ) -> Dict[str, Any]:
        """Get build ref details (GET /api/v1/build/{id}/build_ref/{ref_id})."""
        return await self._request(
            "GET", f"/build/{build_id}/build_ref/{ref_id}",
            token=token
        )
    
    async def get_missing_objects(
        self,
        token: str,
        build_id: int,
        objects: List[str] = None
    ) -> Dict[str, Any]:
        """Get missing objects for a build (GET /api/v1/build/{id}/missing_objects)."""
        params = {}
        if objects:
            params["objects"] = objects
        return await self._request(
            "GET", f"/build/{build_id}/missing_objects",
            token=token,
            params=params
        )
    
    async def add_extra_ids(
        self,
        token: str,
        build_id: int,
        extra_ids: List[str]
    ) -> Dict[str, Any]:
        """Add extra IDs to a build (POST /api/v1/build/{id}/add_extra_ids)."""
        return await self._request(
            "POST", f"/build/{build_id}/add_extra_ids",
            token=token,
            json={"ids": extra_ids}
        )
    
    async def upload_to_build(
        self,
        token: str,
        build_id: int,
        file_data: bytes,
        filename: str
    ) -> Dict[str, Any]:
        """Upload file to a build (POST /api/v1/build/{id}/upload)."""
        session = await self._get_session()
        url = f"{self.base_url}/build/{build_id}/upload"
        headers = {"Authorization": f"Bearer {token}"}
        
        data = aiohttp.FormData()
        data.add_field("file", file_data, filename=filename)
        
        try:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    return {"error": True, "status": response.status, "message": error_text}
                return await response.json()
        except aiohttp.ClientError as e:
            return {"error": True, "message": str(e)}
    
    async def commit_build(
        self,
        token: str,
        build_id: int,
        wait: bool = False
    ) -> Dict[str, Any]:
        """Commit a build (POST /api/v1/build/{id}/commit)."""
        params = {"wait": "true"} if wait else {}
        return await self._request(
            "POST", f"/build/{build_id}/commit",
            token=token,
            params=params
        )
    
    async def get_commit_job(self, token: str, build_id: int) -> Dict[str, Any]:
        """Get commit job status (GET /api/v1/build/{id}/commit)."""
        return await self._request("GET", f"/build/{build_id}/commit", token=token)
    
    async def publish_build(
        self,
        token: str,
        build_id: int,
        wait: bool = False
    ) -> Dict[str, Any]:
        """Publish a build (POST /api/v1/build/{id}/publish)."""
        params = {"wait": "true"} if wait else {}
        return await self._request(
            "POST", f"/build/{build_id}/publish",
            token=token,
            params=params
        )
    
    async def get_publish_job(self, token: str, build_id: int) -> Dict[str, Any]:
        """Get publish job status (GET /api/v1/build/{id}/publish)."""
        return await self._request("GET", f"/build/{build_id}/publish", token=token)
    
    async def purge_build(self, token: str, build_id: int) -> Dict[str, Any]:
        """Purge a build (POST /api/v1/build/{id}/purge)."""
        return await self._request("POST", f"/build/{build_id}/purge", token=token)
    
    # ==================== Job Operations ====================
    
    async def get_job(self, token: str, job_id: int) -> Dict[str, Any]:
        """Get job details (GET /api/v1/job/{id})."""
        return await self._request("GET", f"/job/{job_id}", token=token)
    
    async def get_check_job(
        self,
        token: str,
        build_id: int,
        check_name: str
    ) -> Dict[str, Any]:
        """Get check job status (GET /api/v1/build/{id}/check/{check_name}/job)."""
        return await self._request(
            "GET", f"/build/{build_id}/check/{check_name}/job",
            token=token
        )
    
    async def review_check(
        self,
        token: str,
        job_id: int,
        new_status: str
    ) -> Dict[str, Any]:
        """Review a check job (POST /api/v1/job/{id}/check/review)."""
        return await self._request(
            "POST", f"/job/{job_id}/check/review",
            token=token,
            json={"status": new_status}
        )
    
    # ==================== Repository Operations ====================
    
    async def republish(
        self,
        token: str,
        repo: Optional[str] = None,
        app_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Republish an app (POST /api/v1/repo/{repo}/republish)."""
        repo_name = repo or self.default_repo
        payload = {}
        if app_id:
            payload["app"] = app_id
        return await self._request(
            "POST", f"/repo/{repo_name}/republish",
            token=token,
            json=payload
        )
    
    # ==================== Delta Operations ====================
    
    async def upload_delta(
        self,
        token: str,
        repo: str,
        delta_data: bytes
    ) -> Dict[str, Any]:
        """Upload a delta (POST /api/v1/delta/upload/{repo})."""
        session = await self._get_session()
        url = f"{self.base_url}/delta/upload/{repo}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            async with session.post(url, headers=headers, data=delta_data) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    return {"error": True, "status": response.status, "message": error_text}
                return await response.json()
        except aiohttp.ClientError as e:
            return {"error": True, "message": str(e)}
    
    # ==================== Status Operations ====================
    
    async def get_status(self) -> Dict[str, Any]:
        """Get flat-manager status (GET /status)."""
        session = await self._get_session()
        url = f"{self.repo_url}/status"
        try:
            async with session.get(url) as response:
                if response.content_type == "application/json":
                    return await response.json()
                return {"status": await response.text()}
        except aiohttp.ClientError as e:
            return {"error": True, "message": str(e)}
    
    async def get_job_status(self, job_id: int) -> Dict[str, Any]:
        """Get job status (GET /status/{id})."""
        session = await self._get_session()
        url = f"{self.repo_url}/status/{job_id}"
        try:
            async with session.get(url) as response:
                if response.content_type == "application/json":
                    return await response.json()
                return {"status": await response.text()}
        except aiohttp.ClientError as e:
            return {"error": True, "message": str(e)}
    
    # ==================== Prune Operations ====================
    
    async def prune(self, token: str) -> Dict[str, Any]:
        """Trigger prune operation (POST /api/v1/prune)."""
        return await self._request("POST", "/prune", token=token)


class TokenManager:
    """
    Manages token generation compatible with flat-manager.
    Can use either the gentoken binary or generate tokens directly with PyJWT.
    """
    
    def __init__(self):
        self.secret = settings.flat_manager_secret
        self.gentoken_path = settings.flat_manager_gentoken_path
    
    def _decode_secret(self) -> bytes:
        """Decode base64 secret."""
        return base64.b64decode(self.secret)
    
    def generate_token(
        self,
        name: str,
        sub: str = "build",
        scopes: List[str] = None,
        prefixes: List[str] = None,
        repos: List[str] = None,
        branches: List[str] = None,
        duration_days: int = 365,
        token_type: str = "app"
    ) -> str:
        """
        Generate a flat-manager compatible JWT token using PyJWT.
        This matches the structure from gentoken.rs.
        """
        if scopes is None:
            scopes = ["build", "upload", "download", "publish", "jobs"]
        if prefixes is None:
            prefixes = [""]
        if repos is None:
            repos = [""]
        if branches is None:
            branches = ["stable"]
        
        exp = datetime.utcnow() + timedelta(days=duration_days)
        
        claims = {
            "sub": sub,
            "scope": scopes,
            "name": name,
            "prefixes": prefixes,
            "repos": repos,
            "exp": int(exp.timestamp()),
            "token_type": token_type,
            "branches": branches,
        }
        
        secret = self._decode_secret()
        token = jwt.encode(claims, secret, algorithm="HS256")
        return token
    
    def generate_token_for_role(
        self,
        name: str,
        role: UserRole,
        prefixes: List[str] = None,
        repos: List[str] = None
    ) -> str:
        """Generate a token with scopes based on user role."""
        scopes = get_scopes_for_role(role)
        return self.generate_token(
            name=name,
            scopes=scopes,
            prefixes=prefixes,
            repos=repos
        )
    
    def generate_token_via_binary(
        self,
        name: str,
        scopes: List[str] = None,
        repos: List[str] = None,
        branches: List[str] = None,
        duration: int = None
    ) -> Optional[str]:
        """
        Generate token using the gentoken binary.
        Returns None if the binary is not available.
        """
        try:
            cmd = [self.gentoken_path, "--base64", "--secret", self.secret, "--name", name]
            
            if scopes:
                for scope in scopes:
                    cmd.extend(["--scope", scope])
            if repos:
                for repo in repos:
                    cmd.extend(["--repo", repo])
            if branches:
                for branch in branches:
                    cmd.extend(["--branch", branch])
            if duration:
                cmd.extend(["--duration", str(duration)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"gentoken error: {result.stderr}")
                return None
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            logger.warning(f"gentoken binary not available: {e}")
            return None
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and decode a flat-manager token."""
        try:
            secret = self._decode_secret()
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            return payload
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None


# Singleton instances
_flat_manager_client: Optional[FlatManagerClient] = None
_token_manager: Optional[TokenManager] = None


def get_flat_manager_client() -> FlatManagerClient:
    """Get singleton FlatManagerClient instance."""
    global _flat_manager_client
    if _flat_manager_client is None:
        _flat_manager_client = FlatManagerClient()
    return _flat_manager_client


def get_token_manager() -> TokenManager:
    """Get singleton TokenManager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
