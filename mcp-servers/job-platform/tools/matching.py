import sys
import os
import uuid
import logging
from typing import Optional, List, Dict, Any

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal
from app.config.settings import settings
from app.models.entities import Job, JobMatch, CandidateProfile, AgentRun
from app.schemas.schemas import CandidateProfileBase, CandidateProfileResponse
from app.services.matching_service import matching_service

logger = logging.getLogger(__name__)

async def match_jobs(
    job_ids: Optional[List[str]] = None,
    run_id: Optional[str] = None,
    candidate_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes official deterministic 7-factor matching scoring against candidate resume.
    Returns structured scores, classifications (STRONG, QUALIFIED, POSSIBLE, REJECTED), and saves matches in SQL.
    """
    async with AsyncSessionLocal() as session:
        # Resolve candidate
        if candidate_id:
            cand_entity = await session.get(CandidateProfile, candidate_id)
        else:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand_entity = res.scalars().first()

        if not cand_entity:
            return {"error": "Candidate profile not found"}

        cand_dict = {c.name: getattr(cand_entity, c.name) for c in cand_entity.__table__.columns}
        cand_schema = CandidateProfileResponse.model_validate(cand_dict)

        # Resolve jobs
        if job_ids:
            j_res = await session.execute(select(Job).where(Job.id.in_(job_ids)))
            jobs = j_res.scalars().all()
        elif run_id:
            j_res = await session.execute(select(Job).filter_by(run_id=run_id))
            jobs = j_res.scalars().all()
        else:
            j_res = await session.execute(select(Job).limit(100))
            jobs = j_res.scalars().all()

        if not jobs:
            return {"error": "No jobs found for matching evaluation"}

        matched_results = []
        qualified_count = 0
        strong_count = 0

        for job in jobs:
            job_dict = {c.name: getattr(job, c.name) for c in job.__table__.columns}
            match_breakdown = matching_service.evaluate_match(cand_schema, job_dict)
            
            score = match_breakdown.overall_score
            if score >= settings.STRONG_MATCH_THRESHOLD:
                classification = "STRONG"
                strong_count += 1
                qualified_count += 1
            elif score >= settings.MATCH_THRESHOLD:
                classification = "QUALIFIED"
                qualified_count += 1
            elif score >= settings.POSSIBLE_MATCH_THRESHOLD:
                classification = "POSSIBLE"
                qualified_count += 1
            else:
                classification = "REJECTED"

            # Check existing match or insert
            m_res = await session.execute(select(JobMatch).filter_by(candidate_id=cand_entity.id, job_id=job.id))
            match_rec = m_res.scalars().first()
            if not match_rec:
                match_rec = JobMatch(
                    id=str(uuid.uuid4()),
                    candidate_id=cand_entity.id,
                    job_id=job.id,
                    overall_score=score,
                    skills_score=match_breakdown.skills_score,
                    experience_score=match_breakdown.experience_score,
                    role_score=match_breakdown.role_score,
                    location_score=match_breakdown.location_score,
                    matched_skills=match_breakdown.matched_skills,
                    missing_skills=match_breakdown.missing_skills,
                    recommendation=classification,
                    reasoning=match_breakdown.reasoning
                )
                session.add(match_rec)
            else:
                match_rec.overall_score = score
                match_rec.recommendation = classification
                match_rec.reasoning = match_breakdown.reasoning

            matched_results.append({
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
                "overall_score": score,
                "classification": classification,
                "breakdown": {
                    "skills": match_breakdown.skills_score,
                    "experience": match_breakdown.experience_score,
                    "role": match_breakdown.role_score,
                    "location": match_breakdown.location_score
                },
                "matched_skills": match_breakdown.matched_skills,
                "missing_skills": match_breakdown.missing_skills
            })

        # Update AgentRun metrics if run_id
        if run_id:
            run_obj = await session.get(AgentRun, run_id)
            if run_obj:
                run_obj.qualified_jobs = qualified_count
                run_obj.strong_matches = strong_count
                run_obj.status = "PREPARING_APPLICATIONS"
                run_obj.current_step = "prepare_applications"

        await session.commit()

        # Sort ranked by score descending
        matched_results.sort(key=lambda x: x["overall_score"], reverse=True)

        return {
            "run_id": run_id,
            "total_evaluated": len(matched_results),
            "qualified_count": qualified_count,
            "strong_matches_count": strong_count,
            "thresholds": {
                "strong": settings.STRONG_MATCH_THRESHOLD,
                "qualified": settings.MATCH_THRESHOLD,
                "possible": settings.POSSIBLE_MATCH_THRESHOLD
            },
            "matches": matched_results
        }
