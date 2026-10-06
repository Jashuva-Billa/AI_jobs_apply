import sys
import os
import asyncio
import pytest

# Ensure mcp-servers and backend are on sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "job-platform"))

if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
if mcp_path not in sys.path:
    sys.path.insert(0, mcp_path)

import server
from app.config.settings import settings

@pytest.mark.asyncio
async def test_mcp_tool_discovery():
    """Verify all 15 core MCP tools are properly discovered by MCPServer."""
    tools = await server.mcp.list_tools()
    tool_names = [t.name for t in tools]
    
    expected_tools = [
        "get_candidate_profile",
        "update_candidate_profile",
        "get_candidate_resume",
        "search_jobs",
        "get_search_run",
        "get_search_results",
        "match_jobs",
        "find_recruiter",
        "prepare_application",
        "prepare_applications_batch",
        "get_pending_approvals",
        "approve_applications",
        "reject_applications",
        "send_approved_email",
        "prepare_linkedin_outreach"
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Missing MCP tool: {exp}"

@pytest.mark.asyncio
async def test_candidate_tools():
    """Test candidate profile, resume, and preference updates."""
    # 1. Profile retrieval
    res_prof = await server.mcp.call_tool("get_candidate_profile", {})
    assert not res_prof.is_error
    
    # 2. Resume retrieval
    res_resume = await server.mcp.call_tool("get_candidate_resume", {})
    assert not res_resume.is_error
    
    # 3. Preference update
    res_upd = await server.mcp.call_tool("update_candidate_profile", {
        "preferred_roles": ["AI Engineer", "GenAI Engineer", "RAG Engineer"],
        "preferred_locations": ["Remote India", "Hyderabad"]
    })
    assert not res_upd.is_error

@pytest.mark.asyncio
async def test_end_to_end_mcp_job_pipeline():
    """
    Test full deterministic pipeline:
    search_jobs -> match_jobs -> prepare_applications_batch -> get_pending_approvals -> approve_applications -> send_approved_email
    """
    # Step 1: Execute Job Search
    search_res = await server.mcp.call_tool("search_jobs", {
        "query": "AI Engineer",
        "location": "India",
        "remote": True,
        "max_results": 10
    })
    assert not search_res.is_error
    
    # Step 2: Deterministic 7-factor Matching
    # Get the latest run from SQL
    from sqlalchemy import select
    from app.config.database import AsyncSessionLocal
    from app.models.entities import AgentRun, Application, ApprovalRequest, Job
    
    async with AsyncSessionLocal() as session:
        r_res = await session.execute(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(1))
        latest_run = r_res.scalars().first()
        assert latest_run is not None
        run_id = latest_run.id

    match_res = await server.mcp.call_tool("match_jobs", {"run_id": run_id})
    assert not match_res.is_error

    # Step 3: Check search results retrieval
    results_res = await server.mcp.call_tool("get_search_results", {"run_id": run_id, "page": 1, "page_size": 10})
    assert not results_res.is_error

    # Step 4: Batch Application Preparation under bounded concurrency
    prep_res = await server.mcp.call_tool("prepare_applications_batch", {"run_id": run_id, "max_concurrency": 5})
    assert not prep_res.is_error

    # Step 5: HITL Gate - Fetch Pending Approvals
    pending_res = await server.mcp.call_tool("get_pending_approvals", {"run_id": run_id})
    assert not pending_res.is_error

    # Step 6: Explicit Approval of Applications
    async with AsyncSessionLocal() as session:
        ap_res = await session.execute(select(ApprovalRequest).filter_by(run_id=run_id).limit(2))
        approvals = ap_res.scalars().all()
        approval_ids = [a.id for a in approvals]

    if approval_ids:
        approve_res = await server.mcp.call_tool("approve_applications", {"approval_ids": approval_ids})
        assert not approve_res.is_error

        # Step 7: Send approved email
        async with AsyncSessionLocal() as session:
            app_rec = await session.get(ApprovalRequest, approval_ids[0])
            app_id = app_rec.application_id

        email_res = await server.mcp.call_tool("send_approved_email", {"application_id": app_id})
        assert not email_res.is_error

        # Step 8: LinkedIn Outreach Copy Generation
        li_res = await server.mcp.call_tool("prepare_linkedin_outreach", {"application_id": app_id})
        assert not li_res.is_error

@pytest.mark.asyncio
async def test_rejection_workflow():
    """Test rejecting application records in SQL."""
    from sqlalchemy import select
    from app.config.database import AsyncSessionLocal
    from app.models.entities import ApprovalRequest, ApprovalStatus
    
    async with AsyncSessionLocal() as session:
        ap_res = await session.execute(select(ApprovalRequest).filter_by(status=ApprovalStatus.PENDING).limit(1))
        approval_rec = ap_res.scalars().first()

    if approval_rec:
        reject_res = await server.mcp.call_tool("reject_applications", {"approval_ids": [approval_rec.id]})
        assert not reject_res.is_error

async def main():
    print("Running MCP Tool Discovery test...")
    await test_mcp_tool_discovery()
    print("[PASS] test_mcp_tool_discovery passed!")
    
    print("\nRunning Candidate Tools test...")
    await test_candidate_tools()
    print("[PASS] test_candidate_tools passed!")
    
    print("\nRunning End-to-End MCP Pipeline test...")
    await test_end_to_end_mcp_job_pipeline()
    print("[PASS] test_end_to_end_mcp_job_pipeline passed!")
    
    print("\nRunning Rejection Workflow test...")
    await test_rejection_workflow()
    print("[PASS] test_rejection_workflow passed!")
    
    print("\n==========================================")
    print("ALL MCP SERVER TESTS PASSED SUCCESSFULLY!")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(main())
