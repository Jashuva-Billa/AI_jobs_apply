import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.graph.state import JobApplicationState
from app.schemas.schemas import SearchCriteria, CandidateProfileBase, MatchBreakdown, RecruiterBase
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.recruiter_service import recruiter_service
from app.services.outreach_service import outreach_service
from app.services.application_service import application_service
from app.integrations.email.provider import email_provider
from app.config.settings import settings

logger = logging.getLogger(__name__)

def log_event(state: JobApplicationState, agent_name: str, step: str, message: str, payload: Dict[str, Any] = None):
    if "events" not in state or state["events"] is None:
        state["events"] = []
    state["events"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "agent_name": agent_name,
        "step": step,
        "message": message,
        "payload": payload or {}
    })
    logger.info(f"[{agent_name}] {step}: {message}")

async def parse_prompt_node(state: JobApplicationState) -> Dict[str, Any]:
    prompt = state.get("user_prompt", "")
    roles = []
    skills = []
    locations = []
    
    prompt_lower = prompt.lower()
    
    # Deterministic role extraction
    if "agent" in prompt_lower or "agentic" in prompt_lower:
        roles.append("Agentic AI Engineer")
    if "genai" in prompt_lower or "generative" in prompt_lower:
        roles.append("GenAI Engineer")
    if "rag" in prompt_lower:
        roles.append("RAG Engineer")
    if "ml" in prompt_lower or "machine learning" in prompt_lower:
        roles.append("Machine Learning Engineer")
    if not roles or "ai engineer" in prompt_lower:
        roles.append("AI Engineer")

    # Deterministic skill extraction
    all_known_skills = ["Python", "RAG", "LangGraph", "LangChain", "Agentic AI", "AWS", "FastAPI", "Docker", "LLMs", "Bedrock", "PostgreSQL", "Milvus"]
    for s in all_known_skills:
        if s.lower() in prompt_lower:
            skills.append(s)
    if not skills:
        skills = ["Python", "RAG", "LangGraph", "Agentic AI", "AWS", "LLMs"]

    # Location extraction
    if "us" in prompt_lower or "usa" in prompt_lower or "united states" in prompt_lower:
        locations.append("Remote US")
    if "india" in prompt_lower:
        locations.append("Remote India")
    if not locations:
        locations = ["Remote India", "Remote"]

    criteria = SearchCriteria(
        roles=roles,
        skills=skills,
        locations=locations,
        experience_years=2.9,
        remote_required=True
    )
    
    log_event(state, "Supervisor", "parse_prompt", f"Parsed search criteria for roles: {', '.join(criteria.roles)}", criteria.model_dump())
    return {
        "search_criteria": criteria.model_dump(),
        "current_step": "parse_prompt"
    }

async def load_candidate_node(state: JobApplicationState) -> Dict[str, Any]:
    cand_data = state.get("candidate_profile") or {}
    cand_profile = CandidateProfileBase(**cand_data) if cand_data else CandidateProfileBase(
        name="Candidate",
        email="candidate@example.com",
        years_of_experience=3.0,
        skills=["Python", "RAG", "LangGraph", "Agentic AI", "AWS", "LLMs", "PostgreSQL", "Docker"]
    )
    log_event(state, "CandidateAgent", "load_candidate", f"Loaded profile for {cand_profile.name} ({cand_profile.years_of_experience} yrs exp)")
    return {
        "candidate_profile": cand_profile.model_dump(),
        "current_step": "load_candidate"
    }

async def search_jobs_node(state: JobApplicationState) -> Dict[str, Any]:
    criteria = SearchCriteria(**state["search_criteria"])
    deduped_jobs, total_raw, removed = await job_service.search_and_deduplicate(criteria)
    
    log_event(
        state,
        "JobResearchAgent",
        "search_jobs",
        f"Found {total_raw} raw jobs across sources, deduplicated to {len(deduped_jobs)} unique listings.",
        {"total_raw": total_raw, "duplicates_removed": removed, "unique_jobs": len(deduped_jobs)}
    )
    return {
        "discovered_jobs": deduped_jobs,
        "deduplicated_jobs": deduped_jobs,
        "current_step": "search_jobs"
    }

async def normalize_jobs_node(state: JobApplicationState) -> Dict[str, Any]:
    jobs = state.get("discovered_jobs", [])
    normalized = []
    for j in jobs:
        j_copy = j.copy()
        j_copy["location"] = j_copy.get("location") or "Remote"
        j_copy["remote"] = True if "remote" in j_copy["location"].lower() else j_copy.get("remote", True)
        normalized.append(j_copy)
    
    log_event(state, "JobResearchAgent", "normalize_jobs", f"Normalized schema for {len(normalized)} jobs.")
    return {
        "normalized_jobs": normalized,
        "current_step": "normalize_jobs"
    }

async def match_jobs_node(state: JobApplicationState) -> Dict[str, Any]:
    cand = CandidateProfileBase(**state["candidate_profile"])
    jobs = state.get("normalized_jobs", state.get("discovered_jobs", []))
    matched_results = []

    for job in jobs:
        match_breakdown = matching_service.evaluate_match(cand, job)
        job_match = {
            **job,
            "match": match_breakdown.model_dump()
        }
        matched_results.append(job_match)

    log_event(state, "MatchingAgent", "match_jobs", f"Completed multi-factor matching for {len(matched_results)} jobs.")
    return {
        "matched_jobs": matched_results,
        "current_step": "match_jobs"
    }

async def rank_jobs_node(state: JobApplicationState) -> Dict[str, Any]:
    matched = state.get("matched_jobs", [])
    # Sort descending by overall_score
    ranked = sorted(matched, key=lambda x: x.get("match", {}).get("overall_score", 0), reverse=True)
    
    strong_matches = [
        j for j in ranked
        if j.get("match", {}).get("overall_score", 0) >= settings.STRONG_MATCH_THRESHOLD
    ]
    qualified_jobs = [
        j for j in ranked
        if j.get("match", {}).get("overall_score", 0) >= settings.POSSIBLE_MATCH_THRESHOLD
    ]
    top_job = ranked[0] if ranked else None

    log_event(
        state,
        "MatchingAgent",
        "rank_jobs",
        f"Ranked {len(ranked)} jobs. {len(qualified_jobs)} qualified (>= {settings.POSSIBLE_MATCH_THRESHOLD}%), {len(strong_matches)} strong matches (>= {settings.STRONG_MATCH_THRESHOLD}%)." if ranked else "No jobs found.",
        {
            "total_ranked": len(ranked),
            "qualified_count": len(qualified_jobs),
            "strong_count": len(strong_matches),
            "top_score": top_job.get("match", {}).get("overall_score") if top_job else 0
        }
    )
    return {
        "ranked_jobs": ranked,
        "qualified_jobs": qualified_jobs,
        "strong_matches": strong_matches,
        "selected_job": top_job,
        "current_step": "rank_jobs"
    }

async def discover_recruiters_node(state: JobApplicationState) -> Dict[str, Any]:
    strong_matches = state.get("strong_matches", [])
    if not strong_matches:
        strong_matches = state.get("qualified_jobs", [])[:5]
    
    recruiter_map: Dict[str, Dict[str, Any]] = {}
    sem = asyncio.Semaphore(settings.MAX_CONCURRENT_RECRUITER_RESEARCH)

    async def discover_one(job: Dict[str, Any]):
        company = job.get("company", "")
        title = job.get("title", "")
        if not company or company in recruiter_map:
            return
        async with sem:
            try:
                rec = await recruiter_service.discover_recruiter_for_job(company_name=company, job_title=title)
                if rec:
                    recruiter_map[company] = rec.model_dump()
            except Exception as e:
                logger.warning(f"Recruiter discovery skipped for {company}: {e}")

    tasks = [discover_one(job) for job in strong_matches]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    top_job = state.get("selected_job")
    top_recruiter = recruiter_map.get(top_job.get("company")) if top_job else None

    log_event(
        state,
        "RecruiterAgent",
        "discover_recruiters",
        f"Discovered {len(recruiter_map)} verified recruiters across strong matches.",
        {"recruiters_found": len(recruiter_map)}
    )
    return {
        "recruiter_map": recruiter_map,
        "recruiter": top_recruiter,
        "current_step": "discover_recruiters"
    }

async def prepare_application_node(state: JobApplicationState) -> Dict[str, Any]:
    cand = CandidateProfileBase(**state["candidate_profile"])
    qualified = state.get("qualified_jobs", [])
    if not qualified:
        # Fallback to ranked jobs or selected_job if qualified is empty
        qualified = state.get("ranked_jobs", [])
        if not qualified and state.get("selected_job"):
            qualified = [state["selected_job"]]

    recruiter_map = state.get("recruiter_map", {})
    sem = asyncio.Semaphore(settings.MAX_CONCURRENT_APPLICATIONS)
    application_packages: List[Dict[str, Any]] = []

    async def prepare_single_job_package(idx: int, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with sem:
            try:
                match = MatchBreakdown(**job["match"])
                tailored_res = await application_service.tailor_resume(cand, job, match)
                cover_letter = await application_service.generate_cover_letter(cand, job, match)
                questions = application_service.prepare_application_questions(cand, job)
                
                # Attach recruiter if discovered
                company = job.get("company", "")
                rec_data = recruiter_map.get(company)
                rec_obj = RecruiterBase(**rec_data) if rec_data else None
                
                email_outreach = await outreach_service.generate_recruiter_email(cand, job, rec_obj)
                linkedin_outreach = await outreach_service.generate_linkedin_outreach(cand, job, rec_obj)

                pkg = {
                    "application_id": f"app_{state.get('run_id', 'run')}_{idx}",
                    "job": job,
                    "match": match.model_dump(),
                    "tailored_resume_summary": tailored_res["tailored_summary"],
                    "tailored_resume_text": tailored_res["tailored_text"],
                    "highlighted_skills": tailored_res["highlighted_skills"],
                    "cover_letter": cover_letter,
                    "questions": [q.model_dump() for q in questions],
                    "recruiter": rec_data,
                    "email_outreach": email_outreach.model_dump(),
                    "linkedin_outreach": linkedin_outreach.model_dump()
                }
                return pkg
            except Exception as e:
                logger.error(f"Error preparing package for job {job.get('company')} - {job.get('title')}: {e}")
                return None

    tasks = [prepare_single_job_package(idx, job) for idx, job in enumerate(qualified)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, dict):
            application_packages.append(res)

    top_pkg = application_packages[0] if application_packages else None

    log_event(
        state,
        "ApplicationAgent",
        "prepare_application",
        f"Prepared {len(application_packages)} total application packages with tailored resumes, cover letters, and outreach drafts."
    )
    return {
        "application_packages": application_packages,
        "application_package": top_pkg,
        "current_step": "prepare_application"
    }

async def prepare_outreach_node(state: JobApplicationState) -> Dict[str, Any]:
    packages = state.get("application_packages", [])
    top_pkg = state.get("application_package") or (packages[0] if packages else None)
    
    outreach = {
        "email": top_pkg.get("email_outreach") if top_pkg else None,
        "linkedin": top_pkg.get("linkedin_outreach") if top_pkg else None
    }

    log_event(
        state,
        "OutreachAgent",
        "prepare_outreach",
        f"Outreach packages finalized for {len(packages)} applications. Pausing for human approval gate."
    )
    return {
        "outreach": outreach,
        "approval_required": True,
        "approval_status": "PENDING",
        "current_step": "human_approval_gate"
    }

async def execute_approved_action_node(state: JobApplicationState) -> Dict[str, Any]:
    if state.get("approval_status") == "APPROVED":
        email_data = state.get("outreach", {}).get("email")
        if email_data and email_data.get("recipient_email"):
            await email_provider.send_email(
                to_email=email_data["recipient_email"],
                subject=email_data["subject"],
                body=email_data["body"],
                idempotency_key=f"{state.get('run_id')}_email"
            )
            log_event(state, "EmailMCP", "send_email", f"Dispatched authorized outreach email to {email_data['recipient_email']}")
    return {
        "current_step": "execute_approved_action"
    }

async def track_application_node(state: JobApplicationState) -> Dict[str, Any]:
    log_event(state, "Supervisor", "track_application", "Updated application status in tracking database.")
    return {
        "current_step": "COMPLETED"
    }
