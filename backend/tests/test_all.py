import pytest
import asyncio
from app.schemas.schemas import CandidateProfileBase, SearchCriteria, MatchBreakdown
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.recruiter_service import recruiter_service
from app.services.application_service import application_service, QuestionClassification
from app.services.outreach_service import outreach_service
from app.services.resume_service import resume_service
from app.integrations.email.provider import SMTPEmailProvider

@pytest.fixture
def sample_candidate():
    return CandidateProfileBase(
        name="Alex Morgan",
        email="alex.morgan.ai@example.com",
        years_of_experience=3.5,
        skills=["Python", "RAG", "LangGraph", "Agentic AI", "AWS", "LLMs", "PostgreSQL"],
        technical_skills=["Python", "FastAPI", "Docker"],
        cloud_skills=["AWS"],
        frameworks=["LangGraph"],
        preferred_roles=["AI Engineer", "GenAI Engineer"],
        remote_preference=True,
        work_authorization="Authorized for remote worldwide contractor employment"
    )

@pytest.fixture
def sample_job():
    return {
        "company": "Anthropic AI Labs",
        "title": "Senior AI Systems Engineer",
        "location": "Remote",
        "remote": True,
        "experience_required": "3-5 years",
        "skills": ["Python", "RAG", "LangGraph", "AWS", "LLMs", "MCP"],
        "requirements": ["3+ years Python", "Experience with RAG and LangGraph"]
    }

def test_resume_parsing_heuristics():
    raw_resume = """
    Alex Morgan
    Email: alex.morgan.ai@example.com | Phone: +91 98765 43210
    Location: Bangalore, India
    
    Professional Summary
    AI Systems Engineer with 3.5 years of experience in Python, LangGraph, RAG, and AWS.
    
    Skills: Python, RAG, LangGraph, AWS, LLMs, Docker, FastAPI
    """
    profile = resume_service._heuristic_parse_candidate(raw_resume, "resume.txt")
    assert profile.name == "Alex Morgan"
    assert "alex.morgan" in profile.email
    assert profile.years_of_experience == 3.5
    assert "Python" in profile.skills
    assert "LangGraph" in profile.skills

def test_search_criteria_generation():
    criteria = SearchCriteria(
        roles=["AI Engineer", "GenAI Engineer"],
        min_experience=2,
        max_experience=4,
        locations=["India", "Remote"],
        remote_required=True,
        skills=["Python", "RAG", "LangGraph", "AWS"]
    )
    assert len(criteria.roles) == 2
    assert criteria.remote_required is True

def test_canonical_id_deduplication():
    id1 = job_service.generate_canonical_id("ScaleGen AI", "GenAI Engineer", "Remote")
    id2 = job_service.generate_canonical_id("scalegen ai", "genai-engineer", "remote")
    assert id1 == id2, "Canonical ID should normalize punctuation, case, and whitespace"

def test_matching_scoring_deterministic(sample_candidate, sample_job):
    match = matching_service.evaluate_match(sample_candidate, sample_job)
    assert match.overall_score >= 80.0
    assert match.recommendation in ["STRONG_MATCH", "MATCH"]
    assert "Python" in match.matched_skills
    assert "LangGraph" in match.matched_skills
    assert match.skills_score > 0
    assert match.experience_score > 0
    assert match.location_score == 100.0

def test_application_question_classifications(sample_candidate, sample_job):
    questions = application_service.prepare_application_questions(sample_candidate, sample_job)
    
    # 1. SAFE_FACTUAL question
    python_q = next(q for q in questions if "python" in q.question.lower())
    assert python_q.is_sensitive is False
    assert python_q.needs_user_input is False
    assert python_q.status == "SAFE_FACTUAL"
    assert "3.5" in python_q.answer

    # 2. NEEDS_USER_INPUT question
    salary_q = next(q for q in questions if "salary" in q.question.lower() or "compensation" in q.question.lower())
    assert salary_q.is_sensitive is False
    assert salary_q.needs_user_input is True
    assert salary_q.status == "NEEDS_USER_INPUT"

    # 3. SENSITIVE question
    auth_q = next(q for q in questions if "authorization" in q.question.lower() or "sponsorship" in q.question.lower())
    assert auth_q.is_sensitive is True
    assert auth_q.needs_user_input is True
    assert auth_q.status == "SENSITIVE"

@pytest.mark.asyncio
async def test_factual_resume_tailoring_zero_hallucination(sample_candidate, sample_job):
    match = matching_service.evaluate_match(sample_candidate, sample_job)
    tailored = await application_service.tailor_resume(sample_candidate, sample_job, match)
    
    assert tailored["version_name"] is not None
    # Verify only candidate's actual skills are highlighted
    for skill in tailored["highlighted_skills"]:
        assert skill in sample_candidate.skills

@pytest.mark.asyncio
async def test_recruiter_discovery_zero_hallucination():
    recruiter = await recruiter_service.discover_recruiter_for_job("ScaleGen AI", "GenAI Engineer")
    assert recruiter is not None
    assert "ScaleGen" in recruiter.company_name
    assert recruiter.source_evidence is not None

@pytest.mark.asyncio
async def test_email_idempotency_protection():
    provider = SMTPEmailProvider()
    key = "candidate_123_job_456_email"
    
    res1 = await provider.send_email("recruiter@example.com", "Application", "Body", idempotency_key=key)
    assert res1["status"] == "SENT"

    # Repeated send with identical idempotency key must not duplicate
    res2 = await provider.send_email("recruiter@example.com", "Application", "Body", idempotency_key=key)
    assert res2["status"] == "ALREADY_SENT"

@pytest.mark.asyncio
async def test_outreach_generation_conciseness(sample_candidate, sample_job):
    recruiter = await recruiter_service.discover_recruiter_for_job("Anthropic AI Labs", "Senior AI Systems Engineer")
    email = await outreach_service.generate_recruiter_email(sample_candidate, sample_job, recruiter)
    assert "Anthropic" in email.subject or "Application" in email.subject
    assert len(email.body) > 30

    linkedin = await outreach_service.generate_linkedin_outreach(sample_candidate, sample_job, recruiter)
    assert len(linkedin.body) <= 300, "LinkedIn message should stay under 300 characters for connection note"
