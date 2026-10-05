from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any
from datetime import datetime
from app.config.database import get_db
from app.models.entities import (
    ApprovalRequest, Application, Job, JobMatch, Recruiter, OutreachMessage,
    ApplicationQuestion, ApprovalStatus, ApplicationStatus
)
from app.schemas.schemas import ApprovalDecisionRequest
from app.integrations.email.provider import email_provider
from app.integrations.linkedin.adapter import linkedin_adapter

router = APIRouter(prefix="/approvals", tags=["Approvals"])

@router.get("")
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    """List all pending application packages requiring human approval."""
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    res = await db.execute(query)
    requests = res.scalars().all()

    packages = []
    for req in requests:
        status_val = req.status.value if hasattr(req.status, "value") else str(req.status)
        if status_val != "PENDING":
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

        packages.append({
            "approval_id": req.id,
            "application_id": app.id,
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
                "application_url": job.application_url
            },
            "match": {
                "overall_score": match_obj.overall_score if match_obj else 90.0,
                "matched_skills": match_obj.matched_skills if match_obj else job.skills,
                "missing_skills": match_obj.missing_skills if match_obj else [],
                "recommendation": match_obj.recommendation if match_obj else "STRONG_MATCH",
                "reasoning": match_obj.reasoning if match_obj else "Direct match with candidate experience."
            },
            "recruiter": {
                "id": rec_obj.id if rec_obj else None,
                "name": rec_obj.name if rec_obj else "Talent Acquisition Team",
                "title": rec_obj.title if rec_obj else "Technical Recruiter",
                "public_email": rec_obj.public_email if rec_obj else None,
                "linkedin_url": rec_obj.linkedin_url if rec_obj else None,
                "source_evidence": rec_obj.source_evidence if rec_obj else None
            },
            "package_data": req.package_data or {},
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
            ],
            "email_outreach": {
                "id": email_outreach.id if email_outreach else None,
                "subject": email_outreach.subject if email_outreach else f"Application: {job.title}",
                "body": email_outreach.body if email_outreach else "",
                "recipient_email": email_outreach.recipient_email if email_outreach else rec_obj.public_email if rec_obj else None,
                "recipient_name": email_outreach.recipient_name if email_outreach else rec_obj.name if rec_obj else "Recruiter"
            } if email_outreach else None,
            "linkedin_outreach": {
                "id": linkedin_outreach.id if linkedin_outreach else None,
                "body": linkedin_outreach.body if linkedin_outreach else "",
                "recipient_name": linkedin_outreach.recipient_name if linkedin_outreach else rec_obj.name if rec_obj else "Recruiter"
            } if linkedin_outreach else None,
            "created_at": req.created_at.isoformat() if req.created_at else None
        })

    return packages

@router.post("/{approval_id}/decide")
async def process_approval_decision(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process user decision: Approve & Send, Reject, or Modify."""
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
        target_email = email_outreach.recipient_email
        subject = decision.modified_email_subject or email_outreach.subject or f"Application for {job.title}"
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

    await db.commit()

    return {
        "status": "APPROVED_AND_EXECUTED",
        "application_status": app.status.value,
        "email_status": email_status,
        "linkedin_action": linkedin_action
    }
