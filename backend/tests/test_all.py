import pytest
import asyncio
from app.schemas.schemas import CandidateProfileBase, SearchCriteria, MatchBreakdown
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.recruiter_service import recruiter_service
from app.services.application_service import application_service
from app.services.outreach_service import outreach_service
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
        remote_preference=True
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

def test_safe_vs_sensitive_questions(sample_candidate, sample_job):
    questions = application_service.prepare_application_questions(sample_candidate, sample_job)
    
    # Safe question
    python_q = next(q for q in questions if "python" in q.question.lower())
    assert python_q.is_sensitive is False
    assert python_q.needs_user_input is False
    assert "3.5" in python_q.answer

    # Sensitive question
    salary_q = next(q for q in questions if "salary" in q.question.lower())
    assert salary_q.is_sensitive is True
    assert salary_q.needs_user_input is True

@pytest.mark.asyncio
async def test_recruiter_discovery_zero_hallucination():
    recruiter = await recruiter_service.discover_recruiter_for_job("ScaleGen AI", "GenAI Engineer")
    assert recruiter is not None
    assert "ScaleGen" in recruiter.company_name
    assert recruiter.source_evidence is not None

@pytest.mark.asyncio
async def test_email_idempotency():
    provider = SMTPEmailProvider()
    key = "test_run_123_email"
    res1 = await provider.send_email("test@example.com", "Subject", "Body", idempotency_key=key)
    assert res1["status"] == "SENT"

    # Second send with same idempotency key
    res2 = await provider.send_email("test@example.com", "Subject", "Body", idempotency_key=key)
    assert res2["status"] == "ALREADY_SENT"
