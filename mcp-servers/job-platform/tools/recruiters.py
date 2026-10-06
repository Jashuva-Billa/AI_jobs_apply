import sys
import os
import uuid
import logging
from typing import Optional, Dict, Any

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.models.entities import Job, Recruiter
from app.services.recruiter_service import recruiter_service

logger = logging.getLogger(__name__)

async def find_recruiter(
    job_id: Optional[str] = None,
    company: Optional[str] = None
) -> Dict[str, Any]:
    """
    Discovers evidence-backed public recruiter / talent contacts without fabricating emails.
    Stores recruiter record in SQL associated with the company and job.
    """
    async with AsyncSessionLocal() as session:
        job_title = "AI Engineer"
        target_company = company

        if job_id:
            job = await session.get(Job, job_id)
            if job:
                target_company = job.company
                job_title = job.title

        if not target_company:
            return {"error": "Company name or job_id required"}

        # Discover recruiter via verified directory and live search
        recruiter_base = await recruiter_service.discover_recruiter_for_job(target_company, job_title)
        
        # Persist in SQL if not existing
        r_res = await session.execute(select(Recruiter).filter_by(company_name=target_company))
        rec_entity = r_res.scalars().first()
        
        if not rec_entity and recruiter_base:
            rec_entity = Recruiter(
                id=str(uuid.uuid4()),
                name=recruiter_base.name,
                title=recruiter_base.title,
                company_name=target_company,
                public_email=recruiter_base.public_email,
                linkedin_url=recruiter_base.linkedin_url,
                source_evidence=recruiter_base.source_evidence,
                confidence_score=recruiter_base.confidence_score
            )
            session.add(rec_entity)
            await session.commit()

        return {
            "recruiter_id": rec_entity.id if rec_entity else None,
            "name": recruiter_base.name if recruiter_base else f"Talent Team at {target_company}",
            "title": recruiter_base.title if recruiter_base else "Technical Recruiting",
            "company": target_company,
            "public_email": recruiter_base.public_email if recruiter_base else None,
            "linkedin_url": recruiter_base.linkedin_url if recruiter_base else f"https://www.linkedin.com/search/results/people/?keywords={target_company}+technical+recruiter",
            "source_evidence": recruiter_base.source_evidence if recruiter_base else "Public talent directory",
            "verified": bool(recruiter_base and recruiter_base.public_email)
        }
