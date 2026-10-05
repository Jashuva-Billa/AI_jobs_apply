from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.config.database import get_db
from app.models.entities import Recruiter
from app.schemas.schemas import RecruiterResponse

router = APIRouter(prefix="/recruiters", tags=["Recruiters"])

@router.get("", response_model=List[RecruiterResponse])
async def list_recruiters(db: AsyncSession = Depends(get_db)):
    """List discovered talent acquisition contacts with verifiable evidence."""
    res = await db.execute(select(Recruiter).order_by(Recruiter.created_at.desc()))
    return res.scalars().all()
