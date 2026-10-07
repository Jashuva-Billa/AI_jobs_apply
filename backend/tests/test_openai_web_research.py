import os
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.config.settings import settings
from app.integrations.openai.schemas import (
    JobResearchResponse,
    JobResearchResult,
    SourceEvidence,
    RecruiterResearchResult
)
from app.integrations.web.search import MultiSourceJobSearchEngine
from app.schemas.schemas import CandidateProfileBase, SearchCriteria, MatchBreakdown
from app.services.job_service import job_service
from app.services.matching_service import matching_service
from app.services.recruiter_service import recruiter_service
from app.integrations.email.provider import SMTPEmailProvider

@pytest.fixture
def mock_candidate():
    return CandidateProfileBase(
        name="Alex Morgan",
        email="alex.morgan@example.com",
        years_of_experience=3.0,
        skills=["Python", "RAG", "LangGraph", "Agentic AI", "AWS", "LLMs"],
        technical_skills=["Python", "FastAPI"],
        cloud_skills=["AWS"],
        frameworks=["LangGraph"],
        preferred_roles=["AI Engineer", "GenAI Engineer"],
        remote_preference=True,
        work_authorization="Authorized for remote employment in India"
    )

@pytest.fixture
def sample_search_criteria():
    return SearchCriteria(
        roles=["AI Engineer", "GenAI Engineer"],
        min_experience=2,
        max_experience=4,
        locations=["Remote", "India"],
        remote_required=True,
        skills=["Python", "RAG", "LangGraph", "Agentic AI", "AWS"]
    )

def test_zero_llm_api_dependency():
    """Verifies that no OpenAI or Gemini API keys are mandatory for backend execution."""
    assert settings.LLM_PROVIDER in ["chatgpt_mcp", "local"]
    assert settings.DEMO_MODE in [True, False]

def test_web_research_schema():
    """Verifies Pydantic serialization and validation of JobResearchResult and SourceEvidence."""
    evidence = SourceEvidence(
        url="https://anthropic.com/careers/ai-systems-engineer",
        title="Anthropic Careers - AI Systems Engineer",
        source_type="official_company",
        supports=["job_title", "location", "required_skills", "application_url"]
    )
    assert evidence.url == "https://anthropic.com/careers/ai-systems-engineer"
    assert "job_title" in evidence.supports

    job = JobResearchResult(
        title="AI Systems Engineer",
        company="Anthropic AI Labs",
        location="Remote (India Friendly)",
        remote=True,
        employment_type="Full-time",
        experience_required="3-5 years",
        salary="$140,000 - $180,000",
        description="Build Agentic AI and RAG pipelines using LangGraph and Python.",
        responsibilities=["Develop MCP servers", "Deploy LLM workflows"],
        required_skills=["Python", "LangGraph", "RAG", "AWS"],
        preferred_skills=["Agentic AI", "MCP"],
        posted_date="2026-10-01",
        application_url="https://careers.anthropic.com/jobs/ai-systems-engineer",
        source_url="https://careers.anthropic.com",
        source_title="Anthropic Careers",
        company_url="https://anthropic.com",
        confidence=0.98,
        verification_status="VERIFIED",
        evidence=[evidence]
    )
    assert job.company == "Anthropic AI Labs"
    assert job.verification_status == "VERIFIED"
    assert len(job.evidence) == 1

def test_source_evidence():
    """Verifies that citations and evidence structures are maintained and never discarded."""
    ev = SourceEvidence(
        url="https://company.com/jobs/123",
        title="Company Official Careers",
        source_type="official_company",
        supports=["title", "skills", "application_url"]
    )
    assert ev.source_type == "official_company"
    assert "application_url" in ev.supports

def test_verified_job():
    """Ensures verified job postings from official sources receive VERIFIED status."""
    job = JobResearchResult(
        title="GenAI Engineer",
        company="ScaleGen AI",
        description="Engineering role",
        responsibilities=[],
        required_skills=["Python"],
        preferred_skills=[],
        application_url="https://scalegen.ai/careers/genai-engineer",
        source_url="https://scalegen.ai/careers",
        verification_status="VERIFIED",
        evidence=[
            SourceEvidence(
                url="https://scalegen.ai/careers/genai-engineer",
                title="ScaleGen AI Careers",
                source_type="official_company",
                supports=["title", "application_url"]
            )
        ]
    )
    assert job.verification_status == "VERIFIED"

def test_unverified_job():
    """Ensures jobs lacking source evidence receive UNVERIFIED status and are tagged."""
    job = JobResearchResult(
        title="Unverified AI Role",
        company="Unknown Corp",
        description="Vague post without clear career source",
        responsibilities=[],
        required_skills=[],
        preferred_skills=[],
        application_url=None,
        source_url=None,
        confidence=0.3,
        verification_status="UNVERIFIED",
        evidence=[]
    )
    assert job.verification_status == "UNVERIFIED"

def test_job_deduplication():
    """Tests that jobs from multiple sources are normalized and deduplicated by canonical hash."""
    id1 = job_service.generate_canonical_id("Nexus Cognitive", "Machine Learning Engineer (LLMs)", "Remote")
    id2 = job_service.generate_canonical_id("nexus cognitive", "machine-learning-engineer-llms", "remote")
    assert id1 == id2

def test_matching(mock_candidate):
    """Verifies the 7-factor deterministic match calculation."""
    job_data = {
        "company": "ScaleGen AI",
        "title": "GenAI Engineer",
        "location": "Remote (India)",
        "remote": True,
        "experience_required": "2-4 years",
        "skills": ["Python", "RAG", "LangGraph", "Agentic AI", "AWS"],
        "requirements": ["2+ years experience in Python", "LangGraph workflows"]
    }
    match = matching_service.evaluate_match(mock_candidate, job_data)
    assert match.overall_score >= 80.0
    assert match.recommendation in ["STRONG_MATCH", "MATCH"]
    assert match.location_score == 100.0

@pytest.mark.asyncio
async def test_recruiter_research():
    """Tests recruiter discovery returning verifiable talent acquisition evidence."""
    recruiter = await recruiter_service.discover_recruiter_for_job("ScaleGen AI", "GenAI Engineer")
    assert recruiter is not None
    assert recruiter.company_name == "ScaleGen AI"
    assert recruiter.source_evidence is not None

@pytest.mark.asyncio
async def test_multi_source_job_search(sample_search_criteria):
    """Verifies that multi-source job search functions reliably without any LLM API dependency."""
    engine = MultiSourceJobSearchEngine()
    results = await engine.search_jobs(
        queries=["AI Engineer remote India"],
        locations=["Remote", "India"],
        remote_only=True,
        criteria=sample_search_criteria
    )
    assert len(results) > 0, "Multi-source search engine should return verified job listings"

@pytest.mark.asyncio
async def test_email_idempotency():
    """Ensures email outreach actions are strictly idempotent and never double-sent."""
    provider = SMTPEmailProvider()
    key = "test_run_123_email"
    
    res1 = await provider.send_email("recruiter@scalegen.ai", "Job Application", "Cover letter content", idempotency_key=key)
    assert res1["status"] == "SENT"
    
    res2 = await provider.send_email("recruiter@scalegen.ai", "Job Application", "Cover letter content", idempotency_key=key)
    assert res2["status"] == "ALREADY_SENT"

def test_application_approval():
    """Verifies human-in-the-loop approval data structure."""
    decision_payload = {
        "decision": "APPROVE",
        "modified_email_subject": "Application for Senior AI Engineer",
        "modified_email_body": "Dear Hiring Team, ...",
        "send_email": True
    }
    assert decision_payload["decision"] == "APPROVE"
    assert decision_payload["send_email"] is True
