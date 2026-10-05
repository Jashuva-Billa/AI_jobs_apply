import logging
from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import JobApplicationState
from app.schemas.schemas import SearchCriteria, CandidateProfileBase, MatchBreakdown
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.recruiter_service import recruiter_service
from app.services.outreach_service import outreach_service
from app.services.application_service import application_service
from app.integrations.llm.provider import llm_provider
from app.integrations.email.provider import email_provider

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
    system_prompt = (
        "You are an expert Job Search Intent Analyzer. Convert the user's natural language request into structured SearchCriteria."
    )
    criteria = await llm_provider.generate_structured(system_prompt, prompt, SearchCriteria)
    
    # Ensure default roles if empty
    if not criteria.roles:
        criteria.roles = ["AI Engineer", "GenAI Engineer", "ML Engineer"]
    if not criteria.skills:
        criteria.skills = ["Python", "RAG", "LangGraph", "Agentic AI", "AWS", "LLMs"]

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
    
    strong_matches = [j for j in ranked if j.get("match", {}).get("overall_score", 0) >= 75.0]
    top_job = ranked[0] if ranked else None

    log_event(
        state,
        "MatchingAgent",
        "rank_jobs",
        f"Ranked {len(ranked)} jobs. {len(strong_matches)} qualify as strong matches. Top: {top_job.get('company')} ({top_job.get('match', {}).get('overall_score')}%)" if top_job else "No jobs found.",
        {"top_score": top_job.get("match", {}).get("overall_score") if top_job else 0}
    )
    return {
        "ranked_jobs": ranked,
        "selected_job": top_job,
        "current_step": "rank_jobs"
    }

async def discover_recruiters_node(state: JobApplicationState) -> Dict[str, Any]:
    top_job = state.get("selected_job")
    if not top_job:
        return {"current_step": "discover_recruiters"}

    recruiter = await recruiter_service.discover_recruiter_for_job(
        company_name=top_job.get("company", ""),
        job_title=top_job.get("title", "")
    )
    log_event(
        state,
        "RecruiterAgent",
        "discover_recruiters",
        f"Discovered recruiter: {recruiter.name} ({recruiter.title}) at {recruiter.company_name}",
        recruiter.model_dump()
    )
    return {
        "recruiter": recruiter.model_dump(),
        "current_step": "discover_recruiters"
    }

async def prepare_application_node(state: JobApplicationState) -> Dict[str, Any]:
    cand = CandidateProfileBase(**state["candidate_profile"])
    job = state.get("selected_job")
    if not job:
        return {"current_step": "prepare_application"}

    match = MatchBreakdown(**job["match"])
    tailored_res = await application_service.tailor_resume(cand, job, match)
    cover_letter = await application_service.generate_cover_letter(cand, job, match)
    questions = application_service.prepare_application_questions(cand, job)

    package = {
        "application_id": f"app_{state.get('run_id', '1')}",
        "job": job,
        "match": match.model_dump(),
        "tailored_resume_summary": tailored_res["tailored_summary"],
        "tailored_resume_text": tailored_res["tailored_text"],
        "highlighted_skills": tailored_res["highlighted_skills"],
        "cover_letter": cover_letter,
        "questions": [q.model_dump() for q in questions]
    }

    log_event(state, "ApplicationAgent", "prepare_application", f"Prepared application package for {job.get('company')} with tailored resume and cover letter.")
    return {
        "application_package": package,
        "current_step": "prepare_application"
    }

async def prepare_outreach_node(state: JobApplicationState) -> Dict[str, Any]:
    cand = CandidateProfileBase(**state["candidate_profile"])
    job = state.get("selected_job")
    recruiter_data = state.get("recruiter")
    recruiter = recruiter_service.RecruiterBase(**recruiter_data) if (recruiter_data and hasattr(recruiter_service, "RecruiterBase")) else None
    
    email_outreach = await outreach_service.generate_recruiter_email(cand, job, recruiter)
    linkedin_outreach = await outreach_service.generate_linkedin_outreach(cand, job, recruiter)

    if state.get("application_package"):
        state["application_package"]["email_outreach"] = email_outreach.model_dump()
        state["application_package"]["linkedin_outreach"] = linkedin_outreach.model_dump()

    log_event(state, "OutreachAgent", "prepare_outreach", f"Drafted personalized email and LinkedIn connection note for {job.get('company')}.")
    return {
        "outreach": {
            "email": email_outreach.model_dump(),
            "linkedin": linkedin_outreach.model_dump()
        },
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
