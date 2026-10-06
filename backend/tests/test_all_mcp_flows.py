import pytest
import asyncio
import os
import sys
import uuid

# Ensure backend app is on sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

mcp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "mcp-servers", "job-platform"))
if mcp_path not in sys.path:
    sys.path.insert(0, mcp_path)

from sqlalchemy import select
from app.config.database import AsyncSessionLocal, engine, Base
from app.models.entities import CandidateProfile, Resume, Job, Application, ApprovalRequest, OutreachMessage, ApprovalStatus, ApplicationStatus
from tools.candidate import get_candidate_profile, get_candidate_resume, update_candidate_profile
from tools.jobs import search_jobs, get_search_run, get_search_results
from tools.matching import match_jobs
from tools.recruiters import find_recruiter
from tools.applications import prepare_application, prepare_applications_batch, get_application_status
from tools.approvals import get_pending_approvals, approve_applications, reject_applications
from tools.outreach import send_approved_email, prepare_linkedin_outreach

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def run_master_test_suite():
    print("==================================================================")
    print(" RUNNING COMPREHENSIVE END-TO-END MCP & HITL SAFETY TEST SUITE")
    print("==================================================================")
    await init_db()

    # 1. Candidate Profile & Resume Retrieval (Read-Only)
    print("\n[TEST 1] Candidate Profile Retrieval...")
    prof = await get_candidate_profile()
    assert "name" in prof, "Profile missing name"
    assert prof["years_of_experience"] is not None, "Missing YoE"
    print(f"  [OK] Profile retrieved: {prof['name']} ({prof['years_of_experience']} YoE)")

    print("\n[TEST 2] Candidate Resume Retrieval...")
    res = await get_candidate_resume()
    assert "summary" in res or "raw_text" in res, "Resume missing summary or raw_text"
    print("  [OK] Resume text retrieved successfully")

    # 2. Update Candidate Profile Preferences
    print("\n[TEST 3] Update Candidate Profile...")
    upd = await update_candidate_profile(
        preferred_roles=["AI Engineer", "Generative AI Engineer", "Agentic Systems Engineer"],
        skills=["Python", "FastAPI", "RAG", "LangGraph", "MCP", "AWS Bedrock"]
    )
    assert upd.get("status") == "UPDATED", f"Update failed: {upd}"
    print("  [OK] Candidate profile updated")

    # 3. Job Search & SearchRun
    print("\n[TEST 4] Job Search & Durable SearchRun...")
    search_res = await search_jobs(
        query="AI Engineer",
        location="India",
        remote=True,
        max_results=5
    )
    assert "search_id" in search_res, "Search response missing search_id"
    run_id = search_res["search_id"]
    jobs = search_res.get("jobs", [])
    assert len(jobs) > 0, "No jobs returned in search"
    print(f"  [OK] Found {len(jobs)} jobs under run_id={run_id}")

    print("\n[TEST 5] Get Search Run Inspection...")
    run_info = await get_search_run(run_id)
    assert run_info.get("run_id") == run_id, "Search run inspection failed"
    print(f"  [OK] Search run state: {run_info.get('status')}")

    # 4. Deterministic 7-Factor Matching Engine
    print("\n[TEST 6] Deterministic 7-Factor Matching Engine...")
    match_res = await match_jobs(run_id=run_id)
    assert "matches" in match_res or "results" in match_res, f"Matching failed: {match_res}"
    evaluated_jobs = match_res.get("matches") or match_res.get("results") or []
    assert len(evaluated_jobs) > 0, "No jobs evaluated in matching"
    first_match = evaluated_jobs[0]
    print(f"  [OK] Evaluated {len(evaluated_jobs)} jobs. Top match: {first_match.get('company')} - Score: {first_match.get('overall_score')}% ({first_match.get('classification')})")

    # 5. Recruiter Discovery
    print("\n[TEST 7] Recruiter Discovery...")
    rec_res = await find_recruiter(company="Microsoft", job_id=first_match.get("job_id"))
    assert "name" in rec_res, "Recruiter discovery failed"
    print(f"  [OK] Discovered recruiter contact: {rec_res.get('name')} ({rec_res.get('company')})")

    # 6. Single Application Preparation (HITL Safety Gate)
    print("\n[TEST 8] Application Preparation (Must create PENDING_APPROVAL)...")
    target_job_id = first_match["job_id"]
    prep_res = await prepare_application(job_id=target_job_id, run_id=run_id)
    assert prep_res.get("status") == "PREPARED", f"Preparation failed: {prep_res}"
    assert prep_res.get("approval_status") == "PENDING_APPROVAL", "Must be in PENDING_APPROVAL status"
    app_id = prep_res["application_id"]
    approval_id = prep_res["approval_id"]
    print(f"  [OK] Prepared application_id={app_id}, approval_id={approval_id} (PENDING_APPROVAL)")

    # 7. Duplicate Application Preparation Idempotency
    print("\n[TEST 9] Duplicate Application Preparation Prevention...")
    dup_prep = await prepare_application(job_id=target_job_id, run_id=run_id)
    assert dup_prep.get("status") == "PREPARED", "Duplicate preparation handling failed"
    assert dup_prep.get("application_id") == app_id, "Duplicate should reuse application ID"
    print("  [OK] Handled duplicate application preparation cleanly")

    # 8. Pending Approvals Inspection
    print("\n[TEST 10] Get Pending Approvals Table...")
    pending_res = await get_pending_approvals(run_id=run_id)
    assert pending_res.get("pending_count", 0) >= 1, "Expected at least 1 pending approval"
    print(f"  [OK] Retrieved {pending_res['pending_count']} pending applications awaiting human authorization")

    # 9. Read-Only Application Status Inspection
    print("\n[TEST 11] Read-Only Application Status Inspection...")
    status_res = await get_application_status(application_id=app_id)
    assert status_res.get("status") == "SUCCESS", f"Status inspection failed: {status_res}"
    assert status_res.get("application_status") in ("REVIEW_REQUIRED", "PENDING_APPROVAL", "PENDING"), f"Unexpected status {status_res.get('application_status')}"
    assert status_res.get("approval_status") == "PENDING", f"Expected PENDING approval status, got {status_res.get('approval_status')}"
    assert len(status_res.get("actions", [])) >= 2, "Audit actions should be tracked"
    print(f"  [OK] Verified read-only status: {status_res.get('job', {}).get('company')} ({status_res.get('approval_status')})")

    # 10. Safety Gate: Email Dispatched on Unapproved Application Must Fail
    print("\n[TEST 12] HITL Boundary: Dispatching email for unapproved application must be rejected...")
    unauth_email = await send_approved_email(application_id=app_id)
    assert "error" in unauth_email or unauth_email.get("status") == "FAILED", "Unauthorized email was not rejected!"
    print("  [OK] Unapproved email dispatch safely rejected as expected")

    # 11. Rejection Flow by Exact UUID
    print("\n[TEST 13] Rejection Flow by Exact UUID...")
    # Prepare a second job to test rejection
    if len(evaluated_jobs) > 1:
        second_job_id = evaluated_jobs[1]["job_id"]
        second_prep = await prepare_application(job_id=second_job_id, run_id=run_id)
        second_app_id = second_prep["application_id"]
        second_approval_id = second_prep["approval_id"]
        
        rej_res = await reject_applications(approval_ids=[second_approval_id])
        assert rej_res.get("rejected") == 1, f"Rejection failed: {rej_res}"
        
        rej_status = await get_application_status(application_id=second_app_id)
        assert rej_status.get("approval_status") == "REJECTED", f"Expected REJECTED, got {rej_status.get('approval_status')}"
        print(f"  [OK] Application {second_app_id} rejected cleanly")

    # 12. Approval Flow by Exact UUID
    print("\n[TEST 14] Human Approval Flow by Exact UUID...")
    appr_res = await approve_applications(approval_ids=[approval_id])
    assert appr_res.get("approved") == 1, f"Approval failed: {appr_res}"
    print(f"  [OK] Application {app_id} approved successfully")

    # 13. Post-Approval Status Inspection
    print("\n[TEST 15] Post-Approval Status Inspection...")
    post_appr_status = await get_application_status(application_id=app_id)
    assert post_appr_status.get("approval_status") == "APPROVED", f"Expected APPROVED, got {post_appr_status.get('approval_status')}"
    print(f"  [OK] Application status after approval: {post_appr_status.get('application_status')}, Approval: {post_appr_status.get('approval_status')}")

    # 14. LinkedIn Outreach Compliance Check
    print("\n[TEST 16] LinkedIn Outreach Compliance Check...")
    li_res = await prepare_linkedin_outreach(application_id=app_id)
    assert "compliance_notice" in li_res or "direct_linkedin_url" in li_res, "LinkedIn compliance check failed"
    print(f"  [OK] LinkedIn manual deep-link and copy prepared: {li_res.get('direct_linkedin_url')}")

    # 15. Unknown Application ID Handling (Non-Crashing Error Handling)
    print("\n[TEST 17] Unknown Application ID Clean Error Handling...")
    fake_id = str(uuid.uuid4())
    unknown_res = await get_application_status(application_id=fake_id)
    assert unknown_res.get("status") == "NOT_FOUND", f"Expected NOT_FOUND, got {unknown_res}"
    print("  [OK] Unknown application ID returned clean structured NOT_FOUND response")

    # 16. Empty / Invalid Input Handling
    print("\n[TEST 18] Invalid Application ID Input Handling...")
    empty_res = await get_application_status(application_id="")
    assert empty_res.get("status") == "NOT_FOUND" or "error" in empty_res or empty_res.get("error_code") == "INVALID_APPLICATION_ID"
    print("  [OK] Empty input returned clean structured error response")

    # 17. Batch Preparation under Bounded Concurrency
    print("\n[TEST 19] Batch Application Preparation under Bounded Concurrency...")
    batch_res = await prepare_applications_batch(run_id=run_id, max_concurrency=5)
    assert batch_res.get("status") == "WAITING_FOR_APPROVAL", f"Batch preparation failed: {batch_res}"
    assert batch_res.get("prepared", 0) >= 1, "Expected at least 1 prepared package"
    print(f"  [OK] Batch prepared {batch_res.get('prepared')} packages under bounded concurrency")

    print("\n==================================================================")
    print(" [SUCCESS] ALL 19 COMPREHENSIVE END-TO-END TESTS PASSED!")
    print("==================================================================")

async def main():
    try:
        await run_master_test_suite()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
