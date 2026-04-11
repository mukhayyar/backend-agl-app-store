"""Tests for AGL app HTTP routes."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.conftest import auth_header


class TestListApps:
    def test_list_apps_empty(self, client):
        response = client.get("/http/agl/apps")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_apps_with_data(self, client, sample_app):
        response = client.get("/http/agl/apps")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "org.example.TestApp"
        assert data[0]["name"] == "Test App"

    def test_list_apps_filter_by_type(self, client, sample_app):
        response = client.get("/http/agl/apps?filter=desktop-application")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_list_apps_filter_no_match(self, client, sample_app):
        response = client.get("/http/agl/apps?filter=addon")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_list_apps_sort_alphabetical(self, client, sample_app):
        response = client.get("/http/agl/apps?sort=alphabetical")
        assert response.status_code == 200

    def test_list_apps_sort_created(self, client, sample_app):
        response = client.get("/http/agl/apps?sort=created-at")
        assert response.status_code == 200

    def test_list_apps_sort_updated(self, client, sample_app):
        response = client.get("/http/agl/apps?sort=last-updated-at")
        assert response.status_code == 200

    def test_list_apps_pagination(self, client, sample_app):
        response = client.get("/http/agl/apps?limit=10&offset=0")
        assert response.status_code == 200
        assert len(response.json()) <= 10


class TestSearchApps:
    def test_search_apps_empty_query(self, client, sample_app):
        response = client.get("/http/agl/apps/search?query=")
        assert response.status_code == 200
        data = response.json()
        assert "hits" in data
        assert "total_hits" in data

    def test_search_apps_by_name(self, client, sample_app):
        response = client.get("/http/agl/apps/search?query=Test")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] >= 1
        assert data["hits"][0]["name"] == "Test App"

    def test_search_apps_no_results(self, client, sample_app):
        response = client.get("/http/agl/apps/search?query=nonexistent_xyz")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] == 0

    def test_search_apps_pagination(self, client, sample_app):
        response = client.get("/http/agl/apps/search?query=&page=1&hits_per_page=5")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["hits_per_page"] == 5

    def test_search_by_category(self, client, sample_app):
        response = client.get("/http/agl/apps/search?query=&category=Utility")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] >= 1


class TestCategories:
    def test_get_categories(self, client, sample_app):
        response = client.get("/http/agl/apps/categories")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Utility"
        assert data[0]["app_count"] >= 1

    def test_get_categories_empty(self, client):
        response = client.get("/http/agl/apps/categories")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_category_apps(self, client, sample_app):
        response = client.get("/http/agl/apps/categories/Utility")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] >= 1

    def test_get_category_apps_not_found(self, client):
        response = client.get("/http/agl/apps/categories/NonExistent")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] == 0


class TestCollections:
    def test_recently_updated(self, client, sample_app):
        response = client.get("/http/agl/apps/recently-updated")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] >= 1

    def test_recently_added(self, client, sample_app):
        response = client.get("/http/agl/apps/recently-added")
        assert response.status_code == 200
        data = response.json()
        assert data["total_hits"] >= 1

    def test_verified_apps(self, client, sample_app):
        response = client.get("/http/agl/apps/verified")
        assert response.status_code == 200
        data = response.json()
        # sample_app is not verified
        assert data["total_hits"] == 0


class TestAppDetail:
    def test_get_app(self, client, sample_app):
        response = client.get("/http/agl/apps/org.example.TestApp")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "org.example.TestApp"
        assert data["name"] == "Test App"
        assert data["type"] == "desktop-application"
        assert "Utility" in data["categories"]

    def test_get_app_not_found(self, client):
        response = client.get("/http/agl/apps/org.nonexistent.App")
        assert response.status_code == 404

    def test_get_app_summary(self, client, sample_app):
        response = client.get("/http/agl/apps/org.example.TestApp/summary")
        assert response.status_code == 200
        data = response.json()
        assert "arches" in data
        assert "metadata" in data

    def test_get_app_summary_not_found(self, client):
        response = client.get("/http/agl/apps/org.nonexistent.App/summary")
        assert response.status_code == 404

    def test_get_app_addons(self, client, sample_app):
        response = client.get("/http/agl/apps/org.example.TestApp/addons")
        assert response.status_code == 200
        data = response.json()
        assert "addons" in data
        assert isinstance(data["addons"], list)


class TestHealthCheck:
    def test_health(self, client):
        response = client.get("/http/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root(self, client):
        response = client.get("/http/")
        assert response.status_code == 200
        data = response.json()
        assert "stores" in data
        assert "agl" in data["stores"]
        assert "flathub" in data["stores"]
