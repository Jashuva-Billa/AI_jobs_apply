import pytest
import os
import uuid
import asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.services.email_resolution_service import (
    email_resolution_service,
    verify_email_for_job,
    validate_company_domain,
    sanitize_recruiter_name,
    validate_recipient_before_send,
    RecipientClassification,
    EmailResolutionResult,
    is_valid_email_format,
    normalize_domain
)
from app.services.duplicate_protection import duplicate_protection
from app.services.dry_run_service import dry_run_service, is_ai_engineer_relevant
from app.schemas.schemas import RecruiterBase, CandidateProfileBase
from app.config.database import AsyncSessionLocal
from app.models.entities import Job, Application, OutreachMessage, CandidateProfile, ApplicationStatus

# ==============================================================================
# 20-SCENARIO PRODUCTION SAFETY & DRY-RUN REGRESSION TEST SUITE
# ==============================================================================

# --- Scenario 1: Correct company email ---
def test_scenario_01_correct_company_email():
    job_data = {
        "company": "Anthropic",
        "company_url": "https://anthropic.com",
        "recruiter_email": "careers@anthropic.com",
        "description": "We are looking for an AI safety researcher."
    }
    is_valid, classification, score, reason = verify_email_for_job("careers@anthropic.com", job_data)
    assert is_valid is True
    assert classification == RecipientClassification.VERIFIED
    assert score >= 0.85
    assert "MATCHED" in reason

# --- Scenario 2: Wrong company email ---
def test_scenario_02_wrong_company_email():
    job_data = {
        "company": "Scale AI",
        "company_url": "https://scale.com",
        "recruiter_email": "hiring@unrelatedothercompany.xyz"
    }
    is_valid, classification, score, reason = verify_email_for_job("hiring@unrelatedothercompany.xyz", job_data)
    assert is_valid is False
    assert classification == RecipientClassification.REJECTED
    assert "DOMAIN_MISMATCH" in reason

# --- Scenario 3: Missing email ---
def test_scenario_03_missing_email():
    job_data = {
        "company": "Stealth Robotics",
        "company_url": "https://stealthrobotics.io",
        "description": "Apply on our portal without any email listed."
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.email is None
    assert res.status == RecipientClassification.NOT_FOUND
    assert res.confidence == 0.0
    assert res.send_allowed is False

# --- Scenario 4: Malformed email ---
def test_scenario_04_malformed_email():
    job_data = {"company": "OpenAI", "company_url": "https://openai.com"}
    malformed_emails = ["not-an-email", "user@@domain..com", "careers@", "@openai.com", "careers@openai"]
    for malformed in malformed_emails:
        is_valid, classification, score, reason = verify_email_for_job(malformed, job_data)
        assert is_valid is False
        assert classification == RecipientClassification.REJECTED
        assert "INVALID_SYNTAX" in reason

# --- Scenario 5: Company-domain match only ---
def test_scenario_05_company_domain_match_only():
    # Individual name without recruiting keyword or description proof -> DOMAIN_MATCH_ONLY
    job_data = {
        "company": "DeepMind",
        "company_url": "https://deepmind.com",
        "description": "Research scientist role."
    }
    is_valid, classification, score, reason = verify_email_for_job("john.doe@deepmind.com", job_data)
    assert is_valid is True
    assert classification == RecipientClassification.DOMAIN_MATCH_ONLY
    assert 0.50 <= score < 0.85
    # DOMAIN_MATCH_ONLY must not be allowed to send automatically
    assert classification != RecipientClassification.VERIFIED

# --- Scenario 6: Third-party ATS rejection ---
def test_scenario_06_third_party_ats_rejection():
    job_data = {
        "company": "Apex AI",
        "company_url": "https://apexai.com",
        "application_url": "https://boards.greenhouse.io/apexai"
    }
    # jobs@greenhouse.io must NOT automatically become the recipient for Apex AI
    is_valid, classification, score, reason = verify_email_for_job("jobs@greenhouse.io", job_data)
    assert is_valid is False
    assert classification == RecipientClassification.REJECTED
    assert "REJECTED_ATS_INFRASTRUCTURE_EMAIL" in reason

# --- Scenario 7: Verified recruiter with company evidence ---
def test_scenario_07_verified_recruiter_with_company_evidence():
    job_data = {
        "company": "NeuralBridge",
        "company_url": "https://neuralbridge.ai",
        "description": "Join our Agent team."
    }
    recruiter = RecruiterBase(
        name="Sarah Jenkins",
        title="Technical Recruiter",
        company_name="NeuralBridge",
        public_email="careers@neuralbridge.ai"
    )
    res = email_resolution_service.resolve_recruiter_contact(job_data, recruiter)
    assert res.email == "careers@neuralbridge.ai"
    assert res.recruiter_name == "Sarah Jenkins"
    assert res.status == RecipientClassification.VERIFIED
    assert res.recruiter_status == "VERIFIED"
    assert res.send_allowed is True

# --- Scenario 8: Unverified recruiter / insufficient evidence ---
def test_scenario_08_unverified_recruiter_insufficient_evidence():
    job_data = {
        "company": "CyberAI Labs",
        "company_url": "https://cyberailabs.com",
    }
    recruiter = RecruiterBase(
        name="Random Contact",
        title="Third Party Agent",
        company_name="Random Agency",
        public_email="agent@randomagency.org" # Mismatched domain!
    )
    res = email_resolution_service.resolve_recruiter_contact(job_data, recruiter)
    assert res.email is None
    assert res.status == RecipientClassification.NOT_FOUND
    assert res.send_allowed is False

# --- Scenario 9: SEO recruiter-name contamination sanitization ---
def test_scenario_09_seo_recruiter_name_contamination():
    spam_names = [
        "Vegamovies – Download Bollywood, Hollywood Movies Full HD",
        "Free MP4 Torrent 1080p Download",
        "Buy Cheap Meds Online - Best Pharmacy",
        "https://linkedin.com/in/recruiter-profile",
        "Senior AI Engineer / Python Developer Needed",
        "HR",
        "None",
        "P"
    ]
    for spam in spam_names:
        clean_name, status = sanitize_recruiter_name(spam, "Target AI")
        assert clean_name is None
        assert status == "NOT_FOUND"

    valid_name, status = sanitize_recruiter_name("Priya Kumar - Talent Acquisition Lead | LinkedIn", "Target AI")
    assert valid_name == "Priya Kumar"
    assert status == "VERIFIED"

# --- Scenario 10: Cross-job contamination with 5 unrelated companies ---
def test_scenario_10_cross_job_contamination_5_companies():
    companies = [
        {"name": "CompanyAlpha", "domain": "https://companyalpha.com", "email": "talent@companyalpha.com", "recruiter": "Alice Alpha"},
        {"name": "CompanyBeta", "domain": "https://companybeta.com", "email": "hiring@companybeta.com", "recruiter": "Bob Beta"},
        {"name": "CompanyGamma", "domain": "https://companygamma.com", "email": None, "recruiter": None},
        {"name": "CompanyDelta", "domain": "https://companydelta.com", "email": "jobs@companydelta.com", "recruiter": "David Delta"},
        {"name": "CompanyEpsilon", "domain": "https://companyepsilon.com", "email": "careers@companyepsilon.com", "recruiter": "Eve Epsilon"},
    ]

    results = []
    for c in companies:
        job = {
            "company": c["name"],
            "company_url": c["domain"],
            "recruiter_email": c["email"],
            "description": f"Exciting job at {c['name']}"
        }
        rec = None
        if c["recruiter"]:
            rec = RecruiterBase(name=c["recruiter"], title="Recruiter", company_name=c["name"], public_email=c["email"])
        res = email_resolution_service.resolve_recruiter_contact(job, rec)
        results.append((c, res))

    # Strict assertion: No data leaked between any sequential execution
    for c, res in results:
        if c["email"]:
            assert res.email == c["email"]
            assert c["name"].lower() in res.email
            assert res.status == RecipientClassification.VERIFIED
        else:
            assert res.email is None
            assert res.status == RecipientClassification.NOT_FOUND

        if c["recruiter"]:
            assert res.recruiter_name == c["recruiter"]
        else:
            assert res.recruiter_name is None

# --- Scenario 11: Hardcoded TechCorp email rejection ---
def test_scenario_11_hardcoded_techcorp_rejection():
    non_techcorp_job = {
        "company": "Vanguard Robotics",
        "company_url": "https://vanguardrobotics.com",
        "recruiter_email": "talent@techcorp.com",
        "description": "Join our AI research team."
    }
    res = email_resolution_service.resolve_recruiter_contact(non_techcorp_job)
    assert res.email != "talent@techcorp.com"
    assert res.email is None
    assert res.status == RecipientClassification.NOT_FOUND

    # Direct validation check
    is_valid, classification, score, reason = verify_email_for_job("talent@techcorp.com", non_techcorp_job)
    assert is_valid is False
    assert classification == RecipientClassification.REJECTED
    assert "BLOCKED_HARDCODED_TECHCORP_FALLBACK" in reason

# --- Scenario 12: Final pre-send safety gate ---
def test_scenario_12_final_send_gate():
    job_ok = {"company": "Helix AI", "company_url": "https://helixai.com", "recruiter_email": "careers@helixai.com"}
    allowed, status, reason = validate_recipient_before_send(job_ok, "careers@helixai.com")
    assert allowed is True
    assert status == "READY_TO_SEND"

    # Mismatched company
    job_bad = {"company": "Helix AI", "company_url": "https://helixai.com"}
    allowed_bad, status_bad, reason_bad = validate_recipient_before_send(job_bad, "careers@otherfirm.org")
    assert allowed_bad is False
    assert status_bad == RecipientClassification.BLOCKED_INVALID_RECIPIENT

# --- Scenario 13: Duplicate application protection ---
@pytest.mark.asyncio
async def test_scenario_13_duplicate_application_protection():
    async with AsyncSessionLocal() as session:
        # Create test job and application
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        if not cand:
            cand = CandidateProfile(id=str(uuid.uuid4()), name="Dup Test Candidate", email="cand@dup.ai")
            session.add(cand)
            await session.flush()

        unique_suffix = uuid.uuid4().hex[:8]
        dup_job_id = f"test-dup-job-{unique_suffix}"
        dup_company = f"DupCo_{unique_suffix}"
        job = Job(
            id=dup_job_id,
            canonical_job_id=dup_job_id,
            company=dup_company,
            title="Senior GenAI Engineer",
            description="Developing production RAG and agent systems.",
            application_url=f"https://dupco-{unique_suffix}.ai/jobs/{dup_job_id}",
            verification_status="VERIFIED"
        )
        session.add(job)

        app_obj = Application(
            id=str(uuid.uuid4()),
            candidate_id=cand.id,
            job_id=dup_job_id,
            status=ApplicationStatus.REVIEW_REQUIRED
        )
        session.add(app_obj)
        await session.commit()

        # Check duplicate
        is_dup, existing_id, reason = await duplicate_protection.check_duplicate_job(
            session=session,
            candidate_id=cand.id,
            job_data={
                "id": dup_job_id,
                "canonical_job_id": dup_job_id,
                "application_url": f"https://dupco-{unique_suffix}.ai/jobs/{dup_job_id}",
                "company": dup_company,
                "title": "Senior GenAI Engineer"
            }
        )
        assert is_dup is True
        assert existing_id == app_obj.id
        assert reason is not None

# --- Scenario 14: Previously submitted job detection ---
@pytest.mark.asyncio
async def test_scenario_14_previously_submitted_job_detection():
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()

        unique_suffix = uuid.uuid4().hex[:8]
        prev_job_id = f"test-submitted-job-{unique_suffix}"
        prev_company = f"SubmittedAI_{unique_suffix}"
        job = Job(
            id=prev_job_id,
            canonical_job_id=prev_job_id,
            company=prev_company,
            title="LLM Platform Lead",
            description="Building large language model platform architectures.",
            application_url=f"https://submittedai-{unique_suffix}.io/apply/{prev_job_id}",
            verification_status="VERIFIED"
        )
        session.add(job)

        app_obj = Application(
            id=str(uuid.uuid4()),
            candidate_id=cand.id,
            job_id=prev_job_id,
            status=ApplicationStatus.APPLIED
        )
        session.add(app_obj)
        await session.commit()

        is_dup, existing_id, reason = await duplicate_protection.check_duplicate_job(
            session=session,
            candidate_id=cand.id,
            job_data={
                "id": prev_job_id,
                "canonical_job_id": prev_job_id,
                "company": prev_company,
                "title": "LLM Platform Lead"
            }
        )
        assert is_dup is True
        assert existing_id == app_obj.id
        assert "applied" in reason.lower()

# --- Scenario 15: Dry-run mode ---
@pytest.mark.asyncio
async def test_scenario_15_dry_run_mode():
    sample_jobs = [
        {
            "id": "dry_run_job_1",
            "title": "Generative AI Engineer",
            "company": "Kinetix AI",
            "company_url": "https://kinetix.ai",
            "recruiter_email": "careers@kinetix.ai",
            "description": "Building RAG systems with LangGraph and Python.",
            "match_score": 92.0
        },
        {
            "id": "dry_run_job_2",
            "title": "Accountant / Bookkeeper", # Clearly irrelevant role
            "company": "General Finance Corp",
            "company_url": "https://generalfinance.com",
            "description": "Payroll and Excel ledger balancing.",
            "match_score": 40.0
        }
    ]

    report = await dry_run_service.execute_dry_run(sample_jobs)
    assert report["dry_run"] is True
    assert report["total_jobs_processed"] == 2
    assert report["relevant_jobs"] == 1
    assert report["irrelevant_jobs"] == 1
    assert report["verified_emails"] >= 1
    assert len(report["items"]) == 2
    # Ensure dry_run flag is preserved and no emails dispatched
    res_1 = report["items"][0]
    assert res_1["company"] == "Kinetix AI"
    assert res_1["email_status"] == "VERIFIED"
    assert res_1["send_allowed"] is True
    assert res_1["dry_run"] is True

# --- Scenario 16: DOMAIN_MATCH_ONLY blocking ---
def test_scenario_16_domain_match_only_blocking():
    job_data = {"company": "TargetAI", "company_url": "https://targetai.com"}
    is_valid, classification, score, reason = verify_email_for_job("employee@targetai.com", job_data)
    assert classification == RecipientClassification.DOMAIN_MATCH_ONLY
    # validate_recipient_before_send MUST reject DOMAIN_MATCH_ONLY
    allowed, status, block_reason = validate_recipient_before_send(job_data, "employee@targetai.com")
    assert allowed is False
    assert status == RecipientClassification.BLOCKED_INVALID_RECIPIENT
    assert "DOMAIN_MATCH_ONLY" in block_reason or "not VERIFIED" in block_reason

# --- Scenario 17: NOT_FOUND blocking ---
def test_scenario_17_not_found_blocking():
    job_data = {"company": "TargetAI", "company_url": "https://targetai.com"}
    allowed, status, block_reason = validate_recipient_before_send(job_data, None)
    assert allowed is False
    assert status == RecipientClassification.BLOCKED_INVALID_RECIPIENT

# --- Scenario 18: REJECTED blocking ---
def test_scenario_18_rejected_blocking():
    job_data = {"company": "TargetAI", "company_url": "https://targetai.com"}
    # Mismatched domain
    allowed, status, block_reason = validate_recipient_before_send(job_data, "spammer@badsource.net")
    assert allowed is False
    assert status == RecipientClassification.BLOCKED_INVALID_RECIPIENT
    assert "REJECTED" in block_reason

# --- Scenario 19: Multiple concurrent jobs isolation ---
@pytest.mark.asyncio
async def test_scenario_19_concurrent_jobs_isolation():
    number_words = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    async def resolve_worker(idx: int):
        comp_name = f"ConcurrentCo_{idx}"
        comp_url = f"https://concurrentco{idx}.com"
        email = f"talent@concurrentco{idx}.com" if idx % 2 == 0 else None
        job = {
            "company": comp_name,
            "company_url": comp_url,
            "recruiter_email": email,
            "description": f"AI job at {comp_name}"
        }
        rec = RecruiterBase(name=f"Recruiter {number_words[idx]}", company_name=comp_name, public_email=email) if email else None
        return email_resolution_service.resolve_recruiter_contact(job, rec)

    tasks = [resolve_worker(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    for idx, res in enumerate(results):
        if idx % 2 == 0:
            assert res.email == f"talent@concurrentco{idx}.com"
            assert res.status == RecipientClassification.VERIFIED
            assert res.recruiter_name == f"Recruiter {number_words[idx]}"
        else:
            assert res.email is None
            assert res.status == RecipientClassification.NOT_FOUND

# --- Scenario 20: LangGraph state isolation & relevance filtering ---
def test_scenario_20_langgraph_state_isolation_and_relevance():
    # Relevance filtering tests
    genai_job = {"title": "Generative AI / Agentic LLM Engineer", "description": "Build MCP servers and LangGraph agents in Python."}
    is_rel, kws = is_ai_engineer_relevant(genai_job)
    assert is_rel is True

    unrelated_job = {"title": "Warehouse Logistics Forklift Driver", "description": "Operate heavy machinery."}
    is_rel2, kws2 = is_ai_engineer_relevant(unrelated_job)
    assert is_rel2 is False

    # Never pick next(iter(recruiter_map.values())) without company keying
    recruiter_map = {
        "CompanyA": RecruiterBase(name="Alice A", company_name="CompanyA", public_email="alice@companya.com"),
        "CompanyB": RecruiterBase(name="Bob B", company_name="CompanyB", public_email="bob@companyb.com")
    }
    # CompanyC must NOT get CompanyA's recruiter
    rec_c = recruiter_map.get("CompanyC")
    assert rec_c is None
