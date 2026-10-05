from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config.database import get_db
from app.models.entities import Application, Job, JobMatch, Recruiter, OutreachMessage, ApplicationStatus
from app.schemas.schemas import ApplicationResponse, JobResponse, MatchBreakdown, RecruiterResponse, OutreachMessageResponse

router = APIRouter(prefix="/applications", tags=["Applications"])

@router.get("", response_model=List[ApplicationResponse])
async def list_applications(db: AsyncSession = Depends(get_db)):
    """List all tracked job applications with candidate-job match, recruiter and status."""
    res = await db.execute(select(Application).order_by(Application.updated_at.desc()))
    applications = res.scalars().all()

    results = []
    for app in applications:
        job = await db.get(Job, app.job_id)
        if not job:
            continue

        # Match
        m_res = await db.execute(select(JobMatch).filter_by(job_id=job.id))
        match_obj = m_res.scalars().first()

        # Recruiter
        r_res = await db.execute(select(Recruiter).filter_by(company_name=job.company))
        rec_obj = r_res.scalars().first()

        # Outreaches
        o_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id))
        outreaches = o_res.scalars().all()

        results.append(ApplicationResponse(
            id=app.id,
            candidate_id=app.candidate_id,
            job_id=app.job_id,
            status=app.status.value,
            applied_at=app.applied_at,
            notes=app.notes,
            job=JobResponse(
                id=job.id,
                company=job.company,
                title=job.title,
                location=job.location,
                remote=job.remote,
                employment_type=job.employment_type,
                experience_required=job.experience_required,
                salary=job.salary,
                description=job.description,
                requirements=job.requirements or [],
                skills=job.skills or [],
                application_url=job.application_url,
                source_url=job.source_url,
                posted_date=job.posted_date,
                company_url=job.company_url,
                canonical_job_id=job.canonical_job_id,
                created_at=job.created_at
            ),
            match=MatchBreakdown(
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
            ) if match_obj else None,
            recruiter=RecruiterResponse(
                id=rec_obj.id,
                name=rec_obj.name,
                title=rec_obj.title,
                company_name=rec_obj.company_name,
                public_email=rec_obj.public_email,
                linkedin_url=rec_obj.linkedin_url,
                source_evidence=rec_obj.source_evidence,
                created_at=rec_obj.created_at
            ) if rec_obj else None,
            outreaches=[
                OutreachMessageResponse(
                    id=o.id,
                    application_id=o.application_id,
                    recruiter_id=o.recruiter_id,
                    channel=o.channel,
                    subject=o.subject,
                    body=o.body,
                    recipient_email=o.recipient_email,
                    recipient_name=o.recipient_name,
                    status=o.status,
                    sent_at=o.sent_at,
                    created_at=o.created_at
                )
                for o in outreaches
            ],
            created_at=app.created_at,
            updated_at=app.updated_at
        ))

    return results

@router.patch("/{application_id}/status")
async def update_application_status(
    application_id: str,
    status: str = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db)
):
    """Manually transition application status (e.g. APPLIED, INTERVIEW, REJECTED)."""
    app = await db.get(Application, application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        app.status = ApplicationStatus(status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if status.upper() == "APPLIED" and not app.applied_at:
        app.applied_at = datetime.utcnow()

    if notes:
        app.notes = notes

    await db.commit()
    await db.refresh(app)
    return {"id": app.id, "status": app.status.value, "updated_at": app.updated_at}
