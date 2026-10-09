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
            clean_id = str(app_id_item).strip()
            req = await db.get(ApprovalRequest, clean_id)
            if not req:
                r_res = await db.execute(select(ApprovalRequest).filter_by(application_id=clean_id).order_by(ApprovalRequest.created_at.desc()))
                req = r_res.scalars().first()
            if not req:
                j_res = await db.get(Job, clean_id)
                if j_res:
                    a_res = await db.execute(select(Application).filter_by(job_id=j_res.id).order_by(Application.created_at.desc()))
                    app_from_j = a_res.scalars().first()
                    if app_from_j:
                        r_res2 = await db.execute(select(ApprovalRequest).filter_by(application_id=app_from_j.id).order_by(ApprovalRequest.created_at.desc()))
                        req = r_res2.scalars().first()

            app = None
            if req:
                app = await db.get(Application, req.application_id)
            else:
                app = await db.get(Application, clean_id)

            if not req and not app:
                results.append({"approval_id": app_id_item, "status": "FAILED", "error": f"Record not found for identifier: {app_id_item}"})
                failed_count += 1
                continue

            job = await db.get(Job, app.job_id) if (app and app.job_id) else None

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

                # 1. Dispatch Email outreach if available and enabled with safety gate
                from app.services.email_resolution_service import validate_recipient_before_send, RecipientClassification
                email_status = None
                o_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
                email_outreach = o_res.scalars().first()

                if decision.send_email:
                    if email_outreach and email_outreach.recipient_email:
                        target_email = email_outreach.recipient_email.strip()
                        job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns} if job else {}
                        
                        is_allowed, safety_status, block_reason = validate_recipient_before_send(
                            job_dict, target_email, email_outreach.email_status, email_outreach.email_source, app.candidate_id, app.id
                        )
                        
                        if not is_allowed:
                            email_outreach.email_status = RecipientClassification.BLOCKED_INVALID_RECIPIENT
                            email_outreach.status = "FAILED"
                            email_status = {"status": "BLOCKED", "reason": "BLOCKED_INVALID_RECIPIENT", "error": f"Sending blocked: {block_reason}"}
                        else:
                            try:
                                email_res = await email_provider.send_email(
                                    to_email=target_email,
                                    subject=email_outreach.subject or f"Application for {job.title if job else 'Position'}",
                                    body=email_outreach.body,
                                    idempotency_key=f"{app.candidate_id}_{app.job_id}_EMAIL_OUTREACH"
                                )
                                email_status = email_res
                                provider_status = (email_res or {}).get("status") if isinstance(email_res, dict) else None
                                if provider_status == "SENT":
                                    email_outreach.status = "SENT"
                                    email_outreach.email_status = "VERIFIED"
                                    email_outreach.sent_at = datetime.utcnow()
                                    app.status = ApplicationStatus.RECRUITER_CONTACTED
                                elif provider_status == "ALREADY_SENT":
                                    email_outreach.status = "SENT"
                                    email_outreach.email_status = "VERIFIED"
                                    app.status = ApplicationStatus.RECRUITER_CONTACTED
                                else:
                                    email_outreach.status = "FAILED"
                            except Exception as email_err:
                                email_outreach.status = "FAILED"
                                email_status = {"status": "FAILED", "error": str(email_err)}
                    else:
                        email_status = {"status": "BLOCKED", "reason": "NO_VERIFIED_RECIPIENT_EMAIL", "error": "Cannot dispatch outreach: No verified recipient email found."}
                else:
                    email_status = {"status": "SKIPPED_SEND_EMAIL_FALSE"}

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
                        li_outreach.status = "MANUAL_REQUIRED"
                        li_outreach.sent_at = None
                        linkedin_status = {
                            "status": "MANUAL_REQUIRED",
                            "action": li_action,
                            "notice": "LinkedIn message copy prepared. Manual dispatch required via the provided direct profile link."
                        }
                    except Exception as li_err:
                        li_outreach.status = "FAILED"
                        linkedin_status = {"error": str(li_err)}
                else:
                    linkedin_status = {"status": "SKIPPED_NO_LINKEDIN_DRAFT"}

                results.append({
                    "approval_id": app_id_item,
                    "status": "APPROVED",
                    "application_status": app.status.value if hasattr(app.status, "value") else str(app.status),
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
    clean_id = str(approval_id).strip()
    req = await db.get(ApprovalRequest, clean_id)
    if not req:
        r_res = await db.execute(select(ApprovalRequest).filter_by(application_id=clean_id).order_by(ApprovalRequest.created_at.desc()))
        req = r_res.scalars().first()

    app = None
    if req:
        app = await db.get(Application, req.application_id)
    else:
        app = await db.get(Application, clean_id)

    if not app and not req:
        raise HTTPException(status_code=404, detail="Approval request or application not found")

    job = await db.get(Job, app.job_id) if (app and app.job_id) else None

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

    # Send Email if approved and email is present. Recover email data from the
    # approval package when the normalized OutreachMessage row is missing.
    email_status = None
    o_res = await db.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
    email_outreach = o_res.scalars().first()

    package_email = {}
    if req and isinstance(req.package_data, dict):
        package_email = req.package_data.get("email_outreach") or {}

    if decision.send_email:
        if not email_outreach and package_email.get("recipient_email"):
            email_outreach = OutreachMessage(
                application_id=app.id,
                channel="EMAIL",
                recipient_email=package_email.get("recipient_email"),
                recipient_name=package_email.get("recipient_name") or "Hiring Team",
                subject=package_email.get("subject") or f"Application for {job.title if job else 'Position'}",
                body=package_email.get("body") or "",
                email_status=package_email.get("email_status") or "VERIFIED",
                email_source=package_email.get("email_source") or "approval_package",
                email_confidence=package_email.get("email_confidence") or 0.0,
                status="READY_FOR_APPROVAL"
            )
            db.add(email_outreach)
            await db.flush()

        if decision.modified_recipient_email and email_outreach:
            email_outreach.recipient_email = decision.modified_recipient_email.strip()
        target_email = decision.modified_recipient_email or (email_outreach.recipient_email if email_outreach else package_email.get("recipient_email"))
        subject = decision.modified_email_subject or (email_outreach.subject if email_outreach else package_email.get("subject") or f"Application for {job.title if job else 'Position'}")
        body = decision.modified_email_body or (email_outreach.body if email_outreach else package_email.get("body") or "")

        if target_email and target_email.strip():
            target_email = target_email.strip()
            job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns} if job else {}
            em_status = email_outreach.email_status if email_outreach else "UNVERIFIED"
            em_source = email_outreach.email_source if email_outreach else "manual"
            
            is_allowed, safety_status, block_reason = validate_recipient_before_send(
                job_dict, target_email, em_status, em_source, app.candidate_id, app.id
            )
            
            if not is_allowed:
                if email_outreach:
                    email_outreach.email_status = RecipientClassification.BLOCKED_INVALID_RECIPIENT
                    email_outreach.status = "FAILED"
                email_status = {"status": "BLOCKED", "reason": "BLOCKED_INVALID_RECIPIENT", "error": f"Sending blocked: {block_reason}"}
            else:
                try:
                    email_result = await email_provider.send_email(
                        to_email=target_email,
                        subject=subject,
                        body=body,
                        idempotency_key=f"{app.candidate_id}_{app.job_id}_EMAIL_OUTREACH"
                    )
                    email_status = email_result
                    provider_status = (email_result or {}).get("status") if isinstance(email_result, dict) else None
                    if email_outreach and provider_status == "SENT":
                        email_outreach.status = "SENT"
                        email_outreach.email_status = "VERIFIED"
                        email_outreach.sent_at = datetime.utcnow()
                        app.status = ApplicationStatus.RECRUITER_CONTACTED
                    elif email_outreach and provider_status == "ALREADY_SENT":
                        email_outreach.status = "SENT"
                        email_outreach.email_status = "VERIFIED"
                        app.status = ApplicationStatus.RECRUITER_CONTACTED
                    elif email_outreach:
                        email_outreach.status = "FAILED"
                except Exception as e:
                    if email_outreach:
                        email_outreach.status = "FAILED"
                    email_status = {"status": "FAILED", "error": str(e)}
        else:
            email_status = {"status": "BLOCKED", "reason": "NO_VERIFIED_RECIPIENT_EMAIL", "error": "Cannot dispatch outreach: No verified recipient email found."}
    else:
        email_status = {"status": "SKIPPED_SEND_EMAIL_FALSE"}

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
        "application_status": app.status.value if hasattr(app.status, "value") else str(app.status),
        "email_status": email_status,
        "linkedin_action": linkedin_action
    }
