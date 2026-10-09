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
from app.models.entities import Job, AgentRun, CandidateProfile, JobMatch
from app.schemas.schemas import SearchCriteria
from app.services.job_service import job_service

logger = logging.getLogger(__name__)

async def search_jobs(
    query: str,
    location: Optional[str] = "India",
    remote: Optional[bool] = True,
    seniority: Optional[str] = "mid",
    max_results: Optional[int] = 100,
    candidate_id: Optional[str] = None,
    email_only: Optional[bool] = True
) -> Dict[str, Any]:
    """
    Executes live multi-source job search (RemoteOK, Arbeitnow, DuckDuckGo career pages).
    Creates a durable SearchRun in SQL and persists all discovered jobs with run_id.
    Never invents synthetic jobs.
    If email_only=True, only jobs with a verified public recruiter/company email are
    persisted and returned; jobs without a verified recipient are excluded before
    application preparation.
    """
    run_id = str(uuid.uuid4())
    
    async with AsyncSessionLocal() as session:
        # Resolve candidate
        if candidate_id:
            cand = await session.get(CandidateProfile, candidate_id)
        else:
            res = await session.execute(select(CandidateProfile).limit(1))
            cand = res.scalars().first()
            
        cand_id = cand.id if cand else "default_candidate"

        # Create durable AgentRun record
        run_record = AgentRun(
            id=run_id,
            candidate_id=cand_id,
            user_prompt=query,
            search_prompt=query,
            status="SEARCHING",
            current_step="search_jobs"
        )
        session.add(run_record)
        await session.commit()

        # Build search criteria
        criteria = SearchCriteria(
            roles=[query] if query else ["AI Engineer", "GenAI Engineer", "RAG Engineer"],
            skills=["Python", "RAG", "LangGraph", "FastAPI", "AWS Bedrock", "Milvus"],
            locations=[location] if location else ["Remote India", "Hyderabad"],
            experience_years=2.9,
            remote_required=remote if remote is not None else True
        )

        # Execute live search & deduplication
        dedup_jobs, total_raw, duplicates_removed = await job_service.search_and_deduplicate(criteria)
        
        # Resolve recipient emails BEFORE persisting jobs when email_only is enabled.
        # Jobs without a verified recipient never reach matching/application/HITL.
        from app.services.email_resolution_service import extract_emails_from_text, verify_email_for_job, RecipientClassification, is_valid_email_format
        from app.services.recruiter_service import KNOWN_RECRUITERS, recruiter_service
        import asyncio

        async def resolve_job_email(job: Dict[str, Any]) -> Optional[str]:
            direct = job.get("recruiter_email") or job.get("application_email") or job.get("contact_email") or job.get("email")
            if direct and is_valid_email_format(direct):
                ok, cls, _, _ = verify_email_for_job(direct, job, source_type="job_source")
                if ok and cls in (RecipientClassification.VERIFIED, RecipientClassification.DOMAIN_MATCH_ONLY):
                    return direct.strip().lower()
            evidence = await recruiter_service._discover_public_company_email(job)
            return evidence["email"] if evidence else None

        if email_only:
            sem = asyncio.Semaphore(10)

            async def guarded(job: Dict[str, Any]) -> tuple[Dict[str, Any], Optional[str]]:
                async with sem:
                    try:
                        return job, await resolve_job_email(job)
                    except Exception as e:
                        logger.debug("Email-only screening failed for %s: %s", job.get("company"), e)
                        return job, None

            resolved = await asyncio.gather(*(guarded(j) for j in dedup_jobs))
            email_jobs = []
            for job, email in resolved:
                if email:
                    job = dict(job)
                    job["recruiter_email"] = email
                    email_jobs.append(job)
            capped_jobs = email_jobs[:max_results] if max_results else email_jobs
        else:
            capped_jobs = dedup_jobs[:max_results] if max_results else dedup_jobs

        # Persist jobs associated with run_id in SQL
        persisted_jobs_list = []
        for j in capped_jobs:
            canonical_id = j.get("canonical_job_id") or str(uuid.uuid4())
            job_id = str(uuid.uuid4())
            company_name = j.get("company", "Company")
            desc_text = j.get("description", "")
            rec_email = j.get("recruiter_email") or j.get("application_email") or j.get("contact_email")
            if not rec_email:
                for kn_comp, kn_data in KNOWN_RECRUITERS.items():
                    if kn_comp.lower() == company_name.lower() or (len(company_name) > 4 and company_name.lower() in kn_comp.lower()):
                        rec_email = kn_data.get("public_email")
                        break
            if not rec_email and desc_text:
                for em in extract_emails_from_text(desc_text):
                    is_val, classification, _, _ = verify_email_for_job(em, {"company": company_name, "company_url": j.get("company_url")})
                    if is_val and classification in [RecipientClassification.VERIFIED, RecipientClassification.DOMAIN_MATCH_ONLY]:
                        rec_email = em
                        break

            job_entity = Job(
                id=job_id,
                canonical_job_id=canonical_id,
                run_id=run_id,
                company=company_name,
                title=j.get("title", "Role"),
                location=j.get("location", "Remote"),
                remote=j.get("remote", True),
                employment_type=j.get("employment_type", "Full-time"),
                experience_required=j.get("experience_required", "2-3 years"),
                salary=j.get("salary"),
                description=desc_text,
                requirements=j.get("requirements", []),
                skills=j.get("skills", []),
                application_url=j.get("application_url") or j.get("source_url"),
                source_url=j.get("source_url") or j.get("application_url"),
                source_urls=j.get("source_urls", []),
                posted_date=j.get("posted_date"),
                company_url=j.get("company_url"),
                recruiter_email=rec_email,
                verification_status=j.get("verification_status", "VERIFIED"),
                evidence=j.get("evidence", [])
            )
            session.add(job_entity)
            
            persisted_jobs_list.append({
                "job_id": job_id,
                "canonical_job_id": canonical_id,
                "title": job_entity.title,
                "company": job_entity.company,
                "location": job_entity.location,
                "remote": job_entity.remote,
                "employment_type": job_entity.employment_type,
                "experience_required": job_entity.experience_required,
                "salary": job_entity.salary,
                "skills": job_entity.skills,
                "application_url": job_entity.application_url,
                "source_url": job_entity.source_url,
                "posted_date": job_entity.posted_date,
                "recruiter_email": rec_email,
                "verification_status": job_entity.verification_status
            })

        # Update run metrics
        run_record.total_jobs = total_raw
        run_record.unique_jobs = len(persisted_jobs_list)
        run_record.status = "MATCHING"
        run_record.current_step = "match_jobs"
        await session.commit()

        return {
            "search_id": run_id,
            "run_id": run_id,
            "candidate_id": cand_id,
            "total_raw_found": total_raw,
            "unique_jobs_count": len(persisted_jobs_list),
            "jobs": persisted_jobs_list
        }

async def get_search_run(run_id: str) -> Dict[str, Any]:
    """
    Retrieves the durable SearchRun status, timestamps, and job processing counts from SQL.
    """
    async with AsyncSessionLocal() as session:
        run = await session.get(AgentRun, run_id)
        if not run:
            return {"error": "SearchRun not found", "run_id": run_id}

        return {
            "run_id": run.id,
            "candidate_id": run.candidate_id,
            "prompt": run.search_prompt or run.user_prompt,
            "status": run.status,
            "current_step": run.current_step,
            "total_jobs": run.total_jobs,
            "unique_jobs": run.unique_jobs,
            "qualified_jobs": run.qualified_jobs,
            "strong_matches": run.strong_matches,
            "applications_prepared": run.applications_prepared,
            "approvals_pending": run.approvals_pending,
            "applications_approved": run.applications_approved,
            "applications_rejected": run.applications_rejected,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None
        }

async def get_search_results(run_id: str, page: int = 1, page_size: int = 100) -> Dict[str, Any]:
    """
    Retrieves paginated jobs and match evaluation records for a given search run.
    """
    async with AsyncSessionLocal() as session:
        offset = (page - 1) * page_size
        stmt = select(Job).filter_by(run_id=run_id).offset(offset).limit(page_size)
        res = await session.execute(stmt)
        jobs = res.scalars().all()

        job_ids = [j.id for j in jobs]
        matches_map = {}
        if job_ids:
            m_res = await session.execute(select(JobMatch).where(JobMatch.job_id.in_(job_ids)))
            for m in m_res.scalars().all():
                matches_map[m.job_id] = m

        results = []
        for j in jobs:
            match_obj = matches_map.get(j.id)
            results.append({
                "job_id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "remote": j.remote,
                "experience_required": j.experience_required,
                "application_url": j.application_url,
                "source_url": j.source_url,
                "verification_status": j.verification_status,
                "match_score": match_obj.overall_score if match_obj else None,
                "classification": match_obj.recommendation if match_obj else None
            })

        return {
            "run_id": run_id,
            "page": page,
            "page_size": page_size,
            "count": len(results),
            "results": results
        }

async def get_job_details(job_id: str) -> Dict[str, Any]:
    """
    [READ-ONLY] Retrieve full details, description, requirements, skills, and evidence for a specific job ID.
    """
    async with AsyncSessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:
            return {
                "status": "NOT_FOUND",
                "message": f"Job with ID '{job_id}' not found."
            }

        # Fetch match if available
        m_res = await session.execute(select(JobMatch).filter_by(job_id=job_id).limit(1))
        match_obj = m_res.scalars().first()

        return {
            "status": "FOUND",
            "job_id": job.id,
            "canonical_job_id": job.canonical_job_id,
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "remote": job.remote,
            "employment_type": job.employment_type,
            "experience_required": job.experience_required,
            "salary": job.salary,
            "description": job.description,
            "requirements": job.requirements or [],
            "skills": job.skills or [],
            "application_url": job.application_url,
            "source_url": job.source_url,
            "verification_status": job.verification_status,
            "evidence": job.evidence or [],
            "match": {
                "overall_score": match_obj.overall_score,
                "skills_score": match_obj.skills_score,
                "experience_score": match_obj.experience_score,
                "location_score": match_obj.location_score,
                "role_score": match_obj.role_score,
                "matched_skills": match_obj.matched_skills or [],
                "missing_skills": match_obj.missing_skills or [],
                "recommendation": match_obj.recommendation
            } if match_obj else None
        }

