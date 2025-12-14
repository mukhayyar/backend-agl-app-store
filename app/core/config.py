"""
Configuration settings using pydantic-settings for environment variable management.
"""
import sys
import logging
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

INSECURE_DEFAULTS = frozenset({
    "your_jwt_secret_key_here_change_in_production",
    "changeme",
    "change_this_to_a_random_secret_key",
    "secret",
    "",
})


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://localhost/agl_store"

    # HTTP Server
    http_host: str = "0.0.0.0"
    http_port: int = 8000

    # gRPC Server
    grpc_host: str = "0.0.0.0"
    grpc_port: int = 50051
    max_workers: int = 10

    # OAuth Providers
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    gitlab_client_id: Optional[str] = None
    gitlab_client_secret: Optional[str] = None

    # Stripe
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None

    # flat-manager settings
    flat_manager_url: str = "http://localhost:8080"
    flat_manager_api_url: str = "http://localhost:8080/api/v1"
    flat_manager_repo: str = "stable"
    flat_manager_branch: str = "stable"
    flat_manager_secret: str = ""  # REQUIRED: set via FLAT_MANAGER_SECRET env var
    flat_manager_gentoken_path: str = "gentoken"

    # Flathub proxy settings
    flathub_api_url: str = "https://flathub.org/api/v2"

    # CORS — REQUIRED in production: comma-separated allowed origins
    cors_origins: str = ""

    # JWT Configuration
    jwt_secret_key: str = ""  # REQUIRED: set via JWT_SECRET_KEY env var
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Upload limits
    max_upload_size_mb: int = 500  # Maximum file upload size in MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def validate_for_production(self) -> None:
        """Validate that critical settings are properly configured."""
        errors = []

        if not self.jwt_secret_key or self.jwt_secret_key in INSECURE_DEFAULTS:
            errors.append("JWT_SECRET_KEY is not set or uses an insecure default")

        if not self.flat_manager_secret or self.flat_manager_secret in INSECURE_DEFAULTS:
            errors.append("FLAT_MANAGER_SECRET is not set or uses an insecure default")

        if not self.cors_origins:
            logger.warning(
                "CORS_ORIGINS is empty — CORS will reject all cross-origin requests. "
                "Set CORS_ORIGINS to a comma-separated list of allowed origins."
            )

        if not self.database_url or "localhost" in self.database_url:
            logger.warning("DATABASE_URL points to localhost — ensure this is correct for your environment")

        if errors:
            for err in errors:
                logger.error(f"Configuration error: {err}")
            logger.error("Aborting startup due to missing/insecure configuration. Check your .env file.")
            sys.exit(1)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
