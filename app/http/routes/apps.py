"""
App store app routes.
Provides endpoints for browsing, searching, and getting app details.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, func

from app.core.auth_middleware import TokenClaims, get_current_user
from database import SessionLocal, App, Category, AppStats

router = APIRouter(prefix="/apps", tags=["apps"])


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Response Models ====================

class AppSummary(BaseModel):
    id: str
    name: str
    summary: Optional[str] = None
    icon: Optional[str] = None
    type: str
    developer_name: Optional[str] = None
    is_free_license: bool = True
    is_mobile_friendly: bool = False
    verification_verified: bool = False

    class Config:
        from_attributes = True


class AppDetail(BaseModel):
    id: str
    name: str
    summary: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    type: str
    project_license: Optional[str] = None
    developer_name: Optional[str] = None
    runtime: Optional[str] = None
    is_free_license: bool = True
    is_mobile_friendly: bool = False
    verification_verified: bool = False
    verification_method: Optional[str] = None
    categories: List[str] = []

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    hits: List[AppSummary]
    query: str
    total_hits: int
    page: int
    hits_per_page: int
    total_pages: int


class CategoryResponse(BaseModel):
    name: str
    app_count: int


# ==================== Endpoints ====================

@router.get("", response_model=List[AppSummary])
async def list_apps(
    filter_type: Optional[str] = Query(None, alias="filter"),
    sort: str = Query("alphabetical"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List apps with optional filtering and sorting."""
    query = db.query(App)

    # Apply filter
    if filter_type:
        query = query.filter(App.type == filter_type)

    # Apply sorting
    if sort == "alphabetical":
        query = query.order_by(App.name)
    elif sort == "created-at":
        query = query.order_by(desc(App.added_at))
    elif sort == "last-updated-at":
        query = query.order_by(desc(App.updated_at))

    apps = query.offset(offset).limit(limit).all()

    return [AppSummary.model_validate(app) for app in apps]


@router.get("/search", response_model=SearchResponse)
async def search_apps(
    q: str = Query("", alias="query"),
    page: int = Query(1, ge=1),
    per_page: int = Query(21, le=100, alias="hits_per_page"),
    category: Optional[str] = None,
    runtime: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Search apps by name, summary, or description."""
    query = db.query(App)

    # Text search
    if q:
        search_term = f"%{q.lower()}%"
        query = query.filter(
            or_(
                App.name.ilike(search_term),
                App.summary.ilike(search_term),
                App.description.ilike(search_term),
                App.id.ilike(search_term)
            )
        )

    # Category filter
    if category:
        query = query.join(App.categories).filter(Category.name == category)

    # Runtime filter
    if runtime:
        query = query.filter(App.runtime == runtime)

    # Get total count
    total_hits = query.count()
    total_pages = (total_hits + per_page - 1) // per_page

    # Paginate
    offset = (page - 1) * per_page
    apps = query.offset(offset).limit(per_page).all()

    return SearchResponse(
        hits=[AppSummary.model_validate(app) for app in apps],
        query=q,
        total_hits=total_hits,
        page=page,
        hits_per_page=per_page,
        total_pages=total_pages
    )


# ==================== Categories ====================
# These static routes must be defined BEFORE /{app_id} to avoid conflicts

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(db: Session = Depends(get_db)):
    """Get all categories with app counts."""
    categories = (
        db.query(Category.name, func.count(App.id).label("count"))
        .join(Category.apps)
        .group_by(Category.name)
        .all()
    )

    return [
        CategoryResponse(name=cat.name, app_count=cat.count)
        for cat in categories
    ]


@router.get("/categories/{category}")
async def get_category_apps(
    category: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(21, le=100),
    db: Session = Depends(get_db)
):
    """Get apps in a category."""
    query = db.query(App).join(App.categories).filter(Category.name == category)

    total_hits = query.count()
    total_pages = (total_hits + per_page - 1) // per_page

    offset = (page - 1) * per_page
    apps = query.offset(offset).limit(per_page).all()

    return SearchResponse(
        hits=[AppSummary.model_validate(app) for app in apps],
        query="",
        total_hits=total_hits,
        page=page,
        hits_per_page=per_page,
        total_pages=total_pages
    )


# ==================== Collections ====================
# These static routes must be defined BEFORE /{app_id} to avoid conflicts

@router.get("/recently-updated")
async def get_recently_updated(
    page: int = Query(1, ge=1),
    per_page: int = Query(21, le=100),
    db: Session = Depends(get_db)
):
    """Get recently updated apps."""
    query = db.query(App).order_by(desc(App.updated_at))

    total_hits = query.count()
    total_pages = (total_hits + per_page - 1) // per_page

    offset = (page - 1) * per_page
    apps = query.offset(offset).limit(per_page).all()

    return SearchResponse(
        hits=[AppSummary.model_validate(app) for app in apps],
        query="",
        total_hits=total_hits,
        page=page,
        hits_per_page=per_page,
        total_pages=total_pages
    )


@router.get("/recently-added")
async def get_recently_added(
    page: int = Query(1, ge=1),
    per_page: int = Query(21, le=100),
    db: Session = Depends(get_db)
):
    """Get recently added apps."""
    query = db.query(App).order_by(desc(App.added_at))

    total_hits = query.count()
    total_pages = (total_hits + per_page - 1) // per_page

    offset = (page - 1) * per_page
    apps = query.offset(offset).limit(per_page).all()

    return SearchResponse(
        hits=[AppSummary.model_validate(app) for app in apps],
        query="",
        total_hits=total_hits,
        page=page,
        hits_per_page=per_page,
        total_pages=total_pages
    )


@router.get("/verified")
async def get_verified_apps(
    page: int = Query(1, ge=1),
    per_page: int = Query(21, le=100),
    db: Session = Depends(get_db)
):
    """Get verified apps."""
    query = db.query(App).filter(App.verification_verified == True).order_by(App.name)

    total_hits = query.count()
    total_pages = (total_hits + per_page - 1) // per_page

    offset = (page - 1) * per_page
    apps = query.offset(offset).limit(per_page).all()

    return SearchResponse(
        hits=[AppSummary.model_validate(app) for app in apps],
        query="",
        total_hits=total_hits,
        page=page,
        hits_per_page=per_page,
        total_pages=total_pages
    )


# ==================== App Detail Routes ====================
# Dynamic routes defined AFTER static ones to prevent conflicts

@router.get("/{app_id}", response_model=AppDetail)
async def get_app(app_id: str, db: Session = Depends(get_db)):
    """Get app details by ID."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    data = {
        "id": app.id,
        "name": app.name,
        "summary": app.summary,
        "description": app.description,
        "icon": app.icon,
        "type": app.type,
        "project_license": app.project_license,
        "developer_name": app.developer_name,
        "runtime": app.runtime,
        "is_free_license": app.is_free_license,
        "is_mobile_friendly": app.is_mobile_friendly,
        "verification_verified": app.verification_verified,
        "verification_method": app.verification_method,
        "categories": [cat.name for cat in app.categories],
    }
    return AppDetail(**data)


@router.get("/{app_id}/summary")
async def get_app_summary(
    app_id: str,
    branch: Optional[str] = "stable",
    db: Session = Depends(get_db)
):
    """Get app summary information for installation."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    return {
        "arches": ["x86_64"],
        "branch": branch,
        "timestamp": int(app.updated_at.timestamp()) if app.updated_at else 0,
        "download_size": 0,
        "installed_size": 0,
        "metadata": {
            "name": app.name,
            "runtime": app.runtime or "",
            "sdk": "",
        }
    }


@router.get("/{app_id}/addons")
async def get_app_addons(app_id: str, db: Session = Depends(get_db)):
    """Get addons for an app."""
    addons = db.query(App.id).filter(
        App.type == "addon",
        App.extends == app_id
    ).all()

    return {"addons": [addon.id for addon in addons]}
