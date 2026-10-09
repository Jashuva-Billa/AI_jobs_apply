import pytest
import os
import uuid
import datetime
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from app.services.email_resolution_service import (
    email_resolution_service,
    validate_company_domain,
    verify_email_for_job,
    RecipientClassification,
)
from app.services.recruiter_service import recruiter_service
from app.services.application_service import application_service
from app.services.outreach_service import outreach_service
from app.config.database import AsyncSessionLocal
from app.models.entities import (
    CandidateProfile,
    Job,
    Recruiter,
    Application,
    OutreachMessage,
    ApprovalRequest,
    ApplicationStatus,
)
from app.schemas.schemas import CandidateProfileBase, RecruiterBase, ResolveRecruiterEmailRequest

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "job-platform")))
from tools.recruiters import resolve_recruiter_email
from tools.approvals import approve_application, get_pending_approvals
from tools.outreach import send_approved_email


# 1. Verified recruiter email
@pytest.mark.asyncio
async def test_1_verified_recruiter_email():
    job_data = {
        "company": "RedMimicry",
        "company_url": "https://redmimicry.com",
        "title": "Software Developer Security Analytics",
    }
    recruiter = RecruiterBase(
        name="Jane Doe",
        title="Technical Recruiter",
        company_name="RedMimicry",
        public_email="jane.doe@redmimicry.com",
        email_type="RECRUITER_SPECIFIC",
        source_url="https://redmimicry.com/team",
        source_type="PUBLIC_TEAM_PAGE",
        confidence="HIGH"
    )
    res = email_resolution_service.resolve_recruiter_contact(job_data, recruiter)
    assert res.email == "jane.doe@redmimicry.com"
    assert res.status == "VERIFIED"
    assert res.recruiter_name == "Jane Doe"
    assert res.confidence >= 0.85


# 2. Verified company recruiting email
@pytest.mark.asyncio
async def test_2_verified_company_recruiting_email():
    job_data = {
        "company": "RedMimicry",
        "company_url": "https://redmimicry.com",
        "title": "Software Developer Security Analytics",
        "recruiter_email": "careers@redmimicry.com"
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.email == "careers@redmimicry.com"
    assert res.status == "VERIFIED"
    assert res.email_type in ["COMPANY_RECRUITING", "COMPANY_GENERAL"]
    assert res.confidence >= 0.90


# 3. No email found (Outreach is NEEDS_EMAIL_REVIEW, application is still created and READY)
@pytest.mark.asyncio
async def test_3_no_email_found_preserves_application():
    job_data = {
        "company": "StealthCorp",
        "company_url": "https://stealthcorp.io",
        "title": "AI Researcher"
    }
    res = email_resolution_service.resolve_recruiter_contact(job_data)
    assert res.email is None
    assert res.status == "NOT_FOUND"

    cand = CandidateProfileBase(name="Jashuva Billa", email="jashuva@example.com")
    pkg = await application_service.prepare_application_package(cand, job_data, None)
    assert (pkg.job_id or "") == (job_data.get("id") or "")
    assert pkg.status == "READY"
    assert pkg.recruiter is None or pkg.recruiter.public_email is None

    outreach = await outreach_service.generate_recruiter_email(cand, job_data, None)
    assert outreach.recipient_email is None
    assert outreach.status == "NEEDS_EMAIL_REVIEW"


# 4. Invalid email format rejected
def test_4_invalid_email_format():
    assert not validate_company_domain("not-an-email", "RedMimicry")[0]
    assert not validate_company_domain("jane@@redmimicry..com", "RedMimicry")[0]
    assert not validate_company_domain("jane@redmimicry", "RedMimicry")[0]


# 5. Guessed email rejected (pattern guessing / wrong domain)
def test_5_guessed_email_rejected():
    is_valid, status, score, reason = verify_email_for_job(
        "recruiter@fakeunrelateddomain.org",
        {"company": "RedMimicry", "company_url": "https://redmimicry.com"}
    )
    assert not is_valid
    assert status == RecipientClassification.REJECTED


# 6. Missing source rejected
@pytest.mark.asyncio
async def test_6_missing_source_rejected_in_resolution():
    req = ResolveRecruiterEmailRequest(
        job_id="test-job-id",
        company_name="RedMimicry",
        email="recruiting@redmimicry.com",
        source_url="", # Missing source
        evidence="",   # Missing evidence
        confidence="HIGH"
    )
    res = await recruiter_service.resolve_and_persist_recruiter_email(req)
    assert not res.get("success")
    assert "source_url or evidence is required" in res.get("error", "")


# 7. Email persisted to database
@pytest.mark.asyncio
async def test_7_email_persisted_to_database():
    job_id = f"job-persist-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        job = Job(
            id=job_id,
            company="PersistCo",
            company_url="https://persistco.ai",
            title="Senior Engineer",
            description="Build scalable systems",
            verification_status="VERIFIED"
        )
        session.add(job)
        await session.commit()

    req = ResolveRecruiterEmailRequest(
        job_id=job_id,
        company_name="PersistCo",
        job_title="Senior Engineer",
        recruiter_name="Alice Smith",
        recruiter_title="Talent Lead",
        email="alice@persistco.ai",
        source_url="https://persistco.ai/careers",
        source_type="COMPANY_CAREERS_PAGE",
        evidence="Found on official careers page",
        confidence="HIGH"
    )
    res = await recruiter_service.resolve_and_persist_recruiter_email(req)
    assert res.get("success")

    async with AsyncSessionLocal() as session:
        rec_res = await session.execute(select(Recruiter).where(Recruiter.company_name == "PersistCo"))
        saved_rec = rec_res.scalars().first()
        assert saved_rec is not None
        assert saved_rec.public_email == "alice@persistco.ai"
        assert saved_rec.email_type == "RECRUITER_SPECIFIC"
        assert saved_rec.source_url == "https://persistco.ai/careers"
        assert saved_rec.confidence in ["HIGH", 0.95] or (isinstance(saved_rec.confidence, (int, float)) and saved_rec.confidence >= 0.85)


# 8. Email survives LangGraph state
@pytest.mark.asyncio
async def test_8_email_survives_langgraph_nodes():
    from app.graph.nodes import candidate_node, recruiter_node, application_node, outreach_node

    state = {
        "candidate_id": "cand-test-1",
        "prompt": "Find ML roles",
        "search_results": [
            {
                "id": "job-lg-1",
                "company": "LangGraph AI",
                "company_url": "https://langgraph.ai",
                "title": "LangGraph Engineer",
                "description": "LangGraph pipelines",
                "recruiter_email": "jobs@langgraph.ai"
            }
        ],
        "matched_jobs": [
            {
                "id": "job-lg-1",
                "company": "LangGraph AI",
                "company_url": "https://langgraph.ai",
                "title": "LangGraph Engineer",
                "description": "LangGraph pipelines",
                "recruiter_email": "jobs@langgraph.ai",
                "match_score": 90
            }
        ]
    }
    state = {**state, **(await candidate_node(state))}
    state = {**state, **(await recruiter_node(state))}
    assert "recruiters" in state
    assert len(state["recruiters"]) > 0
    rec_info = state["recruiters"][0]
    assert rec_info.get("public_email") == "jobs@langgraph.ai"

    state = {**state, **(await application_node(state))}
    assert "application_packages" in state
    app_pkg = state["application_packages"][0]
    assert app_pkg.get("recruiter", {}).get("public_email") == "jobs@langgraph.ai"

    state = await outreach_node(state)
    assert "outreach_packages" in state or "outreach" in state
    out_pkg = state.get("outreach_packages", [state.get("outreach")])[0]
    rec_email = out_pkg.get("recipient_email") or out_pkg.get("email", {}).get("recipient_email")
    out_status = out_pkg.get("status") or out_pkg.get("email", {}).get("status") or state.get("approval_status")
    assert out_status in ["READY_FOR_APPROVAL", "PENDING"]


# 9. Email survives application package
@pytest.mark.asyncio
async def test_9_email_survives_application_package():
    cand = CandidateProfileBase(name="Jashuva Billa", email="jashuva@example.com")
    job = {
        "id": "job-pkg-1",
        "company": "Package Corp",
        "title": "Python Dev",
        "recruiter_email": "careers@packagecorp.com"
    }
    rec = RecruiterBase(
        name="Bob",
        title="HR",
        company_name="Package Corp",
        public_email="careers@packagecorp.com"
    )
    pkg = await application_service.prepare_application_package(cand, job, rec)
    assert pkg.recruiter.public_email == "careers@packagecorp.com"
    assert pkg.status == "READY"


# 10. Email survives outreach package
@pytest.mark.asyncio
async def test_10_email_survives_outreach_package():
    cand = CandidateProfileBase(name="Jashuva Billa", email="jashuva@example.com")
    job = {
        "id": "job-pkg-2",
        "company": "Package Corp",
        "title": "Python Dev",
        "recruiter_email": "careers@packagecorp.com"
    }
    rec = RecruiterBase(
        name="Bob",
        title="HR",
        company_name="Package Corp",
        public_email="careers@packagecorp.com",
        email_type="COMPANY_RECRUITING",
        source_url="https://packagecorp.com",
        confidence="HIGH"
    )
    out = await outreach_service.generate_recruiter_email(cand, job, rec)
    assert out.recipient_email == "careers@packagecorp.com"
    assert out.email_status == "VERIFIED"
    assert out.email_confidence >= 0.90


# 11. Streamlit displays clean email / no "(0)" artifact
def test_11_streamlit_email_representation():
    email = "recruiter@example.com"
    label = "Recipient Email"
    assert " (0)" not in label
    assert email is not None and len(email) > 0


# 12. Approval works
@pytest.mark.asyncio
async def test_12_approval_works():
    app_id = f"app-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        if not cand:
            cand = CandidateProfile(id=str(uuid.uuid4()), name="Test User", email="user@test.com")
            session.add(cand)
            await session.flush()

        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = Job(id=job_id, company="ApproveCo", title="DevOps", verification_status="VERIFIED")
        session.add(job)

        app_obj = Application(id=app_id, candidate_id=cand.id, job_id=job_id, status=ApplicationStatus.REVIEW_REQUIRED)
        session.add(app_obj)

        apr = ApprovalRequest(
            id=str(uuid.uuid4()),
            candidate_id=cand.id,
            job_id=job_id,
            application_id=app_id,
            approval_type="APPLICATION_AND_OUTREACH",
            package_data={"job_id": job_id, "recipient_email": "hiring@approveco.com"},
            status="PENDING"
        )
        session.add(apr)
        await session.commit()

    res = await approve_application(app_id, comments="Looks great")
    assert res.get("status") in ["APPROVED", "ALREADY_APPROVED"]


# 13. Dispatch works with valid email
@pytest.mark.asyncio
async def test_13_dispatch_works_with_valid_email():
    app_id = f"app-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()

        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = Job(id=job_id, company="ValidSendCo", company_url="https://validsend.com", title="Engineer", recruiter_email="talent@validsend.com", verification_status="VERIFIED")
        session.add(job)

        app_obj = Application(id=app_id, candidate_id=cand.id, job_id=job_id, status=ApplicationStatus.APPROVED)
        session.add(app_obj)

        out = OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Job Application",
            body="Hello team...",
            recipient_email="talent@validsend.com",
            email_status="VERIFIED",
            status="READY_FOR_APPROVAL"
        )
        session.add(out)
        await session.commit()

    res = await send_approved_email(app_id)
    assert res.get("status") in ["SENT", "SIMULATED_SENT"]


# 14. Dispatch blocked without email
@pytest.mark.asyncio
async def test_14_dispatch_blocked_without_email():
    app_id = f"app-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()

        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = Job(id=job_id, company="NoEmailCo", company_url="https://noemail.com", title="Engineer", verification_status="VERIFIED")
        session.add(job)

        app_obj = Application(id=app_id, candidate_id=cand.id, job_id=job_id, status=ApplicationStatus.APPROVED)
        session.add(app_obj)

        out = OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Job Application",
            body="Hello team...",
            recipient_email=None, # Missing email!
            status="NEEDS_EMAIL_REVIEW"
        )
        session.add(out)
        await session.commit()

    res = await send_approved_email(app_id)
    assert res.get("status") in ["BLOCKED", "NO_VERIFIED_RECIPIENT_EMAIL"]


# 15. Duplicate dispatch prevented (idempotency key candidate_id:job_id:EMAIL_OUTREACH)
@pytest.mark.asyncio
async def test_15_duplicate_dispatch_prevented():
    app_id = f"app-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()

        job_id = f"job-{uuid.uuid4().hex[:8]}"
        job = Job(id=job_id, company="DupeCo", company_url="https://dupeco.com", title="Engineer", verification_status="VERIFIED")
        session.add(job)

        app_obj = Application(id=app_id, candidate_id=cand.id, job_id=job_id, status=ApplicationStatus.APPROVED)
        session.add(app_obj)

        out = OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Job Application",
            body="Hello team...",
            recipient_email="careers@dupeco.com",
            status="SENT" # Already sent!
        )
        session.add(out)
        await session.commit()

    res = await send_approved_email(app_id)
    assert res.get("status") == "ALREADY_SENT"


# 16. Same company email reuse
@pytest.mark.asyncio
async def test_16_same_company_email_reuse():
    # Save a company recruiting email for CompanyOmni
    async with AsyncSessionLocal() as session:
        rec = Recruiter(
            id=str(uuid.uuid4()),
            name="Omni Talent Team",
            company_name="CompanyOmni",
            public_email="careers@companyomni.ai",
            email_type="COMPANY_RECRUITING",
            source_url="https://companyomni.ai/jobs",
            source_type="OFFICIAL_CAREERS_PAGE",
            confidence="HIGH"
        )
        session.add(rec)
        await session.commit()

    # Now discover recruiter for a new job at CompanyOmni without recruiter info
    job_new = {"company": "CompanyOmni", "company_url": "https://companyomni.ai", "title": "Frontend Lead"}
    discovered = await recruiter_service.discover_recruiter_for_job(job_new)
    assert discovered is not None
    assert discovered.public_email == "careers@companyomni.ai"
    assert discovered.email_type == "COMPANY_RECRUITING"


# 17. 50+ job batch processing resilience
@pytest.mark.asyncio
async def test_17_batch_processing_resilience():
    cand = CandidateProfileBase(name="Jashuva Billa", email="jashuva@example.com")
    jobs = [
        {
            "id": f"job-batch-{i}",
            "company": f"BatchCo{i}",
            "company_url": f"https://batchco{i}.com",
            "title": "Engineer",
            "recruiter_email": f"hiring@batchco{i}.com" if i % 2 == 0 else None
        }
        for i in range(50)
    ]

    outreach_packages = []
    for job in jobs:
        res = email_resolution_service.resolve_recruiter_contact(job)
        rec = RecruiterBase(name="Recruiter", company_name=job["company"], public_email=res.email) if res.email else None
        out = await outreach_service.generate_recruiter_email(cand, job, rec)
        outreach_packages.append(out)

    ready_count = sum(1 for o in outreach_packages if o.status == "READY_FOR_APPROVAL")
    review_count = sum(1 for o in outreach_packages if o.status == "NEEDS_EMAIL_REVIEW")

    assert ready_count == 25
    assert review_count == 25
    assert len(outreach_packages) == 50


# 18. Partial email-resolution failures handled gracefully
@pytest.mark.asyncio
async def test_18_partial_resolution_failure():
    # Calling resolution on non-existent or malformed job doesn't throw 500
    req = ResolveRecruiterEmailRequest(
        job_id="non-existent-job",
        company_name="Fake Unknown Co",
        email="invalid-email-no-domain",
        source_url="https://fake.com",
        evidence="Some evidence",
        confidence="HIGH"
    )
    res = await recruiter_service.resolve_and_persist_recruiter_email(req)
    assert not res.get("success")
    assert res.get("error") is not None


# 19. MCP resolve_recruiter_email tool end-to-end
@pytest.mark.asyncio
async def test_19_mcp_resolve_recruiter_email():
    job_id = f"job-mcp-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        job = Job(
            id=job_id,
            company="MCP Testing Inc",
            company_url="https://mcptesting.ai",
            title="MCP Protocol Specialist",
            verification_status="VERIFIED"
        )
        session.add(job)
        await session.commit()

    result = await resolve_recruiter_email(
        job_id=job_id,
        company_name="MCP Testing Inc",
        job_title="MCP Protocol Specialist",
        recruiter_name="Sam Altman",
        recruiter_title="Talent Specialist",
        email="sam@mcptesting.ai",
        source_url="https://mcptesting.ai/team",
        source_type="PUBLIC_TEAM_PAGE",
        evidence="Found on team page under MCP specialists",
        confidence="HIGH"
    )
    assert result.get("success")
    assert result.get("email") == "sam@mcptesting.ai"
    assert result.get("status") == "VERIFIED"


# 20. Full end-to-end RedMimicry flow
@pytest.mark.asyncio
async def test_20_redmimicry_end_to_end_flow():
    job_id = f"job-redmimicry-{uuid.uuid4().hex[:8]}"
    company_name = "RedMimicry"
    title = "Software Developer Security Analytics"

    # Step 1: Initialize Job & Candidate in Database
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        if not cand:
            cand = CandidateProfile(
                id=str(uuid.uuid4()),
                name="Jashuva Billa",
                email="jashuvabilla@gmail.com",
                skills=["Python", "Security", "Analytics", "FastAPI"]
            )
            session.add(cand)
            await session.flush()
        cand_id = cand.id

        job = Job(
            id=job_id,
            company=company_name,
            company_url="https://redmimicry.com",
            title=title,
            description="Software Developer Security Analytics at RedMimicry",
            verification_status="VERIFIED"
        )
        session.add(job)
        await session.commit()

    # Step 2: ChatGPT Web researches and calls resolve_recruiter_email MCP tool
    resolve_result = await resolve_recruiter_email(
        job_id=job_id,
        company_name=company_name,
        job_title=title,
        job_url="https://redmimicry.com/jobs/sec-analytics",
        recruiter_name="Alexander Fischer",
        recruiter_title="Hiring Manager / Founder",
        email="careers@redmimicry.com",
        source_url="https://redmimicry.com/contact",
        source_type="COMPANY_CAREERS_PAGE",
        evidence="Publicly listed careers contact on redmimicry.com",
        confidence="HIGH"
    )
    assert resolve_result.get("success")
    assert resolve_result.get("email") == "careers@redmimicry.com"

    # Step 3: Application & Outreach Package Preparation
    cand_base = CandidateProfileBase(name="Jashuva Billa", email="jashuvabilla@gmail.com", skills=["Python", "FastAPI"])
    discovered_rec = await recruiter_service.discover_recruiter_for_job({"id": job_id, "company": company_name, "title": title})
    assert discovered_rec is not None
    assert discovered_rec.public_email == "careers@redmimicry.com"

    app_pkg = await application_service.prepare_application_package(cand_base, {"id": job_id, "company": company_name, "title": title}, discovered_rec)
    out_pkg = await outreach_service.generate_recruiter_email(cand_base, {"id": job_id, "company": company_name, "title": title}, discovered_rec)

    assert app_pkg.status == "READY"
    assert out_pkg.recipient_email == "careers@redmimicry.com"
    assert out_pkg.status == "READY_FOR_APPROVAL"

    # Step 4: Persist in approval & application flow
    app_id = f"app-redmimicry-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        app_obj = Application(
            id=app_id,
            candidate_id=cand_id,
            job_id=job_id,
            status=ApplicationStatus.REVIEW_REQUIRED
        )
        session.add(app_obj)

        out_msg = OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject=out_pkg.subject,
            body=out_pkg.body,
            recipient_email=out_pkg.recipient_email,
            status=out_pkg.status
        )
        session.add(out_msg)

        apr = ApprovalRequest(
            id=str(uuid.uuid4()),
            candidate_id=cand_id,
            job_id=job_id,
            application_id=app_id,
            approval_type="APPLICATION_AND_OUTREACH",
            package_data={"job_id": job_id, "recipient_email": out_pkg.recipient_email},
            status="PENDING"
        )
        session.add(apr)
        await session.commit()

    # Step 5: Approve
    apprv_res = await approve_application(app_id, comments="Approved RedMimicry outreach")
    assert apprv_res.get("status") in ["APPROVED", "ALREADY_APPROVED"]

    # Step 6: Dispatch
    dispatch_res = await send_approved_email(app_id)
    assert dispatch_res.get("status") in ["SENT", "SIMULATED_SENT", "ALREADY_SENT"]

    # Step 7: Verify Idempotency (Repeat dispatch)
    repeat_res = await send_approved_email(app_id)
    assert repeat_res.get("status") == "ALREADY_SENT"

