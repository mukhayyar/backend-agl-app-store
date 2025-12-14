"""Tests for auth HTTP routes."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import auth_header


class TestLoginMethods:
    def test_get_login_methods(self, client):
        response = client.get("/http/agl/auth/methods")
        assert response.status_code == 200
        data = response.json()
        assert "methods" in data
        methods = [m["method"] for m in data["methods"]]
        assert "github" in methods
        assert "gitlab" in methods
        assert "google" in methods


class TestLogin:
    def test_login_creates_user(self, client, db):
        response = client.post("/http/agl/auth/login", json={
            "provider": "github",
            "access_token": "fake_token_123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "user"
        assert data["user_id"] > 0

    def test_login_returns_existing_user(self, client, db, sample_user):
        response = client.post("/http/agl/auth/login", json={
            "provider": "github",
            "access_token": "fake_token_123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_user.id


class TestGetUser:
    def test_get_user_authenticated(self, client, sample_user, user_token):
        response = client.get("/http/agl/auth/user", headers=auth_header(user_token))
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_user.id
        assert data["display_name"] == "Test User"

    def test_get_user_unauthenticated(self, client):
        response = client.get("/http/agl/auth/user")
        assert response.status_code == 401 or response.status_code == 403


class TestUpdateUser:
    def test_update_display_name(self, client, sample_user, user_token):
        response = client.put("/http/agl/auth/user",
            headers=auth_header(user_token),
            json={"display_name": "New Name"})
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "New Name"

    def test_update_user_unauthenticated(self, client):
        response = client.put("/http/agl/auth/user", json={"display_name": "New"})
        assert response.status_code == 401 or response.status_code == 403


class TestLogout:
    def test_logout(self, client, user_token):
        response = client.post("/http/agl/auth/logout", headers=auth_header(user_token))
        assert response.status_code == 200

    def test_logout_unauthenticated(self, client):
        response = client.post("/http/agl/auth/logout")
        assert response.status_code == 401 or response.status_code == 403


class TestMe:
    def test_me_authenticated(self, client, sample_user, user_token):
        response = client.get("/http/agl/auth/me", headers=auth_header(user_token))
        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is True
        assert data["user_id"] == sample_user.id

    def test_me_unauthenticated(self, client):
        response = client.get("/http/agl/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["logged_in"] is False


class TestAdminEndpoints:
    def test_change_role_as_admin(self, client, admin_token, sample_user):
        response = client.post(
            f"/http/agl/auth/users/{sample_user.id}/role",
            headers=auth_header(admin_token),
            json={"user_id": sample_user.id, "new_role": "publisher"}
        )
        assert response.status_code == 200

    def test_change_role_as_user_forbidden(self, client, user_token, sample_user):
        response = client.post(
            f"/http/agl/auth/users/{sample_user.id}/role",
            headers=auth_header(user_token),
            json={"user_id": sample_user.id, "new_role": "admin"}
        )
        assert response.status_code == 403

    def test_change_role_invalid_role(self, client, admin_token, sample_user):
        response = client.post(
            f"/http/agl/auth/users/{sample_user.id}/role",
            headers=auth_header(admin_token),
            json={"user_id": sample_user.id, "new_role": "superadmin"}
        )
        assert response.status_code == 400

    def test_change_role_user_not_found(self, client, admin_token):
        response = client.post(
            "/http/agl/auth/users/99999/role",
            headers=auth_header(admin_token),
            json={"user_id": 99999, "new_role": "publisher"}
        )
        assert response.status_code == 404

    def test_list_users_as_admin(self, client, admin_token, sample_user):
        response = client.get("/http/agl/auth/users", headers=auth_header(admin_token))
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_users_as_user_forbidden(self, client, user_token):
        response = client.get("/http/agl/auth/users", headers=auth_header(user_token))
        assert response.status_code == 403
