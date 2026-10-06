import pytest
import os
import uuid
import datetime
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.email_resolution_service import (
    email_resolution_service,
    normalize_domain,
    validate_company_domain,
    verify_email_for_job,
    sanitize_recruiter_name,
    extract_emails_from_text,
    EmailResolutionResult,
    RecipientClassification
)
from app.schemas.schemas import CandidateProfileBase, JobBase, OutreachMessageBase, RecruiterBase
from app.services.outreach_service import outreach_service
from app.config.database import AsyncSessionLocal
from app.models.entities import Application, Job, OutreachMessage, ApprovalRequest, ApplicationStatus

# ----------------- TEST 1: Correct Company Email -----------------
def test_correct_company_email():
    """Test 1: Legitimate company domain email returns VERIFIED."""
    job_data = {
        "company": "Example AI",
        "company_url": "https://example.ai",
        "recruiter_email": "careers@example.ai",
        "description": "We are looking for an AI Engineer."
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.status == "VERIFIED"
    assert res.email == "careers@example.ai"
    assert res.source == "job_source"
    assert res.confidence >= 0.90
    assert res.company == "Example AI"

# ----------------- TEST 2: Wrong Company Email -----------------
def test_wrong_company_email():
    """Test 2: Hardcoded/mismatched email (talent@techcorp.com on Example AI) is rejected."""
    job_data = {
        "company": "Example AI",
        "company_url": "https://example.ai",
        "recruiter_email": "talent@techcorp.com",
        "description": "Join our AI research team."
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.email is None
    assert res.status == "NOT_FOUND"
    assert res.email != "talent@techcorp.com"

# ----------------- TEST 3: No Email Found -----------------
def test_no_email_found():
    """Test 3: Job with no email anywhere returns NOT_FOUND with 0 confidence and None email."""
    job_data = {
        "company": "Stealth AI",
        "company_url": "https://stealthai.io",
        "description": "Apply through LinkedIn or official portal."
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.email is None
    assert res.status == "NOT_FOUND"
    assert res.source is None
    assert res.confidence == 0.0

# ----------------- TEST 4: Two Different Jobs Isolation -----------------
def test_cross_job_isolation():
    """Test 4: Recruiter and email info from Job A never leaks into Job B."""
    job_a = {
        "company": "CompanyA",
        "company_url": "https://companya.com",
        "recruiter_email": "jobs@companya.com",
        "description": "Job at Company A"
    }
    recruiter_a = RecruiterBase(
        name="Alice Walker",
        title="Lead Recruiter",
        company_name="CompanyA",
        public_email="jobs@companya.com"
    )

    job_b = {
        "company": "CompanyB",
        "company_url": "https://companyb.com",
        "recruiter_email": None,
        "description": "Job at Company B"
    }

    res_a = email_resolution_service.resolve_recruiter_contact(job_a, recruiter_a)
    assert res_a.email == "jobs@companya.com"
    assert res_a.recruiter_name == "Alice Walker"

    # Process Job B immediately after Job A without recruiter object
    res_b = email_resolution_service.resolve_recruiter_contact(job_b, None)
    assert res_b.email is None
    assert res_b.status == "NOT_FOUND"
    assert res_b.email != "jobs@companya.com"
    assert res_b.recruiter_name is None or res_b.recruiter_name != "Alice Walker"

# ----------------- TEST 5: Email in Job Description -----------------
def test_email_in_job_description_extraction():
    """Test 5: Extracts valid recruiting email from job description text."""
    job_data = {
        "company": "Synthetix Data",
        "company_url": "https://synthetixdata.io",
        "description": "Great role! Please apply by sending your resume to talent@synthetixdata.io or check our site."
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.status == "VERIFIED"
    assert res.email == "talent@synthetixdata.io"
    assert res.source == "job_description"
    assert res.confidence > 0.80

# ----------------- TEST 6: Official Careers Page Extraction -----------------
def test_official_careers_page_domain_match():
    """Test 6: Validates email against company website / application portal."""
    job_data = {
        "company": "Global AI Lab",
        "company_url": "https://globalailab.com",
        "application_url": "https://jobs.ashbyhq.com/globalailab",
        "recruiter_email": "hiring@globalailab.com"
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.status == "VERIFIED"
    assert res.email == "hiring@globalailab.com"

# ----------------- TEST 7: Generic Email Preference -----------------
def test_recruiting_email_preferred_over_generic():
    """Test 7: Prefers recruiting/careers/talent address over info/support/sales."""
    text = "Contact info@neuroflow.ai for general inquiries or send your application directly to careers@neuroflow.ai for the engineering team."
    job_data = {
        "company": "NeuroFlow",
        "company_url": "https://neuroflow.ai",
        "description": text
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.status == "VERIFIED"
    assert res.email == "careers@neuroflow.ai"
    assert res.email != "info@neuroflow.ai"

# ----------------- TEST 8: Invalid Email Rejection -----------------
def test_invalid_email_format():
    """Test 8: Rejects malformed email addresses."""
    assert not validate_company_domain("not-an-email", "Company")[0]
    assert not validate_company_domain("user@@domain..com", "Company")[0]
    assert not validate_company_domain("user@domain", "Company")[0]
    
    job_data = {
        "company": "Apex Corp",
        "recruiter_email": "invalid@@apexcorp",
        "description": "Contact apex-corp"
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.email is None
    assert res.status == "NOT_FOUND"

# ----------------- TEST 9: Cross-Domain Rejection -----------------
def test_cross_domain_rejection_and_ats_whitelist():
    """Test 9: Rejects random third-party domains and rejects ATS infrastructure email as direct company recipient."""
    # Random unrelated domain -> rejected
    is_valid, reason = validate_company_domain("recruiter@randomfirm.com", "Nova AI", "https://novaai.com")
    assert not is_valid
    assert "DOMAIN_MISMATCH" in reason

    # ATS domain used as employer email -> rejected (ATS is infrastructure, not company recipient)
    is_valid_ats, status_ats, score_ats, reason_ats = verify_email_for_job("jobs@greenhouse.io", {"company": "Nova AI", "company_url": "https://novaai.com"})
    assert not is_valid_ats
    assert status_ats == RecipientClassification.REJECTED
    assert "REJECTED_ATS_INFRASTRUCTURE_EMAIL" in reason_ats

# ----------------- TEST 10: Recruiter Name Spam Sanitization -----------------
def test_recruiter_name_spam_sanitization():
    """Test 10: Discards spam search snippets (e.g. Vegamovies, movie downloads) and cleans names."""
    spam_title = "Vegamovies – Download Bollywood, Hollywood, South, Hindi ..."
    clean_name, status = sanitize_recruiter_name(spam_title, "Acme AI")
    assert clean_name is None
    assert status == "NOT_FOUND"

    # Valid human name
    clean_name2, status2 = sanitize_recruiter_name("Sarah Jenkins - Technical Recruiter | LinkedIn", "Acme AI")
    assert clean_name2 == "Sarah Jenkins"
    assert status2 == "VERIFIED"

# ----------------- TEST 11: Send Protection -----------------
@pytest.mark.asyncio
async def test_send_protection_blocks_invalid_recipient():
    """Test 11: Attempt to send email to mismatched/hardcoded domain is blocked with BLOCKED_INVALID_RECIPIENT."""
    from sqlalchemy import select
    from app.models.entities import CandidateProfile

    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        if not cand:
            cand = CandidateProfile(
                id=str(uuid.uuid4()),
                name="Test Candidate",
                email="test@candidate.ai"
            )
            session.add(cand)
            await session.flush()

        # Create test job
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            company="Alpha Neural Inc",
            company_url="https://alphaneural.com",
            title="Senior AI Engineer",
            description="Deep Learning role",
            verification_status="VERIFIED"
        )
        session.add(job)

        app_id = str(uuid.uuid4())
        app_obj = Application(
            id=app_id,
            candidate_id=cand.id,
            job_id=job_id,
            status=ApplicationStatus.APPROVED
        )
        session.add(app_obj)

        # Intentionally attach unauthorized email
        outreach = OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Application for AI Engineer",
            body="Hello...",
            recipient_email="talent@techcorp.com", # WRONG DOMAIN for Alpha Neural Inc!
            status="DRAFT"
        )
        session.add(outreach)
        await session.commit()

    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "job-platform")))
    from tools.outreach import send_approved_email

    send_result = await send_approved_email(app_id)
    assert send_result.get("status") == "BLOCKED_INVALID_RECIPIENT"
    assert "blocked" in send_result.get("error", "").lower()

# ----------------- TEST 12: Outreach Message Generation Integration -----------------
@pytest.mark.asyncio
async def test_outreach_generation_provenance_integration():
    """Test 12: Verifies outreach generation sets correct recipient, salutation, and provenance."""
    cand = CandidateProfileBase(
        name="Jashuva Billa",
        email="jashuvabilla@gmail.com",
        years_of_experience=2.9,
        skills=["Python", "LangGraph", "RAG"]
    )
    job = {
        "company": "DeepFlow AI",
        "company_url": "https://deepflow.ai",
        "title": "Generative AI Engineer",
        "recruiter_email": "careers@deepflow.ai",
        "description": "Building next gen agents"
    }
    recruiter = RecruiterBase(
        name="Elena Rostova",
        title="Director of Talent",
        company_name="DeepFlow AI",
        public_email="careers@deepflow.ai"
    )

    outreach_msg = await outreach_service.generate_recruiter_email(cand, job, recruiter)
    assert outreach_msg.recipient_email == "careers@deepflow.ai"
    assert outreach_msg.recipient_name == "Elena Rostova"
    assert outreach_msg.email_status == "VERIFIED"
    assert outreach_msg.email_source == "job_source"
    assert outreach_msg.email_confidence >= 0.90
    assert outreach_msg.recruiter_status == "VERIFIED"
    assert len(outreach_msg.body) > 20
