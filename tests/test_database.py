"""Tests for database models and relationships."""
import pytest
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import App, User, Category, Release, Screenshot, ScreenshotSize, Favorite, AppStats, Transaction, TransactionDetail, UserRole as DBUserRole


class TestAppModel:
    def test_create_app(self, db):
        app = App(
            id="org.test.App",
            name="Test",
            type="desktop-application",
            summary="Test app",
        )
        db.add(app)
        db.commit()

        fetched = db.query(App).filter(App.id == "org.test.App").first()
        assert fetched is not None
        assert fetched.name == "Test"
        assert fetched.is_free_license is True  # default

    def test_app_defaults(self, db):
        app = App(id="org.test.Defaults", name="Defaults", type="desktop")
        db.add(app)
        db.commit()
        db.refresh(app)
        assert app.is_free_license is True
        assert app.is_mobile_friendly is False
        assert app.verification_verified is False
        assert app.verification_method == "none"

    def test_app_with_categories(self, db):
        cat = Category(name="Game", description="Games")
        app = App(id="org.test.Game", name="Game", type="desktop-application")
        app.categories.append(cat)
        db.add(app)
        db.commit()

        fetched = db.query(App).filter(App.id == "org.test.Game").first()
        assert len(fetched.categories) == 1
        assert fetched.categories[0].name == "Game"


class TestUserModel:
    def test_create_user(self, db):
        user = User(
            display_name="Test User",
            invite_code="test123",
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.id is not None
        assert user.role == "user"

    def test_user_default_role(self, db):
        user = User(display_name="Default", invite_code="def123")
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.role == "user"


class TestReleaseModel:
    def test_create_release(self, db, sample_app):
        release = Release(
            app_id=sample_app.id,
            version="1.0.0",
            type="stable",
            description="Initial release",
        )
        db.add(release)
        db.commit()

        fetched = db.query(Release).filter(Release.app_id == sample_app.id).first()
        assert fetched is not None
        assert fetched.version == "1.0.0"


class TestFavoriteModel:
    def test_create_favorite(self, db, sample_user, sample_app):
        fav = Favorite(user_id=sample_user.id, app_id=sample_app.id)
        db.add(fav)
        db.commit()
        db.refresh(fav)
        assert fav.id is not None
        assert fav.user_id == sample_user.id
        assert fav.app_id == sample_app.id

    def test_favorite_relationships(self, db, sample_user, sample_app):
        fav = Favorite(user_id=sample_user.id, app_id=sample_app.id)
        db.add(fav)
        db.commit()

        user_favs = db.query(Favorite).filter(Favorite.user_id == sample_user.id).all()
        assert len(user_favs) == 1


class TestAppStatsModel:
    def test_create_stats(self, db, sample_app):
        stats = AppStats(
            app_id=sample_app.id,
            date=datetime.utcnow(),
            installs=100,
            updates=50,
            country="US",
        )
        db.add(stats)
        db.commit()

        fetched = db.query(AppStats).filter(AppStats.app_id == sample_app.id).first()
        assert fetched.installs == 100
        assert fetched.country == "US"


class TestTransactionModel:
    def test_create_transaction(self, db, sample_user):
        txn = Transaction(
            id="txn_123",
            user_id=sample_user.id,
            value=500,
            currency="USD",
            kind="donation",
            status="new",
        )
        db.add(txn)
        db.commit()

        fetched = db.query(Transaction).filter(Transaction.id == "txn_123").first()
        assert fetched.value == 500

    def test_transaction_with_details(self, db, sample_user):
        txn = Transaction(
            id="txn_456",
            user_id=sample_user.id,
            value=1000,
            currency="USD",
            kind="purchase",
            status="success",
        )
        detail = TransactionDetail(
            transaction_id="txn_456",
            recipient="org.example.App",
            amount=900,
            currency="USD",
            kind="payment",
        )
        db.add(txn)
        db.add(detail)
        db.commit()

        fetched = db.query(Transaction).filter(Transaction.id == "txn_456").first()
        assert len(fetched.details) == 1
        assert fetched.details[0].amount == 900


class TestScreenshotModel:
    def test_create_screenshot(self, db, sample_app):
        ss = Screenshot(
            app_id=sample_app.id,
            caption="Main window",
            default_screenshot=True,
        )
        db.add(ss)
        db.commit()
        db.refresh(ss)

        size = ScreenshotSize(
            screenshot_id=ss.id,
            width="1920",
            height="1080",
            scale="1x",
            src="https://example.com/ss.png",
        )
        db.add(size)
        db.commit()

        fetched = db.query(Screenshot).filter(Screenshot.app_id == sample_app.id).first()
        assert fetched.caption == "Main window"
        assert len(fetched.sizes) == 1


class TestDeveloperRelationship:
    def test_app_developers(self, db, sample_user, sample_app):
        sample_app.developers.append(sample_user)
        db.commit()

        fetched = db.query(App).filter(App.id == sample_app.id).first()
        assert len(fetched.developers) == 1
        assert fetched.developers[0].display_name == "Test User"

        user = db.query(User).filter(User.id == sample_user.id).first()
        assert len(user.developed_apps) == 1
