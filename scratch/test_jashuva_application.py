import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.settings import settings
from app.config.database import AsyncSessionLocal
from app.models.entities import (
    CandidateProfile, Job, JobMatch, Recruiter, Application,
    ApplicationQuestion, OutreachMessage, ApprovalRequest,
    ApplicationStatus, ApprovalStatus
)
from app.services.application_service import application_service
from app.services.outreach_service import outreach_service
from app.services.matching_service import matching_service
from app.schemas.schemas import CandidateProfileBase, MatchBreakdown, ApprovalDecisionRequest
from app.integrations.email.provider import email_provider

async def main():
    # 0. Ensure tables exist in MySQL
    from app.config.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.main import seed_initial_data
    await seed_initial_data()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        # 1. Fetch Jashuva's candidate profile
        res_c = await session.execute(select(CandidateProfile).limit(1))
        cand = res_c.scalars().first()
        print(f"Loaded Candidate: {cand.name} ({cand.email}) | Exp: {cand.years_of_experience} yrs")

        # 2. Get top matching AI job
        res_j = await session.execute(select(Job).filter(Job.company == "Anthropic AI Labs"))
        job = res_j.scalars().first()
        if not job:
            res_j = await session.execute(select(Job).limit(1))
            job = res_j.scalars().first()
        print(f"Target Role: {job.title} at {job.company}")

        # 3. Compute match
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
        print(f"Match Score: {match_result.overall_score}% ({match_result.recommendation})")
        print(f"Matched Skills: {', '.join(match_result.matched_skills[:6])}")

        # 4. Generate Tailored Resume & Cover Letter
        tailored = await application_service.tailor_resume(cand_schema, {"title": job.title, "company": job.company}, match_result)
        cover_letter = await application_service.generate_cover_letter(cand_schema, {"title": job.title, "company": job.company}, match_result)
        questions = application_service.prepare_application_questions(cand_schema, {"title": job.title, "company": job.company})

        # 5. Discover Recruiter & Outreach
        rec_data = {
            "name": "Sarah Jenkins",
            "title": "Principal Technical Recruiter - AI Systems",
            "company_name": job.company,
            "public_email": "talent@anthropic.com",
            "linkedin_url": "https://www.linkedin.com/in/sarah-jenkins-ai-recruiter",
            "source_evidence": "Anthropic official careers contact directory"
        }
        recruiter_entity = Recruiter(**rec_data)
        session.add(recruiter_entity)
        await session.flush()

        email_outreach = await outreach_service.generate_recruiter_email(cand_schema, {"title": job.title, "company": job.company}, recruiter_entity)
        linkedin_outreach = await outreach_service.generate_linkedin_outreach(cand_schema, {"title": job.title, "company": job.company}, recruiter_entity)

        # 6. Save Application & Approval Package
        app_entity = Application(
            candidate_id=cand.id,
            job_id=job.id,
            status=ApplicationStatus.REVIEW_REQUIRED,
            idempotency_key=f"{cand.id}_{job.id}_live_app",
            notes=f"Tailored application package for Jashuva Billa at {job.company}"
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

        session.add(OutreachMessage(
            application_id=app_entity.id,
            recruiter_id=recruiter_entity.id,
            channel="EMAIL",
            subject=email_outreach.subject,
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

        approval_req = ApprovalRequest(
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
        session.add(approval_req)
        await session.commit()
        print(f"\n[OK] Created Approval Request Package ID: {approval_req.id}")
        print(f"Tailored Summary: {tailored['tailored_summary']}")
        print(f"Cover Letter Preview:\n{cover_letter[:200]}...")
        print(f"\nEmail Outreach Subject: {email_outreach.subject}")
        print(f"Email Body:\n{email_outreach.body}")
        print(f"\nLinkedIn Message ({len(linkedin_outreach.body)} chars):\n{linkedin_outreach.body}")

if __name__ == "__main__":
    asyncio.run(main())
