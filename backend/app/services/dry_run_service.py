import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.schemas import CandidateProfileBase, CandidateProfileResponse, RecruiterBase
from app.services.matching_service import matching_service
from app.services.recruiter_service import recruiter_service
from app.services.outreach_service import outreach_service
from app.services.application_service import application_service
from app.services.email_resolution_service import (
    email_resolution_service,
    verify_email_for_job,
    validate_recipient_before_send,
    RecipientClassification
)
from app.services.duplicate_protection import duplicate_protection
from app.models.entities import CandidateProfile, Job, Application, ApplicationStatus

logger = logging.getLogger(__name__)

# Key skill tokens for Fresh-Job AI Relevance Filtering
AI_CORE_KEYWORDS = {
    "python", "genai", "generative ai", "rag", "agentic", "agent", "langgraph",
    "langchain", "llm", "mcp", "bedrock", "vector", "fastapi", "mlops", "aws"
}

def is_ai_engineer_relevant(job: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Evaluates if the job matches the core AI/GenAI/Agentic candidate focus."""
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "").lower()
    skills = [s.lower() for s in job.get("skills", [])]
    combined_text = f"{title} {desc} {' '.join(skills)}"

    matched = [kw for kw in AI_CORE_KEYWORDS if kw in combined_text]
    # Relevant if title has AI/ML/GenAI/Agent/LLM/RAG/Python or matched multiple core skills
    is_rel = (
        any(k in title for k in ["ai", "genai", "machine learning", "ml", "llm", "rag", "agent", "python", "software"])
        and len(matched) >= 2
    )
    return is_rel, matched

class DryRunService:
    """Orchestrates production dry-run simulations with full audit metrics and zero dispatches."""

    async def execute_dry_run(
        self,
        jobs: List[Dict[str, Any]],
        candidate_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Runs the entire job application pipeline in safe DRY_RUN mode."""
        from app.config.database import AsyncSessionLocal
        
        should_close_session = False
        if session is None:
            session = AsyncSessionLocal()
            should_close_session = True

        try:
            # 1. Fetch Candidate Profile
            cand = None
            if candidate_id:
                cand = await session.get(CandidateProfile, candidate_id)
            if not cand:
                res = await session.execute(select(CandidateProfile).limit(1))
                cand = res.scalars().first()

            if not cand:
                cand_dict = {
                    "id": "cand_dry_run",
                    "name": "Jashuva Billa",
                    "email": "jashuvabilla@gmail.com",
                    "years_of_experience": 2.9,
                    "skills": ["Python", "LangGraph", "RAG", "Agentic AI", "FastAPI", "AWS Bedrock"],
                    "work_experience": [],
                    "projects": []
                }
            else:
                cand_dict = {c.name: getattr(cand, c.name) for c in cand.__table__.columns}

            cand_schema = CandidateProfileBase(**cand_dict)

            # Metrics accumulators
            total_jobs = len(jobs)
            relevant_jobs_count = 0
            irrelevant_jobs_count = 0
            already_applied_count = 0
            new_jobs_count = 0

            verified_emails_count = 0
            domain_match_only_count = 0
            unverified_emails_count = 0
            not_found_emails_count = 0
            rejected_emails_count = 0

            ready_for_approval_count = 0
            blocked_count = 0

            dry_run_items: List[Dict[str, Any]] = []

            for job in jobs:
                job_id = job.get("id") or str(uuid.uuid4())
                company = job.get("company", "Target Company")
                title = job.get("title", "AI Engineer")

                # Relevance Check
                is_rel, matched_kws = is_ai_engineer_relevant(job)
                if not is_rel:
                    irrelevant_jobs_count += 1
                else:
                    relevant_jobs_count += 1

                # Duplicate Check
                is_dup, existing_app_id, dup_reason = await duplicate_protection.check_duplicate_job(
                    session, cand_dict.get("id", ""), job
                )
                if is_dup:
                    already_applied_count += 1
                    status_flag = "SKIPPED_ALREADY_PROCESSED"
                else:
                    new_jobs_count += 1
                    status_flag = "NEW"

                # Match Evaluation
                match_breakdown = matching_service.evaluate_match(cand_schema, job)

                # Contact Discovery & Resolution
                if is_rel:
                    if job.get("recruiter_name") or job.get("recruiter_email"):
                        rec_base = RecruiterBase(
                            name=job.get("recruiter_name") or "Hiring Team",
                            title=job.get("recruiter_title") or "Technical Recruiter",
                            company_name=company,
                            public_email=job.get("recruiter_email")
                        )
                    else:
                        rec_base = await recruiter_service.discover_recruiter_for_job(company, title)
                else:
                    rec_base = None
                resolution = email_resolution_service.resolve_recruiter_contact(job, rec_base)

                # Count classifications
                if resolution.status == RecipientClassification.VERIFIED:
                    verified_emails_count += 1
                elif resolution.status == RecipientClassification.DOMAIN_MATCH_ONLY:
                    domain_match_only_count += 1
                elif resolution.status == RecipientClassification.UNVERIFIED:
                    unverified_emails_count += 1
                elif resolution.status == RecipientClassification.NOT_FOUND:
                    not_found_emails_count += 1
                elif resolution.status == RecipientClassification.REJECTED:
                    rejected_emails_count += 1

                # Final Pre-Send Safety Gate Check
                is_allowed, safety_status, block_reason = validate_recipient_before_send(
                    job, resolution.email, resolution.status, resolution.source, cand_dict.get("id", "")
                )

                if is_allowed and not is_dup and is_rel:
                    ready_for_approval_count += 1
                    app_state = "READY_TO_SEND" if resolution.status == RecipientClassification.VERIFIED else "PREPARED"
                else:
                    blocked_count += 1
                    app_state = "BLOCKED_INVALID_RECIPIENT" if not is_allowed else ("SKIPPED_ALREADY_PROCESSED" if is_dup else "IRRELEVANT")

                # Structured Audit Log
                logger.info(
                    f"\n[DRY_RUN AUDIT]\n"
                    f"JOB_ID={job_id}\n"
                    f"CANONICAL_JOB_ID={job.get('canonical_job_id')}\n"
                    f"COMPANY={company}\n"
                    f"JOB_TITLE={title}\n"
                    f"MATCH_SCORE={match_breakdown.overall_score}\n"
                    f"RECRUITER_NAME={resolution.recruiter_name}\n"
                    f"RECRUITER_STATUS={resolution.recruiter_status}\n"
                    f"RECRUITER_EMAIL={resolution.email}\n"
                    f"EMAIL_STATUS={resolution.status}\n"
                    f"EMAIL_SOURCE={resolution.source}\n"
                    f"EMAIL_CONFIDENCE={resolution.confidence:.2f}\n"
                    f"SEND_ALLOWED={is_allowed}\n"
                    f"BLOCK_REASON={block_reason if not is_allowed else 'NONE'}\n"
                    f"APPLICATION_STATE={app_state}\n"
                    f"DRY_RUN=TRUE (NO EMAILS DISPATCHED)\n"
                    f"-----------------------------------------"
                )

                dry_run_items.append({
                    "job_id": job_id,
                    "company": company,
                    "title": title,
                    "match_score": match_breakdown.overall_score,
                    "relevant": is_rel,
                    "matched_keywords": matched_kws,
                    "duplicate": is_dup,
                    "recruiter_name": resolution.recruiter_name or "Hiring Team",
                    "recruiter_status": resolution.recruiter_status,
                    "recruiter_email": resolution.email,
                    "email_status": resolution.status,
                    "email_source": resolution.source,
                    "email_confidence": round(resolution.confidence, 2),
                    "send_allowed": is_allowed,
                    "safety_status": safety_status,
                    "block_reason": block_reason if not is_allowed else None,
                    "application_state": app_state,
                    "dry_run": True
                })

            report = {
                "dry_run": True,
                "total_jobs_processed": total_jobs,
                "relevant_jobs": relevant_jobs_count,
                "irrelevant_jobs": irrelevant_jobs_count,
                "already_applied_jobs": already_applied_count,
                "new_jobs": new_jobs_count,
                "verified_emails": verified_emails_count,
                "domain_match_only_emails": domain_match_only_count,
                "unverified_emails": unverified_emails_count,
                "not_found_emails": not_found_emails_count,
                "rejected_emails": rejected_emails_count,
                "applications_ready_for_approval": ready_for_approval_count,
                "applications_blocked": blocked_count,
                "items": dry_run_items,
                "disclaimer": "NO EMAILS WERE SENT DURING DRY-RUN."
            }

            return report

        finally:
            if should_close_session:
                await session.close()

dry_run_service = DryRunService()
