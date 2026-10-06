from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config.database import get_db
from app.models.entities import (
    ApprovalRequest, Application, Job, JobMatch, Recruiter, OutreachMessage,
    ApplicationQuestion, ApprovalStatus, ApplicationStatus, AgentRun
)
from app.schemas.schemas import ApprovalDecisionRequest, BulkApprovalDecisionRequest
from app.integrations.email.provider import email_provider
from app.integrations.linkedin.adapter import linkedin_adapter

router = APIRouter(prefix="/approvals", tags=["Approvals"])

@router.get("")
async def list_pending_approvals(
    run_id: Optional[str] = Query(None, description="Filter by search run ID"),
    status: Optional[str] = Query("PENDING", description="Filter by approval status (PENDING, APPROVED, REJECTED, ALL)"),
    db: AsyncSession = Depends(get_db)
):
    """List all application packages requiring human approval."""
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if run_id:
        query = query.filter(ApprovalRequest.run_id == run_id)
    
    res = await db.execute(query)
    requests = res.scalars().all()

    packages = []
    for req in requests:
        status_val = req.status.value if hasattr(req.status, "value") else str(req.status)
        if status and status != "ALL" and status_val != status:
            continue

        app_res = await db.execute(select(Application).filter_by(id=req.application_id))
        app = app_res.scalars().first()
        if not app:
            continue
        job_res = await db.execute(select(Job).filter_by(id=app.job_id))
        job = job_res.scalars().first()
        if not job:
            continue
        
        # Matches
        m_res = await db.execute(select(JobMatch).filter_by(job_id=job.id))
        match_obj = m_res.scalars().first()

        # Recruiter
        r_res = await db.execute(select(Recruiter).filter_by(company_name=job.company))
        rec_obj = r_res.scalars().first()

        # Questions
        q_res = await db.execute(select(ApplicationQuestion).filter_by(application_id=app.id))
        questions = q_res.scalars().all()

        # Outreach
        o_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id))
        outreaches = o_res.scalars().all()

        email_outreach = next((o for o in outreaches if o.channel == "EMAIL"), None)
        linkedin_outreach = next((o for o in outreaches if o.channel == "LINKEDIN"), None)

        pkg_data = req.package_data or {}

        packages.append({
            "approval_id": req.id,
            "application_id": app.id,
            "run_id": req.run_id,
            "status": status_val,
            "job": {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "remote": job.remote,
                "salary": job.salary,
                "description": job.description,
                "requirements": job.requirements or [],
                "skills": job.skills or [],
                "application_url": job.application_url,
                "verification_status": job.verification_status
            },
            "match": {
                "overall_score": match_obj.overall_score if match_obj else (pkg_data.get("match", {}).get("overall_score", 85.0)),
                "skills_score": match_obj.skills_score if match_obj else 80.0,
                "experience_score": match_obj.experience_score if match_obj else 90.0,
                "location_score": match_obj.location_score if match_obj else 100.0,
                "role_score": match_obj.role_score if match_obj else 85.0,
                "matched_skills": match_obj.matched_skills if match_obj else job.skills,
                "missing_skills": match_obj.missing_skills if match_obj else [],
                "recommendation": match_obj.recommendation if match_obj else "STRONG_MATCH",
                "reasoning": match_obj.reasoning if match_obj else "Direct match with candidate profile."
            },
            "recruiter": {
                "id": rec_obj.id if rec_obj else None,
                "name": rec_obj.name if rec_obj else (pkg_data.get("recruiter", {}).get("name") if pkg_data.get("recruiter") else "Talent Acquisition Team"),
                "title": rec_obj.title if rec_obj else (pkg_data.get("recruiter", {}).get("title") if pkg_data.get("recruiter") else "Technical Recruiter"),
                "public_email": rec_obj.public_email if rec_obj else (pkg_data.get("recruiter", {}).get("public_email") if pkg_data.get("recruiter") else None),
                "linkedin_url": rec_obj.linkedin_url if rec_obj else (pkg_data.get("recruiter", {}).get("linkedin_url") if pkg_data.get("recruiter") else None),
                "source_evidence": rec_obj.source_evidence if rec_obj else (pkg_data.get("recruiter", {}).get("source_evidence") if pkg_data.get("recruiter") else None)
            },
            "package_data": pkg_data,
            "tailored_resume_summary": pkg_data.get("tailored_resume_summary"),
            "cover_letter": pkg_data.get("cover_letter"),
            "highlighted_skills": pkg_data.get("highlighted_skills", []),
            "questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "answer": q.answer,
                    "is_sensitive": q.is_sensitive,
                    "needs_user_input": q.needs_user_input,
                    "status": q.status
                }
                for q in questions
            ] if questions else pkg_data.get("questions", []),
            "email_outreach": {
                "id": email_outreach.id if email_outreach else None,
                "subject": email_outreach.subject if email_outreach else (pkg_data.get("email_outreach", {}).get("subject") or f"Application: {job.title}"),
                "body": email_outreach.body if email_outreach else (pkg_data.get("email_outreach", {}).get("body") or ""),
                "recipient_email": email_outreach.recipient_email if email_outreach else (rec_obj.public_email if rec_obj else (pkg_data.get("email_outreach", {}).get("recipient_email"))),
                "recipient_name": email_outreach.recipient_name if email_outreach else (rec_obj.name if rec_obj else "Hiring Team")
            } if (email_outreach or pkg_data.get("email_outreach")) else None,
            "linkedin_outreach": {
                "id": linkedin_outreach.id if linkedin_outreach else None,
                "subject": linkedin_outreach.subject if linkedin_outreach else None,
                "body": linkedin_outreach.body if linkedin_outreach else (pkg_data.get("linkedin_outreach", {}).get("body") or ""),
                "recipient_name": linkedin_outreach.recipient_name if linkedin_outreach else (rec_obj.name if rec_obj else "Hiring Team")
            } if (linkedin_outreach or pkg_data.get("linkedin_outreach")) else None,
            "created_at": req.created_at.isoformat() if req.created_at else None
        })

    return packages

@router.post("/bulk-decide")
async def process_bulk_approval_decision(
    decision: BulkApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Bulk approve or reject multiple application packages with independent error isolation."""
    total = len(decision.approval_ids)
    approved_count = 0
    rejected_count = 0
    failed_count = 0
    results = []

    for app_id_item in decision.approval_ids:
        try:
            req = await db.get(ApprovalRequest, app_id_item)
            if not req:
                results.append({"approval_id": app_id_item, "status": "FAILED", "error": "Approval request not found"})
                failed_count += 1
                continue

            app = await db.get(Application, req.application_id)
            if not app:
                results.append({"approval_id": app_id_item, "status": "FAILED", "error": "Application not found"})
                failed_count += 1
                continue

            job = await db.get(Job, app.job_id)

            if decision.decision == "REJECT":
                req.status = ApprovalStatus.REJECTED
                app.status = ApplicationStatus.REJECTED
                results.append({"approval_id": app_id_item, "status": "REJECTED"})
                rejected_count += 1
            else:
                # APPROVE
                req.status = ApprovalStatus.APPROVED
                req.approved_at = datetime.utcnow()
                app.status = ApplicationStatus.APPROVED

                # 1. Dispatch Email outreach if available and enabled
                email_status = None
                o_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
                email_outreach = o_res.scalars().first()

                if decision.send_email and email_outreach and email_outreach.recipient_email:
                    try:
                        email_res = await email_provider.send_email(
                            to_email=email_outreach.recipient_email,
                            subject=email_outreach.subject or f"Application for {job.title if job else 'Position'}",
                            body=email_outreach.body,
                            idempotency_key=f"{app.id}_email_approved"
                        )
                        email_outreach.status = "SENT"
                        email_outreach.sent_at = datetime.utcnow()
                        app.status = ApplicationStatus.RECRUITER_CONTACTED
                        email_status = email_res
                    except Exception as email_err:
                        email_outreach.status = "FAILED"
                        email_status = {"error": str(email_err)}
                elif not email_outreach or not email_outreach.recipient_email:
                    email_status = {"status": "SKIPPED_NO_RECIPIENT_EMAIL"}

                # 2. Dispatch/Prepare LinkedIn Connection Request & Direct Message Outreach
                linkedin_status = None
                o_li_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="LINKEDIN"))
                li_outreach = o_li_res.scalars().first()
                if li_outreach:
                    try:
                        rec_res = await db.execute(select(Recruiter).filter_by(company_name=job.company if job else "").limit(1))
                        rec_obj = rec_res.scalars().first()
                        li_action = await linkedin_adapter.prepare_message(
                            recipient_name=li_outreach.recipient_name or (rec_obj.name if rec_obj else "Recruiter"),
                            recipient_url=rec_obj.linkedin_url if rec_obj else None,
                            message=li_outreach.body
                        )
                        li_outreach.status = "SENT"
                        li_outreach.sent_at = datetime.utcnow()
                        linkedin_status = {"status": "PREPARED_AND_SENT", "action": li_action}
                        if app.status != ApplicationStatus.RECRUITER_CONTACTED:
                            app.status = ApplicationStatus.RECRUITER_CONTACTED
                    except Exception as li_err:
                        li_outreach.status = "FAILED"
                        linkedin_status = {"error": str(li_err)}
                else:
                    linkedin_status = {"status": "SKIPPED_NO_LINKEDIN_DRAFT"}

                results.append({
                    "approval_id": app_id_item,
                    "status": "APPROVED",
                    "application_status": app.status.value,
                    "email_status": email_status,
                    "linkedin_status": linkedin_status
                })
                approved_count += 1

            # Update AgentRun metrics if run_id exists
            if req.run_id:
                run_obj = await db.get(AgentRun, req.run_id)
                if run_obj:
                    if decision.decision == "REJECT":
                        run_obj.applications_rejected = (run_obj.applications_rejected or 0) + 1
                    else:
                        run_obj.applications_approved = (run_obj.applications_approved or 0) + 1
                    run_obj.approvals_pending = max(0, (run_obj.approvals_pending or 1) - 1)
                    if run_obj.approvals_pending == 0:
                        run_obj.status = "COMPLETED"
                    else:
                        run_obj.status = "PARTIALLY_APPROVED"

        except Exception as e:
            failed_count += 1
            results.append({"approval_id": app_id_item, "status": "FAILED", "error": str(e)})

    await db.commit()

    return {
        "total": total,
        "approved": approved_count,
        "rejected": rejected_count,
        "failed": failed_count,
        "results": results
    }

@router.post("/{approval_id}/decide")
async def process_approval_decision(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process single user decision: Approve & Send, Reject, or Modify."""
    req = await db.get(ApprovalRequest, approval_id)
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")

    app = await db.get(Application, req.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Associated application not found")

    job = await db.get(Job, app.job_id)

    if decision.decision == "REJECT":
        req.status = ApprovalStatus.REJECTED
        app.status = ApplicationStatus.REJECTED
        
        if req.run_id:
            run_obj = await db.get(AgentRun, req.run_id)
            if run_obj:
                run_obj.applications_rejected = (run_obj.applications_rejected or 0) + 1
                run_obj.approvals_pending = max(0, (run_obj.approvals_pending or 1) - 1)
                run_obj.status = "COMPLETED" if run_obj.approvals_pending == 0 else "PARTIALLY_APPROVED"

        await db.commit()
        return {"status": "REJECTED", "message": "Application rejected by user"}

    # APPROVE or MODIFY
    req.status = ApprovalStatus.APPROVED if decision.decision == "APPROVE" else ApprovalStatus.MODIFIED
    req.approved_at = datetime.utcnow()
    req.user_modifications = decision.model_dump()
    app.status = ApplicationStatus.APPROVED

    # Update modified questions if provided
    if decision.modified_answers:
        for q_id, ans in decision.modified_answers.items():
            q_obj = await db.get(ApplicationQuestion, q_id)
            if q_obj:
                q_obj.answer = ans
                q_obj.status = "USER_MODIFIED"

    # Send Email if approved and email is present
    email_status = None
    o_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
    email_outreach = o_res.scalars().first()

    if decision.send_email and email_outreach:
        if decision.modified_recipient_email:
            email_outreach.recipient_email = decision.modified_recipient_email.strip()
        target_email = decision.modified_recipient_email or email_outreach.recipient_email
        subject = decision.modified_email_subject or email_outreach.subject or f"Application for {job.title if job else 'Position'}"
        body = decision.modified_email_body or email_outreach.body

        if target_email:
            try:
                email_result = await email_provider.send_email(
                    to_email=target_email,
                    subject=subject,
                    body=body,
                    idempotency_key=f"{app.id}_email_approved"
                )
                email_outreach.status = "SENT"
                email_outreach.sent_at = datetime.utcnow()
                app.status = ApplicationStatus.RECRUITER_CONTACTED
                email_status = email_result
            except Exception as e:
                email_outreach.status = "FAILED"
                email_status = {"error": str(e)}

    # LinkedIn prepared action
    linkedin_action = None
    o_li_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="LINKEDIN"))
    li_outreach = o_li_res.scalars().first()
    if li_outreach:
        msg = decision.modified_linkedin_body or li_outreach.body
        linkedin_action = await linkedin_adapter.prepare_message(
            recipient_name=li_outreach.recipient_name or "Recruiter",
            recipient_url=None,
            message=msg
        )

    # Update AgentRun metrics
    if req.run_id:
        run_obj = await db.get(AgentRun, req.run_id)
        if run_obj:
            run_obj.applications_approved = (run_obj.applications_approved or 0) + 1
            run_obj.approvals_pending = max(0, (run_obj.approvals_pending or 1) - 1)
            run_obj.status = "COMPLETED" if run_obj.approvals_pending == 0 else "PARTIALLY_APPROVED"

    await db.commit()

    return {
        "status": "APPROVED_AND_EXECUTED",
        "application_status": app.status.value,
        "email_status": email_status,
        "linkedin_action": linkedin_action
    }
