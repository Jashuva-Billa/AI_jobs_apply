import sys
import os
import uuid
import asyncio
import logging
from typing import Optional, List, Dict, Any

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.models.entities import (
    Job, Application, ApplicationQuestion,
    ApprovalRequest, OutreachMessage, CandidateProfile, AgentRun, Recruiter,
    ApplicationStatus, ApprovalStatus
)
from app.schemas.schemas import CandidateProfileBase, CandidateProfileResponse
from app.services.application_service import application_service
from app.services.outreach_service import outreach_service
from app.services.recruiter_service import recruiter_service

logger = logging.getLogger(__name__)

async def _prepare_single_application_task(
    cand_schema: CandidateProfileBase,
    job_entity: Job,
    run_id: Optional[str],
    semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """Prepares a single application package under bounded concurrency."""
    async with semaphore:
        async with AsyncSessionLocal() as session:
            try:
                job_dict = {c.name: getattr(job_entity, c.name) for c in job_entity.__table__.columns}
                
                # 1. Discover recruiter if not existing
                r_res = await session.execute(select(Recruiter).filter_by(company_name=job_entity.company).limit(1))
                rec_entity = r_res.scalars().first()
                if not rec_entity:
                    rec_base = await recruiter_service.discover_recruiter_for_job(job_entity.company, job_entity.title)
                    if rec_base:
                        rec_entity = Recruiter(
                            id=str(uuid.uuid4()),
                            name=rec_base.name,
                            title=rec_base.title,
                            company_name=job_entity.company,
                            public_email=rec_base.public_email,
                            linkedin_url=rec_base.linkedin_url,
                            source_evidence=rec_base.source_evidence
                        )
                        session.add(rec_entity)
                        await session.flush()

                rec_obj = rec_entity

                # 2. Generate factual application package artifacts
                app_pkg_dto = await application_service.prepare_full_package(cand_schema, job_dict, rec_obj)
                
                # 3. Check existing Application or create new
                app_res = await session.execute(select(Application).filter_by(candidate_id=cand_schema.id, job_id=job_entity.id))
                app_rec = app_res.scalars().first()
                if not app_rec:
                    app_id = str(uuid.uuid4())
                    app_rec = Application(
                        id=app_id,
                        run_id=run_id,
                        candidate_id=cand_schema.id,
                        job_id=job_entity.id,
                        status=ApplicationStatus.REVIEW_REQUIRED
                    )
                    session.add(app_rec)
                else:
                    app_id = app_rec.id
                    app_rec.run_id = run_id
                    app_rec.status = ApplicationStatus.REVIEW_REQUIRED

                # 4. Generate Outreach Messages (Email & LinkedIn)
                email_out = await outreach_service.generate_recruiter_email(cand_schema, job_dict, rec_obj)
                li_out = await outreach_service.generate_linkedin_outreach(cand_schema, job_dict, rec_obj)

                # Save Outreach
                o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app_id, channel="EMAIL"))
                if not o_res.scalars().first():
                    session.add(OutreachMessage(
                        id=str(uuid.uuid4()),
                        application_id=app_id,
                        channel="EMAIL",
                        subject=email_out.subject,
                        body=email_out.body,
                        recipient_email=email_out.recipient_email or (rec_obj.public_email if rec_obj else None),
                        recipient_name=rec_obj.name if rec_obj else "Hiring Team",
                        status="DRAFT"
                    ))

                o_li_res = await session.execute(select(OutreachMessage).filter_by(application_id=app_id, channel="LINKEDIN"))
                if not o_li_res.scalars().first():
                    session.add(OutreachMessage(
                        id=str(uuid.uuid4()),
                        application_id=app_id,
                        channel="LINKEDIN",
                        subject=li_out.subject,
                        body=li_out.body,
                        recipient_name=rec_obj.name if rec_obj else "Hiring Team",
                        status="DRAFT"
                    ))

                # 6. Create ApprovalRequest record in SQL
                req_res = await session.execute(select(ApprovalRequest).filter_by(application_id=app_id))
                approval_req = req_res.scalars().first()
                if not approval_req:
                    approval_id = str(uuid.uuid4())
                    approval_req = ApprovalRequest(
                        id=approval_id,
                        run_id=run_id,
                        application_id=app_id,
                        status=ApprovalStatus.PENDING,
                        package_data={
                            "company": job_entity.company,
                            "title": job_entity.title,
                            "tailored_resume_summary": app_pkg_dto.tailored_resume_summary,
                            "cover_letter": app_pkg_dto.cover_letter,
                            "email_outreach": {
                                "subject": email_out.subject,
                                "body": email_out.body,
                                "recipient_email": email_out.recipient_email or (rec_obj.public_email if rec_obj else None)
                            },
                            "linkedin_outreach": {
                                "body": li_out.body
                            }
                        }
                    )
                    session.add(approval_req)
                else:
                    approval_id = approval_req.id

                await session.commit()

                return {
                    "status": "PREPARED",
                    "job_id": job_entity.id,
                    "company": job_entity.company,
                    "title": job_entity.title,
                    "application_id": app_id,
                    "approval_id": approval_id,
                    "email_recipient": email_out.recipient_email or (rec_obj.public_email if rec_obj else None),
                    "recruiter_name": rec_obj.name if rec_obj else "Talent Team"
                }
            except Exception as e:
                logger.error(f"Failed preparing application for {job_entity.company}: {e}")
                return {"status": "FAILED", "job_id": job_entity.id, "error": str(e)}

async def prepare_application(
    candidate_id: Optional[str] = None,
    job_id: str = "",
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Prepares a single complete factual application package (tailored resume, cover letter,
    application answers, email outreach, and LinkedIn outreach) and inserts an ApprovalRequest.
    """
    async with AsyncSessionLocal() as session:
        if candidate_id:
            cand = await session.get(CandidateProfile, candidate_id)
        else:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand = res.scalars().first()

        if not cand:
            return {"error": "Candidate profile not found"}

        job = await session.get(Job, job_id)
        if not job:
            return {"error": "Job not found", "job_id": job_id}

        cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns}
        cand_schema = CandidateProfileResponse.model_validate(cand_dict)
        sem = asyncio.Semaphore(1)
        result = await _prepare_single_application_task(cand_schema, job, run_id, sem)
        return result

async def prepare_applications_batch(
    run_id: str,
    job_ids: Optional[List[str]] = None,
    max_concurrency: int = 10
) -> Dict[str, Any]:
    """
    Prepares application packages in parallel for all qualified jobs under bounded concurrency.
    Inserts ApprovalRequest records with PENDING status in SQL and updates SearchRun status.
    """
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        if not cand:
            return {"error": "Candidate profile not found"}

        cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns}
        cand_schema = CandidateProfileResponse.model_validate(cand_dict)

        # Select target jobs
        if job_ids:
            j_res = await session.execute(select(Job).where(Job.id.in_(job_ids)))
            jobs = j_res.scalars().all()
        else:
            j_res = await session.execute(select(Job).filter_by(run_id=run_id))
            jobs = j_res.scalars().all()

        if not jobs:
            return {"error": "No jobs found for batch application preparation", "run_id": run_id}

        sem = asyncio.Semaphore(max_concurrency or settings.MAX_CONCURRENT_APPLICATIONS)
        tasks = [_prepare_single_application_task(cand_schema, job, run_id, sem) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        prepared_count = sum(1 for r in results if r.get("status") == "PREPARED")
        failed_count = sum(1 for r in results if r.get("status") == "FAILED")

        # Update SearchRun record
        run_obj = await session.get(AgentRun, run_id)
        if run_obj:
            run_obj.applications_prepared = (run_obj.applications_prepared or 0) + prepared_count
            run_obj.approvals_pending = (run_obj.approvals_pending or 0) + prepared_count
            run_obj.status = "WAITING_FOR_APPROVAL"
            run_obj.current_step = "await_approval"
            await session.commit()

        return {
            "run_id": run_id,
            "status": "WAITING_FOR_APPROVAL",
            "total_jobs": len(jobs),
            "prepared": prepared_count,
            "failed": failed_count,
            "approvals_pending": prepared_count,
            "results": results
        }
