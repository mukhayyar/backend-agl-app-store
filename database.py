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
    
    # Relationships
    developed_apps = relationship("App", secondary=app_developers, back_populates="developers")
    connected_accounts = relationship("ConnectedAccount", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    roles = relationship("UserRole", back_populates="user")

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