"""Tests for authentication middleware."""
import pytest
import sys, os
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.auth_middleware import (
    TokenClaims, create_access_token, decode_token,
)
from app.core.roles import UserRole, FlatManagerScope

class TestTokenClaims:
    def test_create_token_claims(self):
        claims = TokenClaims(sub="user/1", name="test", scope=["build", "download"])
        assert claims.sub == "user/1"
        assert claims.name == "test"
        assert claims.scope == ["build", "download"]
        assert claims.token_type == "app"
        assert claims.role == "user"

    def test_default_values(self):
        claims = TokenClaims(sub="test", name="test", scope=[])
        assert claims.prefixes == [""]
        assert claims.repos == [""]
        assert claims.branches == ["stable"]
        assert claims.apps == []

    def test_to_dict(self):
        claims = TokenClaims(sub="user/1", name="test", scope=["download"], user_id=1, role="admin")
        d = claims.to_dict()
        assert d["sub"] == "user/1"
        assert d["user_id"] == 1
        assert d["role"] == "admin"
        assert isinstance(d, dict)

    def test_from_dict(self):
        data = {
            "sub": "user/1",
            "name": "test",
            "scope": ["download"],
            "user_id": 1,
            "role": "publisher",
        }
        claims = TokenClaims.from_dict(data)
        assert claims.user_id == 1
        assert claims.role == "publisher"

    def test_from_dict_defaults(self):
        claims = TokenClaims.from_dict({})
        assert claims.sub == ""
        assert claims.name == ""
        assert claims.scope == []
        assert claims.role == "user"

    def test_has_scope(self):
        claims = TokenClaims(sub="test", name="test", scope=["build", "upload", "download"])
        assert claims.has_scope("build") is True
        assert claims.has_scope("download") is True
        assert claims.has_scope("jobs") is False

    def test_get_user_role(self):
        claims = TokenClaims(sub="test", name="test", scope=[], role="admin")
        assert claims.get_user_role() == UserRole.ADMIN

    def test_get_user_role_invalid(self):
        claims = TokenClaims(sub="test", name="test", scope=[], role="superadmin")
        assert claims.get_user_role() == UserRole.USER

    def test_get_user_role_default(self):
        claims = TokenClaims(sub="test", name="test", scope=[])
        assert claims.get_user_role() == UserRole.USER

class TestCreateAccessToken:
    def test_create_token(self):
        token = create_access_token(user_id=1, role=UserRole.USER)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_admin_token(self):
        token = create_access_token(user_id=1, role=UserRole.ADMIN, name="admin_token")
        claims = decode_token(token)
        assert claims is not None
        assert claims.user_id == 1
        assert claims.role == "admin"
        assert "jobs" in claims.scope
        assert "tokenmanagement" in claims.scope

    def test_create_publisher_token(self):
        token = create_access_token(user_id=2, role=UserRole.PUBLISHER)
        claims = decode_token(token)
        assert claims is not None
        assert "build" in claims.scope
        assert "upload" in claims.scope
        assert "publish" in claims.scope

    def test_create_user_token(self):
        token = create_access_token(user_id=3, role=UserRole.USER)
        claims = decode_token(token)
        assert claims is not None
        assert claims.scope == ["download"]

    def test_custom_expiry(self):
        token = create_access_token(user_id=1, role=UserRole.USER, expires_delta=timedelta(hours=1))
        claims = decode_token(token)
        assert claims is not None

class TestDecodeToken:
    def test_decode_valid_token(self):
        token = create_access_token(user_id=42, role=UserRole.REVIEWER)
        claims = decode_token(token)
        assert claims is not None
        assert claims.user_id == 42
        assert claims.role == "reviewer"

    def test_decode_invalid_token(self):
        claims = decode_token("invalid.token.here")
        assert claims is None

    def test_decode_empty_token(self):
        claims = decode_token("")
        assert claims is None

    def test_decode_expired_token(self):
        token = create_access_token(user_id=1, role=UserRole.USER, expires_delta=timedelta(seconds=-1))
        claims = decode_token(token)
        assert claims is None

    def test_roundtrip(self):
        for role in UserRole:
            token = create_access_token(user_id=1, role=role)
            claims = decode_token(token)
            assert claims is not None
            assert claims.role == role.value
