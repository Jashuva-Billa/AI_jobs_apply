import sys
import os
import asyncio
import uuid
import datetime
import pytest
from sqlalchemy import select

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "job-platform"))

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if mcp_path not in sys.path:
    sys.path.insert(0, mcp_path)

from app.config.database import AsyncSessionLocal
from app.models.entities import (
    CandidateProfile, Job, Application, ApprovalRequest,
    OutreachMessage, Recruiter, ApprovalStatus, ApplicationStatus
)
import server
from tools.applications import get_application_status

@pytest.mark.asyncio
async def test_get_application_status_unknown_id():
    """Verify unknown application ID returns clean NOT_FOUND response."""
    res = await get_application_status("non-existent-app-id-12345")
    assert res.get("status") == "NOT_FOUND"
    assert res.get("error_code") == "APPLICATION_NOT_FOUND"
    assert res.get("application_id") == "non-existent-app-id-12345"

@pytest.mark.asyncio
async def test_get_application_status_pending_app():
    """Verify status retrieval for a pending application with draft email and prepared LinkedIn."""
    app_id = f"test_app_{uuid.uuid4().hex[:8]}"
    job_id = f"test_job_{uuid.uuid4().hex[:8]}"
    approval_id = f"test_appr_{uuid.uuid4().hex[:8]}"

    async with AsyncSessionLocal() as session:
        # Create test job
        job = Job(
            id=job_id,
            company="OpenAI Applied Research",
            title="Senior GenAI Engineer",
            location="Remote",
            description="Developing next-gen models and agents.",
            application_url="https://openai.com/careers/genai-eng"
        )
        session.add(job)

        # Create candidate if needed
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()
        if not cand:
            cand = CandidateProfile(id=str(uuid.uuid4()), name="Jashuva Billa", email="jashuva@example.com")
            session.add(cand)
            await session.flush()

        # Create Application
        app = Application(
            id=app_id,
            candidate_id=cand.id,
            job_id=job_id,
            status=ApplicationStatus.REVIEW_REQUIRED
        )
        session.add(app)

        # Create ApprovalRequest
        appr = ApprovalRequest(
            id=approval_id,
            application_id=app_id,
            status=ApprovalStatus.PENDING,
            package_data={"company": "OpenAI Applied Research", "title": "Senior GenAI Engineer"}
        )
        session.add(appr)

        # Create Outreach Messages (Draft Email & Manual LinkedIn)
        session.add(OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Application for Senior GenAI Engineer",
            body="Hello Hiring Team...",
            recipient_email="recruiter@openai.com",
            recipient_name="OpenAI Talent Team",
            status="DRAFT"
        ))

        session.add(OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="LINKEDIN",
            subject="Connect regarding GenAI Role",
            body="Hi, I noticed your opening...",
            recipient_name="OpenAI Talent Team",
            status="MANUAL_REQUIRED"
        ))

        await session.commit()

    # Call get_application_status
    status_data = await get_application_status(app_id)
    assert status_data.get("status") == "SUCCESS"
    assert status_data.get("application_id") == app_id
    assert status_data.get("approval_id") == approval_id
    assert status_data.get("application_status") == "REVIEW_REQUIRED"
    assert status_data.get("approval_status") == "PENDING"
    
    # Check Job Info
    assert status_data["job"]["title"] == "Senior GenAI Engineer"
    assert status_data["job"]["company"] == "OpenAI Applied Research"
    assert status_data["job"]["application_url"] == "https://openai.com/careers/genai-eng"

    # Check Email Info
    assert status_data["email"]["status"] == "DRAFT"
    assert status_data["email"]["recipient"] == "recruiter@openai.com"

    # Check LinkedIn Info
    assert status_data["linkedin"]["status"] == "MANUAL_REQUIRED"
    assert status_data["linkedin"]["prepared"] is True
    assert status_data["linkedin"]["sent"] is False
    assert status_data["linkedin"]["manual_action_required"] is True

    # Check Actions History
    actions = status_data.get("actions", [])
    assert len(actions) >= 2
    action_names = [a["action"] for a in actions]
    assert "APPLICATION_INITIALIZED" in action_names
    assert "PACKAGE_PREPARED_PENDING_APPROVAL" in action_names
    assert "EMAIL_DRAFT_CREATED" in action_names
    assert "LINKEDIN_MANUAL_REQUIRED" in action_names

@pytest.mark.asyncio
async def test_get_application_status_approved_email_sent_linkedin_sent():
    """Verify status retrieval for an approved application with SENT email and SENT LinkedIn."""
    app_id = f"test_app_{uuid.uuid4().hex[:8]}"
    job_id = f"test_job_{uuid.uuid4().hex[:8]}"
    approval_id = f"test_appr_{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.utcnow()

    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()

        job = Job(
            id=job_id,
            company="Anthropic AI Labs",
            title="Staff RAG Systems Architect",
            location="Remote",
            description="Developing scalable production RAG architectures."
        )
        session.add(job)

        app = Application(
            id=app_id,
            candidate_id=cand.id,
            job_id=job_id,
            status=ApplicationStatus.RECRUITER_CONTACTED
        )
        session.add(app)

        appr = ApprovalRequest(
            id=approval_id,
            application_id=app_id,
            status=ApprovalStatus.APPROVED,
            approved_at=now
        )
        session.add(appr)

        session.add(OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Application for Staff RAG Systems Architect",
            body="Tailored body text...",
            recipient_email="talent@anthropic.com",
            recipient_name="Sarah Jenkins",
            status="SENT",
            sent_at=now
        ))

        session.add(OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="LINKEDIN",
            subject="Outreach Note",
            body="LinkedIn connection note...",
            recipient_name="Sarah Jenkins",
            status="SENT",
            sent_at=now
        ))

        await session.commit()

    status_data = await get_application_status(app_id)
    assert status_data.get("status") == "SUCCESS"
    assert status_data.get("application_status") == "RECRUITER_CONTACTED"
    assert status_data.get("approval_status") == "APPROVED"
    assert status_data["email"]["status"] == "SENT"
    assert status_data["email"]["sent_at"] is not None
    assert status_data["linkedin"]["status"] == "SENT"
    assert status_data["linkedin"]["sent"] is True
    assert status_data["linkedin"]["manual_action_required"] is False

    action_names = [a["action"] for a in status_data.get("actions", [])]
    assert "APPLICATION_APPROVED" in action_names
    assert "EMAIL_SENT" in action_names
    assert "LINKEDIN_OUTREACH_SENT" in action_names

@pytest.mark.asyncio
async def test_get_application_status_rejected_and_email_failed():
    """Verify status retrieval for a rejected application with failed email."""
    app_id = f"test_app_{uuid.uuid4().hex[:8]}"
    job_id = f"test_job_{uuid.uuid4().hex[:8]}"
    approval_id = f"test_appr_{uuid.uuid4().hex[:8]}"
    now = datetime.datetime.utcnow()

    async with AsyncSessionLocal() as session:
        cand_res = await session.execute(select(CandidateProfile).limit(1))
        cand = cand_res.scalars().first()

        job = Job(id=job_id, company="Mistral Tech", title="AI Engineer", location="Paris / Remote", description="Developing open-source LLMs.")
        session.add(job)

        app = Application(id=app_id, candidate_id=cand.id, job_id=job_id, status=ApplicationStatus.REJECTED)
        session.add(app)

        appr = ApprovalRequest(id=approval_id, application_id=app_id, status=ApprovalStatus.REJECTED, approved_at=now)
        session.add(appr)

        session.add(OutreachMessage(
            id=str(uuid.uuid4()),
            application_id=app_id,
            channel="EMAIL",
            subject="Application for AI Engineer",
            body="Body text...",
            recipient_email="invalid-bounce@mistral.ai",
            status="FAILED"
        ))

        await session.commit()

    status_data = await get_application_status(app_id)
    assert status_data.get("status") == "SUCCESS"
    assert status_data.get("application_status") == "REJECTED"
    assert status_data.get("approval_status") == "REJECTED"
    assert status_data["email"]["status"] == "FAILED"
    assert status_data["linkedin"]["status"] == "NOT_STARTED"

    action_names = [a["action"] for a in status_data.get("actions", [])]
    assert "APPLICATION_REJECTED" in action_names
    assert "EMAIL_DELIVERY_FAILED" in action_names

@pytest.mark.asyncio
async def test_read_only_guarantee():
    """Verify get_application_status does not mutate database records."""
    async with AsyncSessionLocal() as session:
        app_res = await session.execute(select(Application).limit(1))
        app = app_res.scalars().first()
        assert app is not None
        initial_status = app.status
        initial_updated_at = app.updated_at
        app_id = app.id

    # Call tool 3 times
    for _ in range(3):
        res = await get_application_status(app_id)
        assert res.get("status") == "SUCCESS"

    # Verify state in DB remains unchanged
    async with AsyncSessionLocal() as session:
        app_after = await session.get(Application, app_id)
        assert app_after.status == initial_status
        assert app_after.updated_at == initial_updated_at

@pytest.mark.asyncio
async def test_mcp_server_call_tool_get_application_status():
    """Verify get_application_status via official MCPServer tool call interface."""
    tools = await server.mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_application_status" in tool_names, "get_application_status tool not registered in MCPServer"

    async with AsyncSessionLocal() as session:
        app_res = await session.execute(select(Application).limit(1))
        app = app_res.scalars().first()
        app_id = app.id if app else "unknown"

    call_res = await server.mcp.call_tool("get_application_status", {"application_id": app_id})
    assert not call_res.is_error
    content_text = call_res.content[0].text if hasattr(call_res.content[0], "text") else str(call_res.content[0])
    assert app_id in content_text or "application_id" in content_text

async def main():
    print("Running test_get_application_status_unknown_id...")
    await test_get_application_status_unknown_id()
    print("[PASS] test_get_application_status_unknown_id")

    print("\nRunning test_get_application_status_pending_app...")
    await test_get_application_status_pending_app()
    print("[PASS] test_get_application_status_pending_app")

    print("\nRunning test_get_application_status_approved_email_sent_linkedin_sent...")
    await test_get_application_status_approved_email_sent_linkedin_sent()
    print("[PASS] test_get_application_status_approved_email_sent_linkedin_sent")

    print("\nRunning test_get_application_status_rejected_and_email_failed...")
    await test_get_application_status_rejected_and_email_failed()
    print("[PASS] test_get_application_status_rejected_and_email_failed")

    print("\nRunning test_read_only_guarantee...")
    await test_read_only_guarantee()
    print("[PASS] test_read_only_guarantee")

    print("\nRunning test_mcp_server_call_tool_get_application_status...")
    await test_mcp_server_call_tool_get_application_status()
    print("[PASS] test_mcp_server_call_tool_get_application_status")

    print("\n==============================================")
    print("ALL GET_APPLICATION_STATUS TESTS PASSED!")
    print("==============================================")

if __name__ == "__main__":
    asyncio.run(main())
