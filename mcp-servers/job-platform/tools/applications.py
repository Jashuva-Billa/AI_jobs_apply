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

                # Save Outreach Messages
                o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app_id, channel="EMAIL"))
                existing_email = o_res.scalars().first()
                if not existing_email:
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
                else:
                    existing_email.subject = email_out.subject
                    existing_email.body = email_out.body

                o_li_res = await session.execute(select(OutreachMessage).filter_by(application_id=app_id, channel="LINKEDIN"))
                existing_li = o_li_res.scalars().first()
                if not existing_li:
                    session.add(OutreachMessage(
                        id=str(uuid.uuid4()),
                        application_id=app_id,
                        channel="LINKEDIN",
                        subject=li_out.subject,
                        body=li_out.body,
                        recipient_name=rec_obj.name if rec_obj else "Hiring Team",
                        status="DRAFT"
                    ))
                else:
                    existing_li.subject = li_out.subject
                    existing_li.body = li_out.body

                # 5. Save Application Questions
                if app_pkg_dto.questions:
                    for q in app_pkg_dto.questions:
                        q_res = await session.execute(
                            select(ApplicationQuestion).filter_by(application_id=app_id, question=q.question)
                        )
                        if not q_res.scalars().first():
                            session.add(ApplicationQuestion(
                                id=str(uuid.uuid4()),
                                application_id=app_id,
                                question=q.question,
                                answer=q.answer,
                                is_sensitive=q.is_sensitive,
                                needs_user_input=q.needs_user_input,
                                status=q.status
                            ))

                # 6. Create or update ApprovalRequest record in SQL (PENDING status)
                req_res = await session.execute(select(ApprovalRequest).filter_by(application_id=app_id))
                approval_req = req_res.scalars().first()
                package_data = {
                    "company": job_entity.company,
                    "title": job_entity.title,
                    "location": job_entity.location or "Remote",
                    "tailored_resume_summary": app_pkg_dto.tailored_resume_summary,
                    "tailored_resume_text": app_pkg_dto.tailored_resume_text,
                    "highlighted_skills": app_pkg_dto.highlighted_skills,
                    "cover_letter": app_pkg_dto.cover_letter,
                    "questions": [q.model_dump() if hasattr(q, "model_dump") else dict(q) for q in (app_pkg_dto.questions or [])],
                    "match_score": app_pkg_dto.match.overall_score if app_pkg_dto.match else None,
                    "match_recommendation": app_pkg_dto.match.recommendation if app_pkg_dto.match else None,
                    "email_outreach": {
                        "subject": email_out.subject,
                        "body": email_out.body,
                        "recipient_email": email_out.recipient_email or (rec_obj.public_email if rec_obj else None)
                    },
                    "linkedin_outreach": {
                        "subject": li_out.subject,
                        "body": li_out.body
                    }
                }

                if not approval_req:
                    approval_id = str(uuid.uuid4())
                    approval_req = ApprovalRequest(
                        id=approval_id,
                        run_id=run_id,
                        application_id=app_id,
                        status=ApprovalStatus.PENDING,
                        action_type="SUBMIT_AND_OUTREACH",
                        package_data=package_data
                    )
                    session.add(approval_req)
                else:
                    approval_id = approval_req.id
                    approval_req.package_data = package_data
                    approval_req.status = ApprovalStatus.PENDING

                await session.commit()

                return {
                    "status": "PREPARED",
                    "approval_status": "PENDING_APPROVAL",
                    "job_id": job_entity.id,
                    "company": job_entity.company,
                    "title": job_entity.title,
                    "application_id": app_id,
                    "approval_id": approval_id,
                    "tailored_resume_summary": app_pkg_dto.tailored_resume_summary,
                    "cover_letter": app_pkg_dto.cover_letter,
                    "highlighted_skills": app_pkg_dto.highlighted_skills,
                    "email_recipient": email_out.recipient_email or (rec_obj.public_email if rec_obj else None),
                    "recruiter_name": rec_obj.name if rec_obj else "Talent Team",
                    "message": f"Application package successfully prepared for {job_entity.title} at {job_entity.company}. Approval record {approval_id} is in PENDING status awaiting user review."
                }
            except Exception as e:
                logger.error(f"Failed preparing application for {job_entity.company}: {e}", exc_info=True)
                return {
                    "status": "FAILED",
                    "error_code": "APPLICATION_PREPARATION_ERROR",
                    "message": f"Failed to prepare application package for {job_entity.company}: {str(e)}",
                    "job_id": job_entity.id,
                    "failed_stage": "package_generation",
                    "error": str(e)
                }

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
            return {
                "status": "FAILED",
                "error_code": "CANDIDATE_NOT_FOUND",
                "message": "Candidate profile not found in database",
                "failed_stage": "candidate_lookup"
            }

        job = await session.get(Job, job_id)
        if not job:
            return {
                "status": "FAILED",
                "error_code": "JOB_NOT_FOUND",
                "message": f"Job with ID '{job_id}' not found in database",
                "job_id": job_id,
                "failed_stage": "job_lookup"
            }

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

async def get_application_status(application_id: str) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve the current persisted status, approval state, outreach delivery details,
    and audit history for a specific application ID across all lifecycle stages.
    Guaranteed read-only: never mutates state, sends emails, or performs outreach.
    """
    if not application_id:
        return {
            "status": "NOT_FOUND",
            "error_code": "INVALID_APPLICATION_ID",
            "message": "application_id parameter is required.",
            "application_id": application_id
        }

    async with AsyncSessionLocal() as session:
        # 1. Fetch Application entity
        app = await session.get(Application, application_id)
        if not app:
            return {
                "status": "NOT_FOUND",
                "error_code": "APPLICATION_NOT_FOUND",
                "message": f"Application with ID '{application_id}' not found in database.",
                "application_id": application_id
            }

        # 2. Fetch Associated Job
        job = await session.get(Job, app.job_id) if app.job_id else None

        # 3. Fetch Associated ApprovalRequest
        appr_res = await session.execute(
            select(ApprovalRequest).filter_by(application_id=app.id).order_by(ApprovalRequest.created_at.desc())
        )
        approval_req = appr_res.scalars().first()

        # 4. Fetch Outreach Messages (Email & LinkedIn)
        out_res = await session.execute(
            select(OutreachMessage).filter_by(application_id=app.id).order_by(OutreachMessage.created_at.asc())
        )
        outreaches = out_res.scalars().all()
        email_out = next((o for o in outreaches if o.channel == "EMAIL"), None)
        li_out = next((o for o in outreaches if o.channel == "LINKEDIN"), None)

        # 5. Fetch Recruiter if present
        recruiter = None
        if email_out and email_out.recruiter_id:
            recruiter = await session.get(Recruiter, email_out.recruiter_id)
        elif job and job.company:
            rec_res = await session.execute(select(Recruiter).filter_by(company_name=job.company).limit(1))
            recruiter = rec_res.scalars().first()

        # Build Email Details
        if email_out:
            email_info = {
                "status": email_out.status,
                "recipient": email_out.recipient_email,
                "recipient_name": email_out.recipient_name,
                "subject": email_out.subject,
                "sent_at": email_out.sent_at.isoformat() if email_out.sent_at else None,
                "created_at": email_out.created_at.isoformat() if email_out.created_at else None
            }
        else:
            email_info = {
                "status": "NOT_STARTED",
                "recipient": None,
                "recipient_name": None,
                "subject": None,
                "sent_at": None,
                "created_at": None
            }

        # Build LinkedIn Details
        if li_out:
            li_status = li_out.status
            is_sent = li_status in ("SENT", "PREPARED_AND_SENT")
            is_prepared = bool(li_out.body)
            manual_req = li_status == "MANUAL_REQUIRED" or (is_prepared and not is_sent)
            li_info = {
                "status": li_status,
                "prepared": is_prepared,
                "sent": is_sent,
                "manual_action_required": manual_req,
                "recipient_name": li_out.recipient_name or (recruiter.name if recruiter else None),
                "linkedin_url": recruiter.linkedin_url if recruiter else None,
                "sent_at": li_out.sent_at.isoformat() if li_out.sent_at else None,
                "created_at": li_out.created_at.isoformat() if li_out.created_at else None
            }
        else:
            li_info = {
                "status": "NOT_STARTED",
                "prepared": False,
                "sent": False,
                "manual_action_required": False,
                "recipient_name": None,
                "linkedin_url": recruiter.linkedin_url if recruiter else None,
                "sent_at": None,
                "created_at": None
            }

        # Build Actions Audit History
        actions = []
        if app.created_at:
            actions.append({
                "action": "APPLICATION_INITIALIZED",
                "status": "SUCCESS",
                "timestamp": app.created_at.isoformat()
            })

        if approval_req:
            if approval_req.created_at:
                actions.append({
                    "action": "PACKAGE_PREPARED_PENDING_APPROVAL",
                    "status": "SUCCESS",
                    "timestamp": approval_req.created_at.isoformat()
                })
            if approval_req.status == ApprovalStatus.APPROVED and approval_req.approved_at:
                actions.append({
                    "action": "APPLICATION_APPROVED",
                    "status": "SUCCESS",
                    "timestamp": approval_req.approved_at.isoformat()
                })
            elif approval_req.status == ApprovalStatus.REJECTED:
                actions.append({
                    "action": "APPLICATION_REJECTED",
                    "status": "SUCCESS",
                    "timestamp": (approval_req.approved_at or approval_req.created_at).isoformat() if (approval_req.approved_at or approval_req.created_at) else None
                })

        if email_out:
            if email_out.status == "SENT":
                actions.append({
                    "action": "EMAIL_SENT",
                    "status": "SUCCESS",
                    "recipient": email_out.recipient_email,
                    "timestamp": email_out.sent_at.isoformat() if email_out.sent_at else None
                })
            elif email_out.status == "FAILED":
                actions.append({
                    "action": "EMAIL_DELIVERY_FAILED",
                    "status": "FAILED",
                    "timestamp": email_out.created_at.isoformat() if email_out.created_at else None
                })
            elif email_out.status == "DRAFT":
                actions.append({
                    "action": "EMAIL_DRAFT_CREATED",
                    "status": "SUCCESS",
                    "timestamp": email_out.created_at.isoformat() if email_out.created_at else None
                })

        if li_out:
            if li_out.status in ("SENT", "PREPARED_AND_SENT"):
                actions.append({
                    "action": "LINKEDIN_OUTREACH_SENT",
                    "status": "SUCCESS",
                    "timestamp": li_out.sent_at.isoformat() if li_out.sent_at else None
                })
            elif li_out.status == "MANUAL_REQUIRED":
                actions.append({
                    "action": "LINKEDIN_MANUAL_REQUIRED",
                    "status": "PENDING",
                    "timestamp": li_out.created_at.isoformat() if li_out.created_at else None
                })
            elif li_out.body:
                actions.append({
                    "action": "LINKEDIN_OUTREACH_PREPARED",
                    "status": "SUCCESS",
                    "timestamp": li_out.created_at.isoformat() if li_out.created_at else None
                })

        if app.applied_at:
            actions.append({
                "action": "APPLICATION_SUBMITTED",
                "status": "SUCCESS",
                "timestamp": app.applied_at.isoformat()
            })

        latest_action = actions[-1] if actions else {
            "action": f"STATUS_{app.status}",
            "timestamp": app.updated_at.isoformat() if app.updated_at else None
        }

        app_status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
        approval_status_val = approval_req.status.value if (approval_req and hasattr(approval_req.status, "value")) else (str(approval_req.status) if approval_req else "NONE")

        return {
            "status": "SUCCESS",
            "application_id": app.id,
            "approval_id": approval_req.id if approval_req else None,
            "job": {
                "job_id": job.id if job else app.job_id,
                "title": job.title if job else "Unknown Role",
                "company": job.company if job else "Unknown Company",
                "location": job.location if job else "Remote",
                "application_url": job.application_url if job else None
            },
            "application_status": app_status_val,
            "approval_status": approval_status_val,
            "email": email_info,
            "linkedin": li_info,
            "latest_action": latest_action,
            "actions": actions,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "updated_at": app.updated_at.isoformat() if app.updated_at else None
        }
