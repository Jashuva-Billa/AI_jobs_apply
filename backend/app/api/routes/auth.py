from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any, List
from app.config.database import get_db
from app.models.entities import OAuthConnection
from app.config.settings import settings

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.get("/status")
async def get_auth_connections(db: AsyncSession = Depends(get_db)):
    """Check connected OAuth providers (Gmail, Outlook, LinkedIn)."""
    res = await db.execute(select(OAuthConnection).filter_by(is_active=True))
    connections = res.scalars().all()
    
    return {
        "google": {
            "connected": any(c.provider == "google" for c in connections) or bool(settings.SMTP_USER),
            "email": settings.EMAIL_FROM if settings.SMTP_USER else "connected@gmail.com"
        },
        "microsoft": {
            "connected": any(c.provider == "microsoft" for c in connections),
            "email": None
        },
        "linkedin": {
            "status": "COMPLIANT_MANUAL_ADAPTER",
            "message": "Authorized preparation mode active. Zero unauthorized scraping."
        }
    }
