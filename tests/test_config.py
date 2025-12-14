"""Tests for application configuration."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import Settings, get_settings


class TestSettings:
    def test_default_settings(self):
        settings = Settings(
            _env_file=None,  # Don't load .env for tests
        )
        assert settings.http_host == "0.0.0.0"
        assert settings.http_port == 8000
        assert settings.grpc_host == "0.0.0.0"
        assert settings.grpc_port == 50051
        assert settings.max_workers == 10

    def test_database_url_has_value(self):
        settings = Settings(_env_file=None)
        # In test env this may be sqlite; in prod it would be postgresql
        assert len(settings.database_url) > 0

    def test_jwt_defaults(self):
        settings = Settings(_env_file=None)
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_token_expire_minutes == 30
        assert settings.jwt_refresh_token_expire_days == 7

    def test_flat_manager_defaults(self):
        settings = Settings(_env_file=None)
        assert settings.flat_manager_repo == "stable"
        assert settings.flat_manager_branch == "stable"

    def test_flathub_api_url_default(self):
        settings = Settings(_env_file=None)
        assert settings.flathub_api_url == "https://flathub.org/api/v2"

    def test_get_settings_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
