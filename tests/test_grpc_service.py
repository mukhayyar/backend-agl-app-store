"""Tests for gRPC service implementation."""
import pytest
import sys, os

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
# generated/ dir uses bare imports like `import pens_agl_store_pb2`
sys.path.insert(0, os.path.join(_project_root, "generated"))

from unittest.mock import MagicMock, patch
from datetime import datetime

# We need to mock database for gRPC service tests
from database import Base, App, User, Category, Favorite, AppStats
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create test database for gRPC service
GRPC_TEST_DB_URL = "sqlite:///./test_grpc.db"
grpc_engine = create_engine(GRPC_TEST_DB_URL, connect_args={"check_same_thread": False})
GRPCTestSession = sessionmaker(autocommit=False, autoflush=False, bind=grpc_engine)


@pytest.fixture(scope="function")
def grpc_db():
    Base.metadata.create_all(bind=grpc_engine)
    session = GRPCTestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=grpc_engine)


@pytest.fixture
def grpc_service(grpc_db):
    """Create gRPC service with test database."""
    from service import PENSAGLStoreService
    service = PENSAGLStoreService()
    service.db = grpc_db  # Override the database session
    return service


@pytest.fixture
def mock_context():
    """Create a mock gRPC context."""
    context = MagicMock()
    context.set_code = MagicMock()
    context.set_details = MagicMock()
    return context


@pytest.fixture
def grpc_app(grpc_db):
    cat = Category(name="Utility", description="Utility apps")
    app = App(
        id="org.example.TestApp",
        name="Test App",
        summary="A test app",
        description="Test description",
        type="desktop-application",
        is_free_license=True,
        developer_name="Test Dev",
        runtime="org.freedesktop.Platform/x86_64/23.08",
        added_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        verification_verified=False,
        verification_method="none",
        is_mobile_friendly=False,
    )
    app.categories.append(cat)
    grpc_db.add(app)
    grpc_db.commit()
    return app


@pytest.fixture
def grpc_user(grpc_db):
    user = User(
        display_name="Test User",
        invite_code="test-grpc-123",
        role="user",
        default_account_provider="github",
        default_account_login="testuser",
        created_at=datetime.utcnow(),
    )
    grpc_db.add(user)
    grpc_db.commit()
    grpc_db.refresh(user)
    return user


class TestListAppstream:
    def test_list_all(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.ListAppstreamRequest()
        response = grpc_service.ListAppstream(request, mock_context)
        assert "org.example.TestApp" in response.app_ids

    def test_list_with_filter(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.ListAppstreamRequest(filter="desktop-application")
        response = grpc_service.ListAppstream(request, mock_context)
        assert len(response.app_ids) >= 1

    def test_list_empty(self, grpc_service, mock_context):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.ListAppstreamRequest()
        response = grpc_service.ListAppstream(request, mock_context)
        assert len(response.app_ids) == 0


class TestGetAppstream:
    def test_get_desktop_app(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.GetAppstreamRequest(app_id="org.example.TestApp")
        response = grpc_service.GetAppstream(request, mock_context)
        assert response.HasField("desktop")
        assert response.desktop.name == "Test App"

    def test_get_app_not_found(self, grpc_service, mock_context):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.GetAppstreamRequest(app_id="org.nonexistent.App")
        grpc_service.GetAppstream(request, mock_context)
        mock_context.set_code.assert_called()


class TestSearchApps:
    def test_search_by_name(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        query = pens_agl_store_pb2.SearchQuery(query="Test", hits_per_page=21, page=1)
        request = pens_agl_store_pb2.SearchAppsRequest(locale="en", query=query)
        response = grpc_service.SearchApps(request, mock_context)
        assert response.total_hits >= 1

    def test_search_no_results(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        query = pens_agl_store_pb2.SearchQuery(query="nonexistent_xyz", hits_per_page=21, page=1)
        request = pens_agl_store_pb2.SearchAppsRequest(locale="en", query=query)
        response = grpc_service.SearchApps(request, mock_context)
        assert response.total_hits == 0


class TestCategories:
    def test_get_categories(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        from google.protobuf.empty_pb2 import Empty
        response = grpc_service.GetCategories(Empty(), mock_context)
        assert "Utility" in response.categories


class TestFavorites:
    def test_add_favorite(self, grpc_service, mock_context, grpc_app, grpc_user):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.AddToFavoritesRequest(app_id="org.example.TestApp")
        grpc_service.AddToFavorites(request, mock_context)

        # Check it was added
        request2 = pens_agl_store_pb2.IsFavoritedRequest(app_id="org.example.TestApp")
        response = grpc_service.IsFavorited(request2, mock_context)
        assert response.is_favorited is True

    def test_remove_favorite(self, grpc_service, mock_context, grpc_app, grpc_user):
        from generated import pens_agl_store_pb2
        # Add first
        add_req = pens_agl_store_pb2.AddToFavoritesRequest(app_id="org.example.TestApp")
        grpc_service.AddToFavorites(add_req, mock_context)
        # Remove
        rem_req = pens_agl_store_pb2.RemoveFromFavoritesRequest(app_id="org.example.TestApp")
        grpc_service.RemoveFromFavorites(rem_req, mock_context)
        # Check
        check_req = pens_agl_store_pb2.IsFavoritedRequest(app_id="org.example.TestApp")
        response = grpc_service.IsFavorited(check_req, mock_context)
        assert response.is_favorited is False


class TestStats:
    def test_get_stats(self, grpc_service, mock_context, grpc_app):
        from google.protobuf.empty_pb2 import Empty
        response = grpc_service.GetStats(Empty(), mock_context)
        assert response.HasField("stats")

    def test_get_stats_for_app(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.GetStatsForAppRequest(app_id="org.example.TestApp")
        response = grpc_service.GetStatsForApp(request, mock_context)
        assert response.HasField("stats")

    def test_get_stats_for_nonexistent_app(self, grpc_service, mock_context):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.GetStatsForAppRequest(app_id="org.nonexistent.App")
        response = grpc_service.GetStatsForApp(request, mock_context)
        # Should return not_found variant or empty response
        assert not response.HasField("stats") or response.HasField("not_found")


class TestHealthcheck:
    def test_healthcheck(self, grpc_service, mock_context, grpc_app):
        from google.protobuf.empty_pb2 import Empty
        response = grpc_service.Healthcheck(Empty(), mock_context)
        assert response is not None


class TestLoginMethods:
    def test_get_login_methods(self, grpc_service, mock_context):
        from google.protobuf.empty_pb2 import Empty
        response = grpc_service.GetLoginMethods(Empty(), mock_context)
        methods = [m.method for m in response.methods]
        assert "github" in methods
        assert "gitlab" in methods


class TestCollections:
    def test_recently_updated(self, grpc_service, mock_context, grpc_app):
        from generated import pens_agl_store_pb2
        request = pens_agl_store_pb2.GetRecentlyUpdatedRequest(page=1, per_page=21)
        response = grpc_service.GetRecentlyUpdated(request, mock_context)
        assert response.total_hits >= 1

    def test_get_runtimes(self, grpc_service, mock_context, grpc_app):
        from google.protobuf.empty_pb2 import Empty
        response = grpc_service.GetRuntimeList(Empty(), mock_context)
        assert len(response.runtimes) >= 1
