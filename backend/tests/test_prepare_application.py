import sys
import os
import asyncio
import uuid
import pytest
from sqlalchemy import select

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "job-platform"))

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if mcp_path not in sys.path:
    sys.path.insert(0, mcp_path)

from app.config.database import AsyncSessionLocal, engine, Base
from app.models.entities import (
    CandidateProfile, Job, Application, ApprovalRequest,
    OutreachMessage, ApplicationQuestion, ApprovalStatus, ApplicationStatus, AgentRun
)
from app.schemas.schemas import CandidateProfileBase, MatchBreakdown
from app.services.application_service import application_service
import server
from tools.applications import prepare_application, prepare_applications_batch
from tools.approvals import get_pending_approvals, approve_applications

@pytest.mark.asyncio
async def test_application_service_prepare_full_package():
    """Verify application_service.prepare_full_package creates a structured ApplicationPackage."""
    cand = CandidateProfileBase(
        name="Jashuva Billa",
        email="jashuva@example.com",
        years_of_experience=2.9,
        skills=["Python", "FastAPI", "RAG", "LangGraph"],
        technical_skills=["Python", "FastAPI"],
        preferred_roles=["AI Engineer"]
    )
    job_dict = {
        "id": f"test_job_{uuid.uuid4().hex[:8]}",
        "title": "Senior AI Systems Engineer",
        "company": "Anthropic AI Labs",
        "location": "Remote",
        "skills": ["Python", "RAG", "LangGraph", "FastAPI"],
        "description": "Building next-gen AI systems."
    }
    
    pkg = await application_service.prepare_full_package(cand, job_dict)
    assert pkg is not None
    assert pkg.tailored_resume_summary is not None
    assert len(pkg.tailored_resume_summary) > 0
    assert pkg.cover_letter is not None
    assert "Anthropic AI Labs" in pkg.cover_letter
    assert len(pkg.questions) > 0
    assert pkg.match is not None

@pytest.mark.asyncio
async def test_prepare_application_and_hitl_flow():
    """
    Test complete prepare_application -> PENDING_APPROVAL -> get_pending_approvals -> approve_applications workflow.
    Verifies:
    - Package is PREPARED in PENDING status
    - No application is submitted
    - No email is sent (status is DRAFT)
    - No LinkedIn action occurs (status is DRAFT)
    - get_pending_approvals lists the approval
    - approve_applications successfully transitions to APPROVED
    - Calling prepare_application twice does not create duplicate applications or approval records.
    """
    async with AsyncSessionLocal() as session:
        # 1. Setup test candidate
        res_c = await session.execute(select(CandidateProfile).limit(1))
        cand = res_c.scalars().first()
        if not cand:
            cand = CandidateProfile(
                id=str(uuid.uuid4()),
                name="Jashuva Billa",
                email="jashuvabilla@example.com",
                years_of_experience=2.9,
                skills=["Python", "RAG", "LangGraph", "FastAPI"],
                preferred_roles=["AI Engineer"]
            )
            session.add(cand)
            await session.commit()
            
        cand_id = cand.id

        # 2. Create isolated test job
        unique_suffix = uuid.uuid4().hex[:8]
        job_id = f"test_job_{unique_suffix}"
        test_company = f"DeepMind Robotics {unique_suffix}"
        test_title = f"Agentic AI Engineer {unique_suffix}"
        test_job = Job(
            id=job_id,
            company=test_company,
            title=test_title,
            location="Remote",
            description="Developing autonomous LLM agents.",
            skills=["Python", "RAG", "LangGraph", "FastAPI"],
            requirements=["2+ years experience"]
        )
        session.add(test_job)
        await session.commit()

    # 3. Call prepare_application via MCP tool function
    result = await prepare_application(candidate_id=cand_id, job_id=job_id)
    assert result.get("status") == "PREPARED", f"Expected PREPARED, got {result}"
    assert result.get("approval_status") == "PENDING_APPROVAL"
    approval_id = result.get("approval_id")
    app_id = result.get("application_id")
    assert approval_id is not None
    assert app_id is not None

    # 4. Verify SQL state: NOT submitted, NOT approved, email NOT sent
    async with AsyncSessionLocal() as session:
        app_rec = await session.get(Application, app_id)
        assert app_rec is not None
        assert app_rec.status == ApplicationStatus.REVIEW_REQUIRED  # Safe pending state
        assert app_rec.applied_at is None  # NOT submitted

        appr_rec = await session.get(ApprovalRequest, approval_id)
        assert appr_rec is not None
        assert appr_rec.status == ApprovalStatus.PENDING  # PENDING approval
        assert appr_rec.approved_at is None

        # Verify Outreach messages are strictly DRAFT
        o_res = await session.execute(select(OutreachMessage).filter_by(application_id=app_id))
        outreaches = o_res.scalars().all()
        assert len(outreaches) >= 1
        for o in outreaches:
            assert o.status in ("DRAFT", "MANUAL_REQUIRED"), f"Outreach message must be DRAFT, got {o.status}"
            assert o.sent_at is None  # NO email sent

    # 5. Verify get_pending_approvals returns the newly created approval
    pending_res = await get_pending_approvals()
    assert pending_res.get("pending_count", 0) >= 1
    matching = [a for a in pending_res.get("approvals", []) if a["approval_id"] == approval_id]
    assert len(matching) == 1
    assert matching[0]["company"] == test_company
    assert matching[0]["title"] == test_title

    # 6. Test Idempotency / Duplicate Detection: Calling prepare_application a second time for same job
    result_dup = await prepare_application(candidate_id=cand_id, job_id=job_id)
    assert result_dup.get("status") in ("PREPARED", "SKIPPED_ALREADY_PROCESSED")

    # Verify no duplicate records created in SQL
    async with AsyncSessionLocal() as session:
        apps = (await session.execute(select(Application).filter_by(candidate_id=cand_id, job_id=job_id))).scalars().all()
        assert len(apps) == 1, "Duplicate Application record created!"
        apprs = (await session.execute(select(ApprovalRequest).filter_by(application_id=app_id))).scalars().all()
        assert len(apprs) == 1, "Duplicate ApprovalRequest record created!"

    # 7. Test Approval Flow: approve_applications
    approve_res = await approve_applications([approval_id])
    assert approve_res.get("approved") == 1
    assert approve_res.get("failed") == 0

    # Verify state after approval
    async with AsyncSessionLocal() as session:
        appr_after = await session.get(ApprovalRequest, approval_id)
        assert appr_after.status == ApprovalStatus.APPROVED

@pytest.mark.asyncio
async def test_mcp_server_call_tool_prepare_application():
    """Verify prepare_application execution directly through official MCP server interface."""
    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        job_res = await session.execute(select(Job).limit(1))
        job = job_res.scalars().first()

    assert cand is not None and job is not None

    mcp_call_res = await server.mcp.call_tool("prepare_application", {
        "candidate_id": cand.id,
        "job_id": job.id
    })
    assert not mcp_call_res.is_error
    data = mcp_call_res.content[0].text if hasattr(mcp_call_res.content[0], "text") else str(mcp_call_res.content[0])
    assert "PREPARED" in data or "approval_id" in data or "SKIPPED_ALREADY_PROCESSED" in data

async def main():
    print("Running test_application_service_prepare_full_package...")
    await test_application_service_prepare_full_package()
    print("[PASS] test_application_service_prepare_full_package")

    print("\nRunning test_prepare_application_and_hitl_flow...")
    await test_prepare_application_and_hitl_flow()
    print("[PASS] test_prepare_application_and_hitl_flow")

    print("\nRunning test_mcp_server_call_tool_prepare_application...")
    await test_mcp_server_call_tool_prepare_application()
    print("[PASS] test_mcp_server_call_tool_prepare_application")

    print("\n==========================================")
    print("ALL PREPARE_APPLICATION TESTS PASSED!")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(main())
