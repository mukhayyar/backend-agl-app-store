"""Tests for Flathub API client."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.flathub_client import (
    FlathubClient, AppType, SortBy, MainCategory, SearchQuery,
    get_flathub_client, close_flathub_client,
)


class TestAppType:
    def test_values(self):
        assert AppType.APPS == "apps"
        assert AppType.DESKTOP == "desktop"
        assert AppType.DESKTOP_APPLICATION == "desktop-application"
        assert AppType.CONSOLE_APPLICATION == "console-application"
        assert AppType.ADDON == "addon"
        assert AppType.RUNTIME == "runtime"


class TestSortBy:
    def test_values(self):
        assert SortBy.ALPHABETICAL == "alphabetical"
        assert SortBy.CREATED_AT == "created-at"
        assert SortBy.LAST_UPDATED_AT == "last-updated-at"


class TestMainCategory:
    def test_values(self):
        assert MainCategory.GAME == "Game"
        assert MainCategory.UTILITY == "Utility"
        assert MainCategory.OFFICE == "Office"
        assert MainCategory.DEVELOPMENT == "Development"


class TestSearchQuery:
    def test_create_query(self):
        q = SearchQuery(query="test")
        assert q.query == "test"
        assert q.page == 1
        assert q.hits_per_page == 25

    def test_query_with_filters(self):
        q = SearchQuery(
            query="game",
            filters=[{"filter_type": "category", "value": "Game"}],
            page=2,
            hits_per_page=10,
        )
        assert q.page == 2
        assert len(q.filters) == 1

    def test_query_model_dump(self):
        q = SearchQuery(query="test")
        data = q.model_dump(exclude_none=True)
        assert data["query"] == "test"
        assert "page" in data


class TestFlathubClient:
    def test_create_client(self):
        client = FlathubClient()
        assert "flathub.org" in client.base_url

    def test_create_client_custom_url(self):
        client = FlathubClient(base_url="https://custom.api.com")
        assert client.base_url == "https://custom.api.com"

    def test_client_property_creates_session(self):
        client = FlathubClient()
        http_client = client.client
        assert http_client is not None
        assert not http_client.is_closed


class TestFlathubClientSingleton:
    def test_get_client(self):
        client1 = get_flathub_client()
        client2 = get_flathub_client()
        assert client1 is client2
