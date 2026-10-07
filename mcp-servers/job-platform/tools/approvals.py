import sys
import os
import datetime
import logging
from typing import Optional, List, Dict, Any

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.models.entities import (
    ApprovalRequest, Application, Job, JobMatch, Recruiter, OutreachMessage,
    AgentRun, ApprovalStatus, ApplicationStatus
)
from app.integrations.email.provider import email_provider
from app.integrations.linkedin.adapter import linkedin_adapter

logger = logging.getLogger(__name__)

async def get_pending_approvals(run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieves all pending human approval records from SQL.
    Returns structured summary with match scores, company names, titles, and recruiter contacts.
    """
    async with AsyncSessionLocal() as session:
        query = select(ApprovalRequest).filter_by(status=ApprovalStatus.PENDING).order_by(ApprovalRequest.created_at.desc())
        if run_id:
            query = query.filter_by(run_id=run_id)

        res = await session.execute(query)
        approvals = res.scalars().all()

        if not approvals:
            return {
                "run_id": run_id,
                "pending_count": 0,
                "approvals": [],
                "message": "No pending applications awaiting approval."
            }

        app_ids = [a.application_id for a in approvals]
        apps_res = await session.execute(select(Application).where(Application.id.in_(app_ids)))
        apps_map = {a.id: a for a in apps_res.scalars().all()}

        job_ids = [a.job_id for a in apps_map.values()]
        jobs_map = {}
        matches_map = {}
        if job_ids:
            j_res = await session.execute(select(Job).where(Job.id.in_(job_ids)))
            for j in j_res.scalars().all():
                jobs_map[j.id] = j

            m_res = await session.execute(select(JobMatch).where(JobMatch.job_id.in_(job_ids)))
            for m in m_res.scalars().all():
                matches_map[m.job_id] = m

        outreaches_res = await session.execute(select(OutreachMessage).where(OutreachMessage.application_id.in_(app_ids)))
        outreaches = outreaches_res.scalars().all()
        email_map = {o.application_id: o for o in outreaches if o.channel == "EMAIL"}
        li_map = {o.application_id: o for o in outreaches if o.channel == "LINKEDIN"}

        pending_items = []
        for req in approvals:
            app_obj = apps_map.get(req.application_id)
            job_obj = jobs_map.get(app_obj.job_id) if app_obj else None
            match_obj = matches_map.get(app_obj.job_id) if app_obj else None
            em_out = email_map.get(req.application_id)
            li_out = li_map.get(req.application_id)
            pkg_data = req.package_data or {}

            pending_items.append({
                "approval_id": req.id,
                "application_id": req.application_id,
                "job_id": app_obj.job_id if app_obj else None,
                "company": job_obj.company if job_obj else pkg_data.get("company", "Company"),
                "title": job_obj.title if job_obj else pkg_data.get("title", "Role"),
                "location": job_obj.location if job_obj else "Remote",
                "match_score": match_obj.overall_score if match_obj else 85.0,
                "classification": match_obj.recommendation if match_obj else "QUALIFIED",
                "recruiter_email": em_out.recipient_email if em_out else None,
                "recruiter_name": em_out.recipient_name if em_out else "Hiring Team",
                "email_subject": em_out.subject if em_out else None,
                "email_body_preview": (em_out.body[:150] + "...") if (em_out and em_out.body) else "",
                "has_linkedin_draft": bool(li_out and li_out.body),
                "created_at": req.created_at.isoformat() if req.created_at else None
            })

        return {
            "run_id": run_id,
            "pending_count": len(pending_items),
            "approvals": pending_items
        }

async def approve_applications(approval_ids: List[str]) -> Dict[str, Any]:
    """
    Approves the specified applications after explicit human confirmation in ChatGPT.
    Updates SQL records to APPROVED, dispatches authorized emails/outreach, and updates AgentRun metrics.
    """
    if not approval_ids:
        return {"error": "No approval_ids provided"}

    async with AsyncSessionLocal() as session:
        approved_count = 0
        failed_count = 0
        results = []

        for app_id_item in approval_ids:
            try:
                req = await session.get(ApprovalRequest, app_id_item)
                if not req:
                    results.append({"approval_id": app_id_item, "status": "FAILED", "error": "ApprovalRequest not found"})
                    failed_count += 1
                    continue

                app = await session.get(Application, req.application_id)
                if not app:
                    results.append({"approval_id": app_id_item, "status": "FAILED", "error": "Application not found"})
                    failed_count += 1
                    continue

                job = await session.get(Job, app.job_id)

                req.status = ApprovalStatus.APPROVED
                req.approved_at = datetime.datetime.utcnow()
                app.status = ApplicationStatus.APPROVED

                # 1. Dispatch Email Outreach if present with safety gate
                from app.services.email_resolution_service import validate_recipient_before_send, RecipientClassification
                email_status = None
                o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
                email_out = o_res.scalars().first()
                if email_out and email_out.recipient_email:
                    target_email = email_out.recipient_email.strip()
                    job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns} if job else {}
                    
                    is_allowed, safety_status, block_reason = validate_recipient_before_send(
                        job_dict, target_email, email_out.email_status, email_out.email_source, app.candidate_id, app.id
                    )
                    
                    if not is_allowed:
                        email_out.email_status = RecipientClassification.BLOCKED_INVALID_RECIPIENT
                        email_out.status = "FAILED"
                        email_status = {"status": "BLOCKED_INVALID_RECIPIENT", "error": f"Sending blocked: {block_reason}"}
                    else:
                        try:
                            email_res = await email_provider.send_email(
                                to_email=target_email,
                                subject=email_out.subject or f"Application for {job.title if job else 'AI Engineer'}",
                                body=email_out.body,
                                idempotency_key=f"{app.id}_email_approved"
                            )
                            email_out.status = "SENT"
                            email_out.email_status = "VERIFIED"
                            email_out.sent_at = datetime.datetime.utcnow()
                            app.status = ApplicationStatus.RECRUITER_CONTACTED
                            email_status = email_res
                        except Exception as em_err:
                            email_out.status = "FAILED"
                            email_status = {"error": str(em_err)}
                else:
                    email_status = {"status": "SKIPPED_NO_RECIPIENT_EMAIL"}

                # 2. Prepare LinkedIn outreach
                linkedin_status = None
                o_li_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="LINKEDIN"))
                li_out = o_li_res.scalars().first()
                if li_out:
                    try:
                        rec_res = await session.execute(select(Recruiter).filter_by(company_name=job.company if job else "").limit(1))
                        rec_obj = rec_res.scalars().first()
                        li_action = await linkedin_adapter.prepare_message(
                            recipient_name=li_out.recipient_name or (rec_obj.name if rec_obj else "Recruiter"),
                            recipient_url=rec_obj.linkedin_url if rec_obj else None,
                            message=li_out.body
                        )
                        li_out.status = "MANUAL_REQUIRED"
                        li_out.sent_at = None
                        linkedin_status = {
                            "status": "MANUAL_REQUIRED",
                            "action": li_action,
                            "notice": "LinkedIn message copy prepared. Manual dispatch required via the provided direct profile link."
                        }
                    except Exception as li_err:
                        li_out.status = "FAILED"
                        linkedin_status = {"error": str(li_err)}

                # Update SearchRun metrics
                if req.run_id:
                    run_obj = await session.get(AgentRun, req.run_id)
                    if run_obj:
                        run_obj.applications_approved = (run_obj.applications_approved or 0) + 1
                        run_obj.approvals_pending = max(0, (run_obj.approvals_pending or 1) - 1)
                        if run_obj.approvals_pending == 0:
                            run_obj.status = "COMPLETED"
                        else:
                            run_obj.status = "PARTIALLY_APPROVED"

                results.append({
                    "approval_id": app_id_item,
                    "status": "APPROVED",
                    "company": job.company if job else "Company",
                    "title": job.title if job else "Role",
                    "email_status": email_status,
                    "linkedin_status": linkedin_status
                })
                approved_count += 1
            except Exception as e:
                failed_count += 1
                results.append({"approval_id": app_id_item, "status": "FAILED", "error": str(e)})

        await session.commit()

        return {
            "total_requested": len(approval_ids),
            "approved": approved_count,
            "failed": failed_count,
            "results": results
        }

async def reject_applications(approval_ids: List[str]) -> Dict[str, Any]:
    """
    Rejects the specified applications in SQL and updates SearchRun metrics.
    """
    if not approval_ids:
        return {"error": "No approval_ids provided"}

    async with AsyncSessionLocal() as session:
        rejected_count = 0
        for app_id_item in approval_ids:
            req = await session.get(ApprovalRequest, app_id_item)
            if req:
                req.status = ApprovalStatus.REJECTED
                app = await session.get(Application, req.application_id)
                if app:
                    app.status = ApplicationStatus.REJECTED
                
                if req.run_id:
                    run_obj = await session.get(AgentRun, req.run_id)
                    if run_obj:
                        run_obj.applications_rejected = (run_obj.applications_rejected or 0) + 1
                        run_obj.approvals_pending = max(0, (run_obj.approvals_pending or 1) - 1)
                rejected_count += 1

        await session.commit()
        return {
            "total_requested": len(approval_ids),
            "rejected": rejected_count
        }

async def approve_application(approval_id: str) -> Dict[str, Any]:
    """
    [WRITE / ACTION - REQUIRES USER CONFIRMATION]
    Approves a single application by its approval ID.
    Dispatches verified recruiter email and updates application status.
    """
    return await approve_applications(approval_ids=[approval_id])

async def reject_application(approval_id: str) -> Dict[str, Any]:
    """
    [WRITE]
    Rejects a single application by its approval ID.
    """
    return await reject_applications(approval_ids=[approval_id])

async def approve_application_batch(approval_ids: List[str]) -> Dict[str, Any]:
    """
    [WRITE / ACTION - REQUIRES USER CONFIRMATION]
    Batch approve applications by their approval IDs.
    """
    return await approve_applications(approval_ids=approval_ids)

async def get_analytics(run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve platform operations analytics: search runs, applications prepared,
    approval rates, outreach stats, and match score distribution.
    """
    async with AsyncSessionLocal() as session:
        # Total Runs
        runs_res = await session.execute(select(AgentRun))
        runs = runs_res.scalars().all()
        total_runs = len(runs)

        # Total Jobs
        jobs_res = await session.execute(select(Job))
        jobs = jobs_res.scalars().all()
        total_jobs = len(jobs)

        # Total Applications
        apps_res = await session.execute(select(Application))
        apps = apps_res.scalars().all()
        total_apps = len(apps)

        # Approvals summary
        appr_res = await session.execute(select(ApprovalRequest))
        approvals = appr_res.scalars().all()
        pending_count = sum(1 for a in approvals if a.status == ApprovalStatus.PENDING)
        approved_count = sum(1 for a in approvals if a.status == ApprovalStatus.APPROVED)
        rejected_count = sum(1 for a in approvals if a.status == ApprovalStatus.REJECTED)

        # Outreaches summary
        out_res = await session.execute(select(OutreachMessage))
        outreaches = out_res.scalars().all()
        emails_sent = sum(1 for o in outreaches if o.channel == "EMAIL" and o.status == "SENT")
        emails_draft = sum(1 for o in outreaches if o.channel == "EMAIL" and o.status == "DRAFT")
        li_prepared = sum(1 for o in outreaches if o.channel == "LINKEDIN" and o.body)

        # Matches score distribution
        m_res = await session.execute(select(JobMatch))
        matches = m_res.scalars().all()
        strong_matches = sum(1 for m in matches if m.overall_score >= 85.0)
        qualified_matches = sum(1 for m in matches if 75.0 <= m.overall_score < 85.0)
        avg_score = round(sum(m.overall_score for m in matches) / max(len(matches), 1), 1) if matches else 0.0

        return {
            "status": "SUCCESS",
            "total_search_runs": total_runs,
            "total_jobs_indexed": total_jobs,
            "total_applications": total_apps,
            "approvals": {
                "pending": pending_count,
                "approved": approved_count,
                "rejected": rejected_count,
                "approval_rate": f"{round((approved_count / max(approved_count + rejected_count, 1)) * 100, 1)}%" if (approved_count + rejected_count) > 0 else "N/A"
            },
            "outreach": {
                "emails_sent": emails_sent,
                "emails_in_draft": emails_draft,
                "linkedin_outreach_prepared": li_prepared
            },
            "matching": {
                "average_match_score": avg_score,
                "strong_matches": strong_matches,
                "qualified_matches": qualified_matches
            }
        }

