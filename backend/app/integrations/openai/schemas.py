from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SourceEvidence(BaseModel):
    url: str = Field(..., description="URL of the web source or citation")
    title: Optional[str] = Field(None, description="Title of the source webpage")
    source_type: str = Field("official_company", description="Type: official_company, job_board, professional_network, aggregator, other")
    supports: List[str] = Field(default_factory=list, description="Fields supported by this source: e.g. job_title, skills, application_url, salary")

class RecruiterResearchResult(BaseModel):
    name: Optional[str] = Field(None, description="Full name of recruiter or hiring team lead")
    title: Optional[str] = Field(None, description="Title: e.g. Technical Recruiter, Talent Partner")
    company: Optional[str] = Field(None, description="Company name")
    email: Optional[str] = Field(None, description="Verified public email if explicitly published; never guessed")
    linkedin_url: Optional[str] = Field(None, description="Public LinkedIn profile URL if verified")
    source_url: Optional[str] = Field(None, description="Evidence URL where recruiter info was discovered")
    confidence: float = Field(0.9, description="Confidence score between 0.0 and 1.0")

class JobResearchResult(BaseModel):
    title: str = Field(..., description="Official job title")
    company: str = Field(..., description="Company name")
    location: Optional[str] = Field("Remote", description="Job location")
    remote: Optional[bool] = Field(True, description="Whether remote work is permitted")
    remote_eligibility: Optional[str] = Field("Remote (India / Global)", description="Remote eligibility specifics")
    employment_type: Optional[str] = Field("Full-time", description="Employment type")
    experience_required: Optional[str] = Field(None, description="Experience requirement, e.g. 2-4 years")
    salary: Optional[str] = Field(None, description="Verified salary if explicitly published, otherwise null")
    description: Optional[str] = Field(None, description="Job summary and description")
    responsibilities: List[str] = Field(default_factory=list, description="Core responsibilities")
    required_skills: List[str] = Field(default_factory=list, description="Mandatory required skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Preferred / nice-to-have skills")
    posted_date: Optional[str] = Field(None, description="Date posted if available (YYYY-MM-DD)")
    application_url: Optional[str] = Field(None, description="Direct URL to apply on official company page")
    source_url: Optional[str] = Field(None, description="Primary source URL")
    source_title: Optional[str] = Field(None, description="Title of the source posting")
    company_url: Optional[str] = Field(None, description="Official company website URL")
    recruiter: Optional[RecruiterResearchResult] = Field(None, description="Verified recruiter info if found")
    confidence: float = Field(0.9, description="Research confidence score between 0.0 and 1.0")
    verification_status: str = Field("VERIFIED", description="VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, EXPIRED")
    evidence: List[SourceEvidence] = Field(default_factory=list, description="List of source evidence and citations")

class JobResearchResponse(BaseModel):
    jobs: List[JobResearchResult] = Field(default_factory=list, description="Extracted verified job opportunities")
    search_queries: List[str] = Field(default_factory=list, description="List of web search queries executed")
    total_found: int = Field(0, description="Total verified jobs discovered")
