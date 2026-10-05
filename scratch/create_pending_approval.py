import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.database import AsyncSessionLocal
from app.models.entities import (
    CandidateProfile, Job, JobMatch, Recruiter, Application,
    ApplicationQuestion, OutreachMessage, ApprovalRequest,
    ApplicationStatus, ApprovalStatus
)
from app.services.application_service import application_service
from app.services.outreach_service import outreach_service
from app.services.matching_service import matching_service
from app.schemas.schemas import CandidateProfileBase
import uuid

async def main():
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        
        # 1. Fetch Candidate
        cand = (await session.execute(select(CandidateProfile).limit(1))).scalars().first()
        
        # 2. Fetch Job
        job = (await session.execute(select(Job).filter(Job.company == "Anthropic AI Labs"))).scalars().first()
        if not job:
            job = (await session.execute(select(Job).limit(1))).scalars().first()
        
        cand_schema = CandidateProfileBase(
            name=cand.name,
            email=cand.email,
            years_of_experience=cand.years_of_experience,
            skills=cand.skills,
            technical_skills=cand.technical_skills,
            cloud_skills=cand.cloud_skills,
            frameworks=cand.frameworks,
            preferred_roles=cand.preferred_roles,
            remote_preference=cand.remote_preference
        )
        
        match_result = matching_service.evaluate_match(cand_schema, {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "remote": job.remote,
            "skills": job.skills,
            "requirements": job.requirements,
            "description": job.description
        })
        
        # Generate Tailored Resume, Cover Letter, Outreach
        tailored = await application_service.tailor_resume(cand_schema, {"title": job.title, "company": job.company}, match_result)
        cover_letter = await application_service.generate_cover_letter(cand_schema, {"title": job.title, "company": job.company}, match_result)
        questions = application_service.prepare_application_questions(cand_schema, {"title": job.title, "company": job.company})

        recruiter_entity = Recruiter(
            name="Sarah Jenkins",
            title="Principal Technical Recruiter - AI Systems",
            company_name=job.company,
            public_email="talent@anthropic.com",
            linkedin_url="https://www.linkedin.com/in/sarah-jenkins-ai-recruiter",
            source_evidence="Anthropic official careers contact directory"
        )
        session.add(recruiter_entity)
        await session.flush()

        app_id = str(uuid.uuid4())
        app_entity = Application(
            id=app_id,
            candidate_id=cand.id,
            job_id=job.id,
            status=ApplicationStatus.REVIEW_REQUIRED,
            idempotency_key=f"jashuva_{job.id}_{str(uuid.uuid4())[:8]}",
            notes=f"Prepared application package for Jashuva Billa at {job.company}"
        )
        session.add(app_entity)
        await session.flush()

        for q in questions:
            session.add(ApplicationQuestion(
                application_id=app_entity.id,
                question=q.question,
                answer=q.answer,
                is_sensitive=q.is_sensitive,
                needs_user_input=q.needs_user_input,
                status=q.status
            ))

        email_outreach = await outreach_service.generate_recruiter_email(cand_schema, {"title": job.title, "company": job.company}, recruiter_entity)
        linkedin_outreach = await outreach_service.generate_linkedin_outreach(cand_schema, {"title": job.title, "company": job.company}, recruiter_entity)

        session.add(OutreachMessage(
            application_id=app_entity.id,
            recruiter_id=recruiter_entity.id,
            channel="EMAIL",
            subject=f"Jashuva Billa - Application for {job.title}",
            body=email_outreach.body,
            recipient_email=recruiter_entity.public_email,
            recipient_name=recruiter_entity.name,
            status="DRAFT"
        ))

        session.add(OutreachMessage(
            application_id=app_entity.id,
            recruiter_id=recruiter_entity.id,
            channel="LINKEDIN",
            subject=linkedin_outreach.subject,
            body=linkedin_outreach.body,
            recipient_name=recruiter_entity.name,
            status="MANUAL_REQUIRED"
        ))

        req = ApprovalRequest(
            id=str(uuid.uuid4()),
            application_id=app_entity.id,
            status=ApprovalStatus.PENDING,
            action_type="SUBMIT_AND_OUTREACH",
            package_data={
                "tailored_resume_summary": tailored["tailored_summary"],
                "tailored_resume_text": tailored["tailored_text"],
                "highlighted_skills": tailored["highlighted_skills"],
                "cover_letter": cover_letter
            }
        )
        session.add(req)
        await session.commit()
        print(f"Created pending approval request: {req.id} for {job.title} at {job.company}")

if __name__ == "__main__":
    asyncio.run(main())
