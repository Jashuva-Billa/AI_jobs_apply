import sys
import os
import asyncio
import logging

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.models.entities import Application, Job, OutreachMessage, ApprovalRequest, Recruiter, ApplicationStatus
from app.services.email_resolution_service import email_resolution_service, sanitize_recruiter_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("revalidate_applications")

async def revalidate_existing_applications():
    """
    Finds existing applications with hardcoded or unverified emails (such as talent@techcorp.com),
    corrupted recruiter names, or unverified domains.
    Re-resolves them against the actual job data and updates database records.
    """
    logger.info("Starting database revalidation for all applications...")
    async with AsyncSessionLocal() as session:
        apps_res = await session.execute(select(Application))
        applications = apps_res.scalars().all()
        
        revalidated_count = 0
        cleaned_techcorp_count = 0
        cleaned_recruiter_names_count = 0

        for app in applications:
            job = await session.get(Job, app.job_id)
            if not job:
                continue

            job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns}
            
            # Fetch existing outreaches
            o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app.id))
            outreaches = o_res.scalars().all()
            
            email_out = next((o for o in outreaches if o.channel == "EMAIL"), None)
            li_out = next((o for o in outreaches if o.channel == "LINKEDIN"), None)

            # Check if recruiter object is linked
            rec_obj = None
            if email_out and email_out.recruiter_id:
                rec_obj = await session.get(Recruiter, email_out.recruiter_id)
            if not rec_obj:
                r_res = await session.execute(select(Recruiter).filter_by(company_name=job.company).limit(1))
                rec_obj = r_res.scalars().first()

            # Re-resolve recruiter contact strictly from actual job data
            resolution = email_resolution_service.resolve_recruiter_contact(job_dict, rec_obj)

            # Check for hardcoded techcorp leak
            current_email = email_out.recipient_email if email_out else None
            if current_email and current_email.lower() == "talent@techcorp.com" and "techcorp" not in job.company.lower():
                cleaned_techcorp_count += 1
                logger.warning(f"Fixing hardcoded talent@techcorp.com leak on application {app.id} ({job.company})")

            # Check for corrupted recruiter name
            current_name = email_out.recipient_name if email_out else (rec_obj.name if rec_obj else None)
            clean_name, name_status = sanitize_recruiter_name(current_name, job.company)
            if current_name and not clean_name and current_name not in ["Hiring Team", "Talent Team"]:
                cleaned_recruiter_names_count += 1
                logger.warning(f"Cleaned corrupted recruiter name '{current_name}' -> '{resolution.recruiter_name or 'Hiring Team'}' on application {app.id}")

            # Update Email Outreach
            if email_out:
                email_out.recipient_email = resolution.email
                email_out.recipient_name = resolution.recruiter_name or "Hiring Team"
                email_out.email_status = resolution.status
                email_out.email_source = resolution.source
                email_out.email_confidence = resolution.confidence
                email_out.recruiter_status = resolution.recruiter_status
                if resolution.status != "VERIFIED":
                    email_out.status = "DRAFT"

            # Update LinkedIn Outreach
            if li_out:
                li_out.recipient_name = resolution.recruiter_name or "Hiring Team"
                li_out.recruiter_status = resolution.recruiter_status

            # Update ApprovalRequest package_data if present
            req_res = await session.execute(select(ApprovalRequest).filter_by(application_id=app.id))
            approval_req = req_res.scalars().first()
            if approval_req and approval_req.package_data:
                pkg = dict(approval_req.package_data)
                if "email_outreach" in pkg:
                    pkg["email_outreach"]["recipient_email"] = resolution.email
                    pkg["email_outreach"]["recipient_name"] = resolution.recruiter_name or "Hiring Team"
                    pkg["email_outreach"]["email_status"] = resolution.status
                    pkg["email_outreach"]["email_source"] = resolution.source
                    pkg["email_outreach"]["email_confidence"] = resolution.confidence
                    pkg["email_outreach"]["recruiter_status"] = resolution.recruiter_status
                approval_req.package_data = pkg

            revalidated_count += 1

        await session.commit()
        logger.info(
            f"Database Revalidation Completed:\n"
            f"- Total Applications Processed: {revalidated_count}\n"
            f"- Hardcoded talent@techcorp.com Cleaned: {cleaned_techcorp_count}\n"
            f"- Corrupted Recruiter Names Cleaned: {cleaned_recruiter_names_count}"
        )

if __name__ == "__main__":
    asyncio.run(revalidate_existing_applications())
