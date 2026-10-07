import sys
import os
import datetime
import urllib.parse
import logging
from typing import Optional, Dict, Any

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.models.entities import Application, Job, OutreachMessage, Recruiter, ApplicationStatus
from app.integrations.email.provider import email_provider

logger = logging.getLogger(__name__)

async def send_approved_email(application_id: str) -> Dict[str, Any]:
    """
    Sends an authorized recruiter outreach email for an application that has been explicitly APPROVED.
    Guaranteed idempotent: candidate_id + job_id + EMAIL_OUTREACH.
    """
    async with AsyncSessionLocal() as session:
        app = await session.get(Application, application_id)
        if not app:
            return {"error": "Application not found", "application_id": application_id}

        if app.status not in [ApplicationStatus.APPROVED, ApplicationStatus.RECRUITER_CONTACTED]:
            return {
                "error": "Application must be in APPROVED status before email dispatch.",
                "current_status": app.status.value,
                "application_id": application_id
            }

        job = await session.get(Job, app.job_id)
        o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="EMAIL"))
        email_out = o_res.scalars().first()

        if not email_out or not email_out.recipient_email:
            return {
                "error": "No verified recruiter email available for this application. Apply via official company career portal.",
                "application_id": application_id,
                "application_url": job.application_url if job else None
            }

        from app.services.email_resolution_service import validate_recipient_before_send, RecipientClassification

        if not job:
            return {"error": "Associated job record not found", "application_id": application_id}

        job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns}
        recipient_email = email_out.recipient_email.strip()

        is_allowed, safety_status, block_reason = validate_recipient_before_send(
            job_dict, recipient_email, email_out.email_status, email_out.email_source, app.candidate_id, application_id
        )

        if not is_allowed:
            email_out.email_status = RecipientClassification.BLOCKED_INVALID_RECIPIENT
            email_out.status = "FAILED"
            await session.commit()
            return {
                "status": "BLOCKED_INVALID_RECIPIENT",
                "error": f"Email sending blocked: {block_reason}.",
                "application_id": application_id
            }

        idempotency_key = f"{app.candidate_id}:{app.job_id}:EMAIL_OUTREACH"

        try:
            email_res = await email_provider.send_email(
                to_email=recipient_email,
                subject=email_out.subject or f"Application for {job.title if job else 'Position'}",
                body=email_out.body,
                idempotency_key=idempotency_key
            )
            email_out.status = "SENT"
            email_out.email_status = "VERIFIED"
            email_out.sent_at = datetime.datetime.utcnow()
            app.status = ApplicationStatus.RECRUITER_CONTACTED
            await session.commit()

            return {
                "status": "SENT",
                "application_id": application_id,
                "recipient_email": email_out.recipient_email,
                "subject": email_out.subject,
                "idempotency_key": idempotency_key,
                "provider_response": email_res
            }
        except Exception as e:
            logger.error(f"Email dispatch error ({application_id}): {e}")
            return {"status": "FAILED", "application_id": application_id, "error": str(e)}

async def prepare_linkedin_outreach(application_id: str) -> Dict[str, Any]:
    """
    Prepares compliant LinkedIn outreach copy with direct recruiter profile and search deep-links.
    Does NOT execute unauthorized browser automation.
    """
    async with AsyncSessionLocal() as session:
        app = await session.get(Application, application_id)
        if not app:
            return {"error": "Application not found", "application_id": application_id}

        job = await session.get(Job, app.job_id)
        o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id, channel="LINKEDIN"))
        li_out = o_res.scalars().first()

        rec_res = await session.execute(select(Recruiter).filter_by(company_name=job.company if job else "").limit(1))
        rec_obj = rec_res.scalars().first()

        company_name = job.company if job else "Company"
        recruiter_name = rec_obj.name if rec_obj else "Talent Acquisition Partner"
        
        if rec_obj and rec_obj.linkedin_url and "linkedin.com/in/" in rec_obj.linkedin_url:
            direct_url = rec_obj.linkedin_url
        else:
            search_query = f"{company_name} {recruiter_name}" if recruiter_name != "Talent Team" else f"{company_name} technical recruiter"
            direct_url = f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote(search_query)}"

        message_body = li_out.body if li_out else (
            f"Hi {recruiter_name.split()[0] if recruiter_name else 'there'}, I saw the {job.title if job else 'AI Engineer'} opening at {company_name}. "
            f"I have 2.9 years of experience in Generative AI, LangGraph multi-agent systems, and RAG pipelines in Python/FastAPI. "
            f"I'd love to connect and share my background for the team!"
        )

        return {
            "application_id": application_id,
            "company": company_name,
            "recruiter_name": recruiter_name,
            "direct_linkedin_url": direct_url,
            "connection_note_preview": message_body[:290],
            "full_message": message_body,
            "compliance_notice": "100% LinkedIn Platform Compliant. Open direct URL and paste pre-approved note manually."
        }

async def prepare_recruiter_outreach(application_id: str) -> Dict[str, Any]:
    """
    [READ/PREPARE] Prepares structured recruiter outreach packages (email draft + compliant LinkedIn note)
    for a specific application ID. Does not send or dispatch anything.
    """
    async with AsyncSessionLocal() as session:
        app = await session.get(Application, application_id)
        if not app:
            return {"status": "NOT_FOUND", "message": f"Application '{application_id}' not found."}

        job = await session.get(Job, app.job_id) if app.job_id else None
        
        # Outreaches
        o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id))
        outreaches = o_res.scalars().all()
        email_out = next((o for o in outreaches if o.channel == "EMAIL"), None)
        li_out = next((o for o in outreaches if o.channel == "LINKEDIN"), None)

        # Recruiter
        rec_res = await session.execute(select(Recruiter).filter_by(company_name=job.company if job else "").limit(1))
        rec_obj = rec_res.scalars().first()

        li_info = await prepare_linkedin_outreach(application_id)

        return {
            "status": "PREPARED",
            "application_id": application_id,
            "job": {
                "company": job.company if job else "Company",
                "title": job.title if job else "Role",
                "location": job.location if job else "Remote"
            },
            "recruiter": {
                "name": rec_obj.name if rec_obj else (email_out.recipient_name if email_out else "Talent Acquisition"),
                "title": rec_obj.title if rec_obj else "Technical Recruiter",
                "email": email_out.recipient_email if email_out else None,
                "email_status": email_out.email_status if email_out else "NOT_FOUND",
                "linkedin_url": rec_obj.linkedin_url if rec_obj else None
            },
            "email_draft": {
                "subject": email_out.subject if email_out else f"Application for {job.title if job else 'AI Engineer'}",
                "body": email_out.body if email_out else "",
                "recipient_email": email_out.recipient_email if email_out else None
            },
            "linkedin_draft": li_info
        }

