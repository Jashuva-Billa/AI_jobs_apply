from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# Candidate Schemas
class WorkExperienceItem(BaseModel):
    title: str
    company: str
    duration: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)

class EducationItem(BaseModel):
    degree: str
    institution: str
    year: Optional[str] = None

class ProjectItem(BaseModel):
    name: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    link: Optional[str] = None

class CandidateProfileBase(BaseModel):
    name: str = ""
    email: str = ""
    phone: Optional[str] = None
    location: Optional[str] = None
    years_of_experience: float = 0.0
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    technical_skills: List[str] = Field(default_factory=list)
    cloud_skills: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    models: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    work_experience: List[WorkExperienceItem] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    preferred_roles: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    remote_preference: bool = True
    work_authorization: Optional[str] = None

class CandidateProfileCreate(CandidateProfileBase):
    pass

class CandidateProfileResponse(CandidateProfileBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Natural Language Prompt Search Criteria
class SearchCriteria(BaseModel):
    roles: List[str] = Field(default_factory=list, description="Target job roles, e.g. AI Engineer, GenAI Engineer")
    min_experience: int = Field(default=0, description="Minimum years of experience")
    max_experience: int = Field(default=10, description="Maximum years of experience")
    locations: List[str] = Field(default_factory=lambda: ["Remote", "India"], description="Target locations")
    remote_required: bool = Field(default=True, description="Whether remote work is required")
    skills: List[str] = Field(default_factory=list, description="Core required skills")
    active_hiring_required: bool = Field(default=True, description="Prioritize actively hiring companies")
    apply: bool = Field(default=True, description="Whether to prepare applications")
    recruiter_outreach: bool = Field(default=True, description="Whether to discover recruiters and prepare outreach")

class AgentPromptRequest(BaseModel):
    prompt: str = Field(..., description="Natural language job search and application instruction")
    candidate_id: Optional[str] = None
    auto_approve_threshold: Optional[float] = None

# Job Schemas
class JobBase(BaseModel):
    company: str
    title: str
    location: str = "Remote"
    remote: bool = True
    employment_type: str = "Full-time"
    experience_required: Optional[str] = None
    salary: Optional[str] = None
    description: str
    requirements: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    application_url: Optional[str] = None
    source_url: Optional[str] = None
    source_urls: List[str] = Field(default_factory=list)
    posted_date: Optional[str] = None
    company_url: Optional[str] = None
    verification_status: str = "VERIFIED" # VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, EXPIRED
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    research_provider: str = "openai_web_search"

class JobResponse(JobBase):
    id: str
    canonical_job_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class MatchBreakdown(BaseModel):
    overall_score: float
    skills_score: float
    experience_score: float
    location_score: float
    role_score: float
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommendation: str # STRONG_MATCH, MATCH, POSSIBLE_MATCH, REJECT
    reasoning: Optional[str] = None

class JobWithMatchResponse(JobResponse):
    match: Optional[MatchBreakdown] = None
    recruiter: Optional[Dict[str, Any]] = None
    application_id: Optional[str] = None
    status: Optional[str] = None

# Recruiter Schemas
class RecruiterBase(BaseModel):
    name: str
    title: str = "Technical Recruiter"
    company_name: str
    public_email: Optional[str] = None
    linkedin_url: Optional[str] = None
    source_evidence: Optional[str] = None

class RecruiterResponse(RecruiterBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# Outreach Schemas
class OutreachMessageBase(BaseModel):
    channel: str = "EMAIL" # EMAIL, LINKEDIN, FOLLOW_UP
    subject: Optional[str] = None
    body: str
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None

class OutreachMessageResponse(OutreachMessageBase):
    id: str
    application_id: str
    recruiter_id: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Application Question Schemas
class ApplicationQuestionSchema(BaseModel):
    id: Optional[str] = None
    question: str
    answer: Optional[str] = None
    is_sensitive: bool = False
    needs_user_input: bool = False
    status: str = "AUTO_GENERATED"

# Application Package for Approval
class ApplicationPackage(BaseModel):
    application_id: str
    job: JobResponse
    match: MatchBreakdown
    recruiter: Optional[RecruiterResponse] = None
    tailored_resume_summary: Optional[str] = None
    tailored_resume_text: Optional[str] = None
    highlighted_skills: List[str] = Field(default_factory=list)
    cover_letter: Optional[str] = None
    questions: List[ApplicationQuestionSchema] = Field(default_factory=list)
    email_outreach: Optional[OutreachMessageBase] = None
    linkedin_outreach: Optional[OutreachMessageBase] = None

class ApprovalDecisionRequest(BaseModel):
    decision: str = "APPROVE" # APPROVE, REJECT, MODIFY
    modified_recipient_email: Optional[str] = None
    modified_email_subject: Optional[str] = None
    modified_email_body: Optional[str] = None
    modified_linkedin_body: Optional[str] = None
    modified_answers: Optional[Dict[str, str]] = None
    send_email: bool = True
    open_linkedin_tab: bool = False

# Application Response
class ApplicationResponse(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    status: str
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None
    job: Optional[JobResponse] = None
    match: Optional[MatchBreakdown] = None
    recruiter: Optional[RecruiterResponse] = None
    outreaches: List[OutreachMessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BulkApprovalDecisionRequest(BaseModel):
    approval_ids: List[str] = Field(..., description="List of approval request IDs to process")
    decision: str = Field("APPROVE", description="Decision: APPROVE or REJECT")
    send_email: bool = Field(True, description="Whether to dispatch verified outreach email upon approval")
    modified_answers: Optional[Dict[str, str]] = None

# Agent Observability
class AgentEventResponse(BaseModel):
    id: str
    run_id: str
    agent_name: str
    step: str
    event_type: str
    message: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime

    class Config:
        from_attributes = True

class AgentRunResponse(BaseModel):
    id: str
    candidate_id: Optional[str] = None
    user_prompt: str
    search_prompt: Optional[str] = None
    status: str
    current_step: str
    total_jobs: int = 0
    unique_jobs: int = 0
    qualified_jobs: int = 0
    strong_matches: int = 0
    applications_prepared: int = 0
    approvals_pending: int = 0
    applications_approved: int = 0
    applications_rejected: int = 0
    summary: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = 0
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    events: List[AgentEventResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True

# Analytics Dashboard
class DashboardStats(BaseModel):
    jobs_found: int = 0
    strong_matches: int = 0
    applications: int = 0
    recruiters_found: int = 0
    emails_sent: int = 0
    responses: int = 0
    interviews: int = 0
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    role_distribution: Dict[str, int] = Field(default_factory=dict)
    score_distribution: Dict[str, int] = Field(default_factory=dict)
    recent_runs: List[Dict[str, Any]] = Field(default_factory=list)
