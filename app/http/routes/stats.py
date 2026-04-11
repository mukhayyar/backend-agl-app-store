"""
Statistics routes.
Provides app download stats and analytics.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.auth_middleware import TokenClaims, get_current_user
from database import SessionLocal, App, AppStats

router = APIRouter(prefix="/stats", tags=["stats"])


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
async def get_overall_stats(db: Session = Depends(get_db)):
    """Get overall store statistics."""
    total_apps = db.query(App).count()
    total_downloads = db.query(func.sum(AppStats.installs)).scalar() or 0
    total_updates = db.query(func.sum(AppStats.updates)).scalar() or 0
    
    # Get category counts
    category_totals = (
        db.query(App.type, func.count(App.id))
        .group_by(App.type)
        .all()
    )
    
    # Downloads by country
    country_stats = (
        db.query(AppStats.country, func.sum(AppStats.installs))
        .group_by(AppStats.country)
        .all()
    )

    # Downloads per day (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_stats = (
        db.query(func.date(AppStats.date), func.sum(AppStats.installs))
        .filter(AppStats.date >= thirty_days_ago)
        .group_by(func.date(AppStats.date))
        .order_by(func.date(AppStats.date))
        .all()
    )

    return {
        "totals": {
            "apps": total_apps,
            "downloads": total_downloads,
            "updates": total_updates,
        },
        "category_totals": [
            {"category": cat, "count": count}
            for cat, count in category_totals
        ],
        "countries": {
            country: count for country, count in country_stats if country
        },
        "downloads_per_day": {
            str(day): count for day, count in daily_stats if day
        },
    }


@router.get("/{app_id}")
async def get_app_stats(app_id: str, db: Session = Depends(get_db)):
    """Get statistics for a specific app."""
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # Get total installs
    total_installs = (
        db.query(func.sum(AppStats.installs))
        .filter(AppStats.app_id == app_id)
        .scalar() or 0
    )
    
    # Get installs by country
    installs_by_country = (
        db.query(AppStats.country, func.sum(AppStats.installs))
        .filter(AppStats.app_id == app_id)
        .group_by(AppStats.country)
        .all()
    )
    
    # Installs per day (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    daily_installs = (
        db.query(func.date(AppStats.date), func.sum(AppStats.installs))
        .filter(AppStats.app_id == app_id, AppStats.date >= thirty_days_ago)
        .group_by(func.date(AppStats.date))
        .order_by(func.date(AppStats.date))
        .all()
    )

    installs_last_month = (
        db.query(func.sum(AppStats.installs))
        .filter(AppStats.app_id == app_id, AppStats.date >= thirty_days_ago)
        .scalar() or 0
    )

    installs_last_7_days = (
        db.query(func.sum(AppStats.installs))
        .filter(AppStats.app_id == app_id, AppStats.date >= seven_days_ago)
        .scalar() or 0
    )

    return {
        "id": app_id,
        "installs_total": total_installs,
        "installs_per_country": {
            country: count for country, count in installs_by_country if country
        },
        "installs_per_day": {
            str(day): count for day, count in daily_installs if day
        },
        "installs_last_month": installs_last_month,
        "installs_last_7_days": installs_last_7_days,
    }
