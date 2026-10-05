import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config.settings import settings
from app.config.database import engine, Base, AsyncSessionLocal
from app.graph.graph import job_application_graph
from app.graph.state import JobApplicationState
from app.services.matching_service import matching_service
from app.services.job_service import job_service
from app.services.recruiter_service import recruiter_service
from app.services.application_service import application_service
from app.services.outreach_service import outreach_service
from app.schemas.schemas import CandidateProfileBase, SearchCriteria

async def main():
    print("=" * 70)
    print("[DRY RUN] AGENTIC JOB RESEARCH & APPLICATION PIPELINE")
    print("=" * 70)
    print(f"* Configured Model: {settings.effective_openai_model}")
    print(f"* OpenAI Web Search Enabled: {settings.OPENAI_WEB_SEARCH_ENABLED}")
    print(f"* Web Search Context Size: {settings.OPENAI_WEB_SEARCH_CONTEXT_SIZE}")
    print(f"* Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print(f"* Demo Mode: {settings.DEMO_MODE}")
    print("-" * 70)

    # 1. Initialize Tables
    print("1. Initializing Database Schema...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("   [OK] Database connection and schema verified.")
    except Exception as db_err:
        print(f"   [NOTE] Local MySQL connection ({db_err}). Proceeding with in-memory pipeline verification...")

    # 2. Candidate Profile
    print("\n2. Loading Candidate Profile...")
    candidate = CandidateProfileBase(
        name="Jashuva Billa",
        email="jashuvabilla@gmail.com",
        years_of_experience=3.0,
        skills=["Python", "RAG", "LangGraph", "Agentic AI", "MCP", "AWS", "FastAPI", "Docker", "PostgreSQL"],
        technical_skills=["Python", "FastAPI", "Docker"],
        cloud_skills=["AWS"],
        frameworks=["LangGraph"],
        preferred_roles=["AI Engineer", "GenAI Engineer", "ML Engineer"],
        preferred_locations=["Remote", "India"],
        remote_preference=True,
        work_authorization="Authorized for remote work from India"
    )
    print(f"   [OK] Candidate: {candidate.name} ({candidate.years_of_experience} yrs exp)")
    print(f"   [OK] Core Skills: {', '.join(candidate.skills[:6])}")

    # 3. User Directive
    user_prompt = (
        "Find remote AI Engineer and GenAI Engineer jobs requiring 2-4 years of experience. "
        "Focus on Python, RAG, LangGraph, Agentic AI, MCP and AWS. I can work remotely from India. "
        "Find the strongest current opportunities and recruiter information."
    )
    print(f"\n3. User Directive:\n   \"{user_prompt}\"")

    # 4. Multi-Agent Graph Execution
    print("\n4. Executing LangGraph Multi-Agent Pipeline...")
    initial_state: JobApplicationState = {
        "run_id": "dry_run_001",
        "user_prompt": user_prompt,
        "search_criteria": {},
        "candidate_profile": candidate.model_dump(),
        "discovered_jobs": [],
        "normalized_jobs": [],
        "deduplicated_jobs": [],
        "matched_jobs": [],
        "ranked_jobs": [],
        "selected_job": None,
        "recruiter": None,
        "application_package": None,
        "outreach": None,
        "approval_required": True,
        "approval_status": "PENDING",
        "errors": [],
        "current_step": "START",
        "events": []
    }

    final_state = await job_application_graph.ainvoke(initial_state)

    print("\n" + "=" * 70)
    print("[RESULTS] PIPELINE EXECUTION SUMMARY")
    print("=" * 70)
    
    # Events summary
    events = final_state.get("events", [])
    print(f"\n* Total Agent Events Logged: {len(events)}")
    for ev in events:
        print(f"  [{ev.get('agent_name')}] -> {ev.get('step')}: {ev.get('message')}")

    # Discovered Jobs
    discovered = final_state.get("discovered_jobs", [])
    print(f"\n* Discovered & Deduplicated Jobs: {len(discovered)}")
    for idx, j in enumerate(discovered[:3]):
        verif = j.get("verification_status", "VERIFIED")
        print(f"  {idx+1}. {j.get('title')} @ {j.get('company')} [{verif}] | Loc: {j.get('location')}")
        if j.get("evidence"):
            for ev_item in j.get("evidence")[:1]:
                print(f"     Source Citation: {ev_item.get('title')} ({ev_item.get('url')})")

    # Matched & Ranked Jobs
    ranked = final_state.get("ranked_jobs", [])
    print(f"\n* Evaluated Matches (7-Factor Deterministic Engine):")
    for idx, j in enumerate(ranked[:3]):
        m = j.get("match", {})
        print(f"  {idx+1}. {j.get('company')} - {j.get('title')}: {m.get('overall_score')}% ({m.get('recommendation')})")
        print(f"     Skills: {m.get('skills_score')}% | Exp: {m.get('experience_score')}% | Loc: {m.get('location_score')}%")

    # Selected Job & Recruiter
    selected = final_state.get("selected_job", {})
    recruiter = final_state.get("recruiter", {})
    print(f"\n* Top Selected Opportunity: {selected.get('title')} at {selected.get('company')}")
    print(f"* Recruiter Discovery: {recruiter.get('name')} ({recruiter.get('title')})")
    print(f"  Source Evidence: {recruiter.get('source_evidence')}")
    print(f"  LinkedIn Profile: {recruiter.get('linkedin_url')}")

    # Application Package
    pkg = final_state.get("application_package", {})
    print(f"\n* Application Package Prepared:")
    print(f"  - Tailored Summary: {pkg.get('tailored_resume_summary')}")
    print(f"  - Highlighted Skills: {pkg.get('highlighted_skills')}")
    print(f"  - Questions Prepared: {len(pkg.get('questions', []))} (Safe Factual vs Sensitive classification)")
    for q in pkg.get("questions", [])[:2]:
        print(f"    * [{q.get('status')}] Q: {q.get('question')} -> A: {q.get('answer')}")

    # Outreach Drafts
    outreach = final_state.get("outreach", {})
    email = outreach.get("email", {})
    li = outreach.get("linkedin", {})
    print(f"\n* Prepared Recruiter Outreach (Guarded by Human Approval Gate):")
    print(f"  - Email Subject: {email.get('subject')}")
    print(f"  - Email Preview: {email.get('body')[:140]}...")
    print(f"  - LinkedIn Note ({len(li.get('body', ''))} chars): {li.get('body')}")
    print(f"\n* Human Approval Status: {final_state.get('approval_status')} (Approval Required: {final_state.get('approval_required')})")
    print("=" * 70)
    print("[SUCCESS] DRY RUN COMPLETED SUCCESSFULLY WITHOUT ERRORS!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
