import os
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, Table, BigInteger, Index, UniqueConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

_connect_args = {}
_engine_kwargs = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
else:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

engine = create_engine(DATABASE_URL, connect_args=_connect_args, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Association tables
app_developers = Table(
    'app_developers',
    Base.metadata,
    Column('app_id', String, ForeignKey('apps.id')),
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('is_primary', Boolean, default=False)
)

app_categories = Table(
    'app_categories',
    Base.metadata,
    Column('app_id', String, ForeignKey('apps.id')),
    Column('category', String, ForeignKey('categories.name'))
)

class App(Base):
    __tablename__ = "apps"
    
    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)
    summary = Column(Text)
    description = Column(Text)
    type = Column(String(50), nullable=False)
    project_license = Column(String(255))
    is_free_license = Column(Boolean, default=True)
    developer_name = Column(String(255))
    icon = Column(String(500))
    runtime = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow)
    added_at = Column(DateTime, default=datetime.utcnow)
    is_mobile_friendly = Column(Boolean, default=False)
    published = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    gpg_fingerprint = Column(String(255), nullable=True)
    gpg_public_key = Column(Text, nullable=True)
    gpg_uid = Column(String(255), nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reminder_30_sent = Column(Boolean, default=False)
    reminder_7_sent = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    scan_result = Column(JSON, nullable=True)        # latest scanner output
    scan_verdict = Column(String(16), nullable=True) # PASS / WARN / BLOCK / PENDING
    scan_at = Column(DateTime, nullable=True)
    scan_blocked = Column(Boolean, default=False)  # True if scanner vetoed
    verification_verified = Column(Boolean, default=False)
    verification_method = Column(String(50), default="none")
    verification_login_name = Column(String(255))
    verification_login_provider = Column(String(50))
    verification_login_is_organization = Column(Boolean, default=False)
    verification_website = Column(String(500))
    verification_timestamp = Column(DateTime)
    extends = Column(String(255))  # For addon/extension apps

    # Relationships
    developers = relationship("User", secondary=app_developers, back_populates="developed_apps")
    categories = relationship("Category", secondary=app_categories, back_populates="apps")
    releases = relationship("Release", back_populates="app")
    screenshots = relationship("Screenshot", back_populates="app")
    stats = relationship("AppStats", back_populates="app")
    favorites = relationship("Favorite", back_populates="app")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    display_name = Column(String(255))
    invite_code = Column(String(100), unique=True)
    accepted_publisher_agreement_at = Column(DateTime)
    default_account_provider = Column(String(50))
    default_account_login = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # RBAC role: admin, reviewer, publisher, user
    role = Column(String(20), default="user", nullable=False)
    is_trusted_publisher = Column(Boolean, default=False)
    trusted_at = Column(DateTime, nullable=True)
    trusted_by = Column(Integer, nullable=True)
    
    # Relationships
    developed_apps = relationship("App", secondary=app_developers, back_populates="developers")
    connected_accounts = relationship("ConnectedAccount", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    roles = relationship("UserRole", back_populates="user")

    # Email auth columns (migration 005_email_auth)
    email = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    email_verification_token = Column(String(128), nullable=True)
    email_verification_expires = Column(DateTime, nullable=True)
    password_reset_token = Column(String(128), nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    is_organization_email = Column(Boolean, default=False, nullable=False)
    organization_domain = Column(String(255), nullable=True)
    auth_provider = Column(String(20), default="github", nullable=False)

class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
        Index("ix_connected_accounts_user_id", "user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_user_id = Column(BigInteger, nullable=False)
    login = Column(String(255))
    avatar_url = Column(String(500))
    display_name = Column(String(255))
    email = Column(String(255))
    last_used = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="connected_accounts")

class Category(Base):
    __tablename__ = "categories"
    
    name = Column(String(100), primary_key=True)
    description = Column(Text)
    
    # Relationships
    apps = relationship("App", secondary=app_categories, back_populates="categories")

class Release(Base):
    __tablename__ = "releases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(255), ForeignKey('apps.id'))
    version = Column(String(100))
    timestamp = Column(DateTime)
    date = Column(DateTime)
    type = Column(String(50))
    urgency = Column(String(50))
    description = Column(Text)
    url = Column(String(500))
    date_eol = Column(DateTime)
    
    # Relationships
    app = relationship("App", back_populates="releases")

class Screenshot(Base):
    __tablename__ = "screenshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(255), ForeignKey('apps.id'))
    caption = Column(Text)
    default_screenshot = Column(Boolean, default=False)
    
    # Relationships
    app = relationship("App", back_populates="screenshots")
    sizes = relationship("ScreenshotSize", back_populates="screenshot")

class ScreenshotSize(Base):
    __tablename__ = "screenshot_sizes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    screenshot_id = Column(Integer, ForeignKey('screenshots.id'))
    width = Column(String(10))
    height = Column(String(10))
    scale = Column(String(10), default="1x")
    src = Column(String(500))
    
    # Relationships
    screenshot = relationship("Screenshot", back_populates="sizes")

class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "app_id", name="uq_user_app_favorite"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    app_id = Column(String(255), ForeignKey('apps.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="favorites")
    app = relationship("App", back_populates="favorites")

class AppStats(Base):
    __tablename__ = "app_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(String(255), ForeignKey('apps.id'))
    date = Column(DateTime)
    installs = Column(Integer, default=0)
    updates = Column(Integer, default=0)
    country = Column(String(2))
    
    # Relationships
    app = relationship("App", back_populates="stats")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String(100), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    value = Column(Integer)
    currency = Column(String(3))
    kind = Column(String(20))  # donation, purchase
    status = Column(String(20))  # new, retry, pending, success, cancelled
    reason = Column(Text)
    created = Column(DateTime, default=datetime.utcnow)
    updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    details = relationship("TransactionDetail", back_populates="transaction")

class TransactionDetail(Base):
    __tablename__ = "transaction_details"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(100), ForeignKey('transactions.id'))
    recipient = Column(String(255))
    amount = Column(Integer)
    currency = Column(String(3))
    kind = Column(String(20))
    
    # Relationships
    transaction = relationship("Transaction", back_populates="details")

class UserRole(Base):
    __tablename__ = "user_roles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    role_name = Column(String(50))
    
    # Relationships
    user = relationship("User", back_populates="roles")

class DeveloperToken(Base):
    """Personal API tokens for developers (used for app submission via CLI/CI)."""
    __tablename__ = "developer_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)  # SHA-256 hex
    token_prefix = Column(String(16), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)

    user = relationship("User", foreign_keys=[user_id])


class AppSubmission(Base):
    """App metadata submission awaiting admin review."""
    __tablename__ = "app_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    app_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    summary = Column(Text)
    description = Column(Text)
    icon = Column(String(500))
    homepage = Column(String(500))
    license = Column(String(255))
    app_type = Column(String(50), default="desktop-application")
    categories = Column(JSON)
    tags = Column(JSON)
    screenshots = Column(JSON)
    status = Column(String(20), default="pending")  # pending | approved | rejected
    rejection_reason = Column(Text)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)
    reviewer_id = Column(Integer, ForeignKey('users.id'))

    submitter = relationship("User", foreign_keys=[user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class DeveloperGpgKey(Base):
    __tablename__ = "developer_gpg_keys"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    fingerprint = Column(String(64), nullable=True)
    public_key = Column(Text, nullable=True)
    uid = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    user = relationship("User", foreign_keys=[user_id])

