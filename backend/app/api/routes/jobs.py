from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from app.config.database import get_db
from app.models.entities import Job, JobMatch, Application, Recruiter
from app.schemas.schemas import JobWithMatchResponse, MatchBreakdown, JobResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=List[JobWithMatchResponse])
async def list_jobs(
    run_id: Optional[str] = Query(None, description="Filter by search run ID"),
    min_score: Optional[float] = Query(None, description="Filter by minimum match score"),
    remote_only: bool = Query(False, description="Filter remote only"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all discovered jobs along with candidate match score and application status."""
    query = select(Job).order_by(Job.created_at.desc())
    if run_id:
        query = query.filter(Job.run_id == run_id)
        
    res = await db.execute(query)
    jobs = res.scalars().all()

    results = []
    for j in jobs:
        # Get match
        m_res = await db.execute(select(JobMatch).filter_by(job_id=j.id))
        match_obj = m_res.scalars().first()
        
        # Get application
        a_res = await db.execute(select(Application).filter_by(job_id=j.id))
        app_obj = a_res.scalars().first()

        # Get recruiter
        r_res = await db.execute(select(Recruiter).filter_by(company_name=j.company))
        rec_obj = r_res.scalars().first()

        match_breakdown = None
        if match_obj:
            match_breakdown = MatchBreakdown(
                overall_score=match_obj.overall_score,
                skills_score=match_obj.skills_score,
                experience_score=match_obj.experience_score,
                location_score=match_obj.location_score,
                role_score=match_obj.role_score,
                matched_skills=match_obj.matched_skills or [],
                missing_skills=match_obj.missing_skills or [],
                concerns=match_obj.concerns or [],
                recommendation=match_obj.recommendation or "MATCH",
                reasoning=match_obj.reasoning
            )

        if min_score is not None and match_breakdown and match_breakdown.overall_score < min_score:
            continue
        if remote_only and not j.remote:
            continue

        results.append(JobWithMatchResponse(
            id=j.id,
            canonical_job_id=j.canonical_job_id,
            company=j.company,
            title=j.title,
            location=j.location,
            remote=j.remote,
            employment_type=j.employment_type,
            experience_required=j.experience_required,
            salary=j.salary,
            description=j.description,
            requirements=j.requirements or [],
            application_url=j.application_url,
            source_url=j.source_url,
            source_urls=j.source_urls or [],
            posted_date=j.posted_date,
            company_url=j.company_url,
            verification_status=j.verification_status or "VERIFIED",
            evidence=j.evidence or [],
            research_provider=j.research_provider or "openai_web_search",
            created_at=j.created_at,
            match=match_breakdown,
            recruiter={
                "name": rec_obj.name,
                "title": rec_obj.title,
                "public_email": rec_obj.public_email,
                "linkedin_url": rec_obj.linkedin_url
            } if rec_obj else None,
            application_id=app_obj.id if app_obj else None,
            status=app_obj.status.value if (app_obj and hasattr(app_obj.status, "value")) else (str(app_obj.status) if app_obj else None)
        ))

    # Sort descending by match score if available
    results.sort(key=lambda x: x.match.overall_score if x.match else 0, reverse=True)
    return results

@router.get("/{job_id}", response_model=JobWithMatchResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get single job details with match breakdown."""
    j = await db.get(Job, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")

    m_res = await db.execute(select(JobMatch).filter_by(job_id=j.id))
    match_obj = m_res.scalars().first()

    match_breakdown = None
    if match_obj:
        match_breakdown = MatchBreakdown(
            overall_score=match_obj.overall_score,
            skills_score=match_obj.skills_score,
            experience_score=match_obj.experience_score,
            location_score=match_obj.location_score,
            role_score=match_obj.role_score,
            matched_skills=match_obj.matched_skills or [],
            missing_skills=match_obj.missing_skills or [],
            concerns=match_obj.concerns or [],
            recommendation=match_obj.recommendation or "MATCH",
            reasoning=match_obj.reasoning
        )

    return JobWithMatchResponse(
        id=j.id,
        canonical_job_id=j.canonical_job_id,
        company=j.company,
        title=j.title,
        location=j.location,
        remote=j.remote,
        employment_type=j.employment_type,
        experience_required=j.experience_required,
        salary=j.salary,
        description=j.description,
        requirements=j.requirements or [],
        skills=j.skills or [],
        application_url=j.application_url,
        source_url=j.source_url,
        source_urls=j.source_urls or [],
        posted_date=j.posted_date,
        company_url=j.company_url,
        verification_status=j.verification_status or "VERIFIED",
        evidence=j.evidence or [],
        research_provider=j.research_provider or "openai_web_search",
        created_at=j.created_at,
        match=match_breakdown
    )
