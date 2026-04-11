"""
Favorites routes for AGL store.
Manages user favorite apps.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc

from app.core.auth_middleware import TokenClaims, require_auth
from database import SessionLocal, Favorite, App

router = APIRouter(prefix="/favorites", tags=["favorites"])


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Response models
class FavoriteResponse(BaseModel):
    app_id: str
    created_at: str

    class Config:
        from_attributes = True


class FavoriteListResponse(BaseModel):
    favorites: List[FavoriteResponse]
    total: int


@router.post("/{app_id}", status_code=201)
async def add_favorite(
    app_id: str,
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Add an app to the user's favorites."""
    # Verify the app exists
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    favorite = Favorite(user_id=claims.user_id, app_id=app_id)
    db.add(favorite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="App is already in favorites")
    db.refresh(favorite)

    return {
        "app_id": favorite.app_id,
        "created_at": str(favorite.created_at),
    }


@router.delete("/{app_id}", status_code=200)
async def remove_favorite(
    app_id: str,
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Remove an app from the user's favorites."""
    favorite = (
        db.query(Favorite)
        .filter(Favorite.user_id == claims.user_id, Favorite.app_id == app_id)
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(favorite)
    db.commit()

    return {"detail": "Favorite removed"}


@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """List all favorites for the authenticated user."""
    favorites = (
        db.query(Favorite)
        .filter(Favorite.user_id == claims.user_id)
        .order_by(desc(Favorite.created_at))
        .all()
    )

    return {
        "favorites": [
            {
                "app_id": fav.app_id,
                "created_at": str(fav.created_at),
            }
            for fav in favorites
        ],
        "total": len(favorites),
    }


@router.get("/{app_id}/check")
async def check_favorite(
    app_id: str,
    claims: TokenClaims = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Check if an app is in the user's favorites."""
    favorite = (
        db.query(Favorite)
        .filter(Favorite.user_id == claims.user_id, Favorite.app_id == app_id)
        .first()
    )

    return {"is_favorited": favorite is not None}
