from typing import TypedDict, List, Dict, Any, Optional
from app.schemas.schemas import (
    SearchCriteria,
    CandidateProfileBase,
    JobBase,
    MatchBreakdown,
    RecruiterBase,
    OutreachMessageBase,
    ApplicationPackage
)

class JobApplicationState(TypedDict):
    run_id: str
    user_prompt: str
    search_criteria: Dict[str, Any]
    candidate_profile: Dict[str, Any]
    discovered_jobs: List[Dict[str, Any]]
    normalized_jobs: List[Dict[str, Any]]
    deduplicated_jobs: List[Dict[str, Any]]
    matched_jobs: List[Dict[str, Any]]
    ranked_jobs: List[Dict[str, Any]]
    qualified_jobs: List[Dict[str, Any]]
    strong_matches: List[Dict[str, Any]]
    application_packages: List[Dict[str, Any]]
    recruiter_map: Dict[str, Dict[str, Any]]
    selected_job: Optional[Dict[str, Any]]
    recruiter: Optional[Dict[str, Any]]
    application_package: Optional[Dict[str, Any]]
    outreach: Optional[Dict[str, Any]]
    approval_required: bool
    approval_status: str # PENDING, APPROVED, REJECTED
    errors: List[str]
    current_step: str
    events: List[Dict[str, Any]]
