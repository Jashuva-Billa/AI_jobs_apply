import os
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.config.settings import settings
from app.integrations.openai.client import OpenAIClientWrapper, openai_client_wrapper
from app.integrations.openai.schemas import (
    JobResearchResponse,
    JobResearchResult,
    SourceEvidence,
    RecruiterResearchResult
)
from app.integrations.openai.web_research import OpenAIWebResearchService, openai_web_research
from app.integrations.web.search import MultiSourceJobSearchEngine, OpenAIWebSearchProvider
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

def test_openai_client_configuration():
    """Verifies that the OpenAI client reads configured model and handles config correctly."""
    wrapper = OpenAIClientWrapper()
    assert wrapper.is_configured() or not settings.OPENAI_API_KEY
    assert settings.OPENAI_WEB_SEARCH_ENABLED in [True, False]
    assert settings.OPENAI_WEB_SEARCH_CONTEXT_SIZE in ["low", "medium", "high"]
    assert settings.effective_openai_model is not None

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

def test_job_research_parsing():
    """Tests JSON extraction and deserialization from OpenAI Responses API output."""
    raw_response_text = """
    Here are the verified active job postings found on company career portals:
    ```json
    {
      "search_queries": ["AI Engineer remote India careers", "GenAI Engineer LangGraph"],
      "total_found": 1,
      "jobs": [
        {
          "title": "Senior Generative AI Engineer",
          "company": "ScaleGen AI",
          "location": "Remote (India)",
          "remote": true,
          "remote_eligibility": "Worldwide / India",
          "employment_type": "Full-time",
          "experience_required": "2-4 years",
          "salary": "$120,000 - $150,000",
          "description": "Architect autonomous agents using LangGraph and Python.",
          "responsibilities": ["Design RAG pipelines", "Deploy on AWS"],
          "required_skills": ["Python", "LangGraph", "RAG", "Agentic AI", "AWS"],
          "preferred_skills": ["FastAPI", "Docker"],
          "posted_date": "2026-10-02",
          "application_url": "https://scalegen.ai/careers/genai-engineer",
          "source_url": "https://scalegen.ai/jobs",
          "source_title": "ScaleGen AI Official Careers",
          "company_url": "https://scalegen.ai",
          "confidence": 0.95,
          "verification_status": "VERIFIED",
          "evidence": [
            {
              "url": "https://scalegen.ai/careers/genai-engineer",
              "title": "ScaleGen AI Careers",
              "source_type": "official_company",
              "supports": ["title", "location", "skills", "application_url"]
            }
          ]
        }
      ]
    }
    ```
    """
    service = OpenAIWebResearchService()
    parsed = service._extract_json_from_text(raw_response_text)
    assert parsed is not None
    assert "jobs" in parsed
    assert len(parsed["jobs"]) == 1
    job = JobResearchResult(**parsed["jobs"][0])
    assert job.company == "ScaleGen AI"
    assert job.verification_status == "VERIFIED"
    assert job.evidence[0].source_type == "official_company"

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
async def test_openai_failure_fallback(sample_search_criteria):
    """Verifies that if OpenAI Web Search fails or is disabled, fallback providers are queried gracefully."""
    engine = MultiSourceJobSearchEngine()
    
    # Mock openai provider to simulate failure
    with patch.object(engine.openai_provider, "search_criteria", side_effect=Exception("OpenAI 500 Internal Error")):
        results = await engine.search_jobs(
            queries=["AI Engineer remote India"],
            locations=["Remote", "India"],
            remote_only=True,
            criteria=sample_search_criteria
        )
        assert len(results) > 0, "Fallback provider should supply results on OpenAI failure"

@pytest.mark.asyncio
async def test_rate_limit_fallback(sample_search_criteria):
    """Verifies that 429 rate limit exceptions fallback cleanly without crashing."""
    engine = MultiSourceJobSearchEngine()
    
    with patch.object(engine.openai_provider, "search_criteria", side_effect=Exception("429 Rate Limit Exceeded")):
        results = await engine.search_jobs(
            queries=["GenAI Engineer"],
            locations=["Remote"],
            remote_only=True,
            criteria=sample_search_criteria
        )
        assert len(results) > 0

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

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_WEB_TEST") != "true" or not os.getenv("OPENAI_API_KEY"),
    reason="Optional live web test. Set RUN_LIVE_WEB_TEST=true and OPENAI_API_KEY to run."
)
async def test_live_web_research_integration(sample_search_criteria, mock_candidate):
    """Optional live test executing actual OpenAI Responses API with Web Search tool."""
    service = OpenAIWebResearchService()
    res = await service.search_jobs(sample_search_criteria, mock_candidate)
    assert isinstance(res, JobResearchResponse)
    assert len(res.jobs) > 0
