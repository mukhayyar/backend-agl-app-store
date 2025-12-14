"""
Pytest fixtures for the App Store backend test suite.

Provides:
- SQLite in-memory test database (overrides PostgreSQL)
- FastAPI TestClient with dependency overrides
- Sample data fixtures (user, admin, category, app)
- JWT auth token fixtures for each role
"""
import pytest
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override env vars BEFORE importing modules so they don't try to
# connect to PostgreSQL or fail on missing secrets.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-production")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database import Base, App, User, Category, Favorite, AppStats, Release
from app.core.auth_middleware import create_access_token
from app.core.roles import UserRole

# Test database - SQLite file-based (avoids threading issues with TestClient)
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test.

    Creates all tables before the test and drops them after,
    ensuring full isolation between tests.
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db):
    """FastAPI TestClient with the database dependency overridden
    to use the test SQLite session."""
    from app.http.http_server import create_app
    from app.http.routes import apps as apps_routes
    from app.http.routes import auth as auth_routes
    from app.http.routes import stats as stats_routes
    from app.http.routes import favorites as favorites_routes

    app = create_app()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    # Override get_db in every route module that defines one
    app.dependency_overrides[apps_routes.get_db] = override_get_db
    app.dependency_overrides[auth_routes.get_db] = override_get_db
    app.dependency_overrides[stats_routes.get_db] = override_get_db
    app.dependency_overrides[favorites_routes.get_db] = override_get_db

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_user(db):
    """A regular user with the USER role."""
    user = User(
        display_name="Test User",
        invite_code="test-invite-123",
        default_account_provider="github",
        default_account_login="testuser",
        role="user",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_user(db):
    """A user with the ADMIN role."""
    user = User(
        display_name="Admin User",
        invite_code="admin-invite-123",
        default_account_provider="github",
        default_account_login="adminuser",
        role="admin",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_category(db):
    """A single 'Utility' category."""
    cat = Category(name="Utility", description="Utility apps")
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@pytest.fixture
def sample_app(db, sample_category):
    """A desktop application linked to the sample category."""
    app = App(
        id="org.example.TestApp",
        name="Test App",
        summary="A test application",
        description="This is a test application for testing purposes",
        type="desktop-application",
        project_license="MIT",
        is_free_license=True,
        developer_name="Test Developer",
        icon="https://example.com/icon.png",
        runtime="org.freedesktop.Platform/x86_64/23.08",
        is_mobile_friendly=False,
        verification_verified=False,
        verification_method="none",
        added_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    app.categories.append(sample_category)
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


# ---------------------------------------------------------------------------
# Auth token fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_token(sample_user):
    """JWT access token for a regular user."""
    return create_access_token(user_id=sample_user.id, role=UserRole.USER)


@pytest.fixture
def admin_token(admin_user):
    """JWT access token for an admin user."""
    return create_access_token(user_id=admin_user.id, role=UserRole.ADMIN)


@pytest.fixture
def publisher_token(db):
    """JWT access token for a publisher user."""
    user = User(
        display_name="Publisher User",
        invite_code="pub-invite-123",
        default_account_provider="github",
        default_account_login="publisher",
        role="publisher",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_access_token(user_id=user.id, role=UserRole.PUBLISHER)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def auth_header(token: str) -> dict:
    """Return an Authorization header dict for the given bearer token."""
    return {"Authorization": f"Bearer {token}"}
