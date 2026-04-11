"""Tests for stats HTTP routes."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestOverallStats:
    def test_get_stats(self, client, sample_app):
        response = client.get("/http/agl/stats")
        assert response.status_code == 200
        data = response.json()
        assert "totals" in data
        assert "apps" in data["totals"]
        assert data["totals"]["apps"] >= 1

    def test_get_stats_empty(self, client):
        response = client.get("/http/agl/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["totals"]["apps"] == 0


class TestAppStats:
    def test_get_app_stats(self, client, sample_app):
        response = client.get("/http/agl/stats/org.example.TestApp")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "org.example.TestApp"
        assert "installs_total" in data
        assert "installs_per_country" in data

    def test_get_app_stats_not_found(self, client):
        response = client.get("/http/agl/stats/org.nonexistent.App")
        assert response.status_code == 404
