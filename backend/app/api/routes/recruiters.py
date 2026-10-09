from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any
from app.config.database import get_db
from app.models.entities import Recruiter
from app.schemas.schemas import RecruiterResponse, ResolveRecruiterEmailRequest
from app.services.recruiter_service import recruiter_service

router = APIRouter(prefix="/recruiters", tags=["Recruiters"])

@router.get("", response_model=List[RecruiterResponse])
async def list_recruiters(db: AsyncSession = Depends(get_db)):
    """List discovered talent acquisition contacts with verifiable evidence."""
    res = await db.execute(select(Recruiter).order_by(Recruiter.created_at.desc()))
    return res.scalars().all()

@router.post("/resolve-email")
async def resolve_recruiter_email_endpoint(
    req: ResolveRecruiterEmailRequest,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Submits, validates, and persists verified recruiter/company email from ChatGPT web research.
    Updates corresponding applications and outreach packages in database.
    """
    res = await recruiter_service.resolve_and_persist_recruiter_email(
        company_name=req.company_name,
        email=req.email,
        job_id=req.job_id,
        job_title=req.job_title,
        job_url=req.job_url,
        recruiter_name=req.recruiter_name,
        recruiter_title=req.recruiter_title,
        source_url=req.source_url,
        source_type=req.source_type,
        evidence=req.evidence,
        confidence=req.confidence
    )
    if res.get("status") == "REJECTED":
        raise HTTPException(status_code=400, detail=res)
    return res
