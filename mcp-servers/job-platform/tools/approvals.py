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

                # 1. Dispatch Email Outreach if present
                email_status = None
                o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
                email_out = o_res.scalars().first()
                if email_out and email_out.recipient_email:
                    try:
                        email_res = await email_provider.send_email(
                            to_email=email_out.recipient_email,
                            subject=email_out.subject or f"Application for {job.title if job else 'AI Engineer'}",
                            body=email_out.body,
                            idempotency_key=f"{app.id}_email_approved"
                        )
                        email_out.status = "SENT"
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
                        li_out.status = "SENT"
                        li_out.sent_at = datetime.datetime.utcnow()
                        linkedin_status = {"status": "PREPARED_AND_SENT", "action": li_action}
                        if app.status != ApplicationStatus.RECRUITER_CONTACTED:
                            app.status = ApplicationStatus.RECRUITER_CONTACTED
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
