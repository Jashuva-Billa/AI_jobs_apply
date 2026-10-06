import pytest
import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock, MagicMock

from sqlalchemy import select
from app.main import app
from app.config.settings import settings
from app.config.database import get_db, AsyncSessionLocal, engine, Base
from app.models.entities import Job, Application, ApprovalRequest, AgentRun, JobMatch, CandidateProfile, ApprovalStatus
from app.schemas.schemas import (
    CandidateProfileBase,
    MatchBreakdown,
    SearchCriteria,
    RecruiterBase,
    OutreachMessageBase
)
from app.services.matching_service import matching_service
from app.services.job_service import job_service, JobResearchService
from app.services.recruiter_service import recruiter_service
from app.services.outreach_service import outreach_service
from app.integrations.web.search import MultiSourceJobSearchEngine, web_job_search, CURATED_AI_JOBS

@pytest.fixture
def sample_candidate():
    return CandidateProfileBase(
        name="Jashuva Billa",
        email="jashuvabilla@gmail.com",
        years_of_experience=2.9,
        skills=["Python", "RAG", "LangGraph", "Agentic AI", "AWS Bedrock", "Milvus", "FastAPI"],
        technical_skills=["Python", "FastAPI", "Docker"],
        cloud_skills=["AWS Bedrock"],
        frameworks=["LangGraph", "LangChain"],
        preferred_roles=["AI Engineer", "GenAI Engineer", "Agentic AI Engineer"],
        remote_preference=True,
        work_authorization="Authorized for remote employment in India"
    )

def generate_100_mock_jobs():
    jobs = []
    for i in range(1, 101):
        jobs.append({
            "company": f"TechCorp {i}",
            "title": f"AI Engineer {i}",
            "location": "Remote, India",
            "remote": True,
            "employment_type": "Full-time",
            "experience_required": "2-4 years",
            "skills": ["Python", "RAG", "LangGraph", "FastAPI", "AWS Bedrock"],
            "description": f"Building agentic AI systems at TechCorp {i}",
            "application_url": f"https://techcorp{i}.com/careers/ai-engineer",
            "source_url": f"https://techcorp{i}.com/careers/ai-engineer",
            "verification_status": "VERIFIED",
            "evidence": [
                {
                    "url": f"https://techcorp{i}.com/careers/ai-engineer",
                    "title": f"TechCorp {i} Official Career Posting",
                    "source_type": "official_company",
                    "supports": ["title", "location", "skills"]
                }
            ]
        })
    return jobs

# ----------------- TEST 1, 2, 3: Batch Persistence & Pipeline -----------------
@pytest.mark.asyncio
async def test_100_jobs_produce_100_persisted_jobs_apps_and_approvals(sample_candidate):
    """Test 1, 2, 3: 100 discovered jobs produce 100 persisted jobs, applications, and approvals."""
    mock_jobs = generate_100_mock_jobs()
    mock_recruiter = RecruiterBase(
        name="Sarah Jenkins",
        title="Technical Recruiter",
        company_name="TechCorp",
        public_email="talent@techcorp.com",
        source_evidence="Official Career Portal"
    )
    mock_email = OutreachMessageBase(channel="EMAIL", subject="AI Engineer Application", body="Dear Recruiter...", recipient_email="talent@techcorp.com", recipient_name="Sarah Jenkins")
    mock_li = OutreachMessageBase(channel="LINKEDIN", subject=None, body="Hi Sarah, would love to connect.", recipient_name="Sarah Jenkins")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch.object(job_service, "search_and_deduplicate", new_callable=AsyncMock) as mock_search, \
             patch.object(recruiter_service, "discover_recruiter_for_job", new_callable=AsyncMock) as mock_rec, \
             patch.object(outreach_service, "generate_recruiter_email", new_callable=AsyncMock) as mock_em, \
             patch.object(outreach_service, "generate_linkedin_outreach", new_callable=AsyncMock) as mock_out_li:
            
            mock_search.return_value = (mock_jobs, 100, 0)
            mock_rec.return_value = mock_recruiter
            mock_em.return_value = mock_email
            mock_out_li.return_value = mock_li
            
            # Execute run
            resp = await client.post("/api/agent/run", json={"prompt": "Find 100 remote AI Engineer roles in India"})
            assert resp.status_code == 200
            data = resp.json()
            test_run_id = data["run_id"]
            assert data["status"] in ["WAITING_FOR_APPROVAL", "COMPLETED"]
            assert data["total_jobs"] == 100
            assert data["qualified_jobs"] == 100
            assert data["applications_prepared"] == 100
            assert data["approvals_pending"] == 100

            # Verify persisted jobs in SQL
            jobs_resp = await client.get(f"/api/jobs?run_id={test_run_id}")
            assert jobs_resp.status_code == 200
            assert len(jobs_resp.json()) == 100

            # Verify persisted applications in SQL
            apps_resp = await client.get(f"/api/applications?run_id={test_run_id}")
            assert apps_resp.status_code == 200
            assert len(apps_resp.json()) == 100

            # Verify persisted approvals in SQL
            approvals_resp = await client.get(f"/api/approvals?run_id={test_run_id}")
            assert approvals_resp.status_code == 200
            assert len(approvals_resp.json()) == 100

# ----------------- TEST 4 & 5: Bulk Approval & Idempotency -----------------
@pytest.mark.asyncio
async def test_bulk_approval_and_idempotency():
    """Test 4 & 5: Bulk approve approvals and verify idempotency."""
    mock_recruiter = RecruiterBase(
        name="Sarah Jenkins",
        title="Technical Recruiter",
        company_name="TechCorp",
        public_email="talent@techcorp.com",
        source_evidence="Official Career Portal"
    )
    mock_email = OutreachMessageBase(channel="EMAIL", subject="AI Engineer Application", body="Dear Recruiter...", recipient_email="talent@techcorp.com", recipient_name="Sarah Jenkins")
    mock_li = OutreachMessageBase(channel="LINKEDIN", subject=None, body="Hi Sarah, would love to connect.", recipient_name="Sarah Jenkins")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check if pending approvals exist, otherwise seed directly
        approvals_resp = await client.get("/api/approvals?status=PENDING")
        approvals = approvals_resp.json()
        if not approvals:
            async with AsyncSessionLocal() as session:
                cand_res = await session.execute(select(CandidateProfile).limit(1))
                cand = cand_res.scalars().first()
                cand_id = cand.id if cand else str(uuid.uuid4())
                if not cand:
                    cand = CandidateProfile(id=cand_id, name="Jashuva Billa", years_of_experience=2.9)
                    session.add(cand)
                
                for i in range(3):
                    j_id = str(uuid.uuid4())
                    a_id = str(uuid.uuid4())
                    appr_id = str(uuid.uuid4())
                    job = Job(id=j_id, company=f"SeedCo {i}", title="AI Engineer", description="AI role")
                    session.add(job)
                    app_ent = Application(id=a_id, candidate_id=cand_id, job_id=j_id)
                    session.add(app_ent)
                    session.add(ApprovalRequest(id=appr_id, application_id=a_id, status=ApprovalStatus.PENDING))
                await session.commit()
            approvals_resp = await client.get("/api/approvals?status=PENDING")
            approvals = approvals_resp.json()

        assert len(approvals) > 0
        approval_ids = [a["approval_id"] for a in approvals[:5]]
        
        # Test 4: Bulk approve
        bulk_resp = await client.post("/api/approvals/bulk-decide", json={
            "approval_ids": approval_ids,
            "decision": "APPROVE"
        })
        assert bulk_resp.status_code == 200
        result = bulk_resp.json()
        assert result["approved"] == len(approval_ids)
        assert result["rejected"] == 0
        assert result["failed"] == 0

        # Test 5: Bulk approval idempotency (repeating approve shouldn't fail)
        bulk_resp_2 = await client.post("/api/approvals/bulk-decide", json={
            "approval_ids": approval_ids,
            "decision": "APPROVE"
        })
        assert bulk_resp_2.status_code == 200
        result_2 = bulk_resp_2.json()
        assert result_2["approved"] == len(approval_ids)
        assert result_2["failed"] == 0

# ----------------- TEST 6: Isolated Failure Resilience -----------------
@pytest.mark.asyncio
async def test_one_failed_application_does_not_fail_the_batch():
    """Test 6: One failed/invalid approval ID does not fail the entire batch."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_id = "non_existent_approval_id_999"
        
        bulk_resp = await client.post("/api/approvals/bulk-decide", json={
            "approval_ids": [fake_id],
            "decision": "APPROVE"
        })
        assert bulk_resp.status_code == 200
        result = bulk_resp.json()
        assert result["failed"] == 1
        assert result["total"] == 1

# ----------------- TEST 7, 8, 9: Search State Restoration -----------------
@pytest.mark.asyncio
async def test_run_recovery_and_persistence():
    """Test 7, 8, 9: Active run can be restored by latest and by run_id."""
    mock_recruiter = RecruiterBase(
        name="Sarah Jenkins",
        title="Technical Recruiter",
        company_name="TechCorp",
        public_email="talent@techcorp.com",
        source_evidence="Official Career Portal"
    )
    mock_email = OutreachMessageBase(channel="EMAIL", subject="AI Engineer Application", body="Dear Recruiter...", recipient_email="talent@techcorp.com", recipient_name="Sarah Jenkins")
    mock_li = OutreachMessageBase(channel="LINKEDIN", subject=None, body="Hi Sarah, would love to connect.", recipient_name="Sarah Jenkins")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        mock_jobs = generate_100_mock_jobs()[:5]
        with patch.object(job_service, "search_and_deduplicate", new_callable=AsyncMock) as mock_search, \
             patch.object(recruiter_service, "discover_recruiter_for_job", new_callable=AsyncMock) as mock_rec, \
             patch.object(outreach_service, "generate_recruiter_email", new_callable=AsyncMock) as mock_em, \
             patch.object(outreach_service, "generate_linkedin_outreach", new_callable=AsyncMock) as mock_out_li:
            
            mock_search.return_value = (mock_jobs, 5, 0)
            mock_rec.return_value = mock_recruiter
            mock_em.return_value = mock_email
            mock_out_li.return_value = mock_li
            
            run_create_resp = await client.post("/api/agent/run", json={"prompt": "Find latest AI roles"})
            assert run_create_resp.status_code == 200
            created_run_id = run_create_resp.json()["run_id"]

        latest_resp = await client.get("/api/agent/runs/latest")
        assert latest_resp.status_code == 200
        latest_run = latest_resp.json()
        assert latest_run is not None
        assert latest_run["run_id"] is not None

        run_id = latest_run["run_id"]
        run_resp = await client.get(f"/api/agent/runs/{run_id}")
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        assert run_data["run_id"] == run_id
        assert "total_jobs" in run_data

# ----------------- TEST 10: No Demo Data in Live Mode -----------------
@pytest.mark.asyncio
async def test_no_demo_jobs_when_demo_mode_false():
    """Test 10: When DEMO_MODE=false, no synthetic/curated jobs are injected if provider returns empty."""
    search_engine = MultiSourceJobSearchEngine()
    
    with patch.object(settings, "DEMO_MODE", False):
        with patch.object(search_engine.openai_provider, "search_criteria", new_callable=AsyncMock) as mock_oai:
            mock_oai.return_value = []
            with patch.object(search_engine.api_provider, "search", new_callable=AsyncMock) as mock_api:
                mock_api.return_value = []
                with patch.object(search_engine.web_provider, "search", new_callable=AsyncMock) as mock_web:
                    mock_web.return_value = []
                    
                    results = await search_engine.search_jobs(["AI Engineer"], ["Remote"], True, SearchCriteria(roles=["AI Engineer"]))
                    assert len(results) == 0, "When DEMO_MODE=false and live providers return 0, no curated jobs should be injected"

# ----------------- TEST 11: Match Thresholds Respected -----------------
def test_configured_thresholds_respected(sample_candidate):
    """Test 11: Configured thresholds (STRONG_MATCH, MATCH, POSSIBLE_MATCH) are properly classified."""
    strong_job = {
        "company": "ScaleAI",
        "title": "AI Engineer",
        "location": "Remote",
        "remote": True,
        "experience_required": "2-4 years",
        "skills": ["Python", "RAG", "LangGraph", "Agentic AI", "AWS Bedrock", "Milvus", "FastAPI"],
        "description": "Building RAG and Agentic systems"
    }
    match = matching_service.evaluate_match(sample_candidate, strong_job)
    assert match.overall_score >= settings.MATCH_THRESHOLD

    low_job = {
        "company": "LegacyCorp",
        "title": "Junior Java Developer",
        "location": "Onsite Chicago",
        "remote": False,
        "experience_required": "7-10 years",
        "skills": ["COBOL", "Java 6", "Mainframe"],
        "description": "Legacy system maintenance"
    }
    low_match = matching_service.evaluate_match(sample_candidate, low_job)
    assert low_match.overall_score < settings.POSSIBLE_MATCH_THRESHOLD
    assert low_match.recommendation == "REJECT"

# ----------------- TEST 12: Email Idempotency -----------------
@pytest.mark.asyncio
async def test_no_duplicate_email_sent_on_repeated_approval():
    """Test 12: Repeated approval actions use idempotency keys to prevent duplicate emails."""
    from app.integrations.email.provider import SMTPEmailProvider
    provider = SMTPEmailProvider()
    
    key = f"idempotency_test_{uuid.uuid4().hex}"
    r1 = await provider.send_email("recruiter@testcorp.com", "Test Subject", "Test Body", idempotency_key=key)
    assert r1["status"] == "SENT"

    r2 = await provider.send_email("recruiter@testcorp.com", "Test Subject", "Test Body", idempotency_key=key)
    assert r2["status"] == "ALREADY_SENT"
