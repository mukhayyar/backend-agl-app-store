"""Tests for flat-manager API client."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.flatmanager_client import FlatManagerClient, TokenManager, get_flat_manager_client, get_token_manager
from app.core.roles import UserRole


class TestTokenManager:
    def test_generate_token(self):
        tm = TokenManager()
        token = tm.generate_token(name="test-token")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_with_scopes(self):
        tm = TokenManager()
        token = tm.generate_token(name="test", scopes=["build", "upload"])
        decoded = tm.validate_token(token)
        assert decoded is not None
        assert "build" in decoded["scope"]
        assert "upload" in decoded["scope"]

    def test_generate_token_for_role_admin(self):
        tm = TokenManager()
        token = tm.generate_token_for_role(name="admin-test", role=UserRole.ADMIN)
        decoded = tm.validate_token(token)
        assert decoded is not None
        assert "jobs" in decoded["scope"]
        assert "tokenmanagement" in decoded["scope"]

    def test_generate_token_for_role_publisher(self):
        tm = TokenManager()
        token = tm.generate_token_for_role(name="pub-test", role=UserRole.PUBLISHER)
        decoded = tm.validate_token(token)
        assert decoded is not None
        assert "build" in decoded["scope"]
        assert "upload" in decoded["scope"]
        assert "publish" in decoded["scope"]
        assert "jobs" not in decoded["scope"]

    def test_generate_token_for_role_user(self):
        tm = TokenManager()
        token = tm.generate_token_for_role(name="user-test", role=UserRole.USER)
        decoded = tm.validate_token(token)
        assert decoded is not None
        assert decoded["scope"] == ["download"]

    def test_validate_valid_token(self):
        tm = TokenManager()
        token = tm.generate_token(name="valid")
        result = tm.validate_token(token)
        assert result is not None
        assert result["name"] == "valid"

    def test_validate_invalid_token(self):
        tm = TokenManager()
        result = tm.validate_token("invalid.token.here")
        assert result is None

    def test_generate_token_custom_params(self):
        tm = TokenManager()
        token = tm.generate_token(
            name="custom",
            sub="custom-sub",
            scopes=["build"],
            prefixes=["org.example"],
            repos=["stable"],
            branches=["stable", "beta"],
            duration_days=30,
            token_type="custom",
        )
        decoded = tm.validate_token(token)
        assert decoded["sub"] == "custom-sub"
        assert decoded["prefixes"] == ["org.example"]
        assert decoded["branches"] == ["stable", "beta"]
        assert decoded["token_type"] == "custom"

    def test_generate_token_via_binary_fallback(self):
        tm = TokenManager()
        # gentoken binary likely doesn't exist, should return None
        result = tm.generate_token_via_binary(name="test")
        assert result is None


class TestFlatManagerClient:
    def test_create_client(self):
        client = FlatManagerClient()
        assert client.base_url is not None
        assert client.default_repo == "stable"

    def test_get_headers_with_token(self):
        client = FlatManagerClient(token="test-token")
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-token"

    def test_get_headers_override_token(self):
        client = FlatManagerClient(token="default-token")
        headers = client._get_headers(token="override-token")
        assert headers["Authorization"] == "Bearer override-token"

    def test_get_headers_no_token(self):
        client = FlatManagerClient()
        headers = client._get_headers()
        assert "Authorization" not in headers


class TestSingletons:
    def test_get_flat_manager_client(self):
        client1 = get_flat_manager_client()
        client2 = get_flat_manager_client()
        assert client1 is client2

    def test_get_token_manager(self):
        tm1 = get_token_manager()
        tm2 = get_token_manager()
        assert tm1 is tm2
