from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.config.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

from sqlalchemy.types import TypeDecorator

class SafeFloat(TypeDecorator):
    impl = String
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            val_upper = value.strip().upper()
            if "HIGH" in val_upper:
                return 0.95
            elif "MED" in val_upper:
                return 0.75
            elif "LOW" in val_upper:
                return 0.50
            try:
                return float(value)
            except ValueError:
                return 0.0
        return 0.0

    def process_bind_param(self, value, dialect):
        if value is None:
            return "0.0"
        if isinstance(value, (int, float)):
            return str(float(value))
        if isinstance(value, str):
            val_upper = value.strip().upper()
            if "HIGH" in val_upper:
                return "0.95"
            elif "MED" in val_upper:
                return "0.75"
            elif "LOW" in val_upper:
                return "0.50"
            try:
                return str(float(value))
            except ValueError:
                return "0.0"
        return "0.0"

class ApplicationStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    MATCHED = "MATCHED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    RECRUITER_CONTACTED = "RECRUITER_CONTACTED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    FAILED = "FAILED"

class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, default="")
    email = Column(String(255), nullable=False, default="")
    phone = Column(String(64), nullable=True)
    location = Column(String(255), nullable=True)
    years_of_experience = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)
    
    # Structured JSON arrays
    skills = Column(JSON, default=list)
    technical_skills = Column(JSON, default=list)
    cloud_skills = Column(JSON, default=list)
    frameworks = Column(JSON, default=list)
    models = Column(JSON, default=list)
    databases = Column(JSON, default=list)
    certifications = Column(JSON, default=list)
    education = Column(JSON, default=list)
    work_experience = Column(JSON, default=list)
    projects = Column(JSON, default=list)
    preferred_roles = Column(JSON, default=list)
    preferred_locations = Column(JSON, default=list)
    remote_preference = Column(Boolean, default=True)
    work_authorization = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    resumes = relationship("Resume", back_populates="candidate", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")

class Resume(Base):
    __tablename__ = "resumes"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(64), ForeignKey("candidate_profiles.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=False)
    parsed_json = Column(JSON, default=dict)
    file_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    candidate = relationship("CandidateProfile", back_populates="resumes")
    versions = relationship("ResumeVersion", back_populates="resume", cascade="all, delete-orphan")

class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    resume_id = Column(String(64), ForeignKey("resumes.id"), nullable=False)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=True)
    version_name = Column(String(255), nullable=False)
    tailored_text = Column(Text, nullable=False)
    tailored_summary = Column(Text, nullable=True)
    highlighted_skills = Column(JSON, default=list)
    highlighted_projects = Column(JSON, default=list)
    changes_made = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    resume = relationship("Resume", back_populates="versions")

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, unique=True)
    website = Column(String(512), nullable=True)
    careers_url = Column(String(512), nullable=True)
    industry = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    jobs = relationship("Job", back_populates="company_rel")
    recruiters = relationship("Recruiter", back_populates="company_rel")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    canonical_job_id = Column(String(128), index=True)
    run_id = Column(String(64), ForeignKey("agent_runs.id"), nullable=True, index=True)
    company_id = Column(String(64), ForeignKey("companies.id"), nullable=True)
    company = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    location = Column(String(255), default="Remote")
    remote = Column(Boolean, default=True)
    employment_type = Column(String(128), default="Full-time")
    experience_required = Column(String(128), nullable=True)
    salary = Column(String(128), nullable=True)
    description = Column(Text, nullable=False, default="")
    requirements = Column(JSON, default=list)
    skills = Column(JSON, default=list)
    application_url = Column(String(1024), nullable=True)
    source_url = Column(String(1024), nullable=True)
    source_urls = Column(JSON, default=list)
    recruiter_email = Column(String(255), nullable=True)
    application_email = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    posted_date = Column(String(64), nullable=True)
    company_url = Column(String(512), nullable=True)
    verification_status = Column(String(64), default="VERIFIED") # VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, EXPIRED
    evidence = Column(JSON, default=list)
    research_provider = Column(String(128), default="openai_web_search")
    
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        if "description" not in kwargs or kwargs["description"] is None:
            kwargs["description"] = ""
        super().__init__(**kwargs)

    company_rel = relationship("Company", back_populates="jobs")
    matches = relationship("JobMatch", back_populates="job", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

class JobMatch(Base):
    __tablename__ = "job_matches"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(String(64), ForeignKey("candidate_profiles.id"), nullable=False)
    overall_score = Column(Float, nullable=False)
    skills_score = Column(Float, default=0.0)
    experience_score = Column(Float, default=0.0)
    location_score = Column(Float, default=0.0)
    role_score = Column(Float, default=0.0)
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    concerns = Column(JSON, default=list)
    recommendation = Column(String(64), default="MATCH") # STRONG_MATCH, MATCH, POSSIBLE_MATCH, REJECT
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("Job", back_populates="matches")

class Recruiter(Base):
    __tablename__ = "recruiters"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    company_id = Column(String(64), ForeignKey("companies.id"), nullable=True)
    name = Column(String(255), nullable=False)
    title = Column(String(255), default="Talent Acquisition")
    company_name = Column(String(255), nullable=False)
    public_email = Column(String(255), nullable=True)
    email_type = Column(String(64), default="RECRUITER_SPECIFIC", nullable=True) # RECRUITER_SPECIFIC, COMPANY_RECRUITING, COMPANY_GENERAL
    source_url = Column(String(1024), nullable=True)
    source_type = Column(String(64), nullable=True)
    source_evidence = Column(Text, nullable=True)
    confidence = Column(SafeFloat, default=0.0, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    linkedin_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    company_rel = relationship("Company", back_populates="recruiters")
    outreaches = relationship("OutreachMessage", back_populates="recruiter")

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("agent_runs.id"), nullable=True, index=True)
    candidate_id = Column(String(64), ForeignKey("candidate_profiles.id"), nullable=False)
    job_id = Column(String(64), ForeignKey("jobs.id"), nullable=False)
    status = Column(String(64), default="DISCOVERED")
    idempotency_key = Column(String(255), unique=True, index=True)
    applied_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    candidate = relationship("CandidateProfile", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    questions = relationship("ApplicationQuestion", back_populates="application", cascade="all, delete-orphan")
    outreach_messages = relationship("OutreachMessage", back_populates="application", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="application", cascade="all, delete-orphan")

class ApplicationQuestion(Base):
    __tablename__ = "application_questions"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    is_sensitive = Column(Boolean, default=False)
    needs_user_input = Column(Boolean, default=False)
    status = Column(String(64), default="AUTO_GENERATED")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("Application", back_populates="questions")

class OutreachMessage(Base):
    __tablename__ = "outreach_messages"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False)
    recruiter_id = Column(String(64), ForeignKey("recruiters.id"), nullable=True)
    channel = Column(String(64), default="EMAIL") # EMAIL, LINKEDIN, FOLLOW_UP
    subject = Column(String(512), nullable=True)
    body = Column(Text, nullable=False)
    recipient_email = Column(String(255), nullable=True)
    recipient_name = Column(String(255), nullable=True)
    email_status = Column(String(64), default="NOT_FOUND") # VERIFIED, UNVERIFIED, NOT_FOUND, INVALID, REJECTED, BLOCKED_INVALID_RECIPIENT
    email_source = Column(String(64), nullable=True) # job_source, job_description, application_page, official_careers_page, verified_recruiter
    email_confidence = Column(SafeFloat, default=0.0)
    recruiter_status = Column(String(64), default="NOT_FOUND") # VERIFIED, UNVERIFIED, NOT_FOUND
    status = Column(String(64), default="DRAFT") # DRAFT, APPROVED, SENT, FAILED, MANUAL_REQUIRED
    sent_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("Application", back_populates="outreach_messages")
    recruiter = relationship("Recruiter", back_populates="outreaches")

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("agent_runs.id"), nullable=True, index=True)
    application_id = Column(String(64), ForeignKey("applications.id"), nullable=False)
    status = Column(String(64), default="PENDING")
    action_type = Column(String(128), default="SUBMIT_AND_OUTREACH") # SEND_EMAIL, SUBMIT_APPLICATION, LINKEDIN_OUTREACH
    package_data = Column(JSON, default=dict)
    user_modifications = Column(JSON, default=dict)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    application = relationship("Application", back_populates="approval_requests")

    def __init__(self, **kwargs):
        valid_cols = {c.name for c in self.__table__.columns}
        valid_kwargs = {k: v for k, v in kwargs.items() if k in valid_cols}
        if "approval_type" in kwargs and "action_type" not in kwargs:
            valid_kwargs["action_type"] = kwargs["approval_type"]
        super().__init__(**valid_kwargs)

class AgentRun(Base):
    __tablename__ = "agent_runs"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    candidate_id = Column(String(64), ForeignKey("candidate_profiles.id"), nullable=True)
    user_prompt = Column(Text, nullable=False)
    search_prompt = Column(Text, nullable=True)
    status = Column(String(64), default="SEARCHING") # SEARCHING, MATCHING, PREPARING_APPLICATIONS, WAITING_FOR_APPROVAL, PARTIALLY_APPROVED, PROCESSING, COMPLETED, FAILED, CANCELLED
    current_step = Column(String(128), default="START")
    
    # Workflow & Batch Metrics
    total_jobs = Column(Integer, default=0)
    unique_jobs = Column(Integer, default=0)
    qualified_jobs = Column(Integer, default=0)
    strong_matches = Column(Integer, default=0)
    applications_prepared = Column(Integer, default=0)
    approvals_pending = Column(Integer, default=0)
    applications_approved = Column(Integer, default=0)
    applications_rejected = Column(Integer, default=0)
    
    summary = Column(JSON, default=dict)
    tokens_used = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    events = relationship("AgentEvent", back_populates="run", cascade="all, delete-orphan")

# Alias SearchRun to AgentRun for unified terminology
SearchRun = AgentRun

class AgentEvent(Base):
    __tablename__ = "agent_events"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    run_id = Column(String(64), ForeignKey("agent_runs.id"), nullable=False)
    agent_name = Column(String(128), nullable=False)
    step = Column(String(128), nullable=False)
    event_type = Column(String(64), default="INFO") # INFO, TOOL_CALL, TOOL_RESULT, DECISION, ERROR
    message = Column(Text, nullable=False)
    payload = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    run = relationship("AgentRun", back_populates="events")

class OAuthConnection(Base):
    __tablename__ = "oauth_connections"
    
    id = Column(String(64), primary_key=True, default=generate_uuid)
    provider = Column(String(64), nullable=False) # google, microsoft, linkedin
    email = Column(String(255), nullable=False)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
